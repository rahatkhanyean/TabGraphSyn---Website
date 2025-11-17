from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from datetime import datetime
from typing import Callable

from django.conf import settings
from .constants import UPLOAD_MARKER

BASE_DIR = Path(settings.BASE_DIR)
DATA_ROOT = BASE_DIR / 'src' / 'data'
SCRIPTS_ROOT = BASE_DIR / 'src' / 'scripts'
LOGS_ROOT = Path(settings.MEDIA_ROOT) / 'generated' / 'logs'


class PipelineError(RuntimeError):
    """Raised when the TabGraphSyn pipeline fails."""


@dataclass(frozen=True)
class PipelineParameters:
    dataset: str
    table: str
    run_name: str = 'single_table'
    seed: int | None = None
    num_samples: int | None = None
    factor_missing: bool = False
    positional_enc: bool = False
    retrain_vae: bool = False
    model_type: str = 'mlp'
    normalization: str = 'quantile'
    gnn_hidden: int | None = None
    denoising_steps: int | None = None
    skip_preprocessing: bool = False
    epochs_vae: int | None = None
    epochs_gnn: int | None = None
    epochs_diff: int | None = None
    enable_epoch_eval: bool = False
    eval_frequency: int = 10
    eval_samples: int = 500


@dataclass
class CommandResult:
    description: str
    command: list[str]
    output: str


@dataclass
class PipelineResult:
    commands: list[CommandResult]
    output_csv: Path | None
    log_path: Path | None = None

    def combined_output(self) -> str:
        sections: list[str] = []
        for command in self.commands:
            header = f"== {command.description} =="
            if command.output:
                sections.append(f"{header}\n{command.output.strip()}")
            else:
                sections.append(header)
        return '\n\n'.join(sections)


@lru_cache(maxsize=1)
def _python_executable() -> Path:
    configured = getattr(settings, 'PIPELINE_PYTHON_EXECUTABLE', None)
    if configured:
        candidate = Path(configured).expanduser()
        if candidate.exists():
            return candidate
        raise PipelineError(
            'Configured pipeline Python executable not found. '
            f'Checked: {candidate}. Update TABGRAPHSYN_PIPELINE_PYTHON or '
            'settings.PIPELINE_PYTHON_EXECUTABLE.'
        )
    return Path(sys.executable)


def available_datasets() -> list[str]:
    original_dir = DATA_ROOT / 'original'
    if not original_dir.exists():
        return []
    datasets: list[str] = []
    for path in original_dir.iterdir():
        if not path.is_dir():
            continue
        marker = path / UPLOAD_MARKER
        if marker.exists():
            continue
        datasets.append(path.name)
    return sorted(datasets)


@lru_cache(maxsize=None)
def tables_for_dataset(dataset: str) -> list[str]:
    metadata_path = DATA_ROOT / 'original' / dataset / 'metadata.json'
    if not metadata_path.exists():
        return []
    with metadata_path.open('r', encoding='utf-8') as fp:
        metadata = json.load(fp)
    tables = metadata.get('tables')
    if isinstance(tables, dict):
        return sorted(tables.keys())
    if isinstance(tables, list):
        return sorted(str(item) for item in tables)
    return []


def _python_command(script: Path, *arguments: str) -> list[str]:
    cmd = [str(_python_executable()), str(script)]
    cmd.extend(arguments)
    return cmd


def _safe_component(value: str) -> str:
    return ''.join(char if char.isalnum() or char in {'-', '_'} else '_' for char in value)


def run_pipeline(
    params: PipelineParameters, *, status_callback: Callable[[str], None] | None = None
) -> PipelineResult:
    pipeline_script = SCRIPTS_ROOT / 'run_pipeline.py'
    epochs_vae = str(params.epochs_vae or 10)
    epochs_gnn = str(params.epochs_gnn or 10)
    epochs_diff = str(params.epochs_diff or 1)
    command = [
        str(_python_executable()),
        str(pipeline_script),
        '--dataset-name', params.dataset,
        '--target-table', params.table,
        '--epochs-gnn', epochs_gnn,
        '--epochs-vae', epochs_vae,
        '--epochs-diff', epochs_diff,
    ]

    # Add epoch evaluation parameters
    if params.enable_epoch_eval:
        command.extend(['--enable-epoch-eval'])
        command.extend(['--eval-frequency', str(params.eval_frequency)])
        command.extend(['--eval-samples', str(params.eval_samples)])
    commands: list[tuple[str, list[str]]] = [
        (f'Run pipeline for {params.dataset}', command)
    ]

    env = os.environ.copy()
    src_path = str(BASE_DIR / 'src')
    existing_pythonpath = env.get('PYTHONPATH')
    env['PYTHONPATH'] = f"{src_path}{os.pathsep}{existing_pythonpath}" if existing_pythonpath else src_path
    env['PYTHONUNBUFFERED'] = '1'

    LOGS_ROOT.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime('%Y%m%d-%H%M%S')
    log_filename = f"{_safe_component(params.dataset)}_{_safe_component(params.table)}_{_safe_component(params.run_name)}_{timestamp}.log"
    log_path = LOGS_ROOT / log_filename

    results: list[CommandResult] = []
    with log_path.open('w', encoding='utf-8') as log_file:
        for description, command in commands:
            header = f"== {description} ==\nCommand: {' '.join(command)}\n"
            log_file.write(header)
            log_file.flush()
            print(header.rstrip(), flush=True)
            if status_callback:
                status_callback(header)

            process = subprocess.Popen(
                command,
                cwd=BASE_DIR,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
            )

            if process.stdout is None:
                raise PipelineError(f'Failed to capture pipeline output. Logs: {log_path}')

            output_lines: list[str] = []
            for line in process.stdout:
                output_lines.append(line)
                log_file.write(line)
                log_file.flush()
                print(line.rstrip(), flush=True)
                if status_callback:
                    status_callback(line)

            process.stdout.close()
            returncode = process.wait()
            output = ''.join(output_lines)

            if returncode != 0:
                raise PipelineError(
                    f"{description} failed with exit code {returncode}.\n"
                    f"Command: {' '.join(command)}\n\n{output}\nLogs: {log_path}"
                )
            results.append(CommandResult(description, command, output))

    output_csv: Path | None = None
    run_dir = DATA_ROOT / 'synthetic' / params.dataset / 'SingleTable' / params.run_name
    candidate = run_dir / f"{params.table}.csv"
    if not candidate.exists():
        raise PipelineError(
            'Synthetic output CSV not found after sampling. '
            f"Expected path: {candidate}"
        )
    output_csv = candidate

    return PipelineResult(commands=results, output_csv=output_csv, log_path=log_path)
