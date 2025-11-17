from __future__ import annotations

from typing import Any, Optional

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.core.exceptions import ImproperlyConfigured
from pymongo import MongoClient
from pymongo.collection import Collection
from pymongo.errors import PyMongoError

_client: MongoClient | None = None


def _connection_settings() -> dict[str, str]:
    try:
        cfg = settings.MONGO_CONNECTION
    except AttributeError as exc:
        raise ImproperlyConfigured('MONGO_CONNECTION is missing from settings.py') from exc
    required = ('URI', 'DATABASE', 'USERS_COLLECTION', 'RUNS_COLLECTION')
    for key in required:
        if not cfg.get(key):
            raise ImproperlyConfigured(f"MONGO_CONNECTION['{key}'] must be configured")
    return cfg


def get_client() -> MongoClient:
    global _client
    cfg = _connection_settings()
    if _client is None:
        _client = MongoClient(cfg['URI'])
    return _client


def get_collection(name: str) -> Collection:
    cfg = _connection_settings()
    client = get_client()
    return client[cfg['DATABASE']][name]



def get_users_collection() -> Collection:
    cfg = _connection_settings()
    return get_collection(cfg['USERS_COLLECTION'])



def get_runs_collection() -> Collection:
    cfg = _connection_settings()
    return get_collection(cfg['RUNS_COLLECTION'])


def get_jobs_collection() -> Collection:
    """Get jobs collection for async job queue metadata"""
    cfg = _connection_settings()
    return get_collection(cfg.get('JOBS_COLLECTION', 'jobs'))


def get_subscriptions_collection() -> Collection:
    """Get subscriptions collection for payment/billing data"""
    cfg = _connection_settings()
    return get_collection(cfg.get('SUBSCRIPTIONS_COLLECTION', 'subscriptions'))


def get_notifications_collection() -> Collection:
    """Get notifications collection for user notifications"""
    cfg = _connection_settings()
    return get_collection(cfg.get('NOTIFICATIONS_COLLECTION', 'notifications'))


def get_datasets_collection() -> Collection:
    """Get datasets collection for chatbot dataset catalog"""
    cfg = _connection_settings()
    return get_collection(cfg.get('DATASETS_COLLECTION', 'datasets'))


def fetch_user(username: str) -> Optional[dict[str, Any]]:
    collection = get_users_collection()
    return collection.find_one({'username': username})


def authenticate_user(username: str, password: str) -> Optional[dict[str, Any]]:
    try:
        user = fetch_user(username)
    except PyMongoError as exc:
        raise RuntimeError(f'Unable to reach MongoDB: {exc}') from exc
    if not user:
        return None
    stored_hash = user.get('password')
    if not stored_hash:
        return None
    if not check_password(password, stored_hash):
        return None
    return user
