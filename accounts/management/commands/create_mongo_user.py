from __future__ import annotations

from django.contrib.auth.hashers import make_password
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone
from pymongo.errors import PyMongoError

from accounts.mongo import get_users_collection


class Command(BaseCommand):
    help = 'Create or update a MongoDB-backed TabGraphSyn workspace user.'

    def add_arguments(self, parser) -> None:
        parser.add_argument('username', help='Unique username used to sign in from the web UI.')
        parser.add_argument('password', help='Plaintext password that will be hashed before storage.')
        parser.add_argument('--email', default='', help='Optional contact email for the user.')
        parser.add_argument('--full-name', dest='full_name', default='', help='Display name shown in the UI.')
        parser.add_argument(
            '--roles',
            default='workspace-user',
            help='Comma separated list of roles to persist alongside the user document.',
        )

    def handle(self, *args, **options) -> None:
        username: str = options['username'].strip()
        password: str = options['password']
        if not username:
            raise CommandError('Username cannot be empty.')
        if not password:
            raise CommandError('Password cannot be empty.')

        roles = [role.strip() for role in options['roles'].split(',') if role.strip()]
        now = timezone.now().isoformat()
        email = (options.get('email') or '').strip()
        email_lower = email.lower() if email else None
        payload = {
            'username': username,
            'password': make_password(password),
            'email': email or None,
            'email_lower': email_lower,
            'email_verified': bool(email_lower),
            'auth_provider': 'password',
            'full_name': options.get('full_name') or username,
            'roles': roles,
            'updated_at': now,
        }
        update_doc = {
            '$set': payload,
            '$setOnInsert': {'created_at': now},
        }
        try:
            collection = get_users_collection()
            result = collection.update_one({'username': username}, update_doc, upsert=True)
        except PyMongoError as exc:
            raise CommandError(f'Unable to write user to MongoDB: {exc}') from exc

        action = 'Updated' if result.matched_count else 'Created'
        self.stdout.write(self.style.SUCCESS(f"{action} MongoDB user '{username}'."))
