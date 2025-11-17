"""
Celery Tasks for TabGraphSyn Pipeline Execution

IMPORTANT: These tasks wrap the TabGraphSyn pipeline without modifying it.
The pipeline is treated as a black box - we only orchestrate execution.
"""

import logging
import time
import uuid
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from celery import Task, shared_task
from django.conf import settings
from django.core.mail import send_mail

from accounts.mongo import get_jobs_collection, get_runs_collection, get_notifications_collection, get_users_collection
from .pipeline import execute_pipeline, PipelineParameters
from .evaluation import compute_evaluation_metrics

logger = logging.getLogger(__name__)


class JobTask(Task):
    """
    Custom Celery task base class with lifecycle callbacks
    """

    def on_success(self, retval, task_id, args, kwargs):
        """Called when task succeeds"""
        logger.info(f'Task {task_id} completed successfully')
        job_token = kwargs.get('job_token') or (args[0] if args else None)
        if job_token:
            self._send_completion_notification(job_token, success=True)

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """Called when task fails"""
        logger.error(f'Task {task_id} failed: {exc}')
        job_token = kwargs.get('job_token') or (args[0] if args else None)
        if job_token:
            self._update_job_failed(job_token, str(exc))
            self._send_completion_notification(job_token, success=False, error=str(exc))

    def _send_completion_notification(self, job_token: str, success: bool, error: Optional[str] = None):
        """Send email notification on job completion/failure"""
        try:
            jobs = get_jobs_collection()
            job = jobs.find_one({'token': job_token})
            if not job:
                return

            # Check if email notifications are enabled
            if not settings.NOTIFICATION_EMAIL_ENABLED:
                logger.info(f'Email notifications disabled, skipping for job {job_token}')
                return

            # Get user email
            users = get_users_collection()
            user = users.find_one({'username': job['owner_username']})
            if not user or not user.get('email'):
                logger.warning(f'No email found for user {job["owner_username"]}')
                return

            # Prepare email content
            if success:
                subject = f'✅ Your synthetic data is ready! - TabGraphSyn'
                message = f"""
Hello {user.get('full_name', job['owner_username'])},

Your synthetic data generation job has completed successfully!

Dataset: {job['dataset']}
Generated Rows: {job.get('generated_rows', 'N/A')}

View your results here:
{settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'http://localhost:8000'}/result/{job_token}/

Thank you for using TabGraphSyn!

---
TabGraphSyn Team
                """
            else:
                subject = f'❌ Job failed - TabGraphSyn'
                message = f"""
Hello {user.get('full_name', job['owner_username'])},

Unfortunately, your synthetic data generation job has failed.

Dataset: {job['dataset']}
Error: {error}

Please try again or contact support if the issue persists.

---
TabGraphSyn Team
                """

            # Send email
            send_mail(
                subject=subject,
                message=message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[user['email']],
                fail_silently=True,
            )

            # Store notification in MongoDB
            notifications = get_notifications_collection()
            notifications.insert_one({
                'user_id': str(user['_id']),
                'username': job['owner_username'],
                'type': 'job_completed' if success else 'job_failed',
                'title': subject,
                'message': message,
                'link': f'/result/{job_token}/',
                'channels': ['email', 'in_app'],
                'email_sent': True,
                'email_sent_at': datetime.utcnow(),
                'read': False,
                'job_token': job_token,
                'created_at': datetime.utcnow(),
            })

            # Update job
            jobs.update_one(
                {'token': job_token},
                {'$set': {'notification_sent': True, 'notification_email': user['email']}}
            )

            logger.info(f'Notification sent to {user["email"]} for job {job_token}')

        except Exception as e:
            logger.error(f'Failed to send notification for job {job_token}: {e}')

    def _update_job_failed(self, job_token: str, error: str):
        """Update job status to failed"""
        try:
            jobs = get_jobs_collection()
            jobs.update_one(
                {'token': job_token},
                {
                    '$set': {
                        'status': 'failed',
                        'error_message': error,
                        'finished_at': datetime.utcnow(),
                        'updated_at': datetime.utcnow(),
                    }
                }
            )
        except Exception as e:
            logger.error(f'Failed to update job {job_token} as failed: {e}')


