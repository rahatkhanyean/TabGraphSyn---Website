from __future__ import annotations

import json
import logging
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import pandas as pd
from celery.result import AsyncResult
from django.conf import settings
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

# Authentication decorators removed - using session-based tracking instead

from .forms import SyntheticDataForm
from .tasks import run_pipeline_task
from .staging import (
    build_metadata_from_profile,
    load_stage,
    materialize_to_pipeline,
    metadata_exists,
    save_metadata,
    stage_upload,
    update_stage_profile,
)
from .tabgraphsyn import (
    PipelineError,
    PipelineParameters,
    available_datasets,
    run_pipeline as execute_pipeline,
    tables_for_dataset,
)
from .evaluation import evaluate_synthetic_run
from .history import fetch_runs_for_user, store_run_history
from . import job_tracker

MEDIA_SUBDIR = 'generated'
DEFAULT_RUN_NAME = 'single_table'
DEFAULT_EPOCHS_VAE = 10
DEFAULT_EPOCHS_GNN = 10
DEFAULT_EPOCHS_DIFF = 1
FALLBACK_DATASETS = {
    'AIDS': 'AIDS',
    'TCGA': 'TCGA',
    'WBCD': 'WBCD',
}


logger = logging.getLogger(__name__)


def _get_or_create_user_id(request: HttpRequest) -> str:
    """
    Get or create a unique user identifier based on session.
    This allows tracking user history without authentication.
    """
    if not request.session.session_key:
        request.session.create()
    return request.session.session_key


def _get_user_profile(request: HttpRequest) -> dict[str, Any]:
    """
    Create a user profile dict from session for compatibility with existing code.
    """
    user_id = _get_or_create_user_id(request)
    return {
        'username': user_id,
        'display_name': f'User-{user_id[:8]}',
        'full_name': f'Anonymous User',
        'name': f'User-{user_id[:8]}',
    }


# Job preparation details captured before launching the pipeline.


@dataclass
class PreparedRun:
    params: PipelineParameters
    data_source: str
    extra_metadata: dict[str, Any]
    description: str
    owner: dict[str, Any] | None = None
    started_at: str | None = None


def _generated_dir() -> Path:
    target = Path(settings.MEDIA_ROOT) / MEDIA_SUBDIR
    target.mkdir(parents=True, exist_ok=True)
    return target


def _metadata_path(token: str) -> Path:
    return _generated_dir() / f'{token}.json'


def _data_path(token: str) -> Path:
    return _generated_dir() / f'{token}.csv'


def _dataset_table_map() -> dict[str, str]:
    mapping: dict[str, str] = {}
    for dataset_name in sorted(available_datasets()):
        tables = tables_for_dataset(dataset_name)
        mapping[dataset_name] = tables[0] if tables else dataset_name
    if not mapping:
        mapping.update(FALLBACK_DATASETS)
    return mapping


def _metadata_template_path(template: str) -> Path:
    return Path(settings.BASE_DIR) / 'src' / 'data' / 'original' / template / 'metadata.json'


def _command_for(dataset: str, table_map: dict[str, str], epochs_gnn: int, epochs_vae: int, epochs_diff: int) -> str:
    table = table_map.get(dataset, dataset)
    return (
        'python src/scripts/run_pipeline.py '
        f'--dataset-name {dataset} '
        f'--target-table {table} '
        f'--epochs-gnn {epochs_gnn} '
        f'--epochs-vae {epochs_vae} '
        f'--epochs-diff {epochs_diff}'
    )




