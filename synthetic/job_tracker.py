from __future__ import annotations

import threading
import time
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

from django.conf import settings

_STAGE_MESSAGES: Dict[str, str] = {
    "queued": "Queued",
    "starting": "Starting",
    "preprocessing": "Preprocessing data",
    "training": "Training models",
    "sampling": "Sampling synthetic rows",
    "evaluation": "Running evaluation",
    "finalizing": "Saving outputs",
    "completed": "Completed",
    "failed": "Failed",
}

_MAX_LOG_LINES = 400


@dataclass
class JobState:
    token: str
    owner_username: Optional[str] = None
    stage: str = "queued"
    message: str = _STAGE_MESSAGES["queued"]
    logs: list[str] = field(default_factory=list)
    error: Optional[str] = None
    result_token: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    progress_percentage: int = 0

    def snapshot(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "ownerUsername": self.owner_username,
            "stage": self.stage,
            "message": self.message,
            "logs": list(self.logs),
            "error": self.error,
            "resultToken": self.result_token,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
            "progressPercentage": self.progress_percentage,
        }


_jobs: dict[str, JobState] = {}
_lock = threading.Lock()


def _jobs_dir() -> Path:
    target = Path(settings.MEDIA_ROOT) / 'generated' / 'jobs'
    target.mkdir(parents=True, exist_ok=True)
    return target


def _job_path(token: str) -> Path:
    return _jobs_dir() / f"{token}.json"


def _state_from_dict(payload: dict[str, Any]) -> JobState:
    state = JobState(token=payload.get("token", ""))
    state.owner_username = payload.get("ownerUsername")
    state.stage = payload.get("stage", state.stage)
    state.message = payload.get("message", state.message)
    state.logs = list(payload.get("logs", []))
    state.error = payload.get("error")
    state.result_token = payload.get("resultToken")
    state.created_at = float(payload.get("createdAt", state.created_at))
    state.updated_at = float(payload.get("updatedAt", state.updated_at))
    state.progress_percentage = int(payload.get("progressPercentage", state.progress_percentage))
    return state


def _persist_state(state: JobState) -> None:
    path = _job_path(state.token)
    tmp_path = path.with_suffix(".tmp")
    payload = state.snapshot()
    tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    tmp_path.replace(path)


def _load_state(token: str) -> Optional[JobState]:
    path = _job_path(token)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return _state_from_dict(payload)


def list_jobs() -> list[JobState]:
    jobs: list[JobState] = []
    try:
        for path in _jobs_dir().glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            jobs.append(_state_from_dict(payload))
    except OSError:
        return jobs
    return jobs


def count_active_jobs() -> int:
    active = 0
    for job in list_jobs():
        if job.stage not in ("completed", "failed"):
            active += 1
    return active


def has_active_job(owner_username: str) -> bool:
    for job in list_jobs():
        if job.owner_username == owner_username and job.stage not in ("completed", "failed"):
            return True
    return False


def job_belongs_to(token: str, owner_username: str) -> bool:
    job = _load_state(token)
    if job is None:
        return False
    return job.owner_username == owner_username


def create_job(token: str, owner_username: Optional[str] = None) -> JobState:
    with _lock:
        state = JobState(token=token, owner_username=owner_username)
        _jobs[token] = state
        _persist_state(state)
        return state


def remove_job(token: str) -> None:
    with _lock:
        _jobs.pop(token, None)
    try:
        _job_path(token).unlink()
    except OSError:
        pass


def get_job(token: str) -> Optional[JobState]:
    state = _load_state(token)
    if state is None:
        with _lock:
            state = _jobs.get(token)
    if state is None:
        return None
    copy = JobState(token=state.token)
    copy.owner_username = state.owner_username
    copy.stage = state.stage
    copy.message = state.message
    copy.logs = list(state.logs)
    copy.error = state.error
    copy.result_token = state.result_token
    copy.created_at = state.created_at
    copy.updated_at = state.updated_at
    copy.progress_percentage = state.progress_percentage
    return copy

def append_log(token: str, line: str) -> None:
    line = line.rstrip("\n")
    with _lock:
        state = _jobs.get(token)
        if state is None:
            return
        state.logs.append(line)
        if len(state.logs) > _MAX_LOG_LINES:
            state.logs = state.logs[-_MAX_LOG_LINES:]
        state.updated_at = time.time()
        stage = _stage_from_line(line)
        if stage:
            state.stage = stage
            state.message = _STAGE_MESSAGES.get(stage, stage.title())
            state.progress_percentage = _progress_for_stage(stage)
        _persist_state(state)


def set_stage(token: str, stage: str, message: Optional[str] = None) -> None:
    with _lock:
        state = _jobs.get(token)
        if state is None:
            return
        state.stage = stage
        state.message = message or _STAGE_MESSAGES.get(stage, stage.title())
        state.progress_percentage = _progress_for_stage(stage)
        state.updated_at = time.time()
        _persist_state(state)


def set_result(token: str, result_token: str) -> None:
    with _lock:
        state = _jobs.get(token)
        if state is None:
            return
        state.result_token = result_token
        state.stage = "completed"
        state.message = _STAGE_MESSAGES["completed"]
        state.progress_percentage = 100
        state.updated_at = time.time()
        _persist_state(state)


def set_error(token: str, error: str) -> None:
    with _lock:
        state = _jobs.get(token)
        if state is None:
            return
        state.error = error
        state.stage = "failed"
        state.message = _STAGE_MESSAGES["failed"]
        state.progress_percentage = 0
        state.updated_at = time.time()
        _persist_state(state)


def _progress_for_stage(stage: str) -> int:
    """Calculate progress percentage based on pipeline stage"""
    stage_progress = {
        "queued": 0,
        "starting": 5,
        "preprocessing": 15,
        "training": 50,
        "sampling": 80,
        "evaluation": 90,
        "finalizing": 95,
        "completed": 100,
        "failed": 0,
    }
    return stage_progress.get(stage, 0)


def _stage_from_line(line: str) -> Optional[str]:
    upper = line.strip().upper()
    if "PREPROCESSING DATA" in upper or "PREPROCESS" in upper:
        return "preprocessing"
    if "TRAINING MODELS" in upper or ("TRAINING" in upper and "MODEL" in upper):
        return "training"
    if "SAMPLING DATA" in upper or ("SAMPLING" in upper and "DATA" in upper):
        return "sampling"
    if "PIPELINE COMPLETED" in upper or "COMPLETED SUCCESSFULLY" in upper:
        return "completed"
    return None


__all__ = [
    "JobState",
    "create_job",
    "remove_job",
    "get_job",
    "list_jobs",
    "count_active_jobs",
    "has_active_job",
    "job_belongs_to",
    "append_log",
    "set_stage",
    "set_result",
    "set_error",
]
