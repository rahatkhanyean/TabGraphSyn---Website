from __future__ import annotations

from typing import Optional

from django.conf import settings
from django.core.cache import cache
from django.http import HttpRequest


def _client_ip(request: HttpRequest) -> str:
    forwarded = request.META.get('HTTP_X_FORWARDED_FOR')
    if forwarded:
        return forwarded.split(',')[0].strip()
    return request.META.get('REMOTE_ADDR', 'unknown')


def rate_limited(request: HttpRequest, action: str, *, identifier: Optional[str] = None) -> bool:
    limits = getattr(settings, 'RATE_LIMITS', {})
    config = limits.get(action)
    if not config:
        return False
    limit = int(config.get('limit', 0))
    window = int(config.get('window', 0))
    if limit <= 0 or window <= 0:
        return False

    key_id = identifier or _client_ip(request)
    cache_key = f"rate:{action}:{key_id}"

    if cache.add(cache_key, 1, timeout=window):
        return False
    try:
        count = cache.incr(cache_key)
    except ValueError:
        cache.set(cache_key, 1, timeout=window)
        count = 1
    return count > limit
