import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent


def _env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in ('1', 'true', 't', 'yes', 'y')


def _env_int(name: str, default: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        return int(raw)
    except ValueError:
        return default

# Security Settings - Load from environment variables
# SECRET_KEY: Must be set in .env file. Used for cryptographic signing.
SECRET_KEY = os.getenv('SECRET_KEY')
if not SECRET_KEY:
    raise ValueError(
        "SECRET_KEY environment variable is not set! "
        "Please create a .env file (copy from .env.example) and set SECRET_KEY. "
        "Generate one with: python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\""
    )
# Validate SECRET_KEY is not the insecure default
if SECRET_KEY == 'django-insecure-tabgraphsyn' or 'your-secret-key-here' in SECRET_KEY.lower():
    raise ValueError(
        "SECRET_KEY is set to an insecure default value! "
        "Please generate a new secure key: python -c \"from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())\""
    )

# DEBUG: Should be False in production
DEBUG = _env_bool('DEBUG', False)

# ALLOWED_HOSTS: Parse comma-separated list from environment
ALLOWED_HOSTS_ENV = os.getenv('ALLOWED_HOSTS', '127.0.0.1,localhost')
ALLOWED_HOSTS: list[str] = [host.strip() for host in ALLOWED_HOSTS_ENV.split(',') if host.strip()]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'accounts',
    'synthetic',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'tabgraphsyn_site.middleware.SecurityHeadersMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'tabgraphsyn_site.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'accounts.context_processors.workspace_user',
                'tabgraphsyn_site.context_processors.csp_nonce',
            ],
        },
    },
]