@shared_task(bind=True, base=JobTask, max_retries=3, default_retry_delay=60)
def run_pipeline_cpu(self, job_token: str, params_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute TabGraphSyn pipeline on CPU worker (FREE TIER)

    This task wraps the TabGraphSyn pipeline WITHOUT modifying it.
    It only handles:
    - Job state management
    - Progress tracking
    - Error handling
    - Result storage

    Args:
        job_token: Unique job token for tracking
        params_dict: Pipeline parameters dictionary

    Returns:
        dict: Job result with output paths and metadata
    """
    logger.info(f'[CPU Worker] Starting job {job_token}')

    jobs = get_jobs_collection()
    runs = get_runs_collection()
    users = get_users_collection()

    try:
        # Update job status to running
        start_time = time.time()
        jobs.update_one(
            {'token': job_token},
            {
                '$set': {
                    'status': 'running',
                    'started_at': datetime.utcnow(),
                    'worker_id': self.request.id,
                    'current_stage': 'preprocessing',
                    'updated_at': datetime.utcnow(),
                }
            }
        )

        # Convert params dict to PipelineParameters
        params = PipelineParameters(**params_dict)

        # Progress callback to update job state
        def progress_callback(stage: str, progress_percent: int, current_epoch: int = 0):
            """Update job progress in MongoDB"""
            try:
                jobs.update_one(
                    {'token': job_token},
                    {
                        '$set': {
                            'current_stage': stage,
                            'progress_percent': progress_percent,
                            'current_epoch': current_epoch,
                            'updated_at': datetime.utcnow(),
                        }
                    }
                )
                logger.info(f'[Job {job_token}] {stage}: {progress_percent}%')
            except Exception as e:
                logger.error(f'Failed to update progress for job {job_token}: {e}')

        # Execute TabGraphSyn pipeline (BLACK BOX - NOT MODIFIED)
        logger.info(f'[Job {job_token}] Calling TabGraphSyn pipeline...')
        progress_callback('training', 10)

        result = execute_pipeline(
            params=params,
            # Note: Current execute_pipeline may not support callbacks - that's OK
            # We can still track stages manually
        )

        progress_callback('sampling', 60)

        # Compute evaluation metrics
        progress_callback('evaluation', 80)
        evaluation_result = None
        if result.get('output_csv'):
            try:
                from .evaluation import compute_evaluation_metrics
                evaluation_result = compute_evaluation_metrics(
                    original_path=result.get('original_csv', ''),
                    synthetic_path=result['output_csv'],
                    metadata=result.get('metadata', {})
                )
            except Exception as e:
                logger.warning(f'Evaluation failed for job {job_token}: {e}')

        progress_callback('finalizing', 95)

        # Calculate execution time
        execution_time = time.time() - start_time

        # Get queue wait time (difference between queued_at and started_at)
        job = jobs.find_one({'token': job_token})
        queue_wait_time = 0
        if job and job.get('queued_at') and job.get('started_at'):
            queue_wait_time = (job['started_at'] - job['queued_at']).total_seconds()

        # Update job status to completed
        jobs.update_one(
            {'token': job_token},
            {
                '$set': {
                    'status': 'completed',
                    'progress_percent': 100,
                    'current_stage': 'completed',
                    'finished_at': datetime.utcnow(),
                    'output_csv_path': result.get('output_csv', ''),
                    'metadata_path': result.get('metadata_path', ''),
                    'log_file_path': result.get('log_file', ''),
                    'generated_rows': result.get('num_rows', 0),
                    'updated_at': datetime.utcnow(),
                }
            }
        )

        # Store run in runs collection (for history)
        run_doc = {
            'token': job_token,
            'job_id': self.request.id,
            'dataset': params.dataset,
            'table': params.table,
            'owner_username': job['owner_username'],
            'owner': job.get('owner', {}),
            'data_source': job.get('data_source', 'preloaded'),
            'started_at': job.get('started_at'),
            'finished_at': datetime.utcnow(),
            'generated_rows': result.get('num_rows', 0),
            'epochs_vae': params.epochs_vae,
            'epochs_gnn': params.epochs_gnn,
            'epochs_diff': params.epochs_diff,
            'evaluation': evaluation_result,
            'execution_time_seconds': execution_time,
            'queue_wait_time_seconds': queue_wait_time,
            'gpu_used': False,  # CPU worker
            'output_csv': result.get('output_csv', ''),
            'log_file': result.get('log_file', ''),
            'recorded_at': datetime.utcnow(),
        }
        runs.insert_one(run_doc)

        # Update user stats
        users.update_one(
            {'username': job['owner_username']},
            {
                '$inc': {
                    'jobs_completed': 1,
                    'total_rows_generated': result.get('num_rows', 0),
                }
            }
        )

        logger.info(f'[Job {job_token}] Completed successfully in {execution_time:.1f}s')

        return {
            'success': True,
            'job_token': job_token,
            'output_csv': result.get('output_csv', ''),
            'generated_rows': result.get('num_rows', 0),
            'execution_time': execution_time,
        }

    except Exception as exc:
        logger.error(f'[Job {job_token}] Failed: {exc}')

        # Update job status to failed
        jobs.update_one(
            {'token': job_token},
            {
                '$set': {
                    'status': 'failed',
                    'error_message': str(exc),
                    'finished_at': datetime.utcnow(),
                    'updated_at': datetime.utcnow(),
                },
                '$inc': {'retry_count': 1}
            }
        )

        # Retry if not exceeded max retries
        job = jobs.find_one({'token': job_token})
        if job and job.get('retry_count', 0) < job.get('max_retries', 3):
            logger.info(f'[Job {job_token}] Retrying... (attempt {job["retry_count"] + 1})')
            raise self.retry(exc=exc)

        raise


@shared_task(bind=True, base=JobTask, max_retries=3, default_retry_delay=60)
def run_pipeline_gpu(self, job_token: str, params_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Execute TabGraphSyn pipeline on GPU worker (PAID TIER)

    Identical to CPU task, but runs on GPU worker with GPU access.

    Args:
        job_token: Unique job token for tracking
        params_dict: Pipeline parameters dictionary

    Returns:
        dict: Job result with output paths and metadata
    """
    logger.info(f'[GPU Worker] Starting job {job_token}')

    # Update job to indicate GPU usage
    jobs = get_jobs_collection()
    jobs.update_one(
        {'token': job_token},
        {'$set': {'queue_name': 'gpu'}}
    )

    # Execute the same logic as CPU task
    # The only difference is this worker has GPU access
    result = run_pipeline_cpu(self, job_token, params_dict)

    # Mark GPU usage
    jobs.update_one(
        {'token': job_token},
        {'$set': {'gpu_used': True}}
    )
    get_runs_collection().update_one(
        {'token': job_token},
        {'$set': {'gpu_used': True}}
    )

    return result


@shared_task
def cleanup_expired_jobs():
    """
    Periodic task to clean up old completed/failed jobs

    Runs every hour via Celery Beat
    """
    logger.info('Running cleanup_expired_jobs...')

    try:
        jobs = get_jobs_collection()

        # Delete jobs older than 7 days if completed or failed
        cutoff_date = datetime.utcnow() - timedelta(days=7)

        result = jobs.delete_many({
            'status': {'$in': ['completed', 'failed', 'canceled']},
            'finished_at': {'$lt': cutoff_date}
        })

        logger.info(f'Deleted {result.deleted_count} expired jobs')

    except Exception as e:
        logger.error(f'Failed to cleanup expired jobs: {e}')


@shared_task
def send_subscription_expiry_reminders():
    """
    Periodic task to send subscription expiry reminders

    Runs daily via Celery Beat
    """
    logger.info('Running send_subscription_expiry_reminders...')

    try:
        from accounts.mongo import get_subscriptions_collection

        subscriptions = get_subscriptions_collection()

        # Find subscriptions expiring in 7 days
        seven_days_from_now = datetime.utcnow() + timedelta(days=7)
        eight_days_from_now = datetime.utcnow() + timedelta(days=8)

        expiring_subs = subscriptions.find({
            'status': 'active',
            'cancel_at_period_end': True,
            'current_period_end': {
                '$gte': seven_days_from_now,
                '$lt': eight_days_from_now
            }
        })

        for sub in expiring_subs:
            # Send reminder email
            users = get_users_collection()
            user = users.find_one({'username': sub['username']})
            if user and user.get('email'):
                send_mail(
                    subject='Your TabGraphSyn subscription expires in 7 days',
                    message=f"""
Hello {user.get('full_name', sub['username'])},

Your TabGraphSyn Pro subscription will expire on {sub['current_period_end'].strftime('%Y-%m-%d')}.

To continue enjoying GPU-accelerated processing and premium features, please renew your subscription:
{settings.SITE_URL if hasattr(settings, 'SITE_URL') else 'http://localhost:8000'}/account/subscription/

Thank you for using TabGraphSyn!

---
TabGraphSyn Team
                    """,
                    from_email=settings.DEFAULT_FROM_EMAIL,
                    recipient_list=[user['email']],
                    fail_silently=True,
                )

                logger.info(f'Sent expiry reminder to {user["email"]}')

    except Exception as e:
        logger.error(f'Failed to send subscription expiry reminders: {e}')
