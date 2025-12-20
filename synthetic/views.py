from __future__ import annotations

import json
import logging
import shutil
import threading
import traceback
from datetime import datetime
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional
from uuid import uuid4

import pandas as pd
from django.conf import settings
from django.http import FileResponse, Http404, HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

# Authentication decorators removed - using session-based tracking instead

from .forms import SyntheticDataForm
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
from accounts.decorators import (
    workspace_api_login_required_if_enabled,
    workspace_login_required_if_enabled,
)
from tabgraphsyn_site.ratelimit import rate_limited

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


def _get_owner_key(request: HttpRequest) -> str:
    auth_user = request.session.get('auth_user') or {}
    username = auth_user.get('username')
    if username:
        return str(username)
    return _get_or_create_user_id(request)


def _get_user_profile(request: HttpRequest) -> dict[str, Any]:
    """
    Create a user profile dict from session for compatibility with existing code.
    Checks for authenticated user first, then falls back to session-based user.
    """
    # Check if user is authenticated via the accounts app
    auth_user = request.session.get('auth_user') or {}
    if auth_user.get('username'):
        display_name = auth_user.get('full_name') or auth_user.get('name') or auth_user.get('username')
        return {
            'username': auth_user.get('username'),
            'display_name': display_name,
            'full_name': auth_user.get('full_name') or display_name,
            'name': auth_user.get('name') or display_name,
            'email': auth_user.get('email'),
            'roles': auth_user.get('roles', []),
        }

    # Fall back to session-based anonymous user
    user_id = _get_or_create_user_id(request)
    return {
        'username': user_id,
        'display_name': f'User-{user_id[:8]}',
        'full_name': f'Anonymous User',
        'name': f'User-{user_id[:8]}',
    }


def _owner_matches(request: HttpRequest, metadata: dict[str, Any]) -> bool:
    owner_username = metadata.get('owner_username')
    if not owner_username:
        owner = metadata.get('owner') or {}
        owner_username = owner.get('username')
    if not owner_username:
        return False
    return str(owner_username) == _get_owner_key(request)


def _enforce_owner(request: HttpRequest, metadata: dict[str, Any]) -> None:
    if settings.WORKSPACE_ENFORCE_OWNER and not _owner_matches(request, metadata):
        raise Http404('Synthetic run not found.')


def _run_capacity_block(owner_username: str | None) -> tuple[int, str] | None:
    max_concurrent = getattr(settings, 'PIPELINE_MAX_CONCURRENT', 1)
    if max_concurrent and job_tracker.count_active_jobs() >= max_concurrent:
        return 429, 'Server is at capacity. Please try again later.'
    if owner_username and job_tracker.has_active_job(owner_username):
        return 409, 'You already have a run in progress. Please wait for it to finish.'
    return None


def _check_result_access(request: HttpRequest, token: str) -> bool:
    """
    Check if the current user has access to view/download a result.
    Returns True when ownership checks are disabled or ownership matches.
    """
    meta_path = _metadata_path(token)
    if not meta_path.exists():
        return False

    try:
        with open(meta_path, 'r', encoding='utf-8') as meta_file:
            metadata = json.load(meta_file)
        if not settings.WORKSPACE_ENFORCE_OWNER:
            return True
        return _owner_matches(request, metadata)
    except Exception as exc:
        logger.error(f"Error checking result access for token {token}: {exc}")
        return False


def home_view(request: HttpRequest) -> HttpResponse:
    """
    Homepage view with YouTube video embed and CTA to start generating.
    """
    youtube_video_url = getattr(settings, 'YOUTUBE_VIDEO_URL', '')

    context = {
        'youtube_video_url': youtube_video_url,
    }
    return render(request, 'home.html', context)


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
    job_token = uuid4().hex
    logger.info(f"Creating pipeline job {job_token} for {prepared.description}")

    owner_username = (prepared.owner or {}).get('username')
    job_tracker.create_job(job_token, owner_username=owner_username)
    job_tracker.set_stage(job_token, 'starting', f"Starting {prepared.description}")

    thread = threading.Thread(
        target=_run_pipeline_job,
        args=(job_token, prepared),
        daemon=True,
    )
    thread.start()
    logger.info(f"Background thread started for job {job_token}")

    return job_token


