"""
Celery Tasks for TabGraphSyn Synthetic Data Generation

This module contains Celery tasks for running the ML pipeline in the background.
It replaces the threading approach with a production-ready task queue system.
"""
from __future__ import annotations

import json
import traceback
from typing import Any
from celery import shared_task
from django.utils import timezone

from .tabgraphsyn import PipelineParameters, run_pipeline as execute_pipeline
from .evaluation import evaluate_synthetic_run


@shared_task(bind=True, name='synthetic.run_pipeline')
def run_pipeline_task(
    self,
    job_token: str,
    params_dict: dict[str, Any],
    prepared_metadata: dict[str, Any],
) -> dict[str, Any]:
    """
    Celery task to run the TabGraphSyn ML pipeline.

    This task executes the three-stage ML pipeline (VAE → GNN → Diffusion) and
    generates synthetic data. It updates task state with progress information
    that the frontend can poll.

    Args:
        self: Celery task instance (bound task)
        job_token: Unique identifier for this job
        params_dict: Dictionary containing pipeline parameters
        prepared_metadata: Metadata about the run (owner, data source, etc.)

    Returns:
        Dictionary containing:
            - status: 'completed' or 'failed'
            - run_token: Token for accessing the generated data
            - error: Error message if failed
    """
    from pathlib import Path
    from uuid import uuid4
    import pandas as pd
    import shutil
    from django.conf import settings

    # Import here to avoid circular imports
    from .views import (
        _data_path,
        _metadata_path,
        _build_run_metadata,
        _generated_dir,
    )
    from .history import store_run_history

    # Reconstruct PipelineParameters from dictionary
    params = PipelineParameters(**params_dict)

    # Extract prepared metadata
    data_source = prepared_metadata.get('data_source', 'unknown')
    extra_metadata = prepared_metadata.get('extra_metadata', {})
    owner = prepared_metadata.get('owner')
    started_at = prepared_metadata.get('started_at') or timezone.now().isoformat()
    description = prepared_metadata.get('description', 'Pipeline run')

    # Update task state to 'STARTING'
    self.update_state(
        state='PROGRESS',
        meta={
            'stage': 'starting',
            'message': f'Starting {description}',
            'progress': 5,
            'logs': [f'Launching pipeline for {description}'],
        }
    )

    try:
        # Callback function to capture pipeline output and update task state
        logs = []

        def status_callback(line: str) -> None:
            """Capture pipeline log output"""
            logs.append(line.rstrip('\n'))

            # Parse stage from log line and update task state
            stage = _parse_stage_from_log(line)
            if stage:
                progress = _progress_for_stage(stage)
                self.update_state(
                    state='PROGRESS',
                    meta={
                        'stage': stage,
                        'message': _stage_message(stage),
                        'progress': progress,
                        'logs': logs[-50:],  # Keep last 50 log lines
                    }
                )

        # Update to preprocessing stage
        self.update_state(
            state='PROGRESS',
            meta={
                'stage': 'preprocessing',
                'message': 'Preprocessing data',
                'progress': 15,
                'logs': logs,
            }
        )

        # Run the ML pipeline
        pipeline_result = execute_pipeline(params, status_callback=status_callback)

        # Generate run token for this output
        run_token = uuid4().hex

        # Read generated data to count rows
        generated_rows = None
        if pipeline_result.output_csv is not None:
            df = pd.read_csv(pipeline_result.output_csv)
            generated_rows = int(len(df))

        # Update to evaluation stage
        self.update_state(
            state='PROGRESS',
            meta={
                'stage': 'evaluation',
                'message': 'Running evaluation',
                'progress': 90,
                'logs': logs,
            }
        )

        # Run evaluation
        evaluation_payload = evaluate_synthetic_run(
            dataset=params.dataset,
            table=params.table,
            synthetic_path=pipeline_result.output_csv,
        )
        extra_metadata['evaluation'] = evaluation_payload

        # Update to finalizing stage
        self.update_state(
            state='PROGRESS',
            meta={
                'stage': 'finalizing',
                'message': 'Saving outputs',
                'progress': 95,
                'logs': logs,
            }
        )

        # Save outputs
        finished_at = timezone.now().isoformat()
        metadata_payload = _build_run_metadata(
            params=params,
            pipeline_result=pipeline_result,
            token=run_token,
            generated_rows=generated_rows,
            data_source=data_source,
            extra_metadata=extra_metadata,
            owner=owner,
            started_at=started_at,
            finished_at=finished_at,
        )

        # Persist run to disk
        _persist_run(
            run_token,
            pipeline_result,
            metadata_payload,
            owner=owner,
            started_at=started_at,
            finished_at=finished_at,
        )

        # Return success result
        return {
            'status': 'completed',
            'run_token': run_token,
            'stage': 'completed',
            'message': 'Pipeline run completed',
            'progress': 100,
            'logs': logs,
        }

    except Exception as exc:
        # Log the full traceback
        error_traceback = traceback.format_exc()
        logs.append(f'ERROR: {exc}')
        logs.append(error_traceback)

        # Update task state to failed
        self.update_state(
            state='FAILURE',
            meta={
                'stage': 'failed',
                'message': str(exc),
                'progress': 0,
                'logs': logs,
                'error': str(exc),
                'traceback': error_traceback,
            }
        )

        # Re-raise the exception so Celery marks the task as failed
        raise


