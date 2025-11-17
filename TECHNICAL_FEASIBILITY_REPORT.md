# TabGraphSyn Enterprise Platform - Technical Feasibility Report

**Date**: November 17, 2025
**Version**: 1.0
**Prepared for**: TabGraphSyn Platform Development

---

## Executive Summary

This report analyzes the feasibility of transforming TabGraphSyn from a basic Django web application into an enterprise-level synthetic data generation platform supporting both free and paid tiers. The current implementation has a solid foundation with MongoDB integration, user authentication, and functional TabGraphSyn pipeline execution. However, it requires significant architectural enhancements to support async job processing, tier-based features, GPU allocation, and scalability.

**Key Findings**:
- ✅ **Feasible** - Project has strong foundation
- ✅ **MongoDB** - Keep and enhance (see section 3)
- ✅ **TabGraphSyn Pipeline** - Well-isolated, ready for async wrapping
- ⚠️ **Critical Gaps** - Need Celery, Redis, payment integration, notifications
- 💰 **Estimated Timeline** - 8-12 weeks for MVP with paid tier
- 💰 **Infrastructure Cost** - $200-500/month for startup phase

---

## 1. Current State Analysis

### 1.1 Architecture Overview

```
Current Architecture (Basic):

┌─────────────────────────────────────────────────────────────┐
│                        User Browser                          │
└──────────────────────┬──────────────────────────────────────┘
                       │ HTTP
┌──────────────────────▼──────────────────────────────────────┐
│                   Django Web Server                          │
│  ┌────────────┐  ┌──────────────┐  ┌──────────────┐        │
│  │  accounts  │  │  synthetic   │  │   templates  │        │
│  │    app     │  │     app      │  │      UI      │        │
│  └────────────┘  └──────────────┘  └──────────────┘        │
└────────┬──────────────────┬────────────────────────────────┘
         │                  │
         │                  │ subprocess.run()
         │                  │
┌────────▼──────────┐  ┌───▼─────────────────────────────────┐
│   MongoDB         │  │   TabGraphSyn Pipeline               │
│   - users         │  │   src/scripts/run_pipeline.py        │
│   - runs          │  │   (VAE + GNN + Diffusion)            │
└───────────────────┘  │   [IMMUTABLE BLACK BOX]              │
                       └──────────────────────────────────────┘
```

### 1.2 Current Capabilities

**Strengths**:
- ✅ User authentication with MongoDB backend (PyMongo)
- ✅ Session-based auth with secure password hashing
- ✅ CSV upload with automatic metadata inference
- ✅ TabGraphSyn pipeline wrapper (subprocess execution)
- ✅ Background thread-based job execution
- ✅ Real-time job status polling API
- ✅ Run history tracking in MongoDB
- ✅ Evaluation metrics computation (UMAP plots, statistical metrics)
- ✅ Docker Compose setup for local development
- ✅ File-based result storage (CSVs, JSON metadata)

**Critical Gaps**:
- ❌ No proper async job queue (uses in-memory threads)
- ❌ No tier management (free vs. paid users)
- ❌ No payment integration
- ❌ No email notifications
- ❌ No GPU resource allocation
- ❌ No job priority system
- ❌ No admin dashboard for monitoring
- ❌ No chatbot for dataset recommendations
- ❌ No production-ready security settings
- ❌ No horizontal scalability

### 1.3 TabGraphSyn Pipeline Interface

**Current Invocation**:
```bash
python src/scripts/run_pipeline.py \
  --dataset-name DATASET \
  --target-table TABLE \
  --epochs-gnn 10 \
  --epochs-vae 10 \
  --epochs-diff 1 \
  --enable-epoch-eval \
  --eval-frequency 10
```

**Input Requirements**:
- CSV file at `/src/data/original/{dataset}/{table}.csv`
- Metadata JSON at `/src/data/original/{dataset}/metadata.json`
- Parameters: epochs (VAE/GNN/Diffusion), seed, sample count

**Output**:
- Synthetic CSV: `/src/data/synthetic/{dataset}/SingleTable/single_table/{table}.csv`
- Training logs: Real-time stdout/stderr
- Epoch metrics: JSON files (if epoch eval enabled)

**Performance Characteristics**:
- **CPU-only**: 5-30 minutes (depends on dataset size, epochs)
- **GPU-accelerated**: 2-10 minutes (estimated 2-5x speedup)
- **Memory**: 4-16GB RAM (depends on dataset)
- **VRAM**: 8-12GB for medium datasets (recommended: RTX 3080+ or A10G)

**Dependencies**:
- PyTorch 2.2.0 with CUDA 11.8
- PyTorch Geometric 2.4.0
- Transformers, scikit-learn, pandas
- Custom package: syntherela (from GitHub)

