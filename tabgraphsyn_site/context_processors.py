from __future__ import annotations

from typing import Any

from django.http import HttpRequest


def csp_nonce(request: HttpRequest) -> dict[str, Any]:
    return {'csp_nonce': getattr(request, 'csp_nonce', '')}
