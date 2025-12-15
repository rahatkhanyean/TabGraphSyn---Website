# TabGraphSyn Celery Usage Guide

This document explains how to use the Celery-based task queue system in TabGraphSyn for production-ready background job processing.

## What Changed: Threading → Celery

### Before (P0):
- Pipeline jobs ran in daemon threads
- Job state stored in memory (lost on restart)
- No task recovery on crash
- Limited to single server

### After (P1):
- Pipeline jobs run as Celery tasks
- Job state persisted in database
- Tasks survive server restarts
- Can scale to multiple workers
- Production-ready architecture

---

## Architecture Overview

```
User Request → Django View → Celery Task Queue (Redis) → Celery Worker → ML Pipeline
                                                               ↓
                                                         Task Results (Database)
```

### Components:
1. **Django** - Web interface (already running)
2. **Redis** - Message broker (queues tasks)
3. **Celery Worker** - Background processor (runs ML pipeline)
4. **Database** - Stores task results (`django-celery-results`)

---

## Installation & Setup

### 1. Install Redis

**Windows:**
```bash
# Using Windows Subsystem for Linux (WSL)
wsl --install  # If not already installed
wsl -d Ubuntu
sudo apt update
sudo apt install redis-server
sudo service redis-server start

# Verify Redis is running
redis-cli ping
# Should return: PONG
```

**Alternative - Use Redis Docker:**
```bash
docker run -d -p 6379:6379 redis:latest
```

**Linux/Mac:**
```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis-server

# macOS
brew install redis
brew services start redis
```

### 2. Verify Installation

All Python packages are already installed from `requirements-web.txt`:
- ✅ celery>=5.3.0
- ✅ redis>=5.0.0
- ✅ django-celery-results>=2.5.0

Test connection:
```bash
python -c "import redis; r = redis.Redis(host='localhost', port=6379, db=0); print(r.ping())"
# Should print: True
```

---

## Running the Application

You need **3 separate terminals** (or use a process manager like `supervisor` in production):

### Terminal 1: Django Development Server
```bash
python manage.py runserver
```

### Terminal 2: Celery Worker
```bash
# Windows (use --pool=solo to avoid multiprocessing issues)
celery -A tabgraphsyn_site worker --loglevel=info --pool=solo

# Linux/Mac (can use default pool)
celery -A tabgraphsyn_site worker --loglevel=info
```

### Terminal 3: Redis Server
```bash
# If using WSL
wsl -d Ubuntu
sudo service redis-server start

# If using Docker
docker run -d -p 6379:6379 redis:latest

# If installed locally (Linux/Mac)
redis-server
```

---

## Understanding Celery Worker Output

When you start the Celery worker, you'll see:

```
 -------------- celery@YOUR-COMPUTER v5.6.0 (dawn-chorus)
--- ***** -----
-- ******* ---- Windows-10.0.19045-SP0 2025-01-15 10:30:00
- *** --- * ---
- ** ---------- [config]
- ** ---------- .> app:         tabgraphsyn:0x...
- ** ---------- .> transport:   redis://localhost:6379/0
- ** ---------- .> results:     django-db
- *** --- * --- .> concurrency: 8 (solo)
-- ******* ---- .> task events: OFF
--- ***** -----

[tasks]
  . synthetic.run_pipeline

[2025-01-15 10:30:00,000: INFO/MainProcess] Connected to redis://localhost:6379/0
[2025-01-15 10:30:00,000: INFO/MainProcess] mingle: searching for neighbors
[2025-01-15 10:30:01,000: INFO/MainProcess] mingle: all alone
[2025-01-15 10:30:01,000: INFO/MainProcess] celery@YOUR-COMPUTER ready.
```

**Key things to look for:**
- ✅ `transport: redis://localhost:6379/0` - Redis connection OK
- ✅ `results: django-db` - Results stored in database
- ✅ `synthetic.run_pipeline` - Your task is registered
- ✅ `celery@YOUR-COMPUTER ready` - Worker is ready to accept tasks

---

## How to Use

### 1. Normal Usage (Frontend)
Everything works exactly as before! No changes needed:
1. Visit `http://127.0.0.1:8000/`
2. Upload CSV or select preloaded dataset
3. Click "Generate Synthetic Data"
4. Monitor progress in real-time
5. Download results when complete

### 2. Monitoring Tasks

**View active tasks:**
```bash
celery -A tabgraphsyn_site inspect active
```

**View registered tasks:**
```bash
celery -A tabgraphsyn_site inspect registered
```

**View worker stats:**
```bash
celery -A tabgraphsyn_site inspect stats
```

**Purge all pending tasks:**
```bash
celery -A tabgraphsyn_site purge
```

### 3. Task Persistence

Tasks are now persistent! Benefits:
- ✅ Restart Django - tasks continue running
- ✅ Restart worker - tasks resume after restart
- ✅ Server crash - tasks can be recovered

View task history in Django admin:
1. Visit `http://127.0.0.1:8000/admin/`
2. Go to "Django Celery Results" → "Task results"

---

## GPU Considerations

**IMPORTANT:** The Celery worker needs GPU access to run the ML pipeline.

### Windows Development:
The worker runs in the same Python environment, so GPU access works automatically.

### Linux Production:
Make sure the Celery worker runs with proper CUDA environment variables:
```bash
export CUDA_VISIBLE_DEVICES=0
celery -A tabgraphsyn_site worker --loglevel=info
```

### Docker Deployment:
Use `--gpus all` flag:
```yaml
# docker-compose.yml
services:
  celery-worker:
    image: tabgraphsyn:latest
    command: celery -A tabgraphsyn_site worker --loglevel=info
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
```

---

## Configuration

All Celery settings are in [.env](.env):

