# TabGraphSyn Enterprise Platform - Implementation Roadmap

**Version**: 1.0
**Target Timeline**: 12-16 weeks
**Last Updated**: November 17, 2025

---

## Overview

This roadmap details the phased implementation of TabGraphSyn's transformation into an enterprise-level platform supporting free and paid tiers with async job processing, GPU acceleration, payment integration, and AI-powered dataset recommendations.

---

## Phase 1: Foundation & Infrastructure (Weeks 1-3)

### Milestone 1.1: Async Job Processing Setup (Week 1)

**Objective**: Replace in-memory thread-based jobs with Celery + Redis

**Tasks**:
- [ ] Install and configure Celery 5.3+
- [ ] Set up Redis 7.0+ as message broker
- [ ] Create Celery app configuration in Django
- [ ] Configure separate queues (cpu, gpu)
- [ ] Set up Flower for monitoring (dev environment)
- [ ] Test basic task execution

**Files to Create/Modify**:
- `requirements.txt` - Add celery, redis, flower
- `tabgraphsyn_site/celery.py` - Celery app initialization
- `tabgraphsyn_site/__init__.py` - Import Celery app
- `docker-compose.yml` - Add Redis service
- `.env.example` - Add Redis connection string

**Testing**:
```bash
# Start Redis
docker-compose up -d redis

# Start Celery worker
celery -A tabgraphsyn_site worker -Q cpu --loglevel=info

# Start Flower monitoring
celery -A tabgraphsyn_site flower
```

**Success Criteria**:
- ✅ Celery worker processes tasks
- ✅ Redis broker operational
- ✅ Flower UI accessible at localhost:5555

---

### Milestone 1.2: Enhanced MongoDB Schema (Week 2)

**Objective**: Extend MongoDB with new collections for jobs, subscriptions, notifications

**Tasks**:
- [ ] Create `jobs` collection schema
- [ ] Create `subscriptions` collection schema
- [ ] Create `notifications` collection schema
- [ ] Create `datasets` collection (for chatbot)
- [ ] Add indexes for performance
- [ ] Migrate existing `users` collection (add tier fields)
- [ ] Write migration script for existing runs
- [ ] Create MongoDB management command

**Files to Create/Modify**:
- `accounts/mongo.py` - Enhanced MongoDB client with new collections
- `accounts/models.py` - Document schemas (dataclasses)
- `accounts/management/commands/migrate_mongodb.py` - Migration script
- `accounts/management/commands/create_indexes.py` - Index creation

**MongoDB Indexes to Create**:
```python
# users collection
users.create_index("username", unique=True)
users.create_index("email", unique=True)
users.create_index([("tier", 1), ("subscription_status", 1)])

# jobs collection
jobs.create_index("job_id", unique=True)
jobs.create_index("token", unique=True)
jobs.create_index([("owner_username", 1), ("created_at", -1)])
jobs.create_index([("status", 1), ("priority", -1), ("queued_at", 1)])

# subscriptions collection
subscriptions.create_index("user_id")
subscriptions.create_index("stripe_subscription_id", unique=True)

# notifications collection
notifications.create_index([("user_id", 1), ("created_at", -1)])
notifications.create_index([("username", 1), ("read", 1)])
```

**Testing**:
```bash
python manage.py migrate_mongodb
python manage.py create_indexes
```

**Success Criteria**:
- ✅ New collections created
- ✅ Indexes applied
- ✅ Existing data migrated

---

### Milestone 1.3: Celery Task Wrapper for TabGraphSyn (Week 3)

**Objective**: Create async task that wraps TabGraphSyn pipeline without modifying it

**Tasks**:
- [ ] Create `synthetic/tasks.py` with Celery tasks
- [ ] Implement `run_pipeline_cpu` task
- [ ] Implement `run_pipeline_gpu` task
- [ ] Add progress tracking callbacks
- [ ] Integrate with MongoDB `jobs` collection
- [ ] Add error handling and retries
- [ ] Update `synthetic/views.py` to use Celery tasks
- [ ] Remove old `job_tracker.py` in-memory tracking

