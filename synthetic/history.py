from __future__ import annotations

import logging
from typing import Any

from django.utils import timezone
from pymongo.errors import PyMongoError

from accounts.mongo import get_runs_collection

logger = logging.getLogger(__name__)


def store_run_history(
    metadata: dict[str, Any],
    *,
    owner: dict[str, Any] | None,
    started_at: str | None,
    finished_at: str | None,
) -> None:
    document = dict(metadata)
    document['owner'] = owner or {}
    document['owner_username'] = (owner or {}).get('username')
    document['owner_display_name'] = (
        (owner or {}).get('full_name')
        or (owner or {}).get('name')
        or (owner or {}).get('username')
    )
    document['started_at'] = started_at
    document['finished_at'] = finished_at or timezone.now().isoformat()
    document['recorded_at'] = timezone.now().isoformat()
    try:
        collection = get_runs_collection()
        collection.insert_one(document)
    except PyMongoError as exc:
        logger.warning('Failed to store run history in MongoDB: %s', exc)


def fetch_runs_for_user(username: str, limit: int = 50) -> list[dict[str, Any]]:
    try:
        collection = get_runs_collection()
        cursor = (
            collection.find({'owner_username': username})
            .sort('finished_at', -1)
            .limit(limit)
        )
        results: list[dict[str, Any]] = []
        for entry in cursor:
            entry['_id'] = str(entry.get('_id'))
            results.append(entry)
        return results
    except PyMongoError as exc:
        raise RuntimeError(f'Unable to load run history: {exc}') from exc
