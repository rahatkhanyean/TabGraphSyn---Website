"""
Celery Configuration for TabGraphSyn

This module initializes the Celery app for async job processing.
Workers process synthetic data generation jobs without blocking web requests.
"""

import os
from celery import Celery
from django.conf import settings

# Set default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'tabgraphsyn_site.settings')

# Create Celery app
app = Celery('tabgraphsyn_site')

# Load configuration from Django settings with CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task for testing Celery setup"""
    print(f'Request: {self.request!r}')
