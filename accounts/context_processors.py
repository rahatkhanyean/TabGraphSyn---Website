from __future__ import annotations

from typing import Any

from django.http import HttpRequest


def workspace_user(request: HttpRequest) -> dict[str, Any]:
    auth_user = request.session.get('auth_user')
    return {'workspace_user': auth_user, 'auth_user': auth_user}