**Files to Create/Modify**:
- `synthetic/tasks.py` - NEW: Celery tasks
- `synthetic/views.py` - Replace threading with Celery
- `synthetic/pipeline.py` - Add progress callbacks
- `synthetic/job_manager.py` - NEW: Job CRUD operations

**Task Structure**:
```python
@shared_task(bind=True, max_retries=3)
def run_pipeline_cpu(self, job_token, params_dict):
    """
    Celery wrapper for TabGraphSyn (CPU-only, free tier)
    DOES NOT MODIFY TabGraphSyn - only orchestrates
    """
    # 1. Fetch job from MongoDB
    # 2. Update status to 'running'
    # 3. Call execute_pipeline() (UNCHANGED TabGraphSyn)
    # 4. Track progress via callbacks
    # 5. Store results in MongoDB
    # 6. Update status to 'completed'
    # 7. Trigger notification
    pass
```

**Testing**:
```bash
# Submit test job
curl -X POST http://localhost:8000/api/start-run/ \
  -d '{"dataset": "AIDS", "epochs_vae": 5}'

# Monitor in Flower
open http://localhost:5555
```

**Success Criteria**:
- ✅ Jobs execute asynchronously via Celery
- ✅ Progress tracked in MongoDB
- ✅ No blocking on web requests
- ✅ TabGraphSyn pipeline unchanged

---

## Phase 2: User Management & Tiers (Weeks 4-6)

### Milestone 2.1: Tier System Implementation (Week 4)

**Objective**: Add free vs. paid tier differentiation

**Tasks**:
- [ ] Update user registration to include tier selection
- [ ] Add tier field to session authentication
- [ ] Create tier-based decorators (`@require_paid_tier`)
- [ ] Add usage tracking (jobs submitted, rows generated)
- [ ] Create tier management views (upgrade, downgrade)
- [ ] Update MongoDB users collection
- [ ] Add tier display in UI

**Files to Create/Modify**:
- `accounts/decorators.py` - Add `@require_paid_tier`
- `accounts/views.py` - Add tier management views
- `accounts/mongo.py` - Update user schema
- `templates/accounts/profile.html` - NEW: User profile page
- `templates/accounts/upgrade.html` - NEW: Upgrade to paid tier

**Tier Restrictions**:
```python
# Free Tier
- CPU-only processing
- Standard queue (FIFO)
- Email notifications
- Basic support

# Paid Tier
- GPU-accelerated processing
- Priority queue
- Advanced email + SMS notifications
- AI chatbot for dataset recommendations
- Priority support
```

**Testing**:
- [ ] Register as free user, verify CPU queue routing
- [ ] Upgrade to paid tier, verify GPU access
- [ ] Downgrade to free, verify restrictions enforced

**Success Criteria**:
- ✅ Users can select tier during registration
- ✅ Paid users routed to GPU queue
- ✅ Free users restricted to CPU queue

---

### Milestone 2.2: User Dashboard (Week 5)

**Objective**: Create user profile and usage tracking dashboard

**Tasks**:
- [ ] Create profile page (personal info, tier, usage stats)
- [ ] Add usage statistics (jobs submitted, completed, failed)
- [ ] Show total rows generated
- [ ] Display subscription status (if paid)
- [ ] Add account settings (email preferences, API keys)
- [ ] Create API key generation endpoint
- [ ] Add API rate limiting

**Files to Create/Modify**:
- `accounts/views.py` - Profile views
- `templates/accounts/profile.html`
- `templates/accounts/settings.html`
- `synthetic/views.py` - Add usage stats aggregation

**Dashboard Metrics**:
```python
{
  "jobs_submitted": 45,
  "jobs_completed": 42,
  "jobs_failed": 3,
  "total_rows_generated": 250000,
  "api_calls_this_month": 120,
  "api_quota_remaining": 880,
  "subscription_status": "active",
  "next_billing_date": "2025-12-01"
}
```

**Success Criteria**:
- ✅ User can view profile and usage
- ✅ API keys generated and functional
- ✅ Rate limiting enforced

---

