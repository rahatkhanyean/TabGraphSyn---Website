from __future__ import annotations

import json
import logging
import re
import secrets
import urllib.parse
import urllib.request
from datetime import timedelta

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.hashers import make_password
from django.core.mail import send_mail
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.crypto import constant_time_compare
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods
from pymongo.errors import PyMongoError

from .forms import LoginForm, RegisterForm
from .mongo import authenticate_user, fetch_user_by_email, get_users_collection
from tabgraphsyn_site.ratelimit import rate_limited


def _redirect_target(request: HttpRequest, fallback: str) -> str:
    candidate = request.POST.get('next') or request.GET.get('next')
    if candidate and url_has_allowed_host_and_scheme(candidate, allowed_hosts={request.get_host()}, require_https=request.is_secure()):
        return candidate
    return fallback


logger = logging.getLogger(__name__)


def _email_verification_enabled() -> bool:
    return getattr(settings, 'EMAIL_VERIFICATION_ENABLED', True)


def _email_verification_required() -> bool:
    return getattr(settings, 'EMAIL_VERIFICATION_REQUIRED', _email_verification_enabled())


def _email_verification_ttl_hours() -> int:
    return getattr(settings, 'EMAIL_VERIFICATION_TOKEN_TTL_HOURS', 24)


def _verification_expires_at() -> int:
    return int((timezone.now() + timedelta(hours=_email_verification_ttl_hours())).timestamp())


def _normalize_email(value: str) -> str:
    return value.strip().lower()


def _normalize_username(value: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9_.-]+', '', value)
    cleaned = cleaned.strip('._-')
    return cleaned or 'user'


def _generate_unique_username(base: str, collection) -> str:
    base_clean = _normalize_username(base)[:140].lower()
    if not collection.find_one({'username': base_clean}):
        return base_clean
    for idx in range(1, 100):
        candidate = f"{base_clean}{idx}"
        if not collection.find_one({'username': candidate}):
            return candidate
    return f"{base_clean}-{secrets.token_hex(3)}"


def _build_auth_profile(user: dict, fallback_username: str | None = None) -> dict[str, str | list[str]]:
    username = user.get('username') or fallback_username or ''
    full_name = user.get('full_name') or user.get('name') or username
    return {
        'username': username,
        'email': user.get('email'),
        'full_name': full_name,
        'roles': user.get('roles', []),
    }


def _set_session_user(request: HttpRequest, user: dict, fallback_username: str | None = None) -> dict[str, str | list[str]]:
    profile = _build_auth_profile(user, fallback_username=fallback_username)
    request.session['auth_user'] = profile
    request.session.set_expiry(60 * 60 * 8)
    return profile


def _send_verification_email(request: HttpRequest, email: str, token: str) -> None:
    verify_url = request.build_absolute_uri(reverse('accounts:verify-email', kwargs={'token': token}))
    context = {
        'verify_url': verify_url,
        'site_name': getattr(settings, 'SITE_NAME', 'TabGraphSyn'),
        'expiry_hours': _email_verification_ttl_hours(),
    }
    subject = f"Verify your {context['site_name']} account"
    message = render_to_string('accounts/email/verify_email.txt', context).strip()
    send_mail(subject, message, settings.DEFAULT_FROM_EMAIL, [email])


def _google_oauth_config(request: HttpRequest) -> dict[str, str] | None:
    if not getattr(settings, 'GOOGLE_OAUTH_ENABLED', False):
        return None
    client_id = getattr(settings, 'GOOGLE_OAUTH_CLIENT_ID', '')
    client_secret = getattr(settings, 'GOOGLE_OAUTH_CLIENT_SECRET', '')
    if not client_id or not client_secret:
        return None
    redirect_uri = getattr(settings, 'GOOGLE_OAUTH_REDIRECT_URI', '')
    if not redirect_uri:
        redirect_uri = request.build_absolute_uri(reverse('accounts:google-callback'))
    return {
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
    }