def _prepare_run_spec(
    form: SyntheticDataForm,
    dataset_map: dict[str, str],
    default_dataset: str,
    epochs_vae: int,
    epochs_gnn: int,
    epochs_diff: int,
    enable_epoch_eval: bool = False,
    eval_frequency: int = 10,
    eval_samples: int = 500,
) -> PreparedRun | None:
    data_source = form.cleaned_data['data_source']
    if data_source == 'preloaded':
        dataset = form.cleaned_data['dataset']
        table = dataset_map.get(dataset, dataset)
        params = PipelineParameters(
            dataset=dataset,
            table=table,
            run_name=DEFAULT_RUN_NAME,
            epochs_vae=epochs_vae,
            epochs_gnn=epochs_gnn,
            epochs_diff=epochs_diff,
            enable_epoch_eval=enable_epoch_eval,
            eval_frequency=eval_frequency,
            eval_samples=eval_samples,
        )
        metadata_template = form.cleaned_data.get('metadata_template')
        extra_metadata = {
            'metadata_mode': 'template',
            'metadata_template': metadata_template or dataset,
        }
        description = f"{dataset} ({table})"
        return PreparedRun(params=params, data_source='preloaded', extra_metadata=extra_metadata, description=description)

    if data_source == 'uploaded':
        token = form.cleaned_data.get('staging_token')
        if not token:
            form.add_error(None, 'Upload session missing. Upload the dataset again.')
            return None
        try:
            stage = load_stage(token)
        except FileNotFoundError:
            form.add_error(None, 'Upload session expired. Upload the dataset again.')
            return None

        dataset_name_input = form.cleaned_data.get('uploaded_dataset_name')
        table_name_input = form.cleaned_data.get('uploaded_table_name')
        metadata_mode = form.cleaned_data.get('metadata_mode')
        metadata_template = form.cleaned_data.get('metadata_template')

        metadata_path: Path | None = None
        metadata_source: dict[str, Any] = {}
        table_name: str | None = None

        if metadata_mode == 'template':
            template_slug = metadata_template or default_dataset
            template_path = _metadata_template_path(template_slug)
            if not template_path.exists():
                form.add_error('metadata_template', 'Selected metadata template is not available.')
                return None
            with template_path.open('r', encoding='utf-8') as meta_file:
                template_payload = json.load(meta_file)
            tables_section = template_payload.get('tables') or {}
            table_name = next(iter(tables_section.keys()), stage.profile['table_name'])
            stage = update_stage_profile(
                token,
                dataset_name=dataset_name_input,
                table_name=table_name,
                preserve_table_name=True,
            )
            metadata_path = template_path
            metadata_source = {
                'metadata_mode': 'template',
                'metadata_template': template_slug,
            }
        else:
            if dataset_name_input or table_name_input:
                stage = update_stage_profile(
                    token,
                    dataset_name=dataset_name_input,
                    table_name=table_name_input,
                )
            if not metadata_exists(token):
                metadata = build_metadata_from_profile(stage)
                metadata_path = save_metadata(token, metadata)
            else:
                metadata_path = stage.metadata_path
            table_name = stage.profile['table_name']
            metadata_source = {
                'metadata_mode': 'custom',
                'metadata_template': None,
            }

        if form.errors:
            return None

        if metadata_path is None or table_name is None:
            form.add_error(None, 'Metadata could not be resolved for the uploaded dataset.')
            return None

        dataset_name = stage.profile['dataset_name']
        try:
            materialize_to_pipeline(
                stage,
                dataset_name=dataset_name,
                table_name=table_name,
                metadata_path=metadata_path,
            )
        except FileExistsError as exc:
            form.add_error('uploaded_dataset_name', str(exc))
            return None

        params = PipelineParameters(
            dataset=dataset_name,
            table=table_name,
            run_name=DEFAULT_RUN_NAME,
            epochs_vae=epochs_vae,
            epochs_gnn=epochs_gnn,
            epochs_diff=epochs_diff,
            enable_epoch_eval=enable_epoch_eval,
            eval_frequency=eval_frequency,
            eval_samples=eval_samples,
        )

        run_metadata = {
            'data_source': 'uploaded',
            'staging_token': token,
            'input_rows': stage.profile['row_count'],
            'input_columns': [column['name'] for column in stage.profile['columns']],
            'input_filename': stage.profile['source_filename'],
            'display_dataset_name': stage.profile.get('display_dataset_name'),
            'display_table_name': stage.profile.get('display_table_name'),
        }
        run_metadata.update(metadata_source)

        description = stage.profile.get('display_dataset_name') or dataset_name
        return PreparedRun(params=params, data_source='uploaded', extra_metadata=run_metadata, description=description)

    form.add_error('data_source', 'Unsupported data source.')
    return None