---

## 2. Proposed Enterprise Architecture

### 2.1 High-Level Architecture Diagram

```
Enterprise Architecture (Proposed):

┌─────────────────────────────────────────────────────────────────┐
│                         User Browser                             │
│              (React/Vue Frontend - Optional)                     │
└────────┬────────────────────────────────────────────────────────┘
         │ HTTPS (REST API + WebSockets/SSE)
         │
┌────────▼────────────────────────────────────────────────────────┐
│                    Load Balancer (nginx)                         │
└────────┬────────────────────────────────────────────────────────┘
         │
    ┌────┴────┐
    │         │
┌───▼───┐ ┌──▼────┐  (Horizontal Scaling)
│Django │ │Django │
│ Web 1 │ │ Web 2 │
└───┬───┘ └──┬────┘
    │        │
    └────┬───┘
         │
    ┌────▼──────────────────────────────────────────┐
    │           Shared Services Layer                │
    │  ┌──────────┐  ┌──────────┐  ┌─────────────┐ │
    │  │  Redis   │  │ MongoDB  │  │  S3/GCS     │ │
    │  │(Cache+   │  │(Primary  │  │(File        │ │
    │  │ Session) │  │  DB)     │  │ Storage)    │ │
    │  └──────────┘  └──────────┘  └─────────────┘ │
    └────────────────────────────────────────────────┘
         │
         │ Celery Tasks (via Redis Broker)
         │
    ┌────▼──────────────────────────────────────────┐
    │           Celery Worker Pool                   │
    │  ┌──────────────┐  ┌───────────────────┐     │
    │  │CPU Workers   │  │  GPU Workers      │     │
    │  │(Free Tier)   │  │  (Paid Tier)      │     │
    │  │Low Priority  │  │  High Priority    │     │
    │  └──────┬───────┘  └────────┬──────────┘     │
    │         │                   │                 │
    │         └───────┬───────────┘                 │
    │                 │                              │
    │         ┌───────▼────────────────┐            │
    │         │  TabGraphSyn Pipeline  │            │
    │         │  (Subprocess Wrapper)  │            │
    │         │  [IMMUTABLE]           │            │
    │         └────────────────────────┘            │
    └───────────────────────────────────────────────┘
         │
         │ Results Storage
         │
    ┌────▼────────────────────────────────┐
    │  File Storage (S3/GCS/Local)        │
    │  - Uploaded CSVs                    │
    │  - Generated Synthetic Data         │
    │  - UMAP Plots, Metadata JSON        │
    └─────────────────────────────────────┘

┌──────────────────────────────────────────────────────────┐
│              External Services                            │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────┐  │
│  │   Stripe    │  │   SendGrid   │  │   OpenAI API   │  │
│  │  (Payment)  │  │   (Email)    │  │   (Chatbot)    │  │
│  └─────────────┘  └──────────────┘  └────────────────┘  │
└──────────────────────────────────────────────────────────┘
```

### 2.2 Technology Stack

**Frontend**:
- Django Templates (current) → Enhanced with AJAX/WebSockets
- Optional: React/Vue.js for admin dashboard

**Backend**:
- **Django 4.2+** (web framework)
- **Celery 5.3+** (async task queue)
- **Redis 7.0+** (message broker + cache + sessions)
- **MongoDB 7.0+** (primary database)
- **nginx** (reverse proxy + load balancer)
- **Gunicorn** (WSGI server for production)

**Message Queue**:
- **Celery** with **Redis broker** (chosen over RabbitMQ for simplicity)
- **Priority queues**: Separate queues for free/paid tiers
- **Result backend**: Redis for short-term, MongoDB for persistence

**File Storage**:
- Development: Local filesystem
- Production: **AWS S3** or **Google Cloud Storage**
- Pre-signed URLs for secure downloads

**Notifications**:
- **SendGrid** or **Amazon SES** for email
- **Twilio** for SMS (optional, paid tier)
- **WebSockets/SSE** for real-time browser notifications

**Payment**:
- **Stripe** (primary recommendation)
- **PayPal** (alternative)
- Subscription management with recurring billing

**Chatbot**:
- **OpenAI GPT-4** with RAG (Retrieval-Augmented Generation)
- **Vector DB**: Pinecone or Weaviate for dataset embeddings
- **LangChain** for orchestration

**Monitoring**:
- **Prometheus** + **Grafana** (metrics)
- **Sentry** (error tracking)
- **Django Admin** (enhanced with custom views)

---

## 3. MongoDB Assessment: Keep vs. Migrate

### 3.1 Current MongoDB Implementation

**Integration Method**: PyMongo (direct, no ORM)
**Collections**:
- `users` - User credentials and profiles
- `runs` - Pipeline execution history

