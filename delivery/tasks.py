"""
Celery tasks for Delivery module
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Count, Q
from datetime import timedelta
import logging

logger = logging.getLogger('atlas_crm')


@shared_task
def check_pending_deliveries():
    """
    Check for pending deliveries and send alerts
    Runs every 15 minutes via Celery Beat
    """
    from .models import Delivery
    from notifications.models import Notification
    from users.models import User

    try:
        # Get deliveries scheduled for today that are still pending
        today = timezone.now().date()

        pending_today = Delivery.objects.filter(
            scheduled_date=today,
            status__in=['pending', 'assigned', 'in_transit']
        ).select_related('order', 'driver')

        pending_count = pending_today.count()

        if pending_count > 0:
            # Notify delivery managers
            delivery_managers = User.objects.filter(
                is_active=True,
                userrole__role__role_type__in=['admin', 'delivery_manager']
            ).distinct()

            for manager in delivery_managers:
                # Check if notification already sent in last hour
                recent_notification = Notification.objects.filter(
                    user=manager,
                    notification_type='delivery_alert',
                    created_at__gte=timezone.now() - timedelta(hours=1)
                ).exists()

                if not recent_notification:
                    Notification.objects.create(
                        user=manager,
                        title="Pending Deliveries Alert",
                        message=f"There are {pending_count} deliveries scheduled for today "
                               f"that are still pending. Please review and assign drivers.",
                        notification_type='delivery_alert',
                        priority='high'
                    )

        logger.info(f"Pending delivery check completed. Found: {pending_count}")
        return {'status': 'success', 'pending_deliveries': pending_count}

    except Exception as e:
        logger.error(f"Pending delivery check failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def update_delivery_statuses():
    """
    Update delivery statuses based on driver GPS/tracking data
    """
    from .models import Delivery, DeliveryStatusLog

    try:
        updated = 0

        # Get in-transit deliveries
        in_transit = Delivery.objects.filter(
            status='in_transit'
        ).select_related('driver', 'order')

        for delivery in in_transit:
            # Check if delivery has been in transit for too long (>6 hours)
            if delivery.pickup_time:
                time_in_transit = timezone.now() - delivery.pickup_time
                if time_in_transit > timedelta(hours=6):
                    # Flag for review
                    delivery.needs_review = True
                    delivery.save(update_fields=['needs_review'])
                    updated += 1

        logger.info(f"Delivery status update completed. Flagged: {updated}")
        return {'status': 'success', 'flagged': updated}

    except Exception as e:
        logger.error(f"Delivery status update failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def send_delivery_notifications():
    """
    Send delivery notifications to customers
    """
    from .models import Delivery
    from notifications.models import Notification

    try:
        sent = 0

        # Get deliveries starting today that haven't been notified
        today = timezone.now().date()

        deliveries = Delivery.objects.filter(
            scheduled_date=today,
            status='assigned',
            customer_notified=False
        ).select_related('order', 'driver')

        for delivery in deliveries:
            if hasattr(delivery.order, 'customer') and delivery.order.customer:
                # Create customer notification
                Notification.objects.create(
                    user=delivery.order.customer.user if hasattr(delivery.order.customer, 'user') else None,
                    title="Delivery Scheduled",
                    message=f"Your order #{delivery.order.order_number} is scheduled for delivery today. "
                           f"Driver: {delivery.driver.get_full_name() if delivery.driver else 'To be assigned'}",
                    notification_type='delivery',
                    priority='normal'
                )

                delivery.customer_notified = True
                delivery.save(update_fields=['customer_notified'])
                sent += 1

        logger.info(f"Delivery notifications sent: {sent}")
        return {'status': 'success', 'notifications_sent': sent}

    except Exception as e:
        logger.error(f"Delivery notification task failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def generate_daily_delivery_report():
    """
    Generate daily delivery performance report
    """
    from .models import Delivery
    from django.db.models import Avg, Count

    try:
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        # Get yesterday's delivery statistics
        stats = Delivery.objects.filter(
            scheduled_date=yesterday
        ).aggregate(
            total=Count('id'),
            delivered=Count('id', filter=Q(status='delivered')),
            failed=Count('id', filter=Q(status='failed')),
            cancelled=Count('id', filter=Q(status='cancelled')),
        )

        # Calculate on-time delivery rate
        on_time = Delivery.objects.filter(
            scheduled_date=yesterday,
            status='delivered',
            actual_delivery_time__lte=timezone.now()  # Simplified check
        ).count()

        total_delivered = stats['delivered'] or 1  # Avoid division by zero
        on_time_rate = (on_time / total_delivered) * 100 if total_delivered > 0 else 0

        report = {
            'date': yesterday.strftime('%Y-%m-%d'),
            'total_deliveries': stats['total'] or 0,
            'delivered': stats['delivered'] or 0,
            'failed': stats['failed'] or 0,
            'cancelled': stats['cancelled'] or 0,
            'on_time_rate': round(on_time_rate, 2),
        }

        logger.info(f"Daily delivery report generated: {report}")
        return {'status': 'success', 'report': report}

    except Exception as e:
        logger.error(f"Daily delivery report failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def assign_drivers_automatically():
    """
    Auto-assign available drivers to pending deliveries
    """
    from .models import Delivery
    from users.models import User

    try:
        assigned = 0

        # Get pending deliveries without driver
        pending = Delivery.objects.filter(
            status='pending',
            driver__isnull=True,
            scheduled_date=timezone.now().date()
        ).select_related('order')

        # Get available drivers
        available_drivers = User.objects.filter(
            is_active=True,
            userrole__role__role_type='driver',
            driver_profile__is_available=True
        ).annotate(
            active_deliveries=Count('delivery_assignments', filter=Q(
                delivery_assignments__status__in=['assigned', 'in_transit']
            ))
        ).filter(active_deliveries__lt=5)  # Max 5 active deliveries per driver

        for delivery in pending:
            if available_drivers.exists():
                # Assign to driver with least active deliveries
                driver = available_drivers.order_by('active_deliveries').first()
                if driver:
                    delivery.driver = driver
                    delivery.status = 'assigned'
                    delivery.save(update_fields=['driver', 'status'])
                    assigned += 1

        logger.info(f"Auto-assigned {assigned} deliveries to drivers")
        return {'status': 'success', 'assigned': assigned}

    except Exception as e:
        logger.error(f"Driver auto-assignment failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}