def _start_pipeline_job(prepared: PreparedRun) -> str:
    """
    Start a pipeline job using Celery (replaces threading approach).

    This function prepares the job parameters and submits the task to Celery.
    The Celery worker will execute the task asynchronously.

    Args:
        prepared: PreparedRun object with pipeline parameters and metadata

    Returns:
        str: Celery task ID (used to track job status)
    """
    # Convert PipelineParameters to dictionary for JSON serialization
    params_dict = {
        'dataset': prepared.params.dataset,
        'table': prepared.params.table,
        'run_name': prepared.params.run_name,
        'num_samples': prepared.params.num_samples,
        'seed': prepared.params.seed,
        'factor_missing': prepared.params.factor_missing,
        'positional_enc': prepared.params.positional_enc,
        'retrain_vae': prepared.params.retrain_vae,
        'skip_preprocessing': prepared.params.skip_preprocessing,
        'model_type': prepared.params.model_type,
        'normalization': prepared.params.normalization,
        'gnn_hidden': prepared.params.gnn_hidden,
        'denoising_steps': prepared.params.denoising_steps,
        'epochs_vae': prepared.params.epochs_vae,
        'epochs_gnn': prepared.params.epochs_gnn,
        'epochs_diff': prepared.params.epochs_diff,
        'enable_epoch_eval': prepared.params.enable_epoch_eval,
        'eval_frequency': prepared.params.eval_frequency,
        'eval_samples': prepared.params.eval_samples,
    }

    # Prepare metadata for the task
    prepared_metadata = {
        'data_source': prepared.data_source,
        'extra_metadata': prepared.extra_metadata,
        'description': prepared.description,
        'owner': prepared.owner,
        'started_at': prepared.started_at or timezone.now().isoformat(),
    }

    # Submit task to Celery
    # The task ID will be used to track job status
    task = run_pipeline_task.delay(
        job_token=None,  # Not used anymore, task.id is the job token
        params_dict=params_dict,
        prepared_metadata=prepared_metadata,
    )

    # Return the Celery task ID as the job token
    return task.id


def upload_view(request: HttpRequest) -> HttpResponse:
    dataset_map = _dataset_table_map()
    dataset_choices = [(name, name) for name in dataset_map.keys()]
    metadata_templates = dataset_choices
    default_dataset = dataset_choices[0][0] if dataset_choices else 'AIDS'

    form = SyntheticDataForm(
        request.POST or None,
        dataset_choices=dataset_choices,
        metadata_templates=metadata_templates,
    )

    try:
        selected_dataset = form['dataset'].value() or default_dataset
    except KeyError:
        selected_dataset = default_dataset

    epochs_vae = _safe_int(form['epochs_vae'].value(), DEFAULT_EPOCHS_VAE)
    epochs_gnn = _safe_int(form['epochs_gnn'].value(), DEFAULT_EPOCHS_GNN)
    epochs_diff = _safe_int(form['epochs_diff'].value(), DEFAULT_EPOCHS_DIFF)

    if request.method == 'POST' and form.is_valid():
        epochs_vae = form.cleaned_data['epochs_vae']
        epochs_gnn = form.cleaned_data['epochs_gnn']
        epochs_diff = form.cleaned_data['epochs_diff']
        enable_epoch_eval = form.cleaned_data.get('enable_epoch_eval', False)
        eval_frequency = form.cleaned_data.get('eval_frequency', 10)
        eval_samples = form.cleaned_data.get('eval_samples', 500)

        prepared = _prepare_run_spec(
            form,
            dataset_map,
            default_dataset,
            epochs_vae,
            epochs_gnn,
            epochs_diff,
            enable_epoch_eval,
            eval_frequency,
            eval_samples,
        )

        if prepared:
            owner_profile = _get_user_profile(request)
            prepared.owner = owner_profile
            prepared.started_at = timezone.now().isoformat()
            try:
                pipeline_result, token, generated_rows = _run_pipeline_and_capture(
                    prepared.params
                )
            except PipelineError as exc:
                form.add_error(None, str(exc))
            else:
                finished_at = timezone.now().isoformat()
                evaluation_payload = evaluate_synthetic_run(
                    dataset=prepared.params.dataset,
                    table=prepared.params.table,
                    synthetic_path=pipeline_result.output_csv,
                )
                extra_metadata = dict(prepared.extra_metadata)
                extra_metadata['evaluation'] = evaluation_payload
                metadata_payload = _build_run_metadata(
                    params=prepared.params,
                    pipeline_result=pipeline_result,
                    token=token,
                    generated_rows=generated_rows,
                    data_source=prepared.data_source,
                    extra_metadata=extra_metadata,
                    owner=owner_profile,
                    started_at=prepared.started_at,
                    finished_at=finished_at,
                )
                _persist_run(
                    token,
                    pipeline_result,
                    metadata_payload,
                    owner=owner_profile,
                    started_at=prepared.started_at,
                    finished_at=finished_at,
                )
                return redirect('synthetic:result', token=token)

    context = {
        'form': form,
        'command_preview': _command_for(selected_dataset, dataset_map, epochs_gnn, epochs_vae, epochs_diff),
        'table_map': dataset_map,
        'defaults': {
            'dataset': default_dataset,
            'epochs_vae': DEFAULT_EPOCHS_VAE,
            'epochs_gnn': DEFAULT_EPOCHS_GNN,
            'epochs_diff': DEFAULT_EPOCHS_DIFF,
        },
        'api_urls': {
            'stage': reverse('synthetic:api-stage-upload'),
            'finalize': reverse('synthetic:api-finalize-metadata'),
            'start': reverse('synthetic:api-start-run'),
            'status': reverse('synthetic:api-run-status', kwargs={'token': 'JOB_TOKEN'}),
            'result': reverse('synthetic:result', kwargs={'token': 'RUN_TOKEN'}),
        },
    }
    return render(request, 'synthetic/upload.html', context)


