"""
Management command to set up all periodic Celery tasks for Atlas CRM.
"""
import json
from django.core.management.base import BaseCommand
from django_celery_beat.models import PeriodicTask, IntervalSchedule, CrontabSchedule


class Command(BaseCommand):
    help = 'Set up all periodic Celery tasks for Atlas CRM'

    def handle(self, *args, **options):
        self.stdout.write('Setting up periodic tasks...\n')

        # Create interval schedules
        every_5_minutes, _ = IntervalSchedule.objects.get_or_create(
            every=5,
            period=IntervalSchedule.MINUTES,
        )

        every_10_minutes, _ = IntervalSchedule.objects.get_or_create(
            every=10,
            period=IntervalSchedule.MINUTES,
        )

        every_30_minutes, _ = IntervalSchedule.objects.get_or_create(
            every=30,
            period=IntervalSchedule.MINUTES,
        )

        every_hour, _ = IntervalSchedule.objects.get_or_create(
            every=1,
            period=IntervalSchedule.HOURS,
        )

        every_day, _ = IntervalSchedule.objects.get_or_create(
            every=1,
            period=IntervalSchedule.DAYS,
        )

        # Create crontab schedules
        daily_8am, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='8',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )

        daily_6am, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='6',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )

        daily_midnight, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='0',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )

        daily_9pm, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='21',
            day_of_week='*',
            day_of_month='*',
            month_of_year='*',
        )

        weekly_monday_6am, _ = CrontabSchedule.objects.get_or_create(
            minute='0',
            hour='6',
            day_of_week='1',  # Monday
            day_of_month='*',
            month_of_year='*',
        )

        # Define all periodic tasks
        tasks = [
            # =====================
            # ORDER TASKS
            # =====================
            {
                'name': 'Check Stale Orders (Every 30 min)',
                'task': 'orders.tasks.check_stale_orders',
                'interval': every_30_minutes,
                'description': 'Find orders that have been in processing too long',
            },
            {
                'name': 'Auto Cancel Unpaid Orders (Every hour)',
                'task': 'orders.tasks.auto_cancel_unpaid_orders',
                'interval': every_hour,
                'description': 'Cancel orders that remain unpaid after 48 hours',
            },
            {
                'name': 'Send Daily Order Summary (8 AM)',
                'task': 'orders.tasks.send_daily_order_summary',
                'crontab': daily_8am,
                'description': 'Send daily order summary email to management',
            },

            # =====================
            # INVENTORY TASKS
            # =====================
            {
                'name': 'Check Low Stock Alerts (Every 10 min)',
                'task': 'inventory.tasks.check_low_stock_alerts',
                'interval': every_10_minutes,
                'description': 'Check for products below minimum stock levels',
            },
            {
                'name': 'Sync Stock Levels (Every 30 min)',
                'task': 'inventory.tasks.sync_stock_levels',
                'interval': every_30_minutes,
                'description': 'Synchronize stock levels across warehouses',
            },
            {
                'name': 'Update Inventory Valuations (Daily 6 AM)',
                'task': 'inventory.tasks.update_inventory_valuations',
                'crontab': daily_6am,
                'description': 'Update inventory valuations for reporting',
            },

            # =====================
            # DELIVERY TASKS
            # =====================
            {
                'name': 'Check Pending Deliveries (Every 10 min)',
                'task': 'delivery.tasks.check_pending_deliveries',
                'interval': every_10_minutes,
                'description': 'Check for deliveries that need attention',
            },
            {
                'name': 'Update Delivery Statuses (Every 5 min)',
                'task': 'delivery.tasks.update_delivery_statuses',
                'interval': every_5_minutes,
                'description': 'Sync delivery statuses from external systems',
            },
            {
                'name': 'Auto Assign Drivers (Every 10 min)',
                'task': 'delivery.tasks.assign_drivers_automatically',
                'interval': every_10_minutes,
                'description': 'Automatically assign drivers to unassigned deliveries',
            },
            {
                'name': 'Send Delivery Notifications (Every 5 min)',
                'task': 'delivery.tasks.send_delivery_notifications',
                'interval': every_5_minutes,
                'description': 'Send notifications for delivery status changes',
            },
            {
                'name': 'Generate Daily Delivery Report (9 PM)',
                'task': 'delivery.tasks.generate_daily_delivery_report',
                'crontab': daily_9pm,
                'description': 'Generate end-of-day delivery performance report',
            },

            # =====================
            # FINANCE TASKS
            # =====================
            {
                'name': 'Generate Daily Finance Report (Midnight)',
                'task': 'finance.tasks.generate_daily_report',
                'crontab': daily_midnight,
                'description': 'Generate daily finance report',
            },
            {
                'name': 'Check Overdue Invoices (Every hour)',
                'task': 'finance.tasks.check_overdue_invoices',
                'interval': every_hour,
                'description': 'Check for overdue invoices and send reminders',
            },
            {
                'name': 'Process Pending Payouts (Daily 6 AM)',
                'task': 'finance.tasks.process_pending_payouts',
                'crontab': daily_6am,
                'description': 'Process pending seller payouts',
            },
            {
                'name': 'Reconcile Daily Transactions (Midnight)',
                'task': 'finance.tasks.reconcile_daily_transactions',
                'crontab': daily_midnight,
                'description': 'Reconcile all transactions from the previous day',
            },
            {
                'name': 'Calculate Seller Commissions (Weekly Monday 6 AM)',
                'task': 'finance.tasks.calculate_seller_commissions',
                'crontab': weekly_monday_6am,
                'description': 'Calculate seller commissions for the previous week',
            },

            # =====================
            # USER TASKS
            # =====================
            {
                'name': 'Clean Old Sessions (Daily Midnight)',
                'task': 'users.tasks.clean_old_sessions',
                'crontab': daily_midnight,
                'description': 'Clean up expired user sessions',
            },
            {
                'name': 'Clear Axes Lockouts (Every hour)',
                'task': 'users.tasks.clear_axes_lockouts',
                'interval': every_hour,
                'description': 'Clear expired login attempt lockouts',
            },
            {
                'name': 'Deactivate Inactive Users (Weekly Monday 6 AM)',
                'task': 'users.tasks.deactivate_inactive_users',
                'crontab': weekly_monday_6am,
                'description': 'Deactivate users inactive for more than 90 days',
            },
            {
                'name': 'Generate User Activity Report (Daily 8 AM)',
                'task': 'users.tasks.generate_user_activity_report',
                'crontab': daily_8am,
                'description': 'Generate daily user activity report',
            },
            {
                'name': 'Send Password Expiry Reminders (Daily 8 AM)',
                'task': 'users.tasks.send_password_expiry_reminders',
                'crontab': daily_8am,
                'description': 'Send reminders for passwords expiring soon',
            },
            {
                'name': 'Sync User Permissions (Every hour)',
                'task': 'users.tasks.sync_user_permissions',
                'interval': every_hour,
                'description': 'Sync user permissions with role changes',
            },
        ]

        created_count = 0
        updated_count = 0

        for task_config in tasks:
            defaults = {
                'enabled': True,
                'description': task_config.get('description', ''),
            }

            # Set schedule type
            if 'interval' in task_config:
                defaults['interval'] = task_config['interval']
                defaults['crontab'] = None
            elif 'crontab' in task_config:
                defaults['crontab'] = task_config['crontab']
                defaults['interval'] = None

            task, created = PeriodicTask.objects.update_or_create(
                name=task_config['name'],
                defaults={
                    'task': task_config['task'],
                    **defaults,
                }
            )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f'  ✓ Created: {task_config["name"]}'))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f'  ↻ Updated: {task_config["name"]}'))

        self.stdout.write('')
        self.stdout.write(self.style.SUCCESS(f'Done! Created {created_count} tasks, updated {updated_count} tasks.'))
        self.stdout.write(self.style.SUCCESS(f'Total periodic tasks: {PeriodicTask.objects.count()}'))
