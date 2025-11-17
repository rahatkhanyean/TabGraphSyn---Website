from __future__ import annotations

from functools import wraps
from urllib.parse import quote

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect
from django.urls import reverse


def _is_authenticated(request: HttpRequest) -> bool:
    return bool(request.session.get('auth_user'))


def workspace_login_required(view_func):
    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs) -> HttpResponse:
        if _is_authenticated(request):
            return view_func(request, *args, **kwargs)
        login_url = reverse('accounts:login')
        next_param = quote(request.get_full_path(), safe='')
        return redirect(f'{login_url}?next={next_param}')

    return _wrapped


def workspace_api_login_required(view_func):
    @wraps(view_func)
    def _wrapped(request: HttpRequest, *args, **kwargs) -> JsonResponse:
        if _is_authenticated(request):
            return view_func(request, *args, **kwargs)
        return JsonResponse({'error': 'Authentication required.'}, status=401)

    return _wrapped