def history_view(request: HttpRequest) -> HttpResponse:
    user = _get_user_profile(request)
    username = user.get('username')
    runs: list[dict[str, Any]] = []
    error: str | None = None
    active_job_token: str | None = None

    # Check if there's an active job for this user
    # Get the job token (Celery task ID) from session if available
    session_job_token = request.session.get('active_job_token')

    if session_job_token:
        # Check if the Celery task is still running
        task_result = AsyncResult(session_job_token)

        if task_result.state in ('SUCCESS', 'FAILURE', 'REVOKED'):
            # Task is done, clear it from session
            del request.session['active_job_token']
            request.session.modified = True
            active_job_token = None
        elif task_result.state in ('PENDING', 'STARTED', 'PROGRESS'):
            # Task is still running
            active_job_token = session_job_token
        else:
            # Task in unknown state
            del request.session['active_job_token']
            request.session.modified = True
            active_job_token = None

    if username:
        try:
            runs = fetch_runs_for_user(username, limit=50)
        except RuntimeError as exc:
            error = str(exc)

    context = {
        'runs': runs,
        'error': error,
        'active_job_token': active_job_token,
    }
    return render(request, 'synthetic/history.html', context)


@require_POST
def api_start_run(request: HttpRequest) -> JsonResponse:
    dataset_map = _dataset_table_map()
    dataset_choices = [(name, name) for name in dataset_map.keys()]
    metadata_templates = dataset_choices
    default_dataset = dataset_choices[0][0] if dataset_choices else 'AIDS'

    form = SyntheticDataForm(
        request.POST,
        dataset_choices=dataset_choices,
        metadata_templates=metadata_templates,
    )

    if not form.is_valid():
        return JsonResponse({'errors': _form_errors(form)}, status=400)

    epochs_vae = form.cleaned_data['epochs_vae']
    epochs_gnn = form.cleaned_data['epochs_gnn']
    epochs_diff = form.cleaned_data['epochs_diff']
    enable_epoch_eval = form.cleaned_data.get('enable_epoch_eval', False)
    eval_frequency = form.cleaned_data.get('eval_frequency', 10)
    eval_samples = form.cleaned_data.get('eval_samples', 500)

    prepared = _prepare_run_spec(
        form,
        dataset_map,
        default_dataset,
        epochs_vae,
        epochs_gnn,
        epochs_diff,
        enable_epoch_eval,
        eval_frequency,
        eval_samples,
    )

    if not prepared:
        return JsonResponse({'errors': _form_errors(form)}, status=400)

    owner_profile = _get_user_profile(request)
    prepared.owner = owner_profile
    prepared.started_at = timezone.now().isoformat()

    # Start the Celery task
    job_token = _start_pipeline_job(prepared)

    # Store the active job token in session so the history page can track it
    request.session['active_job_token'] = job_token

    # Return initial task status
    payload: dict[str, Any] = {
        'jobToken': job_token,
        'stage': 'starting',
        'message': f'Starting {prepared.description}',
        'logs': [],
        'error': None,
        'resultToken': None,
    }
    return JsonResponse(payload, status=202)