def _google_state_is_valid(request: HttpRequest, state: str | None) -> bool:
    saved_state = request.session.get('google_oauth_state')
    saved_ts = request.session.get('google_oauth_state_ts')
    if not (state and saved_state and constant_time_compare(state, saved_state)):
        return False
    if not saved_ts:
        return False
    ttl = getattr(settings, 'GOOGLE_OAUTH_STATE_TTL_SECONDS', 600)
    return int(timezone.now().timestamp()) - int(saved_ts) <= ttl


def _post_form(url: str, payload: dict[str, str]) -> dict:
    data = urllib.parse.urlencode(payload).encode('utf-8')
    request = urllib.request.Request(url, data=data, headers={'Content-Type': 'application/x-www-form-urlencoded'})
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode('utf-8'))


def _get_json(url: str, headers: dict[str, str]) -> dict:
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode('utf-8'))


@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    if request.session.get('auth_user'):
        return redirect('synthetic:generate')

    form = LoginForm(request.POST or None)
    fallback = reverse('synthetic:generate')
    next_url = _redirect_target(request, fallback)
    google_config = _google_oauth_config(request)
    google_login_url = reverse('accounts:google-login')

    if request.method == 'POST' and form.is_valid():
        username = form.cleaned_data['username'].strip()
        password = form.cleaned_data['password']
        ip_raw = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', 'unknown'))
        ip_addr = ip_raw.split(',')[0].strip()
        identifier = f"{ip_addr}:{username}"
        if rate_limited(request, 'login', identifier=identifier):
            form.add_error(None, 'Too many login attempts. Please try again later.')
            return render(
                request,
                'accounts/login.html',
                {
                    'form': form,
                    'next': next_url,
                    'google_oauth_enabled': bool(google_config),
                    'google_oauth_url': f"{google_login_url}?next={urllib.parse.quote(next_url)}" if google_config else '',
                },
                status=429,
            )
        try:
            user = authenticate_user(username, password)
        except RuntimeError as exc:
            form.add_error(None, str(exc))
        else:
            if user:
                if _email_verification_required() and user.get('email') and user.get('email_verified') is False:
                    form.add_error(None, 'Email not verified. Check your inbox before signing in.')
                else:
                    profile = _set_session_user(request, user, fallback_username=username)
                    messages.success(request, f"Welcome back, {profile['full_name']}!")
                    return redirect(next_url)
            else:
                try:
                    existing = get_users_collection().find_one({'username': username})
                except PyMongoError:
                    existing = None
                if existing and existing.get('auth_provider') == 'google' and not existing.get('password'):
                    form.add_error(None, 'This account uses Google sign-in. Use "Continue with Google".')
                else:
                    form.add_error(None, 'Invalid username or password.')

    context = {
        'form': form,
        'next': next_url,
        'google_oauth_enabled': bool(google_config),
        'google_oauth_url': f"{google_login_url}?next={urllib.parse.quote(next_url)}" if google_config else '',
    }
    return render(request, 'accounts/login.html', context)


@require_http_methods(["GET", "POST"])
def logout_view(request: HttpRequest) -> HttpResponse:
    fallback = reverse('accounts:login')
    target = _redirect_target(request, fallback)
    request.session.flush()
    messages.info(request, 'Signed out successfully.')
    return redirect(target)