WSGI_APPLICATION = 'tabgraphsyn_site.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript, Images)
STATIC_URL = 'static/'
STATICFILES_DIRS = [
    BASE_DIR / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'  # For production: python manage.py collectstatic

# Media files (user uploads)
MEDIA_URL = 'media/'
MEDIA_ROOT = BASE_DIR / 'media'

# CSRF Trusted Origins - allow explicit override
CSRF_TRUSTED_ORIGINS_ENV = os.getenv('CSRF_TRUSTED_ORIGINS', '')
if CSRF_TRUSTED_ORIGINS_ENV:
    CSRF_TRUSTED_ORIGINS = [origin.strip() for origin in CSRF_TRUSTED_ORIGINS_ENV.split(',') if origin.strip()]
else:
    CSRF_TRUSTED_ORIGINS = []
    for host in ALLOWED_HOSTS:
        if host in ('127.0.0.1', 'localhost'):
            CSRF_TRUSTED_ORIGINS.append(f'http://{host}')
        else:
            CSRF_TRUSTED_ORIGINS.append(f'https://{host}')
MONGO_CONNECTION = {
    'URI': os.getenv('TABGRAPHSYN_MONGO_URI', 'mongodb://localhost:27017'),
    'DATABASE': os.getenv('TABGRAPHSYN_MONGO_DB', 'tabgraphsyn'),
    'USERS_COLLECTION': os.getenv('TABGRAPHSYN_MONGO_USERS_COLLECTION', 'users'),
    'RUNS_COLLECTION': os.getenv('TABGRAPHSYN_MONGO_RUNS_COLLECTION', 'runs'),
}

PIPELINE_PYTHON_EXECUTABLE = (
    os.getenv('TABGRAPHSYN_PIPELINE_PYTHON')
    or r'C:\ProgramData\miniconda3\envs\tabgraphsyn\python.exe'
)

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# =============================================================================
# Security Settings
# =============================================================================
# These settings protect against common web vulnerabilities
# They are configured differently for development (DEBUG=True) vs production (DEBUG=False)

# SSL/HTTPS Settings (only enforced in production)
SECURE_SSL_REDIRECT = not DEBUG  # Redirect all HTTP to HTTPS in production
SESSION_COOKIE_SECURE = not DEBUG  # Only send session cookie over HTTPS in production
CSRF_COOKIE_SECURE = not DEBUG  # Only send CSRF cookie over HTTPS in production
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = os.getenv('SESSION_COOKIE_SAMESITE', 'Lax')
CSRF_COOKIE_SAMESITE = os.getenv('CSRF_COOKIE_SAMESITE', 'Lax')
CSRF_COOKIE_HTTPONLY = False  # Required for JS-based CSRF token usage in upload.js

# Security Headers (always enabled)
SECURE_BROWSER_XSS_FILTER = True  # Enable browser's XSS filtering
SECURE_CONTENT_TYPE_NOSNIFF = True  # Prevent MIME-type sniffing
X_FRAME_OPTIONS = 'DENY'  # Prevent clickjacking by disabling iframes
SECURE_REFERRER_POLICY = os.getenv('SECURE_REFERRER_POLICY', 'strict-origin-when-cross-origin')
SECURE_CROSS_ORIGIN_OPENER_POLICY = os.getenv('SECURE_CROSS_ORIGIN_OPENER_POLICY', 'same-origin')
PERMISSIONS_POLICY = os.getenv(
    'PERMISSIONS_POLICY',
    'accelerometer=(), camera=(), geolocation=(), gyroscope=(), microphone=(), payment=(), usb=()',
)
CROSS_ORIGIN_RESOURCE_POLICY = os.getenv('CROSS_ORIGIN_RESOURCE_POLICY', 'same-origin')

# Content Security Policy (CSP)
CSP_ENABLED = _env_bool('CSP_ENABLED', default=not DEBUG)
CSP_REPORT_ONLY = _env_bool('CSP_REPORT_ONLY', default=False)
CSP_DEFAULT_SRC = ["'self'"]
CSP_SCRIPT_SRC = [
    "'self'",
    "https://cdn.plot.ly",
    "https://cdn.jsdelivr.net",
    "https://cdn-script.com",
]
CSP_STYLE_SRC = [
    "'self'",
    "'unsafe-inline'",
    "https://cdnjs.cloudflare.com",
]
CSP_IMG_SRC = ["'self'", "data:"]
CSP_FONT_SRC = ["'self'", "https://cdnjs.cloudflare.com"]
CSP_CONNECT_SRC = ["'self'"]
CSP_BASE_URI = ["'self'"]
CSP_FORM_ACTION = ["'self'"]
CSP_FRAME_ANCESTORS = ["'none'"]

USE_PROXY_HEADERS = _env_bool('USE_PROXY_HEADERS', default=not DEBUG)
if USE_PROXY_HEADERS:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    USE_X_FORWARDED_HOST = True

# HSTS (HTTP Strict Transport Security) - only in production
# Tells browsers to only access the site via HTTPS for the specified duration
if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000  # 1 year
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

# File Upload Security
# Maximum upload file size: 100 MB (100 * 1024 * 1024 bytes)
DATA_UPLOAD_MAX_MEMORY_SIZE = 104857600  # 100 MB in bytes
FILE_UPLOAD_MAX_MEMORY_SIZE = 104857600  # 100 MB in bytes

# Access control and rate limiting
WORKSPACE_AUTH_REQUIRED = _env_bool('WORKSPACE_AUTH_REQUIRED', default=not DEBUG)
WORKSPACE_ENFORCE_OWNER = _env_bool('WORKSPACE_ENFORCE_OWNER', default=WORKSPACE_AUTH_REQUIRED)
PIPELINE_MAX_CONCURRENT = _env_int('PIPELINE_MAX_CONCURRENT', 1)

RATE_LIMITS = {
    'login': {'limit': _env_int('RATE_LIMIT_LOGIN', 8), 'window': _env_int('RATE_LIMIT_LOGIN_WINDOW', 900)},
    'register': {'limit': _env_int('RATE_LIMIT_REGISTER', 6), 'window': _env_int('RATE_LIMIT_REGISTER_WINDOW', 900)},
    'stage_upload': {'limit': _env_int('RATE_LIMIT_STAGE_UPLOAD', 6), 'window': _env_int('RATE_LIMIT_STAGE_UPLOAD_WINDOW', 3600)},
    'start_run': {'limit': _env_int('RATE_LIMIT_START_RUN', 3), 'window': _env_int('RATE_LIMIT_START_RUN_WINDOW', 3600)},
}

# =============================================================================
# Email Verification
# =============================================================================
SITE_NAME = os.getenv('SITE_NAME', 'TabGraphSyn')
EMAIL_BACKEND = os.getenv(
    'EMAIL_BACKEND',
    'django.core.mail.backends.console.EmailBackend' if DEBUG else 'django.core.mail.backends.smtp.EmailBackend',
)
EMAIL_HOST = os.getenv('EMAIL_HOST', '')
EMAIL_PORT = _env_int('EMAIL_PORT', 587)
EMAIL_USE_TLS = _env_bool('EMAIL_USE_TLS', True)
EMAIL_HOST_USER = os.getenv('EMAIL_HOST_USER', '')
EMAIL_HOST_PASSWORD = os.getenv('EMAIL_HOST_PASSWORD', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', f'{SITE_NAME} <no-reply@localhost>')

EMAIL_VERIFICATION_ENABLED = _env_bool('EMAIL_VERIFICATION_ENABLED', default=True)
EMAIL_VERIFICATION_REQUIRED = _env_bool('EMAIL_VERIFICATION_REQUIRED', default=EMAIL_VERIFICATION_ENABLED)
EMAIL_VERIFICATION_TOKEN_TTL_HOURS = _env_int('EMAIL_VERIFICATION_TOKEN_TTL_HOURS', 24)

# =============================================================================
# Google OAuth
# =============================================================================
GOOGLE_OAUTH_ENABLED = _env_bool('GOOGLE_OAUTH_ENABLED', default=False)
GOOGLE_OAUTH_CLIENT_ID = os.getenv('GOOGLE_OAUTH_CLIENT_ID', '')
GOOGLE_OAUTH_CLIENT_SECRET = os.getenv('GOOGLE_OAUTH_CLIENT_SECRET', '')
GOOGLE_OAUTH_REDIRECT_URI = os.getenv('GOOGLE_OAUTH_REDIRECT_URI', '')
GOOGLE_OAUTH_ALLOWED_DOMAINS = [
    domain.strip().lower()
    for domain in os.getenv('GOOGLE_OAUTH_ALLOWED_DOMAINS', '').split(',')
    if domain.strip()
]
GOOGLE_OAUTH_STATE_TTL_SECONDS = _env_int('GOOGLE_OAUTH_STATE_TTL_SECONDS', 600)

# =============================================================================
# Homepage Configuration
# =============================================================================
# YouTube video URL for homepage tutorial
# Format: https://www.youtube.com/embed/VIDEO_ID
# Example: https://www.youtube.com/embed/dQw4w9WgXcQ
# Leave empty to show placeholder
YOUTUBE_VIDEO_URL = os.getenv('YOUTUBE_VIDEO_URL', '')