def api_job_status(request: HttpRequest, token: str) -> JsonResponse:
    """
    Get the status of a running or completed Celery task.

    This replaces the in-memory job_tracker with Celery's AsyncResult.

    Args:
        request: HTTP request
        token: Celery task ID

    Returns:
        JsonResponse with task status and metadata
    """
    # Get Celery task result
    task_result = AsyncResult(token)

    # Check if task exists
    if task_result.state == 'PENDING' and not task_result.info:
        # Task doesn't exist or hasn't been picked up yet
        return JsonResponse({'error': 'Job not found.'}, status=404)

    # Build response based on task state
    if task_result.state == 'PROGRESS':
        # Task is running - get progress metadata
        meta = task_result.info or {}
        response_data = {
            'token': token,
            'stage': meta.get('stage', 'running'),
            'message': meta.get('message', 'Processing...'),
            'logs': meta.get('logs', []),
            'error': None,
            'resultToken': None,
            'progressPercentage': meta.get('progress', 0),
            'state': 'PROGRESS',
        }
    elif task_result.state == 'SUCCESS':
        # Task completed successfully
        result = task_result.result or {}
        response_data = {
            'token': token,
            'stage': 'completed',
            'message': result.get('message', 'Completed'),
            'logs': result.get('logs', []),
            'error': None,
            'resultToken': result.get('run_token'),
            'progressPercentage': 100,
            'state': 'SUCCESS',
        }
    elif task_result.state == 'FAILURE':
        # Task failed
        meta = task_result.info or {}
        if isinstance(meta, dict):
            error_msg = meta.get('error', str(task_result.result))
            logs = meta.get('logs', [])
        else:
            error_msg = str(task_result.result)
            logs = []

        response_data = {
            'token': token,
            'stage': 'failed',
            'message': 'Failed',
            'logs': logs,
            'error': error_msg,
            'resultToken': None,
            'progressPercentage': 0,
            'state': 'FAILURE',
        }
    elif task_result.state == 'STARTED':
        # Task has started but no progress yet
        response_data = {
            'token': token,
            'stage': 'starting',
            'message': 'Starting...',
            'logs': [],
            'error': None,
            'resultToken': None,
            'progressPercentage': 5,
            'state': 'STARTED',
        }
    else:
        # Other states (RETRY, REVOKED, etc.)
        response_data = {
            'token': token,
            'stage': task_result.state.lower(),
            'message': task_result.state,
            'logs': [],
            'error': None,
            'resultToken': None,
            'progressPercentage': 0,
            'state': task_result.state,
        }

    response = JsonResponse(response_data)
    response['Cache-Control'] = 'no-store'
    return response


def _form_errors(form: SyntheticDataForm) -> dict[str, list[str]]:
    errors: dict[str, list[str]] = {}
    for field, entries in form.errors.get_json_data().items():
        errors[field] = [entry['message'] for entry in entries]
    return errors