def _persist_run(
    token: str,
    pipeline_result: Any,
    metadata: dict[str, Any],
    *,
    owner: dict[str, Any] | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> None:
    """
    Persist the pipeline run results to disk and database.

    Args:
        token: Unique token for this run
        pipeline_result: Result object from pipeline execution
        metadata: Run metadata dictionary
        owner: User who owns this run
        started_at: ISO timestamp when run started
        finished_at: ISO timestamp when run finished
    """
    import shutil
    from django.conf import settings
    from pathlib import Path

    # Import here to avoid circular imports
    from .views import _data_path, _metadata_path, _generated_dir
    from .history import store_run_history

    # Copy generated CSV to media directory
    if pipeline_result.output_csv is not None:
        csv_target = _data_path(token)
        csv_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pipeline_result.output_csv, csv_target)

    # Save metadata
    metadata.setdefault('started_at', started_at)
    metadata.setdefault('finished_at', finished_at)
    with open(_metadata_path(token), 'w', encoding='utf-8') as meta_file:
        json.dump(metadata, meta_file, indent=2)

    # Store in MongoDB history
    store_run_history(
        metadata,
        owner=owner,
        started_at=metadata.get('started_at'),
        finished_at=metadata.get('finished_at'),
    )


def _parse_stage_from_log(line: str) -> str | None:
    """Parse pipeline stage from log line"""
    upper = line.strip().upper()
    if 'PREPROCESSING DATA' in upper or 'PREPROCESS' in upper:
        return 'preprocessing'
    if 'TRAINING MODELS' in upper or ('TRAINING' in upper and 'MODEL' in upper):
        return 'training'
    if 'SAMPLING DATA' in upper or ('SAMPLING' in upper and 'DATA' in upper):
        return 'sampling'
    if 'PIPELINE COMPLETED' in upper or 'COMPLETED SUCCESSFULLY' in upper:
        return 'completed'
    return None


def _progress_for_stage(stage: str) -> int:
    """Calculate progress percentage based on pipeline stage"""
    stage_progress = {
        'queued': 0,
        'starting': 5,
        'preprocessing': 15,
        'training': 50,
        'sampling': 80,
        'evaluation': 90,
        'finalizing': 95,
        'completed': 100,
        'failed': 0,
    }
    return stage_progress.get(stage, 0)


def _stage_message(stage: str) -> str:
    """Get user-friendly message for a stage"""
    messages = {
        'queued': 'Queued',
        'starting': 'Starting',
        'preprocessing': 'Preprocessing data',
        'training': 'Training models',
        'sampling': 'Sampling synthetic rows',
        'evaluation': 'Running evaluation',
        'finalizing': 'Saving outputs',
        'completed': 'Completed',
        'failed': 'Failed',
    }
    return messages.get(stage, stage.title())
