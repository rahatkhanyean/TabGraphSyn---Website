import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-tabgraphsyn'

DEBUG = True

ALLOWED_HOSTS: list[str] = ['unopinionated-harris-agrobiological.ngrok-free.dev','127.0.0.1']

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
CSRF_TRUSTED_ORIGINS = [
    'https://unopinionated-harris-agrobiological.ngrok-free.dev',
    'http://127.0.0.1' # To allow all subdomains
]
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