**Schema**:
```json
// users collection
{
  "_id": ObjectId,
  "username": "string",
  "password": "hashed_string",
  "email": "string",
  "full_name": "string",
  "roles": ["workspace-user"],
  "created_at": "ISODate",
  "updated_at": "ISODate"
}

// runs collection
{
  "_id": ObjectId,
  "token": "uuid",
  "dataset": "string",
  "table": "string",
  "owner_username": "string",
  "owner": {...},
  "started_at": "ISODate",
  "finished_at": "ISODate",
  "evaluation": {...},
  "generated_rows": "int",
  "epochs_vae": "int",
  "epochs_gnn": "int",
  "epochs_diff": "int",
  ...
}
```

### 3.2 Assessment: Keep MongoDB ✅

**Recommendation**: **Keep MongoDB and enhance**

**Rationale**:

**Pros of Keeping MongoDB**:
1. ✅ **Already Integrated** - Working PyMongo setup, no migration overhead
2. ✅ **Document Model Fit** - Flexible schema for runs, evaluations, metadata
3. ✅ **Scalability** - MongoDB Atlas auto-scaling, sharding support
4. ✅ **JSON-Native** - Aligns with pipeline JSON outputs
5. ✅ **Managed Services** - MongoDB Atlas is production-ready
6. ✅ **Good for Analytics** - Aggregation pipeline for admin dashboard
7. ✅ **No Schema Migrations** - Add fields without ALTER TABLE
8. ✅ **Fast Writes** - Good for high-frequency job status updates

**Cons of Migrating to PostgreSQL**:
1. ❌ **Migration Effort** - Rewrite auth, history, all queries
2. ❌ **Schema Rigidity** - Frequent migrations for evolving features
3. ❌ **JSON Handling** - JSONB less intuitive than native documents
4. ❌ **No Clear Benefit** - PostgreSQL offers no advantage for this use case

**Enhancements Needed**:
1. Add **indexes** for performance:
   ```python
   users.create_index("username", unique=True)
   users.create_index("email", unique=True)
   runs.create_index([("owner_username", 1), ("started_at", -1)])
   runs.create_index("token", unique=True)
   ```
2. Add new collections:
   - `subscriptions` - Billing and payment records
   - `jobs` - Celery job queue metadata
   - `api_keys` - API access tokens
   - `datasets` - Public dataset catalog (for chatbot)
3. Implement **MongoDB transactions** for critical operations
4. Use **MongoDB Atlas** for production (auto-scaling, backups)

### 3.3 Hybrid Database Strategy

**Primary Database**: MongoDB
**Purpose**: Users, jobs, runs, subscriptions, datasets

**Secondary Database**: Redis
**Purpose**: Caching, sessions, Celery broker, rate limiting

**File Storage**: S3/GCS
**Purpose**: Large files (CSVs, plots)

**Rationale**: Leverage strengths of each system without over-complicating.

---

## 4. Enhanced Database Schema Design

### 4.1 MongoDB Collections

#### **Collection: `users`** (Enhanced)
```javascript
{
  "_id": ObjectId,
  "username": "string",              // unique
  "email": "string",                 // unique
  "password": "hashed_string",       // Django PBKDF2
  "full_name": "string",

  // NEW: Tier Management
  "tier": "free" | "paid",           // user tier
  "subscription_status": "active" | "canceled" | "past_due" | null,
  "subscription_id": "string",       // Stripe subscription ID
  "customer_id": "string",           // Stripe customer ID

  // NEW: API Access
  "api_key": "hashed_string",        // optional API key
  "api_quota_monthly": 10,           // API calls per month
  "api_calls_this_month": 0,

  // NEW: Usage Tracking
  "jobs_submitted": 0,
  "jobs_completed": 0,
  "total_rows_generated": 0,

  // Metadata
  "roles": ["workspace-user"],
  "is_active": true,
  "email_verified": false,
  "created_at": ISODate,
  "updated_at": ISODate,
  "last_login": ISODate
}
```

**Indexes**:
```python
users.create_index("username", unique=True)
users.create_index("email", unique=True)
users.create_index("customer_id")
users.create_index([("tier", 1), ("subscription_status", 1)])
```

---