```bash
# Redis connection
CELERY_BROKER_URL=redis://localhost:6379/0

# Task timeouts (ML pipeline can take hours)
CELERY_TASK_TIME_LIMIT=7200          # 2 hours hard limit
CELERY_TASK_SOFT_TIME_LIMIT=7000     # Soft limit (warning)
```

### Adjusting Timeouts

If your models take longer than 2 hours, increase the limits:
```bash
# .env
CELERY_TASK_TIME_LIMIT=14400         # 4 hours
CELERY_TASK_SOFT_TIME_LIMIT=14000
```

---

## Troubleshooting

### 1. "Connection refused" when starting worker

**Problem:** Redis not running

**Solution:**
```bash
# Check Redis
redis-cli ping

# Start Redis (WSL)
wsl -d Ubuntu
sudo service redis-server start

# Or Docker
docker run -d -p 6379:6379 redis:latest
```

### 2. Tasks stay in "PENDING" state

**Problem:** Worker not running or not connected

**Solution:**
1. Check worker is running in separate terminal
2. Check Redis connection: `redis-cli ping`
3. Restart worker: `Ctrl+C` then restart

### 3. "ModuleNotFoundError: No module named 'celery'"

**Problem:** Packages not installed

**Solution:**
```bash
pip install -r requirements-web.txt
```

### 4. Worker crashes during task execution

**Problem:** Task timeout or memory issue

**Solution:**
1. Increase timeout in `.env`
2. Check worker logs for actual error
3. Restart worker with `--loglevel=debug` for more info:
   ```bash
   celery -A tabgraphsyn_site worker --loglevel=debug --pool=solo
   ```

### 5. Task appears complete but result not found

**Problem:** Database migration issue

**Solution:**
```bash
python manage.py migrate django_celery_results
```

---

## Production Deployment

### Option 1: Supervisor (Linux)

Install supervisor:
```bash
sudo apt install supervisor
```

Create config `/etc/supervisor/conf.d/tabgraphsyn.conf`:
```ini
[program:tabgraphsyn_celery]
command=/path/to/venv/bin/celery -A tabgraphsyn_site worker --loglevel=info
directory=/path/to/TabGraphSyn - Django
user=yourusername
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/tabgraphsyn/celery.log
environment=CUDA_VISIBLE_DEVICES="0"
```

Start:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start tabgraphsyn_celery
```

### Option 2: Systemd Service (Linux)

Create `/etc/systemd/system/tabgraphsyn-celery.service`:
```ini
[Unit]
Description=TabGraphSyn Celery Worker
After=network.target redis.service

[Service]
Type=forking
User=yourusername
Group=yourusername
WorkingDirectory=/path/to/TabGraphSyn - Django
Environment="CUDA_VISIBLE_DEVICES=0"
ExecStart=/path/to/venv/bin/celery -A tabgraphsyn_site worker \
          --loglevel=info \
          --pidfile=/var/run/celery/tabgraphsyn.pid \
          --logfile=/var/log/celery/tabgraphsyn.log
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable tabgraphsyn-celery
sudo systemctl start tabgraphsyn-celery
sudo systemctl status tabgraphsyn-celery
```

### Option 3: Docker Compose

See `docker-compose.yml` (to be created in P2).

---

## Scaling

### Multiple Workers
Run multiple workers for parallel processing:

```bash
# Terminal 1
celery -A tabgraphsyn_site worker --loglevel=info --pool=solo -n worker1@%h

# Terminal 2
celery -A tabgraphsyn_site worker --loglevel=info --pool=solo -n worker2@%h
```

**Note:** Each worker needs GPU access. With your GTX 1650 (4GB VRAM), only one ML pipeline task can run at a time. Multiple workers can handle web requests in parallel.

---

## Monitoring Tools

### Flower (Celery Monitoring)

Install:
```bash
pip install flower
```

Run:
```bash
celery -A tabgraphsyn_site flower
```

Visit: `http://localhost:5555`

Shows:
- Active tasks
- Task history
- Worker status
- Real-time graphs
- Task details

---

## API Compatibility

The API remains 100% compatible with the previous version:

**Start job:**
```bash
POST /api/start-run/
Response: {"jobToken": "celery-task-id", "stage": "starting", ...}
```

**Check status:**
```bash
GET /api/run-status/<celery-task-id>/
Response: {"stage": "training", "progress": 50, "logs": [...], ...}
```

**Frontend changes:** ✅ **NONE!** JavaScript polling works exactly as before.

---

## Summary of Files Created/Modified

### Created:
- ✅ `tabgraphsyn_site/celery.py` - Celery configuration
- ✅ `synthetic/tasks.py` - Pipeline Celery task
- ✅ `CELERY_USAGE.md` - This documentation

### Modified:
- ✅ `requirements-web.txt` - Added Celery dependencies
- ✅ `.env` & `.env.example` - Added Redis/Celery config
- ✅ `tabgraphsyn_site/__init__.py` - Load Celery app
- ✅ `tabgraphsyn_site/settings.py` - Celery settings, added django_celery_results
- ✅ `synthetic/views.py` - Replaced threading with Celery

### Removed/Deprecated:
- ⚠️ `synthetic/job_tracker.py` - No longer used (kept for compatibility)
- ⚠️ `threading.Thread` calls - Replaced with Celery tasks

---

## Next Steps (P2 - Production Server Setup)

After testing Celery thoroughly, you can proceed with:
1. Gunicorn configuration
2. Nginx reverse proxy
3. Docker containerization
4. Logging improvements
5. Monitoring setup

---

## Questions?

If you encounter issues:
1. Check Redis is running: `redis-cli ping`
2. Check worker is running and shows "ready"
3. Check Django logs: `python manage.py runserver`
4. Check worker logs in terminal
5. Check task status: `celery -A tabgraphsyn_site inspect active`