### Milestone 2.3: Usage Quotas & Limits (Week 6)

**Objective**: Enforce tier-based quotas

**Tasks**:
- [ ] Define quota limits (jobs/month, rows/job, file size)
- [ ] Implement quota checking middleware
- [ ] Add quota display in UI
- [ ] Create quota exceeded error messages
- [ ] Add quota reset scheduler (monthly)
- [ ] Log quota events

**Quota Configuration**:
```python
TIER_QUOTAS = {
    'free': {
        'jobs_per_month': 10,
        'max_rows_per_job': 10000,
        'max_file_size_mb': 50,
        'max_epochs_total': 50,
    },
    'paid': {
        'jobs_per_month': 1000,
        'max_rows_per_job': 100000,
        'max_file_size_mb': 500,
        'max_epochs_total': 500,
    }
}
```

**Testing**:
- [ ] Free user hits monthly limit, verify blocking
- [ ] Free user uploads 100MB file, verify rejection
- [ ] Paid user exceeds limits, verify allowed

**Success Criteria**:
- ✅ Quotas enforced correctly
- ✅ Clear error messages
- ✅ Automatic monthly reset

---

## Phase 3: Payment Integration (Weeks 7-9)

### Milestone 3.1: Stripe Setup (Week 7)

**Objective**: Integrate Stripe for subscription payments

**Tasks**:
- [ ] Create Stripe account (test + live keys)
- [ ] Install stripe Python library
- [ ] Create Stripe products and prices
  - Monthly: $49/month
  - Annual: $490/year (2 months free)
- [ ] Configure Stripe webhook endpoint
- [ ] Create subscription checkout flow
- [ ] Implement payment success/failure pages

**Files to Create/Modify**:
- `requirements.txt` - Add stripe
- `accounts/stripe_client.py` - NEW: Stripe integration
- `accounts/views.py` - Checkout views
- `accounts/urls.py` - Payment endpoints
- `templates/accounts/checkout.html` - NEW
- `templates/accounts/payment_success.html` - NEW
- `.env.example` - Add Stripe keys

**Stripe Products**:
```python
STRIPE_PRODUCTS = {
    'monthly': {
        'name': 'TabGraphSyn Pro - Monthly',
        'price': 49.00,
        'interval': 'month',
        'features': [
            'GPU-accelerated processing',
            'Priority queue',
            'AI dataset chatbot',
            'Advanced notifications',
            '1000 jobs/month'
        ]
    },
    'annual': {
        'name': 'TabGraphSyn Pro - Annual',
        'price': 490.00,
        'interval': 'year',
        'features': '...'
    }
}
```

**Testing**:
- [ ] Use Stripe test cards (4242 4242 4242 4242)
- [ ] Verify checkout flow
- [ ] Test subscription creation

**Success Criteria**:
- ✅ Checkout flow functional
- ✅ Subscriptions created in Stripe
- ✅ Test payments successful

---

### Milestone 3.2: Webhook Handling (Week 8)

**Objective**: Handle Stripe webhooks for subscription events

**Tasks**:
- [ ] Create webhook endpoint (`/webhooks/stripe/`)
- [ ] Implement signature verification
- [ ] Handle subscription events:
  - `customer.subscription.created`
  - `customer.subscription.updated`
  - `customer.subscription.deleted`
  - `invoice.payment_succeeded`
  - `invoice.payment_failed`
- [ ] Update MongoDB on subscription changes
- [ ] Send email notifications on payment events
- [ ] Log all webhook events

**Files to Create/Modify**:
- `accounts/webhooks.py` - NEW: Webhook handlers
- `accounts/urls.py` - Add webhook endpoint
- `accounts/mongo.py` - Subscription CRUD

**Webhook Event Handling**:
```python
WEBHOOK_EVENTS = {
    'customer.subscription.created': handle_subscription_created,
    'customer.subscription.updated': handle_subscription_updated,
    'customer.subscription.deleted': handle_subscription_canceled,
    'invoice.payment_succeeded': handle_payment_success,
    'invoice.payment_failed': handle_payment_failed,
}
```