@require_http_methods(["GET", "POST"])
def register_view(request: HttpRequest) -> HttpResponse:
    if request.session.get('auth_user'):
        return redirect('synthetic:generate')

    form = RegisterForm(request.POST or None)
    google_config = _google_oauth_config(request)
    google_login_url = reverse('accounts:google-login')

    if request.method == 'POST' and form.is_valid():
        if rate_limited(request, 'register'):
            form.add_error(None, 'Too many registration attempts. Please try again later.')
            return render(
                request,
                'accounts/register.html',
                {
                    'form': form,
                    'google_oauth_enabled': bool(google_config),
                    'google_oauth_url': f"{google_login_url}?next={urllib.parse.quote(reverse('synthetic:generate'))}",
                },
                status=429,
            )
        username = form.cleaned_data['username'].strip()
        password = form.cleaned_data['password']
        email = form.cleaned_data['email'].strip()
        if not username:
            form.add_error('username', 'Username is required.')
        else:
            try:
                collection = get_users_collection()
                existing = collection.find_one({'username': username})
                email_lower = _normalize_email(email)
                existing_email = collection.find_one({'email_lower': email_lower}) if email_lower else None
            except PyMongoError as exc:
                form.add_error(None, f'Unable to reach MongoDB: {exc}')
            else:
                if existing:
                    form.add_error('username', 'That username is already taken.')
                if existing_email:
                    form.add_error('email', 'That email is already registered.')
                else:
                    now = timezone.now().isoformat()
                    verification_required = _email_verification_required()
                    verification_enabled = _email_verification_enabled() and verification_required
                    verification_token = secrets.token_urlsafe(32) if verification_enabled else None
                    verification_expires_at = _verification_expires_at() if verification_enabled else None
                    payload = {
                        'username': username,
                        'password': make_password(password),
                        'email': email,
                        'email_lower': email_lower,
                        'email_verified': not verification_enabled,
                        'email_verification_token': verification_token,
                        'email_verification_expires_at': verification_expires_at,
                        'email_verification_sent_at': now if verification_enabled else None,
                        'auth_provider': 'password',
                        'roles': ['workspace-user'],
                        'created_at': now,
                        'updated_at': now,
                    }
                    try:
                        collection.insert_one(payload)
                    except PyMongoError as exc:
                        form.add_error(None, f'Unable to create user: {exc}')
                    else:
                        if verification_enabled and verification_token:
                            try:
                                _send_verification_email(request, email, verification_token)
                                messages.success(request, 'Account created. Check your email to verify before signing in.')
                            except Exception as exc:
                                logger.exception('Unable to send verification email: %s', exc)
                                messages.warning(
                                    request,
                                    'Account created, but verification email could not be sent. '
                                    'Contact an administrator to enable your login.',
                                )
                        else:
                            messages.success(request, 'Account created. You can sign in now.')
                        return redirect('accounts:login')

    return render(
        request,
        'accounts/register.html',
        {
            'form': form,
            'google_oauth_enabled': bool(google_config),
            'google_oauth_url': f"{google_login_url}?next={urllib.parse.quote(reverse('synthetic:generate'))}" if google_config else '',
        },
    )


@require_http_methods(["GET"])
def verify_email_view(request: HttpRequest, token: str) -> HttpResponse:
    if not token:
        messages.error(request, 'Verification link is invalid.')
        return redirect('accounts:login')
    try:
        collection = get_users_collection()
        user = collection.find_one({'email_verification_token': token})
    except PyMongoError as exc:
        messages.error(request, f'Unable to reach MongoDB: {exc}')
        return redirect('accounts:login')
    if not user:
        messages.error(request, 'Verification link is invalid or has already been used.')
        return redirect('accounts:login')
    if user.get('email_verified'):
        messages.info(request, 'Email already verified. You can sign in.')
        return redirect('accounts:login')
    expires_at = user.get('email_verification_expires_at')
    if expires_at and int(expires_at) < int(timezone.now().timestamp()):
        messages.error(request, 'Verification link has expired. Contact an administrator to resend it.')
        return redirect('accounts:login')
    now = timezone.now().isoformat()
    collection.update_one(
        {'_id': user['_id']},
        {
            '$set': {'email_verified': True, 'updated_at': now},
            '$unset': {
                'email_verification_token': '',
                'email_verification_expires_at': '',
                'email_verification_sent_at': '',
            },
        },
    )
    messages.success(request, 'Email verified. You can sign in now.')
    return redirect('accounts:login')


@require_http_methods(["GET"])
def google_login_view(request: HttpRequest) -> HttpResponse:
    if request.session.get('auth_user'):
        return redirect('synthetic:generate')
    config = _google_oauth_config(request)
    if not config:
        messages.error(request, 'Google sign-in is not configured.')
        return redirect('accounts:login')
    fallback = reverse('synthetic:generate')
    next_url = _redirect_target(request, fallback)
    state = secrets.token_urlsafe(24)
    request.session['google_oauth_state'] = state
    request.session['google_oauth_state_ts'] = int(timezone.now().timestamp())
    request.session['google_oauth_next'] = next_url
    params = {
        'client_id': config['client_id'],
        'redirect_uri': config['redirect_uri'],
        'response_type': 'code',
        'scope': 'openid email profile',
        'state': state,
        'access_type': 'online',
        'prompt': 'select_account',
    }
    auth_url = f"https://accounts.google.com/o/oauth2/v2/auth?{urllib.parse.urlencode(params)}"
    return redirect(auth_url)


