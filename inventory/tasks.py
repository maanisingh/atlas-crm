"""
Celery tasks for Inventory module
"""
from celery import shared_task
from django.db import models
from django.db.models import F, Sum, Q
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger('atlas_crm')


@shared_task
def check_low_stock_alerts():
    """
    Check for products with low stock and create alerts.
    Uses the new InventoryAlert model for comprehensive alert management.
    Runs every 30 minutes via Celery Beat
    """
    from .models import Stock, InventoryRecord, InventoryAlert, StockReservation, Warehouse
    from stock_keeper.models import WarehouseInventory
    from notifications.models import Notification
    from users.models import User

    alerts_created = 0
    alerts_resolved = 0

    try:
        # Check stocks using Stock model
        stocks = Stock.objects.select_related('product').all()

        for stock in stocks:
            # Get total quantity across all warehouses
            total_qty = stock.total_quantity

            # Get reserved quantity
            reserved_qty = StockReservation.get_reserved_quantity(stock.product)
            available_qty = max(0, total_qty - reserved_qty)

            # Check if below minimum threshold
            if available_qty <= stock.min_quantity:
                alert = InventoryAlert.create_low_stock_alert(
                    product=stock.product,
                    warehouse=None,  # Overall alert, not warehouse-specific
                    current_qty=available_qty,
                    threshold_qty=stock.min_quantity
                )
                if alert:
                    alerts_created += 1
                    # Send notifications
                    _send_stock_alert_notifications(alert)

            # Auto-resolve if stock recovered
            elif available_qty > stock.min_quantity:
                resolved = InventoryAlert.objects.filter(
                    product=stock.product,
                    alert_type__in=['low_stock', 'out_of_stock'],
                    is_resolved=False
                ).update(
                    is_resolved=True,
                    resolved_at=timezone.now(),
                    resolution_notes='Auto-resolved: Stock level recovered'
                )
                alerts_resolved += resolved

        # Check warehouse-specific inventory using WarehouseInventory
        warehouse_inventories = WarehouseInventory.objects.select_related(
            'product', 'warehouse'
        ).filter(
            min_stock_level__gt=0
        )

        for inv in warehouse_inventories:
            # Get reserved quantity for this warehouse
            reserved = StockReservation.get_reserved_quantity(inv.product, inv.warehouse)
            available = max(0, inv.quantity - reserved)

            if available <= inv.min_stock_level:
                alert = InventoryAlert.create_low_stock_alert(
                    product=inv.product,
                    warehouse=inv.warehouse,
                    current_qty=available,
                    threshold_qty=inv.min_stock_level
                )
                if alert:
                    alerts_created += 1
                    _send_stock_alert_notifications(alert)
            else:
                # Auto-resolve warehouse-specific alerts
                resolved = InventoryAlert.objects.filter(
                    product=inv.product,
                    warehouse=inv.warehouse,
                    alert_type__in=['low_stock', 'out_of_stock'],
                    is_resolved=False
                ).update(
                    is_resolved=True,
                    resolved_at=timezone.now(),
                    resolution_notes='Auto-resolved: Stock level recovered'
                )
                alerts_resolved += resolved

        # Check for overstock situations
        overstock_alerts = _check_overstock_alerts()
        alerts_created += overstock_alerts

        logger.info(f"Stock alert check completed. Created: {alerts_created}, Resolved: {alerts_resolved}")
        return {
            'status': 'success',
            'alerts_created': alerts_created,
            'alerts_resolved': alerts_resolved
        }

    except Exception as e:
        logger.error(f"Stock alert check failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


def _check_overstock_alerts():
    """Check for overstock situations and create alerts."""
    from .models import Stock, InventoryAlert
    from stock_keeper.models import WarehouseInventory

    alerts_created = 0

    # Check overall stock levels
    stocks = Stock.objects.filter(max_quantity__gt=0).select_related('product')

    for stock in stocks:
        total_qty = stock.total_quantity
        if total_qty > stock.max_quantity:
            existing = InventoryAlert.objects.filter(
                product=stock.product,
                warehouse=None,
                alert_type='overstock',
                is_resolved=False
            ).exists()

            if not existing:
                InventoryAlert.objects.create(
                    product=stock.product,
                    warehouse=None,
                    alert_type='overstock',
                    priority='low',
                    title=f"Overstock: {stock.product.name_en}",
                    message=f"Product has {total_qty} units, exceeding maximum of {stock.max_quantity}",
                    current_quantity=total_qty,
                    threshold_quantity=stock.max_quantity
                )
                alerts_created += 1

    # Check warehouse-specific overstock
    warehouse_inventories = WarehouseInventory.objects.filter(
        max_stock_level__gt=0,
        quantity__gt=F('max_stock_level')
    ).select_related('product', 'warehouse')

    for inv in warehouse_inventories:
        existing = InventoryAlert.objects.filter(
            product=inv.product,
            warehouse=inv.warehouse,
            alert_type='overstock',
            is_resolved=False
        ).exists()

        if not existing:
            InventoryAlert.objects.create(
                product=inv.product,
                warehouse=inv.warehouse,
                alert_type='overstock',
                priority='low',
                title=f"Overstock: {inv.product.name_en} at {inv.warehouse.name}",
                message=f"Warehouse has {inv.quantity} units, exceeding maximum of {inv.max_stock_level}",
                current_quantity=inv.quantity,
                threshold_quantity=inv.max_stock_level
            )
            alerts_created += 1

    return alerts_created


def _send_stock_alert_notifications(alert):
    """Send notifications for stock alerts to relevant users."""
    from notifications.models import Notification
    from users.models import User

    # Determine user roles to notify based on priority
    roles_to_notify = ['admin', 'warehouse_manager', 'stock_keeper']
    if alert.priority in ['high', 'critical']:
        roles_to_notify.append('inventory_manager')

    users = User.objects.filter(
        is_active=True,
        userrole__role__role_type__in=roles_to_notify
    ).distinct()

    notifications_created = []
    for user in users:
        notification = Notification.objects.create(
            user=user,
            title=alert.title,
            message=alert.message,
            notification_type='stock_alert',
            priority='high' if alert.priority in ['high', 'critical'] else 'medium',
            related_object_type='inventory_alert',
            related_object_id=str(alert.id)
        )
        notifications_created.append(notification.id)

    return notifications_created


@shared_task
def expire_stock_reservations():
    """
    Check and expire stock reservations that have passed their expiry time.
    Runs every 15 minutes via Celery Beat
    """
    from .models import StockReservation, InventoryAlert
    from notifications.models import Notification

    expired_count = 0

    try:
        # Find reservations that should be expired
        expired_reservations = StockReservation.objects.filter(
            status__in=['pending', 'confirmed'],
            expires_at__lt=timezone.now()
        ).select_related('product', 'warehouse', 'order')

        for reservation in expired_reservations:
            if reservation.expire():
                expired_count += 1

                # Create alert for expired reservation
                InventoryAlert.objects.create(
                    product=reservation.product,
                    warehouse=reservation.warehouse,
                    alert_type='reservation_expired',
                    priority='medium',
                    title=f"Reservation Expired: {reservation.product.name_en}",
                    message=f"Stock reservation of {reservation.quantity} units for Order {reservation.order.order_code} has expired",
                    current_quantity=reservation.quantity
                )

                # Notify order owner if exists
                if reservation.order.customer:
                    Notification.objects.create(
                        user=reservation.reserved_by,
                        title="Stock Reservation Expired",
                        message=f"Your reservation of {reservation.quantity}x {reservation.product.name_en} for order {reservation.order.order_code} has expired.",
                        notification_type='reservation',
                        priority='medium',
                        related_object_type='order',
                        related_object_id=str(reservation.order.id)
                    )

        logger.info(f"Stock reservation expiry check completed. Expired: {expired_count}")
        return {'status': 'success', 'expired': expired_count}

    except Exception as e:
        logger.error(f"Stock reservation expiry check failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def check_reorder_needed():
    """
    Check products that need to be reordered and create alerts.
    Runs daily via Celery Beat
    """
    from .models import Stock, InventoryAlert, StockReservation
    from sellers.models import Product

    alerts_created = 0

    try:
        stocks = Stock.objects.filter(
            reorder_quantity__gt=0
        ).select_related('product')

        for stock in stocks:
            total_qty = stock.total_quantity
            reserved_qty = StockReservation.get_reserved_quantity(stock.product)
            available_qty = max(0, total_qty - reserved_qty)

            # If available quantity is at or below min, suggest reorder
            if available_qty <= stock.min_quantity:
                # Check if we haven't reordered recently
                days_since_reorder = None
                if stock.last_reorder_date:
                    days_since_reorder = (timezone.now().date() - stock.last_reorder_date).days

                # Only create reorder alert if not already pending and not recently reordered
                existing = InventoryAlert.objects.filter(
                    product=stock.product,
                    alert_type='reorder_needed',
                    is_resolved=False
                ).exists()

                if not existing and (days_since_reorder is None or days_since_reorder > 3):
                    InventoryAlert.objects.create(
                        product=stock.product,
                        alert_type='reorder_needed',
                        priority='high',
                        title=f"Reorder Needed: {stock.product.name_en}",
                        message=f"Available stock ({available_qty}) is below minimum ({stock.min_quantity}). Suggested reorder quantity: {stock.reorder_quantity}",
                        current_quantity=available_qty,
                        threshold_quantity=stock.min_quantity
                    )
                    alerts_created += 1

        logger.info(f"Reorder check completed. Alerts created: {alerts_created}")
        return {'status': 'success', 'alerts_created': alerts_created}

    except Exception as e:
        logger.error(f"Reorder check failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def update_inventory_valuations():
    """
    Update inventory valuations for all products
    """
    from .models import InventoryRecord
    from decimal import Decimal

    try:
        updated = 0
        for record in InventoryRecord.objects.select_related('product').all():
            if hasattr(record.product, 'price') and record.quantity > 0:
                record.unit_cost = record.product.price
                record.total_value = record.quantity * record.unit_cost
                record.save(update_fields=['unit_cost', 'total_value'])
                updated += 1

        logger.info(f"Inventory valuations updated: {updated} records")
        return {'status': 'success', 'updated': updated}

    except Exception as e:
        logger.error(f"Inventory valuation update failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def sync_stock_levels():
    """
    Synchronize stock levels between Stock and InventoryRecord models
    """
    from .models import Stock, InventoryRecord

    try:
        synced = 0
        for stock in Stock.objects.select_related('product').all():
            # Sum all inventory records for this product
            total_quantity = InventoryRecord.objects.filter(
                product=stock.product
            ).aggregate(total=Sum('quantity'))['total'] or 0

            # Update Stock model's computed property is automatic
            # But we can log discrepancies
            if stock.total_quantity != total_quantity:
                logger.warning(
                    f"Stock mismatch for {stock.product.name_en}: "
                    f"Stock model: {stock.total_quantity}, Records sum: {total_quantity}"
                )
                synced += 1

        logger.info(f"Stock levels synchronized: {synced} discrepancies found")
        return {'status': 'success', 'synced': synced}

    except Exception as e:
        logger.error(f"Stock sync failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def generate_inventory_summary_report():
    """
    Generate daily inventory summary report.
    Runs daily via Celery Beat
    """
    from .models import Stock, InventoryRecord, InventoryAlert, StockReservation, Warehouse
    from stock_keeper.models import WarehouseInventory

    try:
        report_data = {
            'generated_at': timezone.now().isoformat(),
            'warehouses': [],
            'alerts_summary': {},
            'reservation_summary': {}
        }

        # Warehouse summary
        from .models import Warehouse
        for warehouse in Warehouse.objects.filter(is_active=True):
            inventory_count = WarehouseInventory.objects.filter(
                warehouse=warehouse
            ).count()

            total_value = WarehouseInventory.objects.filter(
                warehouse=warehouse
            ).aggregate(
                total=Sum(F('quantity') * F('unit_cost'))
            )['total'] or 0

            low_stock_count = WarehouseInventory.objects.filter(
                warehouse=warehouse,
                quantity__lte=F('min_stock_level'),
                min_stock_level__gt=0
            ).count()

            report_data['warehouses'].append({
                'name': warehouse.name,
                'products': inventory_count,
                'total_value': float(total_value),
                'low_stock_items': low_stock_count
            })

        # Alert summary
        alerts = InventoryAlert.objects.filter(is_resolved=False)
        report_data['alerts_summary'] = {
            'total_active': alerts.count(),
            'critical': alerts.filter(priority='critical').count(),
            'high': alerts.filter(priority='high').count(),
            'medium': alerts.filter(priority='medium').count(),
            'low': alerts.filter(priority='low').count(),
            'by_type': {
                alert_type: alerts.filter(alert_type=alert_type).count()
                for alert_type, _ in InventoryAlert.ALERT_TYPES
            }
        }

        # Reservation summary
        reservations = StockReservation.objects.filter(status__in=['pending', 'confirmed'])
        report_data['reservation_summary'] = {
            'active_reservations': reservations.count(),
            'total_reserved_units': reservations.aggregate(total=Sum('quantity'))['total'] or 0,
            'pending': reservations.filter(status='pending').count(),
            'confirmed': reservations.filter(status='confirmed').count()
        }

        logger.info(f"Inventory summary report generated: {report_data['alerts_summary']['total_active']} active alerts")
        return {'status': 'success', 'report': report_data}

    except Exception as e:
        logger.error(f"Inventory report generation failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def cleanup_old_alerts():
    """
    Clean up old resolved alerts and notifications.
    Runs weekly via Celery Beat
    """
    from .models import InventoryAlert

    try:
        # Delete resolved alerts older than 90 days
        cutoff_date = timezone.now() - timedelta(days=90)

        deleted = InventoryAlert.objects.filter(
            is_resolved=True,
            resolved_at__lt=cutoff_date
        ).delete()

        logger.info(f"Cleaned up {deleted[0]} old inventory alerts")
        return {'status': 'success', 'deleted': deleted[0]}

    except Exception as e:
        logger.error(f"Alert cleanup failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}