#### **Collection: `jobs`** (NEW - Celery Job Metadata)
```javascript
{
  "_id": ObjectId,
  "job_id": "celery-task-id",        // Celery task UUID
  "token": "uuid",                   // User-facing job token
  "owner_username": "string",
  "tier": "free" | "paid",

  // Job Configuration
  "dataset": "string",
  "table": "string",
  "data_source": "preloaded" | "uploaded",
  "upload_token": "string",          // if uploaded
  "epochs_vae": 10,
  "epochs_gnn": 10,
  "epochs_diff": 1,
  "enable_epoch_eval": false,

  // Execution State
  "status": "queued" | "running" | "completed" | "failed" | "canceled",
  "priority": 0-10,                  // 0=free, 5-10=paid
  "queue_name": "cpu" | "gpu",
  "worker_id": "string",
  "started_at": ISODate,
  "finished_at": ISODate,
  "queued_at": ISODate,
  "estimated_completion": ISODate,

  // Progress Tracking
  "progress_percent": 0,
  "current_stage": "preprocessing" | "training" | "sampling" | "evaluation",
  "current_epoch": 0,
  "total_epochs": 31,

  // Results
  "output_csv_path": "s3://bucket/...",
  "metadata_path": "s3://bucket/...",
  "log_file_path": "s3://bucket/...",
  "generated_rows": 5000,

  // Error Handling
  "error_message": "string",
  "retry_count": 0,
  "max_retries": 3,

  // Notifications
  "notification_sent": false,
  "notification_email": "string",

  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes**:
```python
jobs.create_index("job_id", unique=True)
jobs.create_index("token", unique=True)
jobs.create_index([("owner_username", 1), ("created_at", -1)])
jobs.create_index([("status", 1), ("priority", -1), ("queued_at", 1)])  # Queue processing
jobs.create_index([("tier", 1), ("status", 1)])
```

---

#### **Collection: `runs`** (Keep, Enhance)
Keep existing schema, add:
```javascript
{
  // ... existing fields ...

  // NEW: Link to job
  "job_id": "celery-task-id",

  // NEW: Evaluation metadata
  "evaluation": {
    "metrics": {
      "marginal_distribution_error": 0.05,
      "pairwise_correlation_error": 0.08,
      "f1_score": 0.92,
      // ... other metrics
    },
    "plot": {
      "data_uri": "base64...",
      "s3_path": "s3://bucket/plots/..."
    },
    "epoch_metrics": [...]  // if epoch eval enabled
  },

  // NEW: Performance tracking
  "execution_time_seconds": 450,
  "queue_wait_time_seconds": 30,
  "gpu_used": true,

  "recorded_at": ISODate
}
```

---

#### **Collection: `subscriptions`** (NEW)
```javascript
{
  "_id": ObjectId,
  "user_id": ObjectId,               // reference to users._id
  "username": "string",
  "stripe_subscription_id": "string",
  "stripe_customer_id": "string",
  "stripe_payment_method_id": "string",

  // Subscription Details
  "plan": "monthly" | "annual",
  "price_id": "string",              // Stripe price ID
  "status": "active" | "canceled" | "past_due" | "trialing",
  "current_period_start": ISODate,
  "current_period_end": ISODate,
  "cancel_at_period_end": false,

  // Billing
  "amount": 49.99,
  "currency": "USD",
  "billing_cycle_anchor": ISODate,

  // Trial
  "trial_start": ISODate,
  "trial_end": ISODate,

  // History
  "created_at": ISODate,
  "updated_at": ISODate,
  "canceled_at": ISODate
}
```

**Indexes**:
```python
subscriptions.create_index("user_id")
subscriptions.create_index("stripe_subscription_id", unique=True)
subscriptions.create_index([("status", 1), ("current_period_end", 1)])
```

---

#### **Collection: `datasets`** (NEW - For Chatbot)
```javascript
{
  "_id": ObjectId,
  "name": "MIMIC-III",
  "category": "clinical" | "genomic" | "patient_records",
  "description": "Large healthcare database with de-identified patient data...",
  "source": "PhysioNet",
  "url": "https://physionet.org/content/mimiciii/",
  "license": "PhysioNet Credentialed Health Data License",

  // Metadata
  "keywords": ["ICU", "EHR", "critical care", "mortality"],
  "data_types": ["time-series", "demographics", "diagnoses"],
  "num_records": 58000,
  "num_features": 200,
  "contains_phi": false,
  "access_requirements": "credentialed",

  // For RAG Chatbot
  "embedding": [0.1, 0.2, ...],      // Vector embedding
  "constraints": {
    "min_samples": 1000,
    "clinical_focus": true,
    "real_world_evidence": true
  },

  "created_at": ISODate,
  "updated_at": ISODate
}
```

**Indexes**:
```python
datasets.create_index("name")
datasets.create_index("category")
datasets.create_index("keywords")
datasets.create_index("embedding")  # Vector search (MongoDB Atlas Vector Search)
```

---

#### **Collection: `notifications`** (NEW)
```javascript
{
  "_id": ObjectId,
  "user_id": ObjectId,
  "username": "string",
  "type": "job_completed" | "job_failed" | "payment_failed" | "subscription_expiring",

  // Notification Content
  "title": "Your synthetic data is ready!",
  "message": "Job #abc123 completed successfully...",
  "link": "/result/abc123",

  // Delivery
  "channels": ["email", "in_app"],
  "email_sent": true,
  "email_sent_at": ISODate,
  "read": false,
  "read_at": ISODate,

  // Metadata
  "job_token": "uuid",
  "created_at": ISODate
}
```

---

### 4.2 Redis Data Structures

**Purpose**: Caching, sessions, Celery broker, rate limiting

**Key Patterns**:

1. **Sessions**: `session:{session_id}` → User session data
2. **Cache**: `cache:runs:{username}` → Recently fetched runs
3. **Rate Limiting**: `ratelimit:{user_id}:{endpoint}` → Request count
4. **Job Results**: `celery-task-meta-{task_id}` → Celery result backend
5. **Queue**: `celery:queue:cpu` / `celery:queue:gpu` → Task queues
6. **Progress**: `job:progress:{job_id}` → Real-time job progress

---

## 5. Celery Job Queue Architecture

### 5.1 Queue Design

**Queue Strategy**: Separate queues for tier-based prioritization

```python
# Queue Configuration
CELERY_TASK_ROUTES = {
    'synthetic.tasks.run_pipeline_cpu': {'queue': 'cpu', 'priority': 0},
    'synthetic.tasks.run_pipeline_gpu': {'queue': 'gpu', 'priority': 5},
}