def _run_pipeline_job(job_token: str, prepared: PreparedRun) -> None:
    def _callback(line: str) -> None:
        job_tracker.append_log(job_token, line)

    try:
        logger.info(f"[Job {job_token}] Starting pipeline execution")
        if prepared.started_at is None:
            prepared.started_at = timezone.now().isoformat()

        job_tracker.append_log(job_token, f"Launching pipeline for {prepared.description}")
        logger.info(f"[Job {job_token}] Pipeline parameters: dataset={prepared.params.dataset}, table={prepared.params.table}, epochs_vae={prepared.params.epochs_vae}, epochs_gnn={prepared.params.epochs_gnn}, epochs_diff={prepared.params.epochs_diff}")

        # Execute pipeline
        pipeline_result, run_token, generated_rows = _run_pipeline_and_capture(
            prepared.params, status_callback=_callback
        )
        logger.info(f"[Job {job_token}] Pipeline execution completed. Generated {generated_rows} rows. Run token: {run_token}")

        # Run evaluation
        extra_metadata = dict(prepared.extra_metadata)
        job_tracker.set_stage(job_token, 'evaluation')
        job_tracker.append_log(job_token, 'Running evaluation...')
        logger.info(f"[Job {job_token}] Starting evaluation")

        evaluation_payload = evaluate_synthetic_run(
            dataset=prepared.params.dataset,
            table=prepared.params.table,
            synthetic_path=pipeline_result.output_csv,
        )
        extra_metadata['evaluation'] = evaluation_payload
        logger.info(f"[Job {job_token}] Evaluation completed: {evaluation_payload.get('status', 'unknown')}")

        # Save outputs
        job_tracker.set_stage(job_token, 'finalizing', 'Saving outputs')
        job_tracker.append_log(job_token, 'Saving outputs...')
        finished_at = timezone.now().isoformat()

        metadata_payload = _build_run_metadata(
            params=prepared.params,
            pipeline_result=pipeline_result,
            token=run_token,
            generated_rows=generated_rows,
            data_source=prepared.data_source,
            extra_metadata=extra_metadata,
            owner=prepared.owner,
            started_at=prepared.started_at,
            finished_at=finished_at,
        )

        _persist_run(
            run_token,
            pipeline_result,
            metadata_payload,
            owner=prepared.owner,
            started_at=prepared.started_at,
            finished_at=finished_at,
        )

        logger.info(f"[Job {job_token}] Pipeline run completed successfully. Result token: {run_token}")
        job_tracker.append_log(job_token, 'Pipeline run completed successfully!')
        job_tracker.set_result(job_token, run_token)

    except PipelineError as exc:
        error_msg = f"Pipeline execution failed: {str(exc)}"
        logger.error(f"[Job {job_token}] {error_msg}")
        logger.error(f"[Job {job_token}] Stack trace:\n{traceback.format_exc()}")
        job_tracker.append_log(job_token, f'PIPELINE ERROR: {exc}')
        job_tracker.set_error(job_token, error_msg)

    except Exception as exc:
        error_msg = f"Unexpected error: {str(exc)}"
        logger.error(f"[Job {job_token}] {error_msg}")
        logger.error(f"[Job {job_token}] Stack trace:\n{traceback.format_exc()}")
        job_tracker.append_log(job_token, f'ERROR: {exc}')
        job_tracker.append_log(job_token, 'Please check Django logs for detailed error information.')
        job_tracker.set_error(job_token, error_msg)


@workspace_login_required_if_enabled
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
            block = _run_capacity_block(owner_profile.get('username'))
            if block:
                form.add_error(None, block[1])
            else:
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


@workspace_login_required_if_enabled
def history_view(request: HttpRequest) -> HttpResponse:
    user = _get_user_profile(request)
    username = user.get('username')
    runs: list[dict[str, Any]] = []
    error: str | None = None
    active_job_token: str | None = None

    # Check if there's an active job for this user
    # Get the job token from session if available
    session_job_token = request.session.get('active_job_token')

    if session_job_token:
        # Check if the job is still running
        job_state = job_tracker.get_job(session_job_token)
        if job_state and job_state.stage in ('completed', 'failed'):
            # Job is done, clear it from session
            del request.session['active_job_token']
            request.session.modified = True
            active_job_token = None
        elif job_state:
            # Job is still running
            active_job_token = session_job_token
        else:
            # Job not found (might have been cleaned up)
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


