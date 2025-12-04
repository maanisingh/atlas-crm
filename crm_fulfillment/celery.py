"""
Celery configuration for Atlas CRM & Fulfillment System
"""
from __future__ import absolute_import, unicode_literals
import os
from celery import Celery
from celery.schedules import crontab

# Set the default Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm_fulfillment.settings')

app = Celery('crm_fulfillment')

# Load config from Django settings with CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()

# Celery Beat Schedule - Periodic Tasks
app.conf.beat_schedule = {
    # Check low stock alerts every 30 minutes
    'check-low-stock-alerts': {
        'task': 'inventory.tasks.check_low_stock_alerts',
        'schedule': crontab(minute='*/30'),
    },
    # Send daily order summary
    'daily-order-summary': {
        'task': 'orders.tasks.send_daily_order_summary',
        'schedule': crontab(hour=8, minute=0),  # 8 AM daily
    },
    # Check pending deliveries
    'check-pending-deliveries': {
        'task': 'delivery.tasks.check_pending_deliveries',
        'schedule': crontab(minute='*/15'),  # Every 15 minutes
    },
    # Generate daily finance reports
    'daily-finance-report': {
        'task': 'finance.tasks.generate_daily_report',
        'schedule': crontab(hour=23, minute=30),  # 11:30 PM daily
    },
    # Clean old sessions
    'clean-old-sessions': {
        'task': 'users.tasks.clean_old_sessions',
        'schedule': crontab(hour=3, minute=0),  # 3 AM daily
    },
    # Database backup
    'database-backup': {
        'task': 'crm_fulfillment.tasks.backup_database',
        'schedule': crontab(hour=2, minute=0),  # 2 AM daily
    },
}


@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')