def _load_epoch_metrics(dataset: str, table: str, run_name: str) -> dict[str, Any] | None:
    """
    Load epoch-wise evaluation metrics from training logs.

    Returns dict with metrics_history or None if not found.
    """
    import glob

    # Construct the expected log directory
    logs_dir = Path(settings.BASE_DIR) / 'logs' / 'training_metrics'
    if not logs_dir.exists():
        return None

    # Build search pattern for this dataset/table/run
    table_factor = f"{table}_factor" if not table.endswith('_factor') else table
    search_pattern = f"{dataset}_{table_factor}_{run_name}_*.json"

    # Find matching log files
    matching_files = list(logs_dir.glob(search_pattern))

    if not matching_files:
        # Try without _factor suffix
        search_pattern_alt = f"{dataset}_{table}_{run_name}_*.json"
        matching_files = list(logs_dir.glob(search_pattern_alt))

    if not matching_files:
        return None

    # Use the most recent file
    most_recent = max(matching_files, key=lambda p: p.stat().st_mtime)

    try:
        with open(most_recent, 'r', encoding='utf-8') as f:
            data = json.load(f)

        metrics_history = data.get('metrics_history', [])
        if not metrics_history:
            return None

        return {
            'dataname': data.get('dataname'),
            'run': data.get('run'),
            'eval_frequency': data.get('eval_frequency'),
            'num_eval_samples': data.get('num_eval_samples'),
            'denoising_steps': data.get('denoising_steps'),
            'metrics_history': metrics_history,
            'log_file': str(most_recent),
        }
    except Exception as e:
        logger.warning(f"Failed to load epoch metrics from {most_recent}: {e}")
        return None


def result_view(request: HttpRequest, token: str) -> HttpResponse:
    csv_path = _data_path(token)
    meta_path = _metadata_path(token)
    if not meta_path.exists():
        raise Http404('Synthetic run metadata not found.')

    with open(meta_path, 'r', encoding='utf-8') as meta_file:
        metadata = json.load(meta_file)

    preview_headers: list[str] = []
    preview_rows: list[list[str]] = []
    generated_rows: int | None = metadata.get('generated_rows')
    has_csv = csv_path.exists()
    if has_csv:
        df = pd.read_csv(csv_path)
        generated_rows = int(len(df))
        preview = df.head(20)
        preview_headers = preview.columns.tolist()
        preview_rows = preview.fillna('').astype(str).values.tolist()

    metadata['generated_rows'] = generated_rows

    evaluation: dict[str, Any] = {}
    evaluation_headers: list[str] = []
    evaluation_rows: list[list[str]] = []
    evaluation_plot_data_uri: str | None = None
    evaluation_plot_path: str | None = None
    evaluation_download_url: str | None = None
    umap_coordinates: str | None = None

    raw_evaluation = metadata.get('evaluation')
    if isinstance(raw_evaluation, dict):
        evaluation = raw_evaluation
        metrics = evaluation.get('metrics') or []
        if metrics:
            evaluation_headers = list(metrics[0].keys())
            evaluation_rows = [[row.get(header, '') for header in evaluation_headers] for row in metrics]
        plot_payload = evaluation.get('plot') or {}
        evaluation_plot_data_uri = plot_payload.get('data_uri')
        evaluation_plot_path = plot_payload.get('path')
        if evaluation_plot_path:
            evaluation_download_url = reverse('synthetic:download-plot', kwargs={'token': token})

        # Get UMAP coordinates for interactive visualization
        umap_coords = evaluation.get('umap_coordinates')
        if umap_coords:
            umap_coordinates = json.dumps(umap_coords)

    # Load epoch evaluation data if available
    epoch_metrics_data: dict[str, Any] | None = None
    epoch_metrics_json: str | None = None
    dataset = metadata.get('dataset')
    table = metadata.get('table')
    run_name = metadata.get('run_name', 'single_table')
    if dataset and table:
        epoch_metrics_data = _load_epoch_metrics(dataset, table, run_name)
        if epoch_metrics_data:
            # Serialize metrics_history to JSON for JavaScript
            epoch_metrics_json = json.dumps(epoch_metrics_data.get('metrics_history', []))

    context = {
        'metadata': metadata,
        'run_token': token,
        'preview_headers': preview_headers,
        'preview_rows': preview_rows,
        'has_output': has_csv,
        'download_url': request.build_absolute_uri(reverse('synthetic:download', kwargs={'token': token})) if has_csv else None,
        'evaluation': evaluation,
        'evaluation_headers': evaluation_headers,
        'evaluation_rows': evaluation_rows,
        'evaluation_plot_data_uri': evaluation_plot_data_uri,
        'evaluation_plot_path': evaluation_plot_path,
        'evaluation_download_url': evaluation_download_url,
        'umap_coordinates': umap_coordinates,
        'epoch_metrics': epoch_metrics_data,
        'epoch_metrics_json': epoch_metrics_json,
    }
    return render(request, 'synthetic/result.html', context)