@workspace_api_login_required_if_enabled
@require_POST
def api_start_run(request: HttpRequest) -> JsonResponse:
    logger.info("API: Start run request received")
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
        errors = _form_errors(form)
        logger.warning(f"API: Form validation failed: {errors}")
        return JsonResponse({'errors': errors}, status=400)

    owner_key = _get_owner_key(request)
    if rate_limited(request, 'start_run', identifier=owner_key):
        return JsonResponse({'error': 'Too many run requests. Please try again later.'}, status=429)

    epochs_vae = form.cleaned_data['epochs_vae']
    epochs_gnn = form.cleaned_data['epochs_gnn']
    epochs_diff = form.cleaned_data['epochs_diff']
    enable_epoch_eval = form.cleaned_data.get('enable_epoch_eval', False)
    eval_frequency = form.cleaned_data.get('eval_frequency', 10)
    eval_samples = form.cleaned_data.get('eval_samples', 500)

    logger.info(f"API: Preparing pipeline run with epochs (VAE={epochs_vae}, GNN={epochs_gnn}, Diff={epochs_diff})")

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
        errors = _form_errors(form)
        logger.error(f"API: Failed to prepare run spec: {errors}")
        return JsonResponse({'errors': errors}, status=400)

    logger.info(f"API: Run prepared successfully for dataset={prepared.params.dataset}, table={prepared.params.table}")

    owner_profile = _get_user_profile(request)
    block = _run_capacity_block(owner_profile.get('username'))
    if block:
        return JsonResponse({'error': block[1]}, status=block[0])
    prepared.owner = owner_profile
    prepared.started_at = timezone.now().isoformat()

    try:
        job_token = _start_pipeline_job(prepared)
        logger.info(f"API: Pipeline job started successfully with token {job_token}")
    except Exception as exc:
        error_msg = f"Failed to start pipeline job: {str(exc)}"
        logger.error(f"API: {error_msg}")
        logger.error(f"API: Stack trace:\n{traceback.format_exc()}")
        return JsonResponse({'error': error_msg}, status=500)

    # Store the active job token in session so the history page can track it
    request.session['active_job_token'] = job_token

    snapshot = job_tracker.get_job(job_token)
    payload: dict[str, Any] = {'jobToken': job_token}
    if snapshot:
        snap = snapshot.snapshot()
        payload['stage'] = snap['stage']
        payload['message'] = snap['message']
        payload['logs'] = snap['logs']
        payload['error'] = snap['error']
        payload['resultToken'] = snap['resultToken']

    logger.info(f"API: Returning success response for job {job_token}")
    return JsonResponse(payload, status=202)


@workspace_api_login_required_if_enabled
def api_job_status(request: HttpRequest, token: str) -> JsonResponse:
    if settings.WORKSPACE_ENFORCE_OWNER:
        owner_key = _get_owner_key(request)
        if not job_tracker.job_belongs_to(token, owner_key):
            return JsonResponse({'error': 'Job not found.'}, status=404)
    job = job_tracker.get_job(token)
    if job is None:
        return JsonResponse({'error': 'Job not found.'}, status=404)
    response = JsonResponse(job.snapshot())
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


def _format_timestamp(value: str | None) -> str | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return value
    return parsed.strftime('%b %d, %Y %H:%M')


def _format_duration(started_at: str | None, finished_at: str | None) -> str | None:
    if not started_at or not finished_at:
        return None
    try:
        start = datetime.fromisoformat(started_at)
        finish = datetime.fromisoformat(finished_at)
    except ValueError:
        return None
    delta = finish - start
    total_seconds = int(delta.total_seconds())
    if total_seconds < 0:
        return None
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours}h {minutes}m"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _build_result_summary(metadata: dict[str, Any], preview_headers: list[str]) -> dict[str, Any]:
    dataset_label = metadata.get('display_dataset_name') or metadata.get('dataset') or 'Dataset'
    table_label = metadata.get('display_table_name') or metadata.get('table') or 'Table'
    data_source = metadata.get('data_source') or 'preloaded'
    input_columns = metadata.get('input_columns')
    input_column_count: int | None = None
    if isinstance(input_columns, list):
        input_column_count = len(input_columns)
    elif preview_headers:
        input_column_count = len(preview_headers)
    return {
        'dataset_label': dataset_label,
        'table_label': table_label,
        'data_source': data_source,
        'run_name': metadata.get('run_name') or 'single_table',
        'started_at': _format_timestamp(metadata.get('started_at')),
        'finished_at': _format_timestamp(metadata.get('finished_at')),
        'duration': _format_duration(metadata.get('started_at'), metadata.get('finished_at')),
        'input_rows': metadata.get('input_rows'),
        'input_columns': input_column_count,
        'input_filename': metadata.get('input_filename'),
    }