**Testing**:
- [ ] Use Stripe CLI to forward webhooks
- [ ] Test each event type
- [ ] Verify database updates

**Success Criteria**:
- ✅ All webhook events handled
- ✅ User tier updated automatically
- ✅ No missed webhook events

---

### Milestone 3.3: Subscription Management (Week 9)

**Objective**: Allow users to manage subscriptions

**Tasks**:
- [ ] Create subscription management page
- [ ] Implement cancel subscription flow
- [ ] Add payment method update
- [ ] Show billing history
- [ ] Implement reactivate subscription
- [ ] Add invoice downloads
- [ ] Handle failed payments (dunning)

**Files to Create/Modify**:
- `templates/accounts/subscription.html` - NEW
- `templates/accounts/billing_history.html` - NEW
- `accounts/views.py` - Subscription management views

**Features**:
- View current subscription status
- Cancel subscription (at period end)
- Reactivate canceled subscription
- Update payment method
- Download invoices
- View payment history

**Success Criteria**:
- ✅ Users can cancel subscriptions
- ✅ Billing history displayed
- ✅ Payment methods updatable

---

## Phase 4: Notifications & Monitoring (Weeks 10-11)

### Milestone 4.1: Email Notification System (Week 10)

**Objective**: Automated email notifications for job events

**Tasks**:
- [ ] Set up SendGrid account
- [ ] Create email templates:
  - Job completed
  - Job failed
  - Payment successful
  - Payment failed
  - Subscription expiring
- [ ] Implement email sending task (Celery)
- [ ] Add email preferences to user settings
- [ ] Create notification history
- [ ] Add unsubscribe functionality

**Files to Create/Modify**:
- `requirements.txt` - Add sendgrid
- `accounts/notifications.py` - NEW: Notification system
- `synthetic/tasks.py` - Add email trigger on job completion
- `templates/emails/` - NEW: Email templates

**Email Templates**:
```
1. job_completed.html
   - Subject: "Your synthetic data is ready!"
   - Content: Job details, download link, metrics preview

2. job_failed.html
   - Subject: "Job failed - TabGraphSyn"
   - Content: Error message, support link

3. payment_success.html
   - Subject: "Payment confirmed - TabGraphSyn Pro"
   - Content: Invoice, next billing date

4. subscription_expiring.html
   - Subject: "Your subscription expires in 7 days"
   - Content: Renewal link
```

**Testing**:
- [ ] Send test emails to all templates
- [ ] Verify unsubscribe works
- [ ] Test email preferences

**Success Criteria**:
- ✅ Emails sent on job completion
- ✅ Professional templates
- ✅ Unsubscribe functional

---

### Milestone 4.2: Admin Dashboard (Week 11)

**Objective**: Monitoring and management interface

**Tasks**:
- [ ] Enhance Django Admin with custom views
- [ ] Add job queue monitoring dashboard
- [ ] Integrate Celery Flower
- [ ] Create user management interface
- [ ] Add analytics dashboard:
  - Jobs per day/week/month
  - Revenue tracking
  - Error rate monitoring
  - User growth metrics
- [ ] Implement manual job cancellation
- [ ] Add system health checks

**Files to Create/Modify**:
- `accounts/admin.py` - Enhanced admin models
- `synthetic/admin.py` - Job monitoring
- `templates/admin/` - Custom admin templates
- `synthetic/views.py` - Admin analytics endpoints

**Dashboard Metrics**:
```python
ANALYTICS = {
    'jobs': {
        'today': 45,
        'week': 312,
        'month': 1240,
        'failed_rate': 2.1
    },
    'users': {
        'total': 523,
        'free': 480,
        'paid': 43,
        'growth_rate': 15.3
    },
    'revenue': {
        'mrr': 2107,  # Monthly Recurring Revenue
        'arr': 25284,  # Annual Recurring Revenue
        'churn_rate': 3.2
    },
    'infrastructure': {
        'cpu_workers': 4,
        'gpu_workers': 2,
        'queue_length': 12,
        'avg_wait_time_min': 8.5
    }
}
```