def download_view(request: HttpRequest, token: str) -> FileResponse:
    csv_path = _data_path(token)
    meta_path = _metadata_path(token)
    if not csv_path.exists() or not meta_path.exists():
        raise Http404('Synthetic dataset not found.')

    with open(meta_path, 'r', encoding='utf-8') as meta_file:
        metadata = json.load(meta_file)

    filename = f"{metadata.get('dataset')}_{metadata.get('table')}_{metadata.get('run_name', token)}.csv"
    return FileResponse(csv_path.open('rb'), as_attachment=True, filename=filename)


def download_plot(request: HttpRequest, token: str) -> FileResponse:
    meta_path = _metadata_path(token)
    if not meta_path.exists():
        raise Http404('Synthetic run metadata not found.')

    with open(meta_path, 'r', encoding='utf-8') as meta_file:
        metadata = json.load(meta_file)

    plot_payload = metadata.get('evaluation', {}).get('plot', {})
    plot_path_str = plot_payload.get('path')
    if not plot_path_str:
        raise Http404('UMAP plot not available for this run.')

    plot_path = Path(plot_path_str)
    if not plot_path.is_absolute():
        plot_path = Path(settings.BASE_DIR) / plot_path
    if not plot_path.exists():
        raise Http404('UMAP plot file not found.')

    filename = plot_path.name
    return FileResponse(plot_path.open('rb'), as_attachment=True, filename=filename)


def api_dataset_view(request: HttpRequest, token: str) -> JsonResponse:
    """API endpoint to serve the full dataset for a given run token."""
    csv_path = _data_path(token)
    meta_path = _metadata_path(token)

    if not csv_path.exists() or not meta_path.exists():
        return JsonResponse({'error': 'Dataset not found.'}, status=404)

    try:
        # Read the CSV file
        df = pd.read_csv(csv_path)

        # Convert to list of lists for JSON serialization
        headers = df.columns.tolist()
        rows = df.fillna('').astype(str).values.tolist()

        response_data = {
            'headers': headers,
            'rows': rows,
            'total_rows': len(rows)
        }

        return JsonResponse(response_data)

    except Exception as e:
        return JsonResponse({'error': f'Failed to load dataset: {str(e)}'}, status=500)


@require_POST
def api_stage_upload(request: HttpRequest) -> JsonResponse:
    upload = request.FILES.get('dataset')
    if upload is None:
        return JsonResponse({'error': 'No dataset provided.'}, status=400)
    dataset_name = request.POST.get('datasetName')
    table_name = request.POST.get('tableName')
    try:
        stage = stage_upload(upload, dataset_name=dataset_name, table_name=table_name)
    except ValueError as exc:
        return JsonResponse({'error': str(exc)}, status=400)
    except Exception:
        return JsonResponse({'error': 'Failed to process uploaded file.'}, status=500)
    payload = {
        'token': stage.token,
        'datasetName': stage.profile['dataset_name'],
        'tableName': stage.profile['table_name'],
        'displayDatasetName': stage.profile.get('display_dataset_name'),
        'displayTableName': stage.profile.get('display_table_name'),
        'rowCount': stage.profile['row_count'],
        'columns': stage.profile['columns'],
        'sourceFilename': stage.profile['source_filename'],
    }
    return JsonResponse(payload)


