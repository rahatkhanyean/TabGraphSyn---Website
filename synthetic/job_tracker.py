from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

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
    stage: str = "queued"
    message: str = _STAGE_MESSAGES["queued"]
    logs: list[str] = field(default_factory=list)
    error: Optional[str] = None
    result_token: Optional[str] = None
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)

    def snapshot(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "stage": self.stage,
            "message": self.message,
            "logs": list(self.logs),
            "error": self.error,
            "resultToken": self.result_token,
            "createdAt": self.created_at,
            "updatedAt": self.updated_at,
        }


_jobs: dict[str, JobState] = {}
_lock = threading.Lock()


def create_job(token: str) -> JobState:
    with _lock:
        state = JobState(token=token)
        _jobs[token] = state
        return state


def remove_job(token: str) -> None:
    with _lock:
        _jobs.pop(token, None)


def get_job(token: str) -> Optional[JobState]:
    with _lock:
        state = _jobs.get(token)
        if state is None:
            return None
        copy = JobState(token=state.token)
        copy.stage = state.stage
        copy.message = state.message
        copy.logs = list(state.logs)
        copy.error = state.error
        copy.result_token = state.result_token
        copy.created_at = state.created_at
        copy.updated_at = state.updated_at
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


def set_stage(token: str, stage: str, message: Optional[str] = None) -> None:
    with _lock:
        state = _jobs.get(token)
        if state is None:
            return
        state.stage = stage
        state.message = message or _STAGE_MESSAGES.get(stage, stage.title())
        state.updated_at = time.time()


def set_result(token: str, result_token: str) -> None:
    with _lock:
        state = _jobs.get(token)
        if state is None:
            return
        state.result_token = result_token
        state.stage = "completed"
        state.message = _STAGE_MESSAGES["completed"]
        state.updated_at = time.time()


def set_error(token: str, error: str) -> None:
    with _lock:
        state = _jobs.get(token)
        if state is None:
            return
        state.error = error
        state.stage = "failed"
        state.message = _STAGE_MESSAGES["failed"]
        state.updated_at = time.time()


def _stage_from_line(line: str) -> Optional[str]:
    upper = line.strip().upper()
    if "PREPROCESSING DATA" in upper:
        return "preprocessing"
    if "TRAINING MODELS" in upper:
        return "training"
    if "SAMPLING DATA" in upper:
        return "sampling"
    return None


__all__ = [
    "JobState",
    "create_job",
    "remove_job",
    "get_job",
    "append_log",
    "set_stage",
    "set_result",
    "set_error",
]
