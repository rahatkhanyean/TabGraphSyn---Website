"""
Management command to create MongoDB indexes for all collections

Usage:
    python manage.py create_indexes
"""

from django.core.management.base import BaseCommand
from pymongo import ASCENDING, DESCENDING
from accounts.mongo import (
    get_users_collection,
    get_runs_collection,
    get_jobs_collection,
    get_subscriptions_collection,
    get_notifications_collection,
    get_datasets_collection,
)


class Command(BaseCommand):
    help = 'Create MongoDB indexes for all collections'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Creating MongoDB indexes...'))

        # Users collection indexes
        self.stdout.write('Creating indexes for users collection...')
        users = get_users_collection()
        users.create_index('username', unique=True, name='idx_username_unique')
        users.create_index('email', unique=True, name='idx_email_unique')
        users.create_index([('tier', ASCENDING), ('subscription_status', ASCENDING)], name='idx_tier_status')
        users.create_index('customer_id', name='idx_customer_id')
        self.stdout.write(self.style.SUCCESS('  ✓ Users indexes created'))

        # Runs collection indexes
        self.stdout.write('Creating indexes for runs collection...')
        runs = get_runs_collection()
        runs.create_index('token', unique=True, name='idx_token_unique')
        runs.create_index([('owner_username', ASCENDING), ('started_at', DESCENDING)], name='idx_owner_started')
        runs.create_index('job_id', name='idx_job_id')
        self.stdout.write(self.style.SUCCESS('  ✓ Runs indexes created'))

        # Jobs collection indexes
        self.stdout.write('Creating indexes for jobs collection...')
        jobs = get_jobs_collection()
        jobs.create_index('job_id', unique=True, name='idx_job_id_unique')
        jobs.create_index('token', unique=True, name='idx_token_unique')
        jobs.create_index([('owner_username', ASCENDING), ('created_at', DESCENDING)], name='idx_owner_created')
        jobs.create_index([('status', ASCENDING), ('priority', DESCENDING), ('queued_at', ASCENDING)], name='idx_queue_processing')
        jobs.create_index([('tier', ASCENDING), ('status', ASCENDING)], name='idx_tier_status')
        self.stdout.write(self.style.SUCCESS('  ✓ Jobs indexes created'))

        # Subscriptions collection indexes
        self.stdout.write('Creating indexes for subscriptions collection...')
        subscriptions = get_subscriptions_collection()
        subscriptions.create_index('user_id', name='idx_user_id')
        subscriptions.create_index('stripe_subscription_id', unique=True, name='idx_stripe_sub_id_unique')
        subscriptions.create_index([('status', ASCENDING), ('current_period_end', ASCENDING)], name='idx_status_period_end')
        subscriptions.create_index('username', name='idx_username')
        self.stdout.write(self.style.SUCCESS('  ✓ Subscriptions indexes created'))

        # Notifications collection indexes
        self.stdout.write('Creating indexes for notifications collection...')
        notifications = get_notifications_collection()
        notifications.create_index([('username', ASCENDING), ('created_at', DESCENDING)], name='idx_username_created')
        notifications.create_index([('username', ASCENDING), ('read', ASCENDING)], name='idx_username_read')
        notifications.create_index('job_token', name='idx_job_token')
        self.stdout.write(self.style.SUCCESS('  ✓ Notifications indexes created'))

        # Datasets collection indexes (for chatbot)
        self.stdout.write('Creating indexes for datasets collection...')
        datasets = get_datasets_collection()
        datasets.create_index('name', name='idx_name')
        datasets.create_index('category', name='idx_category')
        datasets.create_index('keywords', name='idx_keywords')
        # Note: For vector search, use MongoDB Atlas Vector Search indexes (created via Atlas UI)
        self.stdout.write(self.style.SUCCESS('  ✓ Datasets indexes created'))

        self.stdout.write(self.style.SUCCESS('\n✅ All MongoDB indexes created successfully!'))
        self.stdout.write(self.style.WARNING('\nNote: For vector search on datasets.embedding, create a Vector Search index in MongoDB Atlas.'))