def _build_config_items(metadata: dict[str, Any]) -> list[dict[str, str]]:
    items: list[dict[str, str]] = []
    fields = [
        ('Model type', 'model_type'),
        ('Normalization', 'normalization'),
        ('Epochs (VAE)', 'epochs_vae'),
        ('Epochs (GNN)', 'epochs_gnn'),
        ('Epochs (Diff)', 'epochs_diff'),
        ('GNN hidden', 'gnn_hidden'),
        ('Denoising steps', 'denoising_steps'),
        ('Random seed', 'random_seed'),
        ('Samples', 'num_samples'),
    ]
    for label, key in fields:
        value = metadata.get(key)
        if value is None or value == '':
            continue
        items.append({'label': label, 'value': str(value)})

    boolean_fields = [
        ('Retrain VAE', 'retrain_vae'),
        ('Positional enc', 'positional_enc'),
        ('Skip preprocessing', 'skip_preprocessing'),
        ('Factor missing', 'factor_missing'),
    ]
    for label, key in boolean_fields:
        if metadata.get(key):
            items.append({'label': label, 'value': 'Yes'})
    return items


EVALUATION_METRIC_GUIDE = [
    {
        'key': 'Quality Score',
        'label': 'Quality score',
        'description': (
            'Composite measure of how closely synthetic data matches real data across multiple '
            'statistical dimensions.'
        ),
        'range': '0-1',
        'interpretation': 'Higher values indicate better overall realism.',
        'direction': 'Higher is better.',
    },
    {
        'key': 'Column Shapes',
        'label': 'Column shapes',
        'description': 'Measures how well the distribution shape of each individual column is preserved.',
        'range': '0 to infinity (typically small positive values)',
        'interpretation': 'Lower values indicate closer alignment of marginal distributions.',
        'direction': 'Lower is better.',
    },
    {
        'key': 'Column Pair Trends',
        'label': 'Column pair trends',
        'description': 'Measures how well relationships between pairs of columns are preserved.',
        'range': '0 to infinity (typically small positive values)',
        'interpretation': 'Lower values indicate better preservation of pairwise dependencies.',
        'direction': 'Lower is better.',
    },
    {
        'key': 'Detection Score',
        'label': 'Detection score',
        'description': (
            'Measures how difficult it is for a classifier to distinguish synthetic records from real '
            'records.'
        ),
        'range': '0-1 (0.5 is about random guessing)',
        'interpretation': 'Scores closer to 0.5 indicate stronger privacy protection.',
        'direction': 'Higher is better (closer to 0.5).',
    },
    {
        'key': 'NewRowSynthesis_score',
        'label': 'New row synthesis score',
        'description': (
            'Measures the proportion of synthetic records that are not exact replicas of real records.'
        ),
        'range': '0-1',
        'interpretation': 'Higher values indicate stronger protection against memorization.',
        'direction': 'Higher is better.',
    },
    {
        'key': 'RMSE',
        'label': 'RMSE',
        'description': 'Measures the average numerical difference between real and synthetic values.',
        'range': '0 to infinity',
        'interpretation': 'Lower values indicate closer numerical agreement.',
        'direction': 'Lower is better.',
    },
    {
        'key': 'Wasserstein',
        'label': 'Wasserstein distance',
        'description': 'Measures the distance between real and synthetic feature distributions.',
        'range': '0 to infinity',
        'interpretation': 'Lower values indicate more similar distributions.',
        'direction': 'Lower is better.',
    },
    {
        'key': 'Kolmogorov-Smirnov statistic',
        'label': 'Kolmogorov-Smirnov (KS) statistic',
        'description': (
            'Measures the maximum difference between cumulative distributions of real and synthetic '
            'data.'
        ),
        'range': '0-1',
        'interpretation': 'Lower values indicate better distribution alignment.',
        'direction': 'Lower is better.',
    },
    {
        'key': 'RSP Area',
        'label': 'RSP area',
        'description': (
            'Measures differences in structural or rule-based patterns between real and synthetic data.'
        ),
        'range': '0-1',
        'interpretation': 'Lower values indicate fewer structural deviations.',
        'direction': 'Lower is better.',
    },
]


