import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent

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
DEBUG = os.getenv('DEBUG', 'False').lower() in ('true', '1', 't', 'yes')

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

# CSRF Trusted Origins - Build from ALLOWED_HOSTS
# Add https:// prefix for production hosts, http:// for localhost
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

# Security Headers (always enabled)
SECURE_BROWSER_XSS_FILTER = True  # Enable browser's XSS filtering
SECURE_CONTENT_TYPE_NOSNIFF = True  # Prevent MIME-type sniffing
X_FRAME_OPTIONS = 'DENY'  # Prevent clickjacking by disabling iframes

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