**Success Criteria**:
- ✅ Admin dashboard accessible
- ✅ Real-time metrics displayed
- ✅ Job monitoring functional

---

## Phase 5: GPU & Performance (Week 12)

### Milestone 5.1: GPU Worker Setup

**Objective**: Deploy GPU-enabled workers for paid tier

**Tasks**:
- [ ] Provision AWS g5.xlarge Spot instance
- [ ] Install CUDA 11.8 + drivers
- [ ] Set up GPU-enabled Celery worker
- [ ] Configure GPU queue routing
- [ ] Test TabGraphSyn with GPU
- [ ] Benchmark CPU vs GPU performance
- [ ] Implement GPU availability checking
- [ ] Add fallback to CPU if GPU unavailable
- [ ] Configure auto-scaling (optional)

**Infrastructure Setup**:
```bash
# Launch EC2 instance
aws ec2 run-instances \
  --image-id ami-xxxxx \
  --instance-type g5.xlarge \
  --spot-options ...

# Install dependencies
sudo apt-get update
sudo apt-get install nvidia-driver-525
pip install torch==2.2.0+cu118 --extra-index-url https://download.pytorch.org/whl/cu118

# Start GPU worker
celery -A tabgraphsyn_site worker -Q gpu --concurrency=2
```

**Testing**:
- [ ] Submit paid tier job, verify GPU worker picks it up
- [ ] Monitor GPU utilization (nvidia-smi)
- [ ] Compare execution times: CPU vs GPU
- [ ] Test spot instance interruption handling

**Performance Benchmarks**:
```
Dataset: AIDS (5,000 rows)
Epochs: VAE=10, GNN=10, Diffusion=1

CPU (t3.xlarge):     18 min
GPU (A10G):          6 min
Speedup:             3x
```

**Success Criteria**:
- ✅ GPU workers operational
- ✅ Paid tier jobs use GPU
- ✅ 2-5x speedup achieved

---

## Phase 6: UI/UX Enhancements (Week 13)

### Milestone 6.1: Real-time Progress Tracking

**Objective**: WebSocket or SSE for live job updates

**Tasks**:
- [ ] Choose technology: Django Channels (WebSocket) or SSE
- [ ] Install and configure Django Channels
- [ ] Create WebSocket consumer for job updates
- [ ] Update Celery tasks to broadcast progress
- [ ] Modify frontend to connect to WebSocket
- [ ] Add progress bar with stage indicators
- [ ] Show live log streaming (optional)

**Files to Create/Modify**:
- `requirements.txt` - Add channels, daphne
- `tabgraphsyn_site/asgi.py` - ASGI configuration
- `synthetic/consumers.py` - NEW: WebSocket consumer
- `synthetic/routing.py` - NEW: WebSocket routing
- `static/js/job_progress.js` - NEW: WebSocket client

**WebSocket Protocol**:
```javascript
// Client connects
ws = new WebSocket('ws://localhost:8000/ws/job/<token>/')

// Server sends updates
{
  "type": "job_update",
  "status": "running",
  "stage": "training",
  "progress": 35,
  "current_epoch": 7,
  "total_epochs": 20,
  "message": "Training VAE model..."
}
```

**Success Criteria**:
- ✅ Real-time progress updates
- ✅ No polling required
- ✅ Progress bar reflects actual state

---

### Milestone 6.2: UI Polish

**Objective**: Improve visual design and UX

**Tasks**:
- [ ] Add drag-and-drop file upload
- [ ] Improve form styling (modern CSS)
- [ ] Add loading animations
- [ ] Create better result visualizations
- [ ] Make responsive for mobile
- [ ] Add dark mode toggle (optional)
- [ ] Improve error messages
- [ ] Add tooltips and help text

**Files to Modify**:
- `templates/synthetic/upload.html`
- `templates/synthetic/result.html`
- `static/css/main.css`
- `static/js/upload.js`

**Design Improvements**:
- Clean, modern interface (Tailwind CSS or Bootstrap 5)
- Intuitive multi-step form
- Clear progress indicators
- Professional result display
- Mobile-friendly layout

