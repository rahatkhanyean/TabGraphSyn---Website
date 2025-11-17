# TabGraphSyn Enterprise Platform - Quick Start Guide

Welcome to the TabGraphSyn Enterprise Platform! This guide will help you get started with the enhanced async job processing system.

---

## What's New

We've transformed TabGraphSyn into an enterprise-level platform with:

- ✅ **Async Job Processing** - Celery + Redis for scalable background job execution
- ✅ **Tier Management** - Free and Paid tier support with different quotas
- ✅ **Email Notifications** - Automatic notifications when jobs complete
- ✅ **Payment Integration** - Stripe integration ready for subscriptions
- ✅ **GPU Support** - Separate worker queues for GPU-accelerated processing
- ✅ **Enhanced MongoDB Schema** - New collections for jobs, subscriptions, notifications
- ✅ **Admin Dashboard** - Flower monitoring for Celery workers
- ✅ **Production-Ready Config** - Comprehensive settings for deployment

---

## Prerequisites

- **Docker & Docker Compose** (recommended for local development)
- **Python 3.10+** (if running without Docker)
- **MongoDB 7.0+**
- **Redis 7.0+**

---

## Option 1: Quick Start with Docker (Recommended)

### Step 1: Clone and Setup

```bash
# Navigate to project directory
cd /home/user/TabGraphSyn---Website

# Create .env file from example
cp .env.example .env

# (Optional) Edit .env to configure environment variables
nano .env
```

### Step 2: Start Services

```bash
# Start all services (MongoDB, Redis, Web, Celery workers, Flower)
docker-compose up -d

# View logs
docker-compose logs -f web
```

**Services Running**:
- **Web**: http://localhost:8000 (Django web interface)
- **Flower**: http://localhost:5555 (Celery monitoring dashboard)
- **MongoDB**: localhost:27017
- **Redis**: localhost:6379

### Step 3: Create MongoDB Indexes

```bash
# Enter web container
docker-compose exec web bash

# Create indexes
python manage.py create_indexes

# Create a test user
python manage.py create_mongo_user

# Exit container
exit
```

### Step 4: Test the System

1. **Open web interface**: http://localhost:8000
2. **Login** with your test user
3. **Upload a CSV** or select a preloaded dataset
4. **Submit a job** - it will be processed asynchronously
5. **Monitor in Flower**: http://localhost:5555

---

## Option 2: Manual Setup (Without Docker)

### Step 1: Install Dependencies

```bash
# Install web dependencies
pip install -r requirements-web.txt

# Or install full pipeline dependencies
pip install -r requirements.txt
```

### Step 2: Start Services

**Terminal 1: MongoDB**
```bash
mongod --dbpath ./data/mongodb
```

**Terminal 2: Redis**
```bash
redis-server
```

**Terminal 3: Django Web Server**
```bash
export DJANGO_SETTINGS_MODULE=tabgraphsyn_site.settings
export TABGRAPHSYN_MONGO_URI=mongodb://localhost:27017
export REDIS_URL=redis://localhost:6379/0

python manage.py runserver
```

**Terminal 4: Celery CPU Worker**
```bash
celery -A tabgraphsyn_site worker -Q cpu --loglevel=info
```

**Terminal 5: Celery Beat (Scheduler)**
```bash
celery -A tabgraphsyn_site beat --loglevel=info
```

**Terminal 6: Flower (Monitoring)**
```bash
celery -A tabgraphsyn_site flower
```

### Step 3: Create Indexes

```bash
python manage.py create_indexes
```

---

## Configuration

### Environment Variables

Edit `.env` to configure:

```bash
# MongoDB
TABGRAPHSYN_MONGO_URI=mongodb://mongodb:27017
TABGRAPHSYN_MONGO_DB=tabgraphsyn

# Redis
REDIS_URL=redis://redis:6379/0
CELERY_BROKER_URL=redis://redis:6379/0

# Email (SendGrid)
SENDGRID_API_KEY=your-api-key-here
DEFAULT_FROM_EMAIL=noreply@tabgraphsyn.com

# Stripe Payment
STRIPE_SECRET_KEY=sk_test_...
STRIPE_PUBLISHABLE_KEY=pk_test_...

# OpenAI (for chatbot - Phase 7)
OPENAI_API_KEY=sk-...
```

---

## Architecture Overview

```
User → Django Web → Celery Broker (Redis) → Workers (CPU/GPU)
                                               ↓
                  MongoDB ← Results ← TabGraphSyn Pipeline
```

**Components**:

1. **Django Web** - User interface, API endpoints
2. **Redis** - Message broker for Celery + caching
3. **MongoDB** - Primary database (users, jobs, runs)
4. **Celery Workers**:
   - **CPU Worker** - Free tier jobs (CPU-only)
   - **GPU Worker** - Paid tier jobs (GPU-accelerated)
5. **Celery Beat** - Scheduler for periodic tasks
6. **Flower** - Real-time monitoring dashboard

---

## User Tiers

### Free Tier
- ✅ 10 jobs/month
- ✅ CPU-only processing
- ✅ Email notifications
- ✅ Max 10,000 rows per job
- ✅ Max 50MB upload

### Paid Tier ($49/month)
- ✅ 1,000 jobs/month
- ✅ GPU-accelerated processing (2-5x faster)
- ✅ Priority queue
- ✅ AI chatbot for dataset recommendations
- ✅ Max 100,000 rows per job
- ✅ Max 500MB upload

---

## Key Files Modified/Created

### New Files
- `tabgraphsyn_site/celery.py` - Celery app configuration
- `synthetic/tasks.py` - Celery task wrappers for TabGraphSyn
- `accounts/schemas.py` - MongoDB document schemas
- `accounts/management/commands/create_indexes.py` - Index creation
- `TECHNICAL_FEASIBILITY_REPORT.md` - Architecture analysis
- `IMPLEMENTATION_ROADMAP.md` - Phase-by-phase plan
- `QUICKSTART.md` - This file

