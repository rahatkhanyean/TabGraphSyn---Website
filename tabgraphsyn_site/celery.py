"""
Celery Configuration for TabGraphSyn

This module configures Celery for handling background tasks in the TabGraphSyn application.
Celery is used to run ML pipeline jobs asynchronously, replacing the threading approach.

Usage:
    Start Celery worker:
        celery -A tabgraphsyn_site worker --loglevel=info --pool=solo

    On Windows, use --pool=solo to avoid issues with the default multiprocessing pool:
        celery -A tabgraphsyn_site worker --loglevel=info --pool=solo

    On Linux/Mac, you can use the default pool:
        celery -A tabgraphsyn_site worker --loglevel=info
"""
from __future__ import absolute_import, unicode_literals
import os
from celery import Celery

# Set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tabgraphsyn_site.settings')

# Create the Celery app
app = Celery('tabgraphsyn')

# Load configuration from Django settings
# - namespace='CELERY' means all celery-related settings must be prefixed with 'CELERY_'
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed Django apps
# This will look for tasks.py in each app directory
app.autodiscover_tasks()

# Configure Celery to use django-celery-results for storing task results
app.conf.update(
    # Use Django ORM as the result backend (stores results in database)
    result_backend='django-db',

    # Task serialization format (JSON is safer than pickle)
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',

    # Timezone settings
    timezone='UTC',
    enable_utc=True,

    # Task result settings
    result_expires=86400,  # Results expire after 24 hours (86400 seconds)

    # Worker settings
    worker_prefetch_multiplier=1,  # Worker takes 1 task at a time (good for long-running tasks)
    worker_max_tasks_per_child=1,  # Worker process restarts after each task (prevents memory leaks)

    # Task execution settings
    task_acks_late=True,  # Task is acknowledged after completion (not before execution)
    task_reject_on_worker_lost=True,  # Re-queue task if worker dies

    # Tracking settings
    task_track_started=True,  # Track when tasks start (enables progress monitoring)
)


@app.task(bind=True)
def debug_task(self):
    """Debug task to test Celery configuration"""
    print(f'Request: {self.request!r}')