**Success Criteria**:
- ✅ Professional appearance
- ✅ Intuitive user flow
- ✅ Mobile responsive

---

## Phase 7: AI Chatbot (Weeks 14-15) [PAID TIER ONLY]

### Milestone 7.1: Dataset Catalog Curation

**Objective**: Build dataset database for chatbot

**Tasks**:
- [ ] Research 50-100 clinical datasets (PhysioNet, Kaggle, UCI, etc.)
- [ ] Create dataset catalog CSV
- [ ] Import into MongoDB `datasets` collection
- [ ] Add metadata (category, keywords, constraints)
- [ ] Generate embeddings with OpenAI
- [ ] Set up MongoDB Atlas Vector Search
- [ ] Test similarity search

**Dataset Sources**:
- PhysioNet (MIMIC-III, eICU, MIMIC-IV)
- Kaggle Healthcare datasets
- UCI Machine Learning Repository
- NIH datasets
- ClinicalTrials.gov
- Open Data Portals

**Dataset Schema**:
```json
{
  "name": "MIMIC-III",
  "category": "clinical",
  "description": "Large ICU database...",
  "url": "https://physionet.org/content/mimiciii/",
  "num_records": 58000,
  "keywords": ["ICU", "EHR", "mortality"],
  "embedding": [0.1, 0.2, ...],
  "constraints": {
    "clinical_focus": true,
    "contains_phi": false,
    "access": "credentialed"
  }
}
```

**Success Criteria**:
- ✅ 50+ datasets cataloged
- ✅ Embeddings generated
- ✅ Vector search functional

---

### Milestone 7.2: Chatbot Implementation

**Objective**: Build RAG-based chatbot for dataset recommendations

**Tasks**:
- [ ] Set up OpenAI API client
- [ ] Create chatbot endpoint (`/api/chatbot/`)
- [ ] Implement RAG pipeline:
  1. User query → Embedding
  2. Vector search MongoDB
  3. Retrieve top 5 datasets
  4. Generate response with GPT-4
- [ ] Add conversation history tracking
- [ ] Create chatbot UI (chat widget)
- [ ] Restrict to paid tier only
- [ ] Add rate limiting (10 queries/day)

**Files to Create/Modify**:
- `requirements.txt` - Add openai, langchain
- `synthetic/chatbot.py` - NEW: Chatbot logic
- `synthetic/views.py` - Chatbot endpoint
- `templates/synthetic/chatbot.html` - NEW: Chat UI
- `static/js/chatbot.js` - NEW: Chat widget

**Chatbot Flow**:
```
User: "I need a clinical dataset with patient outcomes for heart disease"

System:
1. Generate embedding for query
2. Search MongoDB datasets (vector similarity)
3. Retrieve: HeartDisease UCI, MIMIC-III Cardiovascular subset, ...
4. Generate response:

"Here are 3 clinical datasets for heart disease research:

1. **UCI Heart Disease Dataset**
   - 303 patients, 14 features
   - Focus: Diagnosis prediction
   - Access: Public, free
   - URL: ...

2. **MIMIC-III Cardiovascular Subset**
   - 15,000+ ICU admissions
   - Focus: Outcomes, treatments
   - Access: PhysioNet credentialed
   - URL: ...

Would you like more details on any of these?"
```

**Success Criteria**:
- ✅ Chatbot returns relevant datasets
- ✅ Responses accurate and helpful
- ✅ Only accessible to paid users

---

## Phase 8: Production Deployment (Weeks 16-17)

### Milestone 8.1: Infrastructure Setup

**Objective**: Deploy to AWS production environment

**Tasks**:
- [ ] Create AWS account and IAM roles
- [ ] Set up VPC with public/private subnets
- [ ] Provision EC2 instances:
  - 2x t3.medium (web servers)
  - 2x t3.xlarge (CPU workers)
  - 1x g5.xlarge Spot (GPU worker)