def _metric_key(label: str | None) -> str:
    if not label:
        return ''
    return ''.join(ch for ch in label.lower() if ch.isalnum())


def _metric_info_for_label(label: str | None) -> dict[str, str] | None:
    if not label:
        return None
    target = _metric_key(label)
    if not target:
        return None
    for entry in EVALUATION_METRIC_GUIDE:
        if target in (_metric_key(entry['key']), _metric_key(entry['label'])):
            return entry
    return None


def _build_metric_tooltip(info: dict[str, str] | None) -> str:
    if not info:
        return ''
    parts = [info.get('description', '').strip()]
    if info.get('range'):
        parts.append(f"Range: {info['range']}")
    if info.get('interpretation'):
        parts.append(f"Interpretation: {info['interpretation']}")
    if info.get('direction'):
        parts.append(f"Direction: {info['direction']}")
    return '\n'.join(part for part in parts if part)


def _build_evaluation_summary(evaluation: dict[str, Any]) -> list[dict[str, str]]:
    if not evaluation or evaluation.get('status') != 'success':
        return []
    metrics = evaluation.get('metrics') or []
    if not metrics:
        return []
    row = metrics[0]
    preferred = [
        ('Quality Score', 'Overall synthetic quality'),
        ('Column Shapes', 'Univariate similarity'),
        ('Column Pair Trends', 'Bivariate consistency'),
        ('Detection Score', 'Detectability gap'),
        ('RMSE', 'Numeric reconstruction error'),
        ('Wasserstein', 'Distribution distance'),
        ('Kolmogorov-Smirnov statistic', 'Distribution shift'),
        ('NewRowSynthesis_score', 'Novelty score'),
    ]
    summary: list[dict[str, str]] = []
    for label, hint in preferred:
        value = row.get(label)
        if value in (None, '', 'nan'):
            continue
        metric_info = _metric_info_for_label(label)
        summary.append({
            'key': label,
            'label': metric_info['label'] if metric_info else label,
            'value': str(value),
            'hint': hint,
            'tooltip': _build_metric_tooltip(metric_info),
        })
        if len(summary) >= 4:
            break
    if not summary:
        for label, value in row.items():
            if value in (None, '', 'nan'):
                continue
            metric_info = _metric_info_for_label(str(label))
            summary.append({
                'key': str(label),
                'label': metric_info['label'] if metric_info else str(label),
                'value': str(value),
                'hint': '',
                'tooltip': _build_metric_tooltip(metric_info),
            })
            if len(summary) >= 4:
                break
    return summary


def _evaluation_status(evaluation: dict[str, Any]) -> dict[str, str]:
    status = evaluation.get('status') if evaluation else None
    if status == 'success':
        return {'label': 'Evaluation ready', 'tone': 'success'}
    if status in ('missing_dependency', 'missing_real_data', 'missing_synthetic', 'skipped'):
        return {'label': 'Evaluation unavailable', 'tone': 'warning'}
    if status == 'error':
        return {'label': 'Evaluation failed', 'tone': 'danger'}
    if status:
        return {'label': 'Evaluation pending', 'tone': 'neutral'}
    return {'label': 'Evaluation pending', 'tone': 'neutral'}