@require_http_methods(["GET"])
def google_callback_view(request: HttpRequest) -> HttpResponse:
    config = _google_oauth_config(request)
    if not config:
        messages.error(request, 'Google sign-in is not configured.')
        return redirect('accounts:login')
    error = request.GET.get('error')
    if error:
        messages.error(request, f'Google sign-in failed: {error}')
        return redirect('accounts:login')
    state = request.GET.get('state')
    if not _google_state_is_valid(request, state):
        messages.error(request, 'Google sign-in validation failed. Please try again.')
        return redirect('accounts:login')
    code = request.GET.get('code')
    if not code:
        messages.error(request, 'Google sign-in did not return a valid authorization code.')
        return redirect('accounts:login')

    request.session.pop('google_oauth_state', None)
    request.session.pop('google_oauth_state_ts', None)

    try:
        token_data = _post_form(
            'https://oauth2.googleapis.com/token',
            {
                'code': code,
                'client_id': config['client_id'],
                'client_secret': config['client_secret'],
                'redirect_uri': config['redirect_uri'],
                'grant_type': 'authorization_code',
            },
        )
        access_token = token_data.get('access_token')
        if not access_token:
            raise RuntimeError('Missing access token from Google.')
        userinfo = _get_json(
            'https://openidconnect.googleapis.com/v1/userinfo',
            {'Authorization': f"Bearer {access_token}"},
        )
    except Exception as exc:
        logger.exception('Google OAuth exchange failed: %s', exc)
        messages.error(request, 'Google sign-in failed while fetching your profile.')
        return redirect('accounts:login')

    email = userinfo.get('email')
    email_verified = userinfo.get('email_verified')
    if not email:
        messages.error(request, 'Google sign-in did not return an email address.')
        return redirect('accounts:login')
    if not email_verified:
        messages.error(request, 'Google reports this email address is not verified.')
        return redirect('accounts:login')
    allowed_domains = getattr(settings, 'GOOGLE_OAUTH_ALLOWED_DOMAINS', [])
    email_lower = _normalize_email(email)
    domain = email_lower.split('@')[-1]
    if allowed_domains and domain not in allowed_domains:
        messages.error(request, 'This Google account is not authorized for access.')
        return redirect('accounts:login')

    try:
        collection = get_users_collection()
        user = fetch_user_by_email(email_lower)
        now = timezone.now().isoformat()
        if user:
            updates = {
                'email': email,
                'email_lower': email_lower,
                'email_verified': True,
                'full_name': userinfo.get('name') or user.get('full_name') or user.get('username'),
                'google_sub': userinfo.get('sub'),
                'updated_at': now,
            }
            if not user.get('password'):
                updates['auth_provider'] = 'google'
            collection.update_one(
                {'_id': user['_id']},
                {
                    '$set': updates,
                    '$unset': {
                        'email_verification_token': '',
                        'email_verification_expires_at': '',
                        'email_verification_sent_at': '',
                    },
                },
            )
            user.update(updates)
        else:
            username = _generate_unique_username(email_lower.split('@')[0], collection)
            user = {
                'username': username,
                'email': email,
                'email_lower': email_lower,
                'email_verified': True,
                'full_name': userinfo.get('name') or username,
                'roles': ['workspace-user'],
                'auth_provider': 'google',
                'google_sub': userinfo.get('sub'),
                'created_at': now,
                'updated_at': now,
            }
            collection.insert_one(user)
    except PyMongoError as exc:
        messages.error(request, f'Unable to reach MongoDB: {exc}')
        return redirect('accounts:login')

    profile = _set_session_user(request, user, fallback_username=user.get('username'))
    messages.success(request, f"Welcome, {profile['full_name']}!")
    next_url = request.session.pop('google_oauth_next', reverse('synthetic:generate'))
    return redirect(next_url)