- [ ] Configure Application Load Balancer
- [ ] Set up MongoDB Atlas M10 cluster
- [ ] Configure ElastiCache Redis
- [ ] Set up S3 bucket for file storage
- [ ] Configure Route53 DNS
- [ ] Obtain SSL certificate (Let's Encrypt)
- [ ] Set up security groups and firewall rules

**Architecture**:
```
Internet → Route53 → ALB → [EC2 Web1, EC2 Web2]
                              ↓
                       [Redis, MongoDB Atlas]
                              ↓
                       [EC2 CPU Workers, EC2 GPU Worker]
                              ↓
                         S3 (File Storage)
```

**Success Criteria**:
- ✅ All infrastructure provisioned
- ✅ HTTPS working
- ✅ Load balancer distributing traffic

---

### Milestone 8.2: CI/CD Pipeline

**Objective**: Automated testing and deployment

**Tasks**:
- [ ] Create GitHub Actions workflow
- [ ] Set up automated testing:
  - Unit tests
  - Integration tests
  - E2E tests (Playwright/Selenium)
- [ ] Configure automatic deployment on merge to main
- [ ] Set up staging environment
- [ ] Implement blue-green deployment
- [ ] Add rollback capability
- [ ] Configure secrets management (AWS Secrets Manager)

**Files to Create**:
- `.github/workflows/test.yml`
- `.github/workflows/deploy.yml`
- `tests/` - Test suite

**Deployment Workflow**:
```yaml
name: Deploy to Production

on:
  push:
    branches: [main]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - Checkout code
      - Run unit tests
      - Run integration tests

  deploy:
    needs: test
    runs-on: ubuntu-latest
    steps:
      - SSH to EC2
      - Pull latest code
      - Run migrations
      - Restart services
      - Run smoke tests
```

**Success Criteria**:
- ✅ Automated tests passing
- ✅ Deployments automated
- ✅ Zero-downtime deployments

---

### Milestone 8.3: Monitoring & Logging

**Objective**: Production monitoring and alerting

**Tasks**:
- [ ] Set up CloudWatch for logs and metrics
- [ ] Configure Sentry for error tracking
- [ ] Set up Prometheus + Grafana (optional)
- [ ] Create alert rules:
  - High error rate
  - Job failure rate > 10%
  - Worker down
  - Database connection issues
- [ ] Set up log aggregation
- [ ] Create runbooks for common issues
- [ ] Configure PagerDuty/OpsGenie (optional)

**Metrics to Track**:
- Request rate, latency, error rate
- Job queue length
- Worker utilization (CPU, GPU)
- Database performance
- File storage usage
- Celery task success/failure rate

**Success Criteria**:
- ✅ All metrics visible
- ✅ Alerts configured
- ✅ Error tracking functional

---

## Phase 9: Testing & Beta Launch (Week 18)

### Milestone 9.1: Comprehensive Testing

**Objective**: End-to-end testing of all features

**Test Scenarios**:

**Free Tier User Journey**:
- [ ] Register account
- [ ] Upload CSV file
- [ ] Submit job
- [ ] Receive email notification
- [ ] Download synthetic data
- [ ] View run history
- [ ] Hit monthly quota limit

**Paid Tier User Journey**:
- [ ] Register account
- [ ] Upgrade to paid tier (Stripe)
- [ ] Submit job (verify GPU usage)
- [ ] Use chatbot
- [ ] Download results
- [ ] Manage subscription
- [ ] Cancel subscription

**Admin Journey**:
- [ ] Access admin dashboard
- [ ] Monitor job queue
- [ ] View analytics
- [ ] Cancel user job manually
- [ ] Review payment history

**Load Testing**:
- [ ] Simulate 100 concurrent users
- [ ] Verify queue handling
- [ ] Check database performance
- [ ] Monitor resource usage

**Security Testing**:
- [ ] OWASP top 10 vulnerabilities
- [ ] File upload validation
- [ ] SQL/NoSQL injection attempts
- [ ] XSS attempts
- [ ] CSRF protection
- [ ] Rate limiting bypass attempts

**Success Criteria**:
- ✅ All user journeys functional
- ✅ No critical bugs
- ✅ Security audit passed

---

### Milestone 9.2: Beta Launch

**Objective**: Launch to limited beta users

**Tasks**:
- [ ] Create landing page
- [ ] Write user documentation
- [ ] Create video tutorials
- [ ] Set up support email/chat
- [ ] Invite 50 beta users
- [ ] Collect feedback
- [ ] Monitor for issues
- [ ] Iterate based on feedback

**Documentation to Create**:
- Getting Started Guide
- API Documentation
- FAQ
- Troubleshooting Guide
- Video: "How to generate synthetic data"
- Video: "Understanding evaluation metrics"

**Success Criteria**:
- ✅ Beta users onboarded
- ✅ Positive feedback
- ✅ No major issues

---

## Phase 10: Public Launch (Week 19-20)

### Milestone 10.1: Marketing & Launch Prep

**Tasks**:
- [ ] Finalize pricing page
- [ ] Launch marketing website
- [ ] Prepare press release
- [ ] Set up social media accounts
- [ ] Create launch video
- [ ] Prepare customer support workflows
- [ ] Set up analytics (Google Analytics, Mixpanel)

**Success Criteria**:
- ✅ Website live
- ✅ Marketing materials ready
- ✅ Support team trained

---

### Milestone 10.2: Public Launch

**Tasks**:
- [ ] Announce on Product Hunt
- [ ] Post on relevant subreddits (r/MachineLearning, r/datascience)
- [ ] Share on Twitter/LinkedIn
- [ ] Email beta users
- [ ] Monitor for issues
- [ ] Provide customer support
- [ ] Collect feedback

**Launch Day Checklist**:
- [ ] All systems operational
- [ ] Support team on standby
- [ ] Monitoring dashboards open
- [ ] Backup plan ready
- [ ] Celebrate! 🎉

---

## Success Metrics

### Technical Metrics
- **Uptime**: >99.5%
- **Job Success Rate**: >95%
- **Avg Job Wait Time**: <5 min (paid), <30 min (free)
- **API Response Time**: <500ms (p95)
- **Error Rate**: <1%

### Business Metrics
- **User Acquisition**: 100 users in Month 1
- **Conversion Rate**: 10% free → paid
- **Monthly Recurring Revenue**: $500 by Month 3
- **Customer Satisfaction**: 4.5/5 stars
- **Churn Rate**: <5%

---

## Risk Management

### Technical Risks
- **Spot instance interruption**: Auto-restart with checkpointing
- **Database downtime**: MongoDB Atlas multi-region replica set
- **Worker crashes**: Auto-restart with supervisord/systemd

### Business Risks
- **Low adoption**: Pivot marketing strategy, offer discounts
- **High costs**: Optimize infrastructure, use spot instances
- **Payment fraud**: Enable Stripe Radar

---

## Post-Launch Roadmap (Months 4-12)

### Future Features
- [ ] Multi-table synthetic data generation
- [ ] API access for programmatic usage
- [ ] Jupyter notebook integration
- [ ] More evaluation metrics (ML utility, privacy metrics)
- [ ] Custom model training (fine-tuning)
- [ ] Team/organization accounts
- [ ] White-label solution for enterprises
- [ ] On-premise deployment option

---

## Appendix: Quick Reference

### Key Commands

```bash
# Start development environment
docker-compose up -d

# Run migrations
python manage.py migrate
python manage.py migrate_mongodb

# Start Celery workers
celery -A tabgraphsyn_site worker -Q cpu --loglevel=info
celery -A tabgraphsyn_site worker -Q gpu --loglevel=info

# Start Flower monitoring
celery -A tabgraphsyn_site flower

# Run tests
pytest tests/

# Deploy to production
git push origin main  # Triggers CI/CD
```

### Important URLs

- **Development**: http://localhost:8000
- **Flower**: http://localhost:5555
- **Admin**: http://localhost:8000/admin
- **Stripe Dashboard**: https://dashboard.stripe.com/test
- **MongoDB Atlas**: https://cloud.mongodb.com/

---

**End of Roadmap**

**Next Steps**: Begin Phase 1, Milestone 1.1 (Celery + Redis Setup)