@workspace_login_required_if_enabled
def result_view(request: HttpRequest, token: str) -> HttpResponse:
    # Check if user has access to this result
    if not _check_result_access(request, token):
        raise Http404('Synthetic run not found or access denied.')

    csv_path = _data_path(token)
    meta_path = _metadata_path(token)
    if not meta_path.exists():
        raise Http404('Synthetic run metadata not found.')

    with open(meta_path, 'r', encoding='utf-8') as meta_file:
        metadata = json.load(meta_file)
    _enforce_owner(request, metadata)

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
    evaluation_header_meta: list[dict[str, str]] = []
    evaluation_rows: list[list[str]] = []
    evaluation_pairs: list[dict[str, str]] = []
    evaluation_plot_data_uri: str | None = None
    evaluation_plot_path: str | None = None
    evaluation_download_url: str | None = None
    umap_coordinates: str | None = None
    show_umap = False

    raw_evaluation = metadata.get('evaluation')
    if isinstance(raw_evaluation, dict):
        evaluation = raw_evaluation
        metrics = evaluation.get('metrics') or []
        if metrics:
            evaluation_headers = list(metrics[0].keys())
            evaluation_rows = [[row.get(header, '') for header in evaluation_headers] for row in metrics]
            for header in evaluation_headers:
                metric_info = _metric_info_for_label(header)
                evaluation_header_meta.append({
                    'key': header,
                    'label': metric_info['label'] if metric_info else header,
                    'tooltip': _build_metric_tooltip(metric_info),
                })
            if evaluation_rows:
                first_row = evaluation_rows[0]
                for idx, header_meta in enumerate(evaluation_header_meta):
                    value = first_row[idx] if idx < len(first_row) else ''
                    evaluation_pairs.append({
                        'label': header_meta.get('label', ''),
                        'tooltip': header_meta.get('tooltip', ''),
                        'value': str(value),
                    })
        plot_payload = evaluation.get('plot') or {}
        evaluation_plot_data_uri = plot_payload.get('data_uri')
        evaluation_plot_path = plot_payload.get('path')
        if evaluation_plot_path:
            evaluation_download_url = reverse('synthetic:download-plot', kwargs={'token': token})

        # Get UMAP coordinates for interactive visualization
        umap_coords = evaluation.get('umap_coordinates')
        if umap_coords:
            umap_coordinates = json.dumps(umap_coords)
        if evaluation.get('status') == 'success':
            show_umap = bool(umap_coordinates or evaluation_plot_data_uri or evaluation_plot_path)

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

    result_summary = _build_result_summary(metadata, preview_headers)
    config_items = _build_config_items(metadata)
    evaluation_summary = _build_evaluation_summary(evaluation)
    evaluation_status = _evaluation_status(evaluation)

    context = {
        'metadata': metadata,
        'run_token': token,
        'preview_headers': preview_headers,
        'preview_rows': preview_rows,
        'has_output': has_csv,
        'download_url': request.build_absolute_uri(reverse('synthetic:download', kwargs={'token': token})) if has_csv else None,
        'evaluation': evaluation,
        'evaluation_headers': evaluation_headers,
        'evaluation_header_meta': evaluation_header_meta,
        'evaluation_rows': evaluation_rows,
        'evaluation_pairs': evaluation_pairs,
        'evaluation_plot_data_uri': evaluation_plot_data_uri,
        'evaluation_plot_path': evaluation_plot_path,
        'evaluation_download_url': evaluation_download_url,
        'umap_coordinates': umap_coordinates,
        'show_umap': show_umap,
        'epoch_metrics': epoch_metrics_data,
        'epoch_metrics_json': epoch_metrics_json,
        'result_summary': result_summary,
        'config_items': config_items,
        'evaluation_summary': evaluation_summary,
        'evaluation_status': evaluation_status,
        'evaluation_metric_guide': EVALUATION_METRIC_GUIDE,
    }
    return render(request, 'synthetic/result.html', context)


@workspace_login_required_if_enabled
def download_view(request: HttpRequest, token: str) -> FileResponse:
    # Check if user has access to this result
    if not _check_result_access(request, token):
        raise Http404('Synthetic dataset not found or access denied.')

    csv_path = _data_path(token)
    meta_path = _metadata_path(token)
    if not csv_path.exists() or not meta_path.exists():
        raise Http404('Synthetic dataset not found.')

    with open(meta_path, 'r', encoding='utf-8') as meta_file:
        metadata = json.load(meta_file)

    filename = f"{metadata.get('dataset')}_{metadata.get('table')}_{metadata.get('run_name', token)}.csv"
    return FileResponse(csv_path.open('rb'), as_attachment=True, filename=filename)


@workspace_login_required_if_enabled
def download_plot(request: HttpRequest, token: str) -> FileResponse:
    # Check if user has access to this result
    if not _check_result_access(request, token):
        raise Http404('Synthetic run not found or access denied.')

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


