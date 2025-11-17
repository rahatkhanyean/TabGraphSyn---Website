from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from pymongo.errors import PyMongoError
from django.views.decorators.http import require_http_methods

from .forms import LoginForm, RegisterForm
from .mongo import authenticate_user, get_users_collection


def _redirect_target(request: HttpRequest, fallback: str) -> str:
    candidate = request.POST.get('next') or request.GET.get('next')
    if candidate and url_has_allowed_host_and_scheme(candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return candidate
    return fallback


def login_view(request: HttpRequest) -> HttpResponse:
    if request.session.get('auth_user'):
        return redirect('synthetic:upload')

    form = LoginForm(request.POST or None)
    fallback = reverse('synthetic:upload')
    next_url = _redirect_target(request, fallback)

    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username'].strip()
        password = form.cleaned_data['password']
        try:
            user = authenticate_user(username, password)
        except RuntimeError as exc:
            form.add_error(None, str(exc))
        else:
            if user:
                profile = {
                    'username': user.get('username', username),
                    'email': user.get('email'),
                    'full_name': user.get('full_name') or user.get('name') or username,
                    'roles': user.get('roles', []),
                }
                request.session['auth_user'] = profile
                request.session.set_expiry(60 * 60 * 8)
                messages.success(request, f"Welcome back, {profile['full_name']}!")
                return redirect(next_url)
            form.add_error(None, 'Invalid username or password.')

    context = {'form': form, 'next': next_url}
    return render(request, 'accounts/login.html', context)


@require_http_methods(["GET", "POST"])
def logout_view(request: HttpRequest) -> HttpResponse:
    fallback = reverse('accounts:login')
    target = _redirect_target(request, fallback)
    request.session.flush()
    messages.info(request, 'Signed out successfully.')
    return redirect(target)


def register_view(request: HttpRequest) -> HttpResponse:
    if request.session.get('auth_user'):
        return redirect('synthetic:upload')

    form = RegisterForm(request.POST or None)

    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username'].strip()
        password = form.cleaned_data['password']
        if not username:
            form.add_error('username', 'Username is required.')
        else:
            try:
                collection = get_users_collection()
                existing = collection.find_one({'username': username})
            except PyMongoError as exc:
                form.add_error(None, f'Unable to reach MongoDB: {exc}')
            else:
                if existing:
                    form.add_error('username', 'That username is already taken.')
                else:
                    now = timezone.now().isoformat()
                    payload = {
                        'username': username,
                        'password': make_password(password),
                        'roles': ['workspace-user'],
                        'created_at': now,
                        'updated_at': now,
                    }
                    try:
                        collection.insert_one(payload)
                    except PyMongoError as exc:
                        form.add_error(None, f'Unable to create user: {exc}')
                    else:
                        messages.success(request, 'Account created. You can sign in now.')
                        return redirect('accounts:login')

    return render(request, 'accounts/register.html', {'form': form})