@require_POST
def api_finalize_metadata(request: HttpRequest) -> JsonResponse:
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    token = payload.get('token')
    if not token:
        return JsonResponse({'error': 'Missing upload token.'}, status=400)

    dataset_name = payload.get('datasetName')
    table_name = payload.get('tableName')
    primary_key = payload.get('primaryKey')
    column_entries = payload.get('columns') or []

    try:
        stage = update_stage_profile(token, dataset_name=dataset_name, table_name=table_name)
    except FileNotFoundError:
        return JsonResponse({'error': 'Upload session not found.'}, status=404)

    column_overrides: dict[str, dict[str, str]] = {}
    for entry in column_entries:
        name = entry.get('name')
        if not name:
            continue
        override: dict[str, str] = {}
        kind = entry.get('kind')
        if kind:
            override['kind'] = str(kind)
        if entry.get('representation') is not None:
            override['representation'] = str(entry['representation'])
        column_overrides[str(name)] = override

    metadata = build_metadata_from_profile(stage, primary_key=primary_key or None, column_overrides=column_overrides)
    metadata_path = save_metadata(token, metadata)

    response = {
        'metadataPath': str(metadata_path),
        'datasetName': stage.profile['dataset_name'],
        'tableName': stage.profile['table_name'],
        'displayDatasetName': stage.profile.get('display_dataset_name'),
        'displayTableName': stage.profile.get('display_table_name'),
    }
    return JsonResponse(response)


def _safe_int(value: Any, fallback: int) -> int:
    try:
        parsed = int(value)
        return parsed if parsed > 0 else fallback
    except (TypeError, ValueError):
        return fallback


def _run_pipeline_and_capture(
    params: PipelineParameters, *, status_callback=None
) -> tuple[Any, str, int | None]:
    pipeline_result = execute_pipeline(params, status_callback=status_callback)
    token = uuid4().hex
    generated_rows = None
    if pipeline_result.output_csv is not None:
        df = pd.read_csv(pipeline_result.output_csv)
        generated_rows = int(len(df))
    return pipeline_result, token, generated_rows



def _build_run_metadata(
    *,
    params: PipelineParameters,
    pipeline_result: Any,
    token: str,
    generated_rows: int | None,
    data_source: str,
    extra_metadata: dict[str, Any] | None = None,
    owner: dict[str, Any] | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> dict[str, Any]:
    requested_at = started_at or timezone.now().isoformat()
    metadata = {
        'token': token,
        'dataset': params.dataset,
        'table': params.table,
        'run_name': params.run_name,
        'requested_at': requested_at,
        'started_at': started_at or requested_at,
        'finished_at': finished_at,
        'num_samples': params.num_samples,
        'random_seed': params.seed,
        'factor_missing': params.factor_missing,
        'positional_enc': params.positional_enc,
        'retrain_vae': params.retrain_vae,
        'skip_preprocessing': params.skip_preprocessing,
        'model_type': params.model_type,
        'normalization': params.normalization,
        'gnn_hidden': params.gnn_hidden,
        'denoising_steps': params.denoising_steps,
        'epochs_vae': params.epochs_vae,
        'epochs_gnn': params.epochs_gnn,
        'epochs_diff': params.epochs_diff,
        'generated_rows': generated_rows,
        'data_source': data_source,
        'log_file': str(pipeline_result.log_path) if pipeline_result.log_path else None,
        'output_csv': str(pipeline_result.output_csv) if pipeline_result.output_csv else None,
        'logs': [
            {
                'description': command.description,
                'command': command.command,
                'output': command.output,
            }
            for command in pipeline_result.commands
        ],
    }
    if owner:
        metadata['owner'] = {
            'username': owner.get('username'),
            'email': owner.get('email'),
            'full_name': owner.get('full_name') or owner.get('name') or owner.get('username'),
            'roles': owner.get('roles', []),
        }
        metadata['owner_username'] = owner.get('username')
    if extra_metadata:
        metadata.update(extra_metadata)
    return metadata
    if extra_metadata:
        metadata.update(extra_metadata)
    return metadata

def _persist_run(
    token: str,
    pipeline_result: Any,
    metadata: dict[str, Any],
    *,
    owner: dict[str, Any] | None = None,
    started_at: str | None = None,
    finished_at: str | None = None,
) -> None:
    if pipeline_result.output_csv is not None:
        csv_target = _data_path(token)
        csv_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(pipeline_result.output_csv, csv_target)
    metadata.setdefault('started_at', started_at)
    metadata.setdefault('finished_at', finished_at)
    with open(_metadata_path(token), 'w', encoding='utf-8') as meta_file:
        json.dump(metadata, meta_file, indent=2)
    store_run_history(metadata, owner=owner, started_at=metadata.get('started_at'), finished_at=metadata.get('finished_at'))
