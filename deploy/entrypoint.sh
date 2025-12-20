#!/bin/bash
set -e

echo "Starting TabGraphSyn deployment..."

# Wait for MongoDB if needed
if [ -n "$TABGRAPHSYN_MONGO_URI" ]; then
    echo "Waiting for MongoDB..."
    sleep 5
fi

# Run database migrations
echo "Running database migrations..."
cd /app
python manage.py migrate --noinput || echo "Migrations failed or not needed"

# Create superuser if needed (from environment variables)
if [ -n "$DJANGO_SUPERUSER_USERNAME" ] && [ -n "$DJANGO_SUPERUSER_EMAIL" ] && [ -n "$DJANGO_SUPERUSER_PASSWORD" ]; then
    echo "Creating superuser..."
    python manage.py shell -c "
from django.contrib.auth import get_user_model;
User = get_user_model();
if not User.objects.filter(username='$DJANGO_SUPERUSER_USERNAME').exists():
    User.objects.create_superuser('$DJANGO_SUPERUSER_USERNAME', '$DJANGO_SUPERUSER_EMAIL', '$DJANGO_SUPERUSER_PASSWORD');
    print('Superuser created');
else:
    print('Superuser already exists');
" || echo "Superuser creation skipped"
fi

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput || echo "Static files collection failed"

# Start supervisor (manages nginx and gunicorn)
echo "Starting services..."
exec /usr/bin/supervisord -c /etc/supervisor/conf.d/supervisord.conf
