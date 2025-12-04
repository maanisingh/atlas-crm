"""
Celery tasks for Orders module
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Count, Sum, Q
from datetime import timedelta
import logging

logger = logging.getLogger('atlas_crm')


@shared_task
def send_daily_order_summary():
    """
    Send daily order summary to managers
    Runs at 8 AM daily
    """
    from .models import Order
    from users.models import User
    from notifications.models import Notification
    from django.core.mail import send_mail
    from django.conf import settings
    from django.template.loader import render_to_string

    try:
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        # Get yesterday's order statistics
        stats = Order.objects.filter(
            created_at__date=yesterday
        ).aggregate(
            total_orders=Count('id'),
            total_value=Sum('total_price'),
            confirmed=Count('id', filter=Q(status='confirmed')),
            cancelled=Count('id', filter=Q(status='cancelled')),
            delivered=Count('id', filter=Q(status='delivered')),
        )

        # Get pending orders count
        pending_count = Order.objects.filter(
            status__in=['pending', 'seller_submitted', 'callcenter_review']
        ).count()

        summary = {
            'date': yesterday.strftime('%Y-%m-%d'),
            'total_orders': stats['total_orders'] or 0,
            'total_value': float(stats['total_value'] or 0),
            'confirmed': stats['confirmed'] or 0,
            'cancelled': stats['cancelled'] or 0,
            'delivered': stats['delivered'] or 0,
            'pending': pending_count,
        }

        # Create notifications for managers
        managers = User.objects.filter(
            is_active=True,
            userrole__role__role_type__in=['admin', 'manager']
        ).distinct()

        for manager in managers:
            Notification.objects.create(
                user=manager,
                title=f"Daily Order Summary - {yesterday.strftime('%B %d, %Y')}",
                message=f"Orders: {summary['total_orders']}, "
                       f"Value: ${summary['total_value']:,.2f}, "
                       f"Delivered: {summary['delivered']}, "
                       f"Pending: {summary['pending']}",
                notification_type='report',
                priority='normal'
            )

        logger.info(f"Daily order summary sent: {summary}")
        return {'status': 'success', 'summary': summary}

    except Exception as e:
        logger.error(f"Daily order summary failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def check_stale_orders():
    """
    Check for orders that have been pending too long
    """
    from .models import Order
    from notifications.models import Notification
    from users.models import User

    try:
        # Orders pending for more than 24 hours
        stale_threshold = timezone.now() - timedelta(hours=24)

        stale_orders = Order.objects.filter(
            status__in=['pending', 'seller_submitted', 'callcenter_review'],
            created_at__lt=stale_threshold
        ).select_related('seller')

        stale_count = stale_orders.count()

        if stale_count > 0:
            # Notify call center managers
            cc_managers = User.objects.filter(
                is_active=True,
                userrole__role__role_type__in=['admin', 'callcenter_manager']
            ).distinct()

            for manager in cc_managers:
                Notification.objects.create(
                    user=manager,
                    title=f"Stale Orders Alert",
                    message=f"There are {stale_count} orders pending for more than 24 hours. "
                           f"Please review and process them.",
                    notification_type='alert',
                    priority='high'
                )

        logger.info(f"Stale order check completed. Found: {stale_count}")
        return {'status': 'success', 'stale_orders': stale_count}

    except Exception as e:
        logger.error(f"Stale order check failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def auto_cancel_unpaid_orders():
    """
    Auto-cancel orders that haven't been paid within 48 hours
    """
    from .models import Order, StatusLog

    try:
        cancel_threshold = timezone.now() - timedelta(hours=48)

        # Find unpaid orders older than threshold
        unpaid_orders = Order.objects.filter(
            status='pending',
            payment_status='pending',
            created_at__lt=cancel_threshold
        )

        cancelled_count = 0
        for order in unpaid_orders:
            order.status = 'cancelled'
            order.save()

            StatusLog.objects.create(
                order=order,
                status='cancelled',
                notes='Auto-cancelled due to non-payment after 48 hours'
            )
            cancelled_count += 1

        logger.info(f"Auto-cancelled {cancelled_count} unpaid orders")
        return {'status': 'success', 'cancelled': cancelled_count}

    except Exception as e:
        logger.error(f"Auto-cancel task failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}