# Worker Pools
# CPU Workers (Free Tier): 4 workers, CPU-only
celery -A tabgraphsyn_site worker -Q cpu --concurrency=4 --hostname=cpu@%h

# GPU Workers (Paid Tier): 2 workers, GPU access, higher priority
celery -A tabgraphsyn_site worker -Q gpu --concurrency=2 --hostname=gpu@%h
```

### 5.2 Celery Task Wrapper (Preserves TabGraphSyn)

**File**: `synthetic/tasks.py` (NEW)

```python
from celery import Task, shared_task
from .pipeline import execute_pipeline, PipelineParameters
from .job_tracker import job_tracker
import logging

class CallbackTask(Task):
    """Custom task with callbacks for progress tracking"""

    def on_success(self, retval, task_id, args, kwargs):
        # Send email notification
        pass

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        # Log error, notify user
        pass

@shared_task(bind=True, base=CallbackTask, max_retries=3)
def run_pipeline_cpu(self, job_token, params_dict):
    """
    Celery task wrapper for TabGraphSyn pipeline (CPU)

    This wrapper DOES NOT modify the TabGraphSyn pipeline.
    It only orchestrates execution and tracks progress.
    """
    params = PipelineParameters(**params_dict)

    # Update job status
    job_tracker.update_job(job_token, status='running', stage='preprocessing')

    try:
        # Call TabGraphSyn pipeline (UNCHANGED)
        result = execute_pipeline(
            params=params,
            progress_callback=lambda stage, pct:
                job_tracker.update_job(job_token, stage=stage, progress=pct)
        )

        job_tracker.update_job(job_token, status='completed', result=result)
        return result

    except Exception as e:
        job_tracker.update_job(job_token, status='failed', error=str(e))
        raise

@shared_task(bind=True, base=CallbackTask, max_retries=3)
def run_pipeline_gpu(self, job_token, params_dict):
    """GPU-accelerated version (paid tier)"""
    # Same as CPU, but worker has GPU access
    return run_pipeline_cpu.apply(args=(job_token, params_dict))
