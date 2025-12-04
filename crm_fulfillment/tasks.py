"""
Core Celery tasks for Atlas CRM system
"""
from celery import shared_task
from django.conf import settings
from django.core.management import call_command
from datetime import datetime
import os
import subprocess
import logging

logger = logging.getLogger('atlas_crm')


@shared_task(bind=True, max_retries=3)
def backup_database(self):
    """
    Automated database backup task
    Runs daily at 2 AM
    """
    try:
        backup_dir = os.path.join(settings.BASE_DIR, 'backups')
        os.makedirs(backup_dir, exist_ok=True)

        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = os.path.join(backup_dir, f'atlas_crm_backup_{timestamp}.sql')

        # Get database settings
        db_settings = settings.DATABASES['default']

        if db_settings['ENGINE'] == 'django.db.backends.postgresql':
            # PostgreSQL backup
            env = os.environ.copy()
            env['PGPASSWORD'] = db_settings['PASSWORD']

            cmd = [
                'pg_dump',
                '-h', db_settings['HOST'],
                '-p', str(db_settings['PORT']),
                '-U', db_settings['USER'],
                '-d', db_settings['NAME'],
                '-f', backup_file,
                '--no-owner',
                '--no-acl',
            ]

            result = subprocess.run(cmd, env=env, capture_output=True, text=True)

            if result.returncode != 0:
                logger.error(f"Database backup failed: {result.stderr}")
                raise Exception(f"Backup failed: {result.stderr}")

            # Compress the backup
            subprocess.run(['gzip', backup_file], check=True)
            backup_file += '.gz'

            # Clean old backups (keep last 7 days)
            cleanup_old_backups(backup_dir, days=7)

            logger.info(f"Database backup completed: {backup_file}")
            return {'status': 'success', 'file': backup_file}

        return {'status': 'skipped', 'reason': 'Non-PostgreSQL database'}

    except Exception as e:
        logger.error(f"Database backup task failed: {str(e)}")
        self.retry(exc=e, countdown=60 * 5)  # Retry in 5 minutes


def cleanup_old_backups(backup_dir, days=7):
    """Remove backup files older than specified days"""
    import glob
    from datetime import timedelta

    cutoff = datetime.now() - timedelta(days=days)

    for backup_file in glob.glob(os.path.join(backup_dir, 'atlas_crm_backup_*.sql.gz')):
        file_time = datetime.fromtimestamp(os.path.getmtime(backup_file))
        if file_time < cutoff:
            os.remove(backup_file)
            logger.info(f"Removed old backup: {backup_file}")


@shared_task
def send_email_async(subject, message, from_email, recipient_list, html_message=None):
    """
    Async email sending task
    """
    from django.core.mail import send_mail

    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"Email sent successfully to {recipient_list}")
        return {'status': 'success', 'recipients': recipient_list}
    except Exception as e:
        logger.error(f"Failed to send email: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def generate_report_async(report_type, params=None):
    """
    Generate reports asynchronously
    """
    from django.utils import timezone

    params = params or {}

    try:
        if report_type == 'daily_orders':
            from orders.reports import generate_daily_orders_report
            return generate_daily_orders_report(**params)
        elif report_type == 'inventory':
            from inventory.reports import generate_inventory_report
            return generate_inventory_report(**params)
        elif report_type == 'finance':
            from finance.reports import generate_finance_report
            return generate_finance_report(**params)
        elif report_type == 'delivery':
            from delivery.reports import generate_delivery_report
            return generate_delivery_report(**params)
        else:
            return {'status': 'error', 'message': f'Unknown report type: {report_type}'}
    except Exception as e:
        logger.error(f"Report generation failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}