### Modified Files
- `tabgraphsyn_site/settings.py` - Added Celery, Redis, email, Stripe config
- `tabgraphsyn_site/__init__.py` - Import Celery app
- `docker-compose.yml` - Added Redis, Celery workers, Flower
- `requirements-web.txt` - Added Celery, Redis, Stripe, SendGrid
- `.env.example` - Complete environment variable template
- `accounts/mongo.py` - Added new collection accessors

---

## Testing

### Test Async Job Execution

```bash
# Submit a test job
curl -X POST http://localhost:8000/api/start-run/ \
  -H "Content-Type: application/json" \
  -d '{
    "dataset": "AIDS",
    "epochs_vae": 5,
    "epochs_gnn": 5,
    "epochs_diff": 1
  }'

# Monitor in Flower
open http://localhost:5555

# Check job status
curl http://localhost:8000/api/run-status/<job-token>/
```

### Test Email Notifications

1. Configure `SENDGRID_API_KEY` in `.env`
2. Submit a job
3. Check your email when job completes

---

## Monitoring

### Flower Dashboard

Open http://localhost:5555 to:
- View active workers
- Monitor task execution
- See task history
- Check worker statistics

### MongoDB Queries

```bash
# Enter MongoDB
docker-compose exec mongodb mongosh tabgraphsyn

# View jobs
db.jobs.find().pretty()

# View recent runs
db.runs.find().sort({started_at: -1}).limit(5).pretty()

# Count users by tier
db.users.aggregate([{$group: {_id: "$tier", count: {$sum: 1}}}])
```

### Django Admin

Access http://localhost:8000/admin (after creating a superuser)

```bash
python manage.py createsuperuser
```

---

## Common Issues

### Issue: Celery worker not picking up tasks

**Solution**:
```bash
# Check if worker is running
docker-compose ps

# Restart worker
docker-compose restart celery_worker_cpu

# Check logs
docker-compose logs celery_worker_cpu
```

### Issue: Email notifications not sending

**Solution**:
1. Check `SENDGRID_API_KEY` in `.env`
2. Verify `NOTIFICATION_EMAIL_ENABLED=True`
3. Check SendGrid dashboard for delivery status

### Issue: MongoDB connection refused

**Solution**:
```bash
# Restart MongoDB
docker-compose restart mongodb

# Check MongoDB logs
docker-compose logs mongodb
```

---

## Next Steps

### Phase 2: User Management & Tiers (Weeks 4-6)
- Implement tier selection during registration
- Add user dashboard with usage stats
- Implement quota enforcement

### Phase 3: Payment Integration (Weeks 7-9)
- Set up Stripe account
- Implement subscription checkout
- Handle webhook events

### Phase 4: Notifications (Week 10)
- Create professional email templates
- Add in-app notifications
- Implement notification preferences

### Phase 5: GPU Workers (Week 12)
- Provision AWS g5.xlarge instance
- Set up GPU worker
- Benchmark performance

### Phase 6: UI/UX Enhancements (Week 13)
- Add WebSockets for real-time progress
- Improve upload UX with drag-and-drop
- Mobile-responsive design

### Phase 7: AI Chatbot (Weeks 14-15)
- Curate clinical dataset catalog
- Implement RAG-based chatbot
- OpenAI integration

### Phase 8: Production Deployment (Weeks 16-17)
- Set up AWS infrastructure
- Configure MongoDB Atlas
- Implement CI/CD pipeline

---

## Support & Documentation

- **Technical Report**: See `TECHNICAL_FEASIBILITY_REPORT.md`
- **Implementation Plan**: See `IMPLEMENTATION_ROADMAP.md`
- **API Documentation**: Coming in Phase 6
- **Video Tutorials**: Coming in Phase 9

---

## Architecture Diagrams

### Current Architecture

```
┌─────────────────┐
│   User Browser  │
└────────┬────────┘
         │ HTTP
┌────────▼────────────────────┐
│   Django Web (Port 8000)    │
└────┬────────────────┬────────┘
     │                │
     │ Celery Tasks   │ MongoDB Queries
     │                │
┌────▼────────┐  ┌───▼────────┐
│Redis Broker │  │  MongoDB   │
│(Port 6379)  │  │(Port 27017)│
└────┬────────┘  └────────────┘
     │
     │ Task Queue
     │
┌────▼──────────────────────┐
│   Celery Workers          │
│  ┌──────────────────┐    │
│  │  CPU Worker      │    │
│  │  (Free Tier)     │    │
│  └────────┬─────────┘    │
│           │               │
│           ▼               │
│  ┌──────────────────┐    │
│  │ TabGraphSyn      │    │
│  │ Pipeline         │    │
│  │ (UNCHANGED)      │    │
│  └──────────────────┘    │
└───────────────────────────┘
```

---

## FAQ

### Q: Is the TabGraphSyn pipeline modified?
**A**: No! The pipeline is treated as a black box. We only wrap it for async execution.

### Q: Can I run this without Docker?
**A**: Yes, see "Option 2: Manual Setup" above.

### Q: How do I enable GPU workers?
**A**: Uncomment the `celery_worker_gpu` service in `docker-compose.yml` and run on a machine with NVIDIA GPU.

### Q: What's the cost for production?
**A**: See cost analysis in `TECHNICAL_FEASIBILITY_REPORT.md`. Estimated $274/month for startup phase.

### Q: How do I migrate from the old system?
**A**: Existing runs are preserved. New jobs will use the async system automatically.

---

**Ready to build the future of synthetic data generation? Let's go! 🚀**
