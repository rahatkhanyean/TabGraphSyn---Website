"""
TabGraphSyn Django Project Initialization

This module ensures that Celery is loaded when Django starts.
"""
from __future__ import absolute_import, unicode_literals

# Import the Celery app so it's available throughout the Django project
from .celery import app as celery_app

__all__ = ('celery_app',)
