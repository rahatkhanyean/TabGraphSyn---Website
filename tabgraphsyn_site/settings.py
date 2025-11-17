import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-tabgraphsyn'

DEBUG = True

ALLOWED_HOSTS: list[str] = []

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

# ==============================================================================
# CELERY CONFIGURATION
# ==============================================================================

# Celery Broker (Redis)
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/1')

# Task serialization
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True

# Task execution settings
CELERY_TASK_ACKS_LATE = True  # Acknowledge tasks after execution (not before)
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Fetch one task at a time (important for long-running tasks)
CELERY_TASK_REJECT_ON_WORKER_LOST = True  # Re-queue tasks if worker crashes
CELERY_TASK_TIME_LIMIT = 3600  # Hard limit: 1 hour per task
CELERY_TASK_SOFT_TIME_LIMIT = 3300  # Soft limit: 55 minutes (allows graceful shutdown)

# Task routing - separate queues for CPU and GPU workers
CELERY_TASK_ROUTES = {
    'synthetic.tasks.run_pipeline_cpu': {
        'queue': 'cpu',
        'routing_key': 'cpu',
    },
    'synthetic.tasks.run_pipeline_gpu': {
        'queue': 'gpu',
        'routing_key': 'gpu',
    },
}

# Default queue
CELERY_TASK_DEFAULT_QUEUE = 'cpu'
CELERY_TASK_DEFAULT_EXCHANGE = 'tasks'
CELERY_TASK_DEFAULT_ROUTING_KEY = 'cpu'

# Result backend settings
CELERY_RESULT_EXPIRES = 3600  # Results expire after 1 hour
CELERY_RESULT_PERSISTENT = False  # Don't persist results (we store in MongoDB)

# Celery Beat (Scheduler) - for periodic tasks
CELERY_BEAT_SCHEDULE = {
    'cleanup-expired-jobs': {
        'task': 'synthetic.tasks.cleanup_expired_jobs',
        'schedule': 3600.0,  # Run every hour
    },
    'reset-monthly-quotas': {
        'task': 'accounts.tasks.reset_monthly_quotas',
        'schedule': 86400.0,  # Run daily (checks for month rollover)
    },
}

# Worker settings
CELERY_WORKER_MAX_TASKS_PER_CHILD = 10  # Restart worker after 10 tasks (prevent memory leaks)
CELERY_WORKER_DISABLE_RATE_LIMITS = False

# Monitoring
CELERY_WORKER_SEND_TASK_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True

# ==============================================================================
# REDIS CONFIGURATION (Cache + Sessions)
# ==============================================================================

REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/0')

# Cache backend
CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.redis.RedisCache',
        'LOCATION': REDIS_URL,
        'OPTIONS': {
            'db': 2,  # Use separate Redis DB for cache
            'parser_class': 'redis.connection.HiredisParser',
            'pool_class': 'redis.BlockingConnectionPool',
            'pool_class_kwargs': {
                'max_connections': 50,
                'timeout': 20,
            }
        },
        'KEY_PREFIX': 'tabgraphsyn',
        'TIMEOUT': 300,  # 5 minutes default
    }
}

# Session backend (use Redis for sessions in production)
# SESSION_ENGINE = 'django.contrib.sessions.backends.cache'
# SESSION_CACHE_ALIAS = 'default'

# ==============================================================================
# ENHANCED MONGODB CONFIGURATION
# ==============================================================================

# Extend MongoDB collections for new features
MONGO_CONNECTION['JOBS_COLLECTION'] = os.getenv('TABGRAPHSYN_MONGO_JOBS_COLLECTION', 'jobs')
MONGO_CONNECTION['SUBSCRIPTIONS_COLLECTION'] = os.getenv('TABGRAPHSYN_MONGO_SUBSCRIPTIONS_COLLECTION', 'subscriptions')
MONGO_CONNECTION['NOTIFICATIONS_COLLECTION'] = os.getenv('TABGRAPHSYN_MONGO_NOTIFICATIONS_COLLECTION', 'notifications')
MONGO_CONNECTION['DATASETS_COLLECTION'] = os.getenv('TABGRAPHSYN_MONGO_DATASETS_COLLECTION', 'datasets')

# ==============================================================================
# EMAIL CONFIGURATION (SendGrid)
# ==============================================================================

EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST = 'smtp.sendgrid.net'
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = 'apikey'  # SendGrid username is always 'apikey'
EMAIL_HOST_PASSWORD = os.getenv('SENDGRID_API_KEY', '')
DEFAULT_FROM_EMAIL = os.getenv('DEFAULT_FROM_EMAIL', 'noreply@tabgraphsyn.com')
SERVER_EMAIL = DEFAULT_FROM_EMAIL

# Email notification settings
NOTIFICATION_EMAIL_ENABLED = os.getenv('NOTIFICATION_EMAIL_ENABLED', 'True').lower() == 'true'

# ==============================================================================
# STRIPE PAYMENT CONFIGURATION
# ==============================================================================

STRIPE_PUBLISHABLE_KEY = os.getenv('STRIPE_PUBLISHABLE_KEY', '')
STRIPE_SECRET_KEY = os.getenv('STRIPE_SECRET_KEY', '')
STRIPE_WEBHOOK_SECRET = os.getenv('STRIPE_WEBHOOK_SECRET', '')

# Stripe product/price IDs
STRIPE_PRICE_ID_MONTHLY = os.getenv('STRIPE_PRICE_ID_MONTHLY', '')
STRIPE_PRICE_ID_ANNUAL = os.getenv('STRIPE_PRICE_ID_ANNUAL', '')

# ==============================================================================
# TIER CONFIGURATION
# ==============================================================================

TIER_QUOTAS = {
    'free': {
        'jobs_per_month': 10,
        'max_rows_per_job': 10000,
        'max_file_size_mb': 50,
        'max_epochs_total': 50,  # VAE + GNN + Diffusion combined
        'gpu_access': False,
        'chatbot_access': False,
        'priority': 0,
    },
    'paid': {
        'jobs_per_month': 1000,
        'max_rows_per_job': 100000,
        'max_file_size_mb': 500,
        'max_epochs_total': 500,
        'gpu_access': True,
        'chatbot_access': True,
        'priority': 5,
    }
}

# ==============================================================================
# OPENAI CONFIGURATION (for chatbot)
# ==============================================================================

OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
OPENAI_MODEL = os.getenv('OPENAI_MODEL', 'gpt-4')

# ==============================================================================
# SECURITY SETTINGS (Production - update when deploying)
# ==============================================================================

# TODO: Update these settings for production:
# DEBUG = False
# SECRET_KEY = os.getenv('SECRET_KEY')  # Use strong random key
# ALLOWED_HOSTS = ['tabgraphsyn.com', 'www.tabgraphsyn.com']
# SECURE_SSL_REDIRECT = True
# SESSION_COOKIE_SECURE = True
# CSRF_COOKIE_SECURE = True
# SECURE_HSTS_SECONDS = 31536000
# SECURE_HSTS_INCLUDE_SUBDOMAINS = True
# SECURE_HSTS_PRELOAD = True

# ==============================================================================
# LOGGING CONFIGURATION
# ==============================================================================

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '[{levelname}] {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
        'file': {
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'django.log',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'INFO',
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'celery': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'synthetic': {
            'handlers': ['console', 'file'],
            'level': 'DEBUG' if DEBUG else 'INFO',
            'propagate': False,
        },
    },
}