```

### 5.3 Priority System

**Free Tier**: Priority 0, CPU queue, FIFO
**Paid Tier**: Priority 5-10, GPU queue, priority-based

**Celery Configuration**:
```python
CELERY_TASK_ACKS_LATE = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1  # Fetch one task at a time
CELERY_TASK_REJECT_ON_WORKER_LOST = True
```

---

## 6. GPU Infrastructure Recommendations

### 6.1 Hardware Requirements

**TabGraphSyn Pipeline Needs**:
- **VRAM**: 8-12GB (minimum), 16-24GB (recommended for large datasets)
- **Compute**: CUDA 11.8+, Tensor Cores beneficial
- **CPU**: 8+ cores (for parallel preprocessing)
- **RAM**: 16-32GB
- **Storage**: 500GB SSD (for datasets, temp files)

### 6.2 Cloud GPU Options

#### **Option 1: AWS EC2 (Recommended for Startups)**

| Instance Type | GPU | VRAM | vCPU | RAM | On-Demand | Spot (avg) |
|---------------|-----|------|------|-----|-----------|------------|
| **g5.xlarge** | A10G | 24GB | 4 | 16GB | $1.01/hr | $0.30/hr |
| **g5.2xlarge** | A10G | 24GB | 8 | 32GB | $1.21/hr | $0.36/hr |
| g4dn.xlarge | T4 | 16GB | 4 | 16GB | $0.52/hr | $0.16/hr |

**Recommendation**: Start with **g5.xlarge Spot instances** ($0.30/hr = $220/month @ 100% utilization)

**Pros**:
- Spot pricing = 70% cost savings
- A10G GPUs are powerful (24GB VRAM)
- Easy auto-scaling with EC2 Auto Scaling Groups
- Mature ecosystem (CloudWatch, IAM, VPC)

**Cons**:
- Spot instances can be interrupted (use checkpointing)
- Requires AWS expertise

---

#### **Option 2: Google Cloud Platform**

| Instance Type | GPU | VRAM | vCPU | RAM | On-Demand | Preemptible |
|---------------|-----|------|------|-----|-----------|-------------|
| **n1-standard-4 + T4** | T4 | 16GB | 4 | 15GB | $0.47/hr | $0.14/hr |
| n1-standard-8 + V100 | V100 | 16GB | 8 | 30GB | $2.48/hr | $0.74/hr |

**Recommendation**: T4 with preemptible instances ($0.14/hr)

---

#### **Option 3: Azure**

| Instance Type | GPU | VRAM | vCPU | RAM | On-Demand | Spot |
|---------------|-----|------|------|-----|-----------|------|
| NC6s v3 | V100 | 16GB | 6 | 112GB | $3.06/hr | $0.92/hr |
| NC4as T4 v3 | T4 | 16GB | 4 | 28GB | $0.53/hr | $0.16/hr |

---

#### **Option 4: Specialized GPU Cloud (Lambda Labs, RunPod)**

**Lambda Labs**:
- **A10 (24GB)**: $0.60/hr on-demand
- **RTX 3090 (24GB)**: $0.50/hr
- No spot pricing, but lower base costs

**RunPod**:
- **RTX 4090 (24GB)**: $0.44/hr
- **A40 (48GB)**: $0.79/hr

**Pros**: Cheaper, GPU-focused, simple interface
**Cons**: Less mature, limited regions, no enterprise SLA

---

### 6.3 Recommended GPU Strategy for MVP

**Phase 1 (MVP - Months 1-3)**:
- **Development**: Local CPU (laptop/desktop)
- **Testing**: AWS g5.xlarge Spot (on-demand when needed)
- **Production**: 1x g5.xlarge Spot + auto-scaling (paid tier only)
- **Free Tier**: CPU-only on Django web server

**Phase 2 (Growth - Months 4-12)**:
- **Paid Tier**: 2-4x g5.xlarge Spot instances with auto-scaling
- **Free Tier**: Dedicated CPU worker pool (t3.xlarge)
- **Monitoring**: CloudWatch GPU utilization metrics

**Cost Estimate**:
- **Phase 1**: $150-300/month (GPU + storage)
- **Phase 2**: $500-1000/month (multi-GPU + redundancy)

---

## 7. Implementation Roadmap

### 7.1 Milestone 1: Foundation (Weeks 1-2)

**Goals**: Set up async infrastructure, enhance MongoDB

**Tasks**:
1. ✅ Install Celery, Redis, Flower (monitoring)
2. ✅ Create enhanced MongoDB schema (users, jobs, subscriptions)
3. ✅ Migrate existing code to use new `jobs` collection
4. ✅ Implement tier management in user model
5. ✅ Create Celery task wrapper for TabGraphSyn (CPU-only)
6. ✅ Test async job execution locally

**Deliverables**:
- Celery workers running
- Jobs executing asynchronously
- MongoDB schema updated

---

### 7.2 Milestone 2: User Management & Auth (Weeks 3-4)

**Goals**: Tier system, subscription tracking

**Tasks**:
1. Add tier field to user registration
2. Create subscription management views
3. Implement tier-based access control decorators
4. Add usage tracking (jobs submitted, rows generated)
5. Create user profile page

**Deliverables**:
- Free vs. Paid tier differentiation
- User dashboard with usage stats

---

### 7.3 Milestone 3: Payment Integration (Weeks 5-6)

**Goals**: Stripe integration for paid tier

**Tasks**:
1. Create Stripe account, get API keys
2. Implement Stripe Checkout for subscription
3. Create webhook handlers for subscription events
4. Build subscription management UI (upgrade, cancel)
5. Add payment history page

**Deliverables**:
- Working payment flow
- Subscription auto-renewal
- Webhook handling

---

### 7.4 Milestone 4: Notifications (Week 7)

**Goals**: Email notifications for job completion

**Tasks**:
1. Set up SendGrid account
2. Create email templates (job completed, job failed)
3. Implement Celery task callbacks for emails
4. Add notification preferences to user profile
5. Test email delivery

**Deliverables**:
- Email notifications working
- Professional email templates

---

### 7.5 Milestone 5: Admin Dashboard (Week 8)

**Goals**: Monitoring and management interface

**Tasks**:
1. Enhance Django Admin with custom views
2. Add job queue monitoring (Celery Flower integration)
3. Create user management interface
4. Add analytics dashboard (jobs/day, revenue, errors)
5. Implement manual job cancellation

**Deliverables**:
- Admin dashboard accessible
- Real-time job monitoring

---

### 7.6 Milestone 6: GPU Integration (Week 9)

**Goals**: GPU worker pool for paid tier

**Tasks**:
1. Provision AWS g5.xlarge Spot instance
2. Set up GPU-enabled Celery worker
3. Configure GPU queue routing
4. Test TabGraphSyn with GPU acceleration
5. Implement fallback to CPU if GPU unavailable

**Deliverables**:
- GPU workers processing paid tier jobs
- Performance benchmarks (CPU vs. GPU)

---

### 7.7 Milestone 7: UI/UX Improvements (Week 10)

**Goals**: Better user experience, progress tracking

**Tasks**:
1. Add WebSockets or Server-Sent Events for real-time updates
2. Improve upload form UI (drag-and-drop)
3. Add progress bars with stage indicators
4. Enhance result page with better visualizations
5. Make responsive for mobile

**Deliverables**:
- Modern, polished UI
- Real-time progress updates

---

### 7.8 Milestone 8: Chatbot (Weeks 11-12)

**Goals**: AI-powered dataset recommendation

**Tasks**:
1. Curate clinical dataset catalog (50-100 datasets)
2. Generate embeddings with OpenAI
3. Store in MongoDB Atlas Vector Search
4. Build chatbot API endpoint
5. Integrate chatbot UI (paid tier only)

**Deliverables**:
- Working chatbot for dataset search
- 50+ clinical datasets indexed

---

### 7.9 Milestone 9: Production Deployment (Week 13-14)

**Goals**: Deploy to production environment

**Tasks**:
1. Set up production infrastructure (AWS/GCP)
2. Configure MongoDB Atlas
3. Set up nginx + Gunicorn
4. Implement SSL certificates (Let's Encrypt)
5. Configure backups and monitoring
6. Set up CI/CD pipeline (GitHub Actions)

**Deliverables**:
- Production environment live
- Automated deployments
- Monitoring and alerting

---

### 7.10 Milestone 10: Testing & Launch (Week 15-16)

**Goals**: Comprehensive testing, beta launch

**Tasks**:
1. End-to-end testing (free and paid flows)
2. Load testing (simulate 100 concurrent users)
3. Security audit (OWASP top 10)
4. Beta user onboarding
5. Marketing materials (landing page, docs)

**Deliverables**:
- Beta launch
- Documentation complete
- Pricing page live

---

## 8. Cost Analysis

### 8.1 Infrastructure Costs (Monthly)

**Startup Phase (Months 1-6)**:

| Service | Tier | Cost |
|---------|------|------|
| **AWS EC2 Web** | t3.medium (2 vCPU, 4GB) | $30 |
| **AWS EC2 CPU Workers** | t3.xlarge (4 vCPU, 16GB) | $60 |
| **AWS EC2 GPU Workers** | g5.xlarge Spot (20% uptime) | $45 |
| **MongoDB Atlas** | M10 (2GB RAM, backup) | $57 |
| **Redis** | ElastiCache t3.micro | $12 |
| **S3 Storage** | 100GB + transfer | $25 |
| **SendGrid** | 100k emails/month | $20 |
| **Domain + SSL** | Route53, Cert Manager | $5 |
| **Monitoring** | CloudWatch, Sentry | $20 |
| **TOTAL** | | **$274/month** |

**Growth Phase (Months 7-12)**:

| Service | Tier | Cost |
|---------|------|------|
| **AWS EC2 Web** | t3.large (2 vCPU, 8GB) x2 | $120 |
| **AWS EC2 CPU Workers** | t3.xlarge x2 | $120 |
| **AWS EC2 GPU Workers** | g5.xlarge Spot (50% uptime) | $110 |
| **MongoDB Atlas** | M30 (8GB RAM, replica set) | $390 |
| **Redis** | ElastiCache t3.medium | $50 |
| **S3 Storage** | 500GB + transfer | $60 |
| **SendGrid** | 500k emails/month | $60 |
| **Load Balancer** | ALB | $25 |
| **Monitoring** | Enhanced | $50 |
| **TOTAL** | | **$985/month** |

### 8.2 External Services

| Service | Free Tier | Paid Tier |
|---------|-----------|-----------|
| **Stripe** | 2.9% + $0.30/transaction | Same |
| **OpenAI API** | N/A | $0.03/1k tokens (chatbot) |
| **Twilio SMS** | N/A | $0.0075/SMS (optional) |

### 8.3 Revenue Projections

**Pricing Strategy**:
- **Free Tier**: $0/month (CPU-only, queue, email notifications)
- **Paid Tier**: $49/month (GPU, priority queue, chatbot, faster processing)

**Break-even Analysis**:
- Startup Phase: Need **6 paid users** to cover costs ($274 / $49)
- Growth Phase: Need **21 paid users** to cover costs ($985 / $49)

---

## 9. Security Considerations

### 9.1 Current Issues (Development)

- ❌ `DEBUG = True` (exposes sensitive errors)
- ❌ Insecure `SECRET_KEY`
- ❌ `ALLOWED_HOSTS = []` (allows all)
- ❌ No HTTPS enforcement
- ❌ No CSRF protection for API endpoints
- ❌ No rate limiting
- ❌ No input validation on file uploads

### 9.2 Production Security Checklist

**Django Settings**:
```python
DEBUG = False
SECRET_KEY = os.getenv('SECRET_KEY')  # Strong, random
ALLOWED_HOSTS = ['tabgraphsyn.com', 'www.tabgraphsyn.com']
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = 31536000
```

**Additional Measures**:
1. ✅ HTTPS everywhere (Let's Encrypt)
2. ✅ Rate limiting (django-ratelimit or nginx)
3. ✅ File upload validation (CSV only, max 100MB, virus scan)
4. ✅ SQL injection protection (parameterized queries - already using PyMongo)
5. ✅ XSS protection (escape HTML in templates)
6. ✅ CORS headers (django-cors-headers)
7. ✅ Security headers (django-security)
8. ✅ Dependency scanning (Dependabot, Snyk)

---

## 10. Risks & Mitigations

### 10.1 Technical Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Spot instance interruption** | Medium | Medium | Checkpointing, auto-restart |
| **MongoDB Atlas downtime** | Low | High | Multi-region replica set |
| **Celery worker crashes** | Medium | Medium | Auto-restart, health checks |
| **File storage corruption** | Low | High | S3 versioning, backups |
| **GPU out of memory** | Medium | Medium | Dynamic batch sizing, fallback to CPU |
| **Payment fraud** | Medium | High | Stripe Radar, manual review |

### 10.2 Business Risks

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| **Low user adoption** | Medium | High | MVP testing, user interviews |
| **High infrastructure costs** | Medium | Medium | Auto-scaling, cost monitoring |
| **Competitor undercutting** | Low | Medium | Differentiate on quality, features |
| **Regulatory compliance** | Low | High | HIPAA/GDPR audit (if handling PHI) |

---

## 11. Scalability Path

### 11.1 Current Capacity

- **Web**: ~50 concurrent users (single Django instance)
- **Jobs**: ~4 concurrent CPU jobs, ~2 GPU jobs
- **Storage**: Limited by local disk

### 11.2 Scaling Strategy

**100 Users**:
- 2x Django web servers (load balanced)
- 4x CPU workers, 2x GPU workers
- MongoDB Atlas M30
- S3 for file storage

**1,000 Users**:
- 5x Django web servers (auto-scaling)
- 10x CPU workers, 5x GPU workers (auto-scaling)
- MongoDB Atlas M60 (sharded cluster)
- CDN for static assets (CloudFront)
- Multi-region deployment

**10,000 Users**:
- Kubernetes orchestration (EKS/GKE)
- 50+ workers (auto-scaling)
- MongoDB Atlas M200+
- Microservices architecture (separate API, workers, chatbot)
- Global load balancing

---

## 12. Conclusion

**Feasibility**: ✅ **HIGHLY FEASIBLE**

**Key Strengths**:
- Solid foundation with working Django + MongoDB + TabGraphSyn
- Clear separation between web tier and pipeline (easy to async-ify)
- MongoDB is the right choice (keep and enhance)
- TabGraphSyn pipeline already isolated (easy to wrap)

**Critical Path**:
1. Implement Celery + Redis (2 weeks)
2. Add tier management (2 weeks)
3. Integrate Stripe (2 weeks)
4. Add notifications (1 week)
5. Build admin dashboard (1 week)
6. Add GPU workers (1 week)
7. Polish UI (1 week)
8. Deploy to production (2 weeks)

**Timeline**: 12-16 weeks to production-ready MVP

**Cost**: $274/month (startup) → $985/month (growth)

**Break-even**: 6 paid users ($49/month)

**Next Steps**:
1. Approve architecture and roadmap
2. Start Milestone 1 (Celery + Redis setup)
3. Provision development infrastructure
4. Begin iterative implementation

---

**Report Prepared By**: Claude Code
**Date**: November 17, 2025
**Version**: 1.0