@workspace_api_login_required_if_enabled
def api_dataset_view(request: HttpRequest, token: str) -> JsonResponse:
    """API endpoint to serve the full dataset for a given run token."""
    # Check if user has access to this result
    if not _check_result_access(request, token):
        return JsonResponse({'error': 'Dataset not found or access denied.'}, status=404)

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

        response = JsonResponse(response_data)
        response['Cache-Control'] = 'no-store'
        return response

    except Exception as e:
        return JsonResponse({'error': f'Failed to load dataset: {str(e)}'}, status=500)


@workspace_api_login_required_if_enabled
@require_POST
def api_stage_upload(request: HttpRequest) -> JsonResponse:
    logger.info("API: Stage upload request received")
    owner_key = _get_owner_key(request)
    if rate_limited(request, 'stage_upload', identifier=owner_key):
        return JsonResponse({'error': 'Too many uploads. Please try again later.'}, status=429)
    upload = request.FILES.get('dataset')
    if upload is None:
        logger.warning("API: No dataset file provided in upload request")
        return JsonResponse({'error': 'No dataset provided.'}, status=400)

    dataset_name = request.POST.get('datasetName')
    table_name = request.POST.get('tableName')
    logger.info(f"API: Uploading file '{upload.name}' (size: {upload.size} bytes, dataset: {dataset_name}, table: {table_name})")

    try:
        stage = stage_upload(upload, dataset_name=dataset_name, table_name=table_name)
        logger.info(f"API: File staged successfully with token {stage.token}. Rows: {stage.profile['row_count']}, Columns: {len(stage.profile['columns'])}")
    except ValueError as exc:
        logger.error(f"API: Upload validation error: {exc}")
        return JsonResponse({'error': str(exc)}, status=400)
    except Exception as exc:
        logger.error(f"API: Upload processing failed: {exc}")
        logger.error(f"API: Stack trace:\n{traceback.format_exc()}")
        return JsonResponse({'error': f'Failed to process uploaded file: {str(exc)}'}, status=500)

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
    logger.info(f"API: Returning staged upload data for token {stage.token}")
    return JsonResponse(payload)


@workspace_api_login_required_if_enabled
@require_POST
def api_finalize_metadata(request: HttpRequest) -> JsonResponse:
    logger.info("API: Finalize metadata request received")
    try:
        payload = json.loads(request.body.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        logger.error(f"API: Invalid JSON in metadata finalization: {exc}")
        return JsonResponse({'error': 'Invalid JSON payload.'}, status=400)

    token = payload.get('token')
    if not token:
        logger.warning("API: Metadata finalization called without token")
        return JsonResponse({'error': 'Missing upload token.'}, status=400)

    dataset_name = payload.get('datasetName')
    table_name = payload.get('tableName')
    primary_key = payload.get('primaryKey')
    column_entries = payload.get('columns') or []

    logger.info(f"API: Finalizing metadata for token {token}, dataset={dataset_name}, table={table_name}, primary_key={primary_key}, columns={len(column_entries)}")

    try:
        stage = update_stage_profile(token, dataset_name=dataset_name, table_name=table_name)
    except FileNotFoundError:
        logger.error(f"API: Upload session not found for token {token}")
        return JsonResponse({'error': 'Upload session not found.'}, status=404)
    except Exception as exc:
        logger.error(f"API: Failed to update stage profile: {exc}")
        logger.error(f"API: Stack trace:\n{traceback.format_exc()}")
        return JsonResponse({'error': f'Failed to update profile: {str(exc)}'}, status=500)

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

    try:
        logger.info(f"API: Building metadata from profile with {len(column_overrides)} column overrides")
        metadata = build_metadata_from_profile(stage, primary_key=primary_key or None, column_overrides=column_overrides)
        metadata_path = save_metadata(token, metadata)
        logger.info(f"API: Metadata saved successfully to {metadata_path}")
    except Exception as exc:
        logger.error(f"API: Failed to build or save metadata: {exc}")
        logger.error(f"API: Stack trace:\n{traceback.format_exc()}")
        return JsonResponse({'error': f'Failed to finalize metadata: {str(exc)}'}, status=500)

    response = {
        'metadataPath': str(metadata_path),
        'datasetName': stage.profile['dataset_name'],
        'tableName': stage.profile['table_name'],
        'displayDatasetName': stage.profile.get('display_dataset_name'),
        'displayTableName': stage.profile.get('display_table_name'),
    }
    logger.info(f"API: Metadata finalization successful for token {token}")
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
