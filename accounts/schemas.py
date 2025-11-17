"""
MongoDB Document Schemas

Dataclasses representing MongoDB document structures.
These are NOT ORM models - just type hints for document structure.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any


@dataclass
class UserDocument:
    """User document schema"""
    username: str
    email: str
    password: str  # Django hashed password
    full_name: str = ''

    # Tier Management
    tier: str = 'free'  # 'free' or 'paid'
    subscription_status: Optional[str] = None  # 'active', 'canceled', 'past_due', None
    subscription_id: Optional[str] = None  # Stripe subscription ID
    customer_id: Optional[str] = None  # Stripe customer ID

    # API Access
    api_key: Optional[str] = None
    api_quota_monthly: int = 10
    api_calls_this_month: int = 0

    # Usage Tracking
    jobs_submitted: int = 0
    jobs_completed: int = 0
    total_rows_generated: int = 0

    # Metadata
    roles: List[str] = field(default_factory=lambda: ['workspace-user'])
    is_active: bool = True
    email_verified: bool = False
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    last_login: Optional[datetime] = None


@dataclass
class JobDocument:
    """Job document schema (Celery task metadata)"""
    job_id: str  # Celery task UUID
    token: str  # User-facing job token
    owner_username: str
    tier: str  # 'free' or 'paid'

    # Job Configuration
    dataset: str
    table: str
    data_source: str  # 'preloaded' or 'uploaded'
    upload_token: Optional[str] = None
    epochs_vae: int = 10
    epochs_gnn: int = 10
    epochs_diff: int = 1
    enable_epoch_eval: bool = False

    # Execution State
    status: str = 'queued'  # 'queued', 'running', 'completed', 'failed', 'canceled'
    priority: int = 0  # 0=free, 5-10=paid
    queue_name: str = 'cpu'  # 'cpu' or 'gpu'
    worker_id: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    queued_at: Optional[datetime] = None
    estimated_completion: Optional[datetime] = None

    # Progress Tracking
    progress_percent: int = 0
    current_stage: str = 'queued'  # 'preprocessing', 'training', 'sampling', 'evaluation'
    current_epoch: int = 0
    total_epochs: int = 0

    # Results
    output_csv_path: Optional[str] = None
    metadata_path: Optional[str] = None
    log_file_path: Optional[str] = None
    generated_rows: int = 0

    # Error Handling
    error_message: Optional[str] = None
    retry_count: int = 0
    max_retries: int = 3

    # Notifications
    notification_sent: bool = False
    notification_email: Optional[str] = None

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


@dataclass
class RunDocument:
    """Run document schema (enhanced existing schema)"""
    token: str
    dataset: str
    table: str
    owner_username: str
    owner: Dict[str, Any]

    # Timestamps
    started_at: datetime
    finished_at: Optional[datetime] = None
    recorded_at: Optional[datetime] = None

    # Configuration
    run_name: str = 'single_table'
    data_source: str = 'preloaded'
    generated_rows: int = 0
    epochs_vae: int = 10
    epochs_gnn: int = 10
    epochs_diff: int = 1

    # Link to job
    job_id: Optional[str] = None

    # Evaluation
    evaluation: Optional[Dict[str, Any]] = None

    # Performance tracking
    execution_time_seconds: Optional[float] = None
    queue_wait_time_seconds: Optional[float] = None
    gpu_used: bool = False

    # Logs and output
    log_file: Optional[str] = None
    output_csv: Optional[str] = None
    logs: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class SubscriptionDocument:
    """Subscription document schema"""
    user_id: str  # MongoDB ObjectId as string
    username: str
    stripe_subscription_id: str
    stripe_customer_id: str
    stripe_payment_method_id: Optional[str] = None

    # Subscription Details
    plan: str = 'monthly'  # 'monthly' or 'annual'
    price_id: str = ''
    status: str = 'active'  # 'active', 'canceled', 'past_due', 'trialing'
    current_period_start: Optional[datetime] = None
    current_period_end: Optional[datetime] = None
    cancel_at_period_end: bool = False

    # Billing
    amount: float = 0.0
    currency: str = 'USD'
    billing_cycle_anchor: Optional[datetime] = None

    # Trial
    trial_start: Optional[datetime] = None
    trial_end: Optional[datetime] = None

    # History
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    canceled_at: Optional[datetime] = None


@dataclass
class NotificationDocument:
    """Notification document schema"""
    user_id: str  # MongoDB ObjectId as string
    username: str
    type: str  # 'job_completed', 'job_failed', 'payment_failed', 'subscription_expiring'

    # Content
    title: str
    message: str
    link: Optional[str] = None

    # Delivery
    channels: List[str] = field(default_factory=lambda: ['email', 'in_app'])
    email_sent: bool = False
    email_sent_at: Optional[datetime] = None
    read: bool = False
    read_at: Optional[datetime] = None

    # Metadata
    job_token: Optional[str] = None
    created_at: Optional[datetime] = None


@dataclass
class DatasetDocument:
    """Dataset document schema (for chatbot)"""
    name: str
    category: str  # 'clinical', 'genomic', 'patient_records'
    description: str
    source: str
    url: str
    license: str

    # Metadata
    keywords: List[str] = field(default_factory=list)
    data_types: List[str] = field(default_factory=list)
    num_records: int = 0
    num_features: int = 0
    contains_phi: bool = False
    access_requirements: str = 'public'

    # For RAG Chatbot
    embedding: Optional[List[float]] = None  # Vector embedding for similarity search
    constraints: Dict[str, Any] = field(default_factory=dict)

    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
