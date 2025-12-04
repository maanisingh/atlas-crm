"""
Inventory Alert Service - Handles alert management and notifications
"""
from django.db import models, transaction
from django.utils import timezone
from datetime import timedelta
import logging

logger = logging.getLogger('atlas_crm')


class InventoryAlertService:
    """Service for managing inventory alerts and notifications."""

    @staticmethod
    def check_stock_levels(product, warehouse=None):
        """Check stock levels and create alerts if needed."""
        from .models import Stock, InventoryAlert, StockReservation
        from stock_keeper.models import WarehouseInventory

        alerts_created = []

        try:
            # Get stock settings
            stock = Stock.objects.filter(product=product).first()
            if not stock:
                return alerts_created

            # Calculate available quantity
            total_qty = stock.total_quantity
            reserved_qty = StockReservation.get_reserved_quantity(product, warehouse)
            available_qty = max(0, total_qty - reserved_qty)

            # Check for low stock
            if available_qty <= stock.min_quantity:
                alert = InventoryAlert.create_low_stock_alert(
                    product=product,
                    warehouse=warehouse,
                    current_qty=available_qty,
                    threshold_qty=stock.min_quantity
                )
                if alert:
                    alerts_created.append(alert)
                    InventoryAlertService._send_notifications(alert)

            # Check for overstock
            elif stock.max_quantity > 0 and total_qty > stock.max_quantity:
                existing = InventoryAlert.objects.filter(
                    product=product,
                    warehouse=warehouse,
                    alert_type='overstock',
                    is_resolved=False
                ).exists()

                if not existing:
                    alert = InventoryAlert.objects.create(
                        product=product,
                        warehouse=warehouse,
                        alert_type='overstock',
                        priority='low',
                        title=f"Overstock: {product.name_en}",
                        message=f"Stock level ({total_qty}) exceeds maximum ({stock.max_quantity})",
                        current_quantity=total_qty,
                        threshold_quantity=stock.max_quantity
                    )
                    alerts_created.append(alert)

            return alerts_created

        except Exception as e:
            logger.error(f"Error checking stock levels: {str(e)}")
            return alerts_created

    @staticmethod
    def _send_notifications(alert):
        """Send notifications for an alert."""
        from notifications.models import Notification
        from users.models import User

        roles = ['admin', 'warehouse_manager', 'stock_keeper']
        if alert.priority in ['high', 'critical']:
            roles.extend(['inventory_manager', 'operations_manager'])

        users = User.objects.filter(
            is_active=True,
            userrole__role__role_type__in=roles
        ).distinct()

        for user in users:
            Notification.objects.create(
                user=user,
                title=alert.title,
                message=alert.message,
                notification_type='stock_alert',
                priority='high' if alert.priority in ['high', 'critical'] else 'medium',
                related_object_type='inventory_alert',
                related_object_id=str(alert.id)
            )

    @staticmethod
    def resolve_alerts_for_product(product, warehouse=None, notes=''):
        """Auto-resolve alerts when stock is replenished."""
        from .models import InventoryAlert

        filters = {
            'product': product,
            'alert_type__in': ['low_stock', 'out_of_stock'],
            'is_resolved': False
        }
        if warehouse:
            filters['warehouse'] = warehouse

        return InventoryAlert.objects.filter(**filters).update(
            is_resolved=True,
            resolved_at=timezone.now(),
            resolution_notes=notes or 'Auto-resolved: Stock replenished'
        )

    @staticmethod
    def get_dashboard_summary():
        """Get alert summary for dashboard."""
        from .models import InventoryAlert, StockReservation

        alerts = InventoryAlert.objects.filter(is_resolved=False)
        reservations = StockReservation.objects.filter(status__in=['pending', 'confirmed'])

        return {
            'total_alerts': alerts.count(),
            'critical_alerts': alerts.filter(priority='critical').count(),
            'high_alerts': alerts.filter(priority='high').count(),
            'low_stock_alerts': alerts.filter(alert_type='low_stock').count(),
            'out_of_stock_alerts': alerts.filter(alert_type='out_of_stock').count(),
            'active_reservations': reservations.count(),
            'reserved_units': reservations.aggregate(
                total=models.Sum('quantity')
            )['total'] or 0
        }


class StockReservationService:
    """Service for managing stock reservations."""

    @staticmethod
    @transaction.atomic
    def create_reservation(order, order_item, warehouse, user=None, expires_hours=24):
        """Create a stock reservation for an order item."""
        from .models import StockReservation

        # Check available quantity
        available = StockReservation.get_available_quantity(
            order_item.product, warehouse
        )

        if available < order_item.quantity:
            raise ValueError(
                f"Insufficient stock. Available: {available}, Requested: {order_item.quantity}"
            )

        reservation = StockReservation.objects.create(
            product=order_item.product,
            warehouse=warehouse,
            order=order,
            order_item=order_item,
            quantity=order_item.quantity,
            status='pending',
            reserved_by=user,
            expires_at=timezone.now() + timedelta(hours=expires_hours)
        )

        # Check if this creates a low stock situation
        InventoryAlertService.check_stock_levels(order_item.product, warehouse)

        return reservation

    @staticmethod
    @transaction.atomic
    def fulfill_reservation(reservation):
        """Mark reservation as fulfilled when order ships."""
        if reservation.fulfill():
            # Resolve any alerts since stock was properly allocated
            InventoryAlertService.resolve_alerts_for_product(
                reservation.product,
                reservation.warehouse,
                f'Stock allocated for Order {reservation.order.order_code}'
            )
            return True
        return False

    @staticmethod
    @transaction.atomic
    def cancel_reservation(reservation, reason=''):
        """Cancel reservation and release stock."""
        if reservation.cancel(reason):
            # Re-check stock levels - available stock increased
            InventoryAlertService.check_stock_levels(
                reservation.product,
                reservation.warehouse
            )
            return True
        return False

    @staticmethod
    def get_order_reservations(order):
        """Get all reservations for an order."""
        from .models import StockReservation
        return StockReservation.objects.filter(order=order).select_related(
            'product', 'warehouse', 'order_item'
        )
