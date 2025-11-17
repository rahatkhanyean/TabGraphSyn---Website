# TabGraphSyn - Docker Setup

This guide will help you run the TabGraphSyn Django application using Docker Desktop.

## Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop) installed and running
- At least 8GB of RAM available for Docker
- At least 10GB of free disk space

## Quick Start

### 1. Build and Start the Containers

Open a terminal in the project directory and run:

```bash
docker-compose up --build
```

This will:
- Build the Django application Docker image
- Start MongoDB container
- Start the Django web application container
- Create necessary volumes for data persistence

### 2. Access the Application

Once the containers are running, open your browser and navigate to:

```
http://localhost:8000
```

### 3. Stop the Containers

To stop the application:

```bash
docker-compose down
```

To stop and remove all volumes (⚠️ this will delete all data):

```bash
docker-compose down -v
```

## Docker Commands Reference

### Build and Run
```bash
# Build and start in detached mode (background)
docker-compose up -d --build

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f web
```

### Database Management
```bash
# Run Django migrations
docker-compose exec web python manage.py migrate

# Create a superuser
docker-compose exec web python manage.py createsuperuser

# Collect static files
docker-compose exec web python manage.py collectstatic --noinput
```

### Container Management
```bash
# List running containers
docker-compose ps

# Stop containers
docker-compose stop

# Start stopped containers
docker-compose start

# Restart containers
docker-compose restart

# Remove containers
docker-compose down
```

### Development
```bash
# Access Django shell
docker-compose exec web python manage.py shell

# Access container bash
docker-compose exec web bash

# Access MongoDB shell
docker-compose exec mongodb mongosh tabgraphsyn
```

## Services

### Web Application (Django)
- **Port**: 8000
- **Container Name**: tabgraphsyn_web
- **Volumes**:
  - Application code mounted at `/app`
  - Static files at `/app/staticfiles`
  - Media files at `/app/media`

### MongoDB
- **Port**: 27017
- **Container Name**: tabgraphsyn_mongodb
- **Database**: tabgraphsyn
- **Volume**: `mongodb_data` (persistent)

## Environment Variables

You can customize the MongoDB connection by setting environment variables in `docker-compose.yml`:

- `TABGRAPHSYN_MONGO_URI`: MongoDB connection URI (default: mongodb://mongodb:27017)
- `TABGRAPHSYN_MONGO_DB`: Database name (default: tabgraphsyn)
- `TABGRAPHSYN_MONGO_USERS_COLLECTION`: Users collection name (default: users)
- `TABGRAPHSYN_MONGO_RUNS_COLLECTION`: Runs collection name (default: runs)

## Troubleshooting

### Port Already in Use
If port 8000 or 27017 is already in use, you can change the ports in `docker-compose.yml`:

```yaml
ports:
  - "8001:8000"  # Change host port from 8000 to 8001
```

### Application Not Starting
Check the logs:
```bash
docker-compose logs web
```

### MongoDB Connection Issues
Ensure MongoDB is running:
```bash
docker-compose ps mongodb
```

### Rebuild After Changes
If you make changes to requirements.txt or Dockerfile:
```bash
docker-compose down
docker-compose up --build
```

### Clear Everything and Start Fresh
```bash
docker-compose down -v
docker system prune -a
docker-compose up --build
```

## Production Deployment

For production deployment, consider:

1. Using a production WSGI server (already configured with Gunicorn)
2. Setting `DEBUG = False` in settings.py
3. Using environment variables for sensitive data
4. Setting up proper `ALLOWED_HOSTS`
5. Using a reverse proxy like Nginx
6. Implementing SSL/TLS certificates

## Data Persistence

The following volumes are created for data persistence:
- `mongodb_data`: MongoDB database files
- `static_volume`: Django static files
- `media_volume`: User uploaded files

These volumes persist even when containers are stopped or removed (unless you use `docker-compose down -v`).
