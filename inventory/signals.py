"""
Inventory Signals - Handle order events for stock reservations
"""
from django.db.models.signals import post_save, pre_delete
from django.dispatch import receiver
from django.utils import timezone
import logging

logger = logging.getLogger('atlas_crm')


@receiver(post_save, sender='orders.Order')
def handle_order_status_change(sender, instance, created, **kwargs):
    """Handle order status changes for stock reservations."""
    from .models import StockReservation
    from .services import StockReservationService, InventoryAlertService

    try:
        # Get all reservations for this order
        reservations = StockReservation.objects.filter(order=instance)

        if instance.status == 'confirmed':
            # Confirm all pending reservations
            reservations.filter(status='pending').update(status='confirmed')
            logger.info(f"Confirmed reservations for order {instance.order_code}")

        elif instance.status in ['shipped', 'delivered']:
            # Fulfill reservations
            for reservation in reservations.filter(status__in=['pending', 'confirmed']):
                reservation.fulfill()
            logger.info(f"Fulfilled reservations for order {instance.order_code}")

        elif instance.status in ['cancelled', 'rejected']:
            # Cancel reservations and release stock
            for reservation in reservations.filter(status__in=['pending', 'confirmed']):
                reservation.cancel(f'Order {instance.status}')
            logger.info(f"Cancelled reservations for order {instance.order_code}")

    except Exception as e:
        logger.error(f"Error handling order status change: {str(e)}")


@receiver(post_save, sender='orders.OrderItem')
def handle_order_item_save(sender, instance, created, **kwargs):
    """Create stock reservation when order item is created."""
    from .models import StockReservation
    from .services import StockReservationService
    from stock_keeper.models import WarehouseInventory

    if not created:
        return

    try:
        # Find warehouse with stock
        inventory = WarehouseInventory.objects.filter(
            product=instance.product,
            quantity__gt=0
        ).select_related('warehouse').first()

        if inventory:
            # Check if reservation already exists
            existing = StockReservation.objects.filter(
                order=instance.order,
                order_item=instance
            ).exists()

            if not existing:
                StockReservationService.create_reservation(
                    order=instance.order,
                    order_item=instance,
                    warehouse=inventory.warehouse,
                    user=getattr(instance.order, 'created_by', None),
                    expires_hours=48
                )
                logger.info(f"Created reservation for order item {instance.id}")

    except ValueError as e:
        logger.warning(f"Could not create reservation: {str(e)}")
    except Exception as e:
        logger.error(f"Error creating order item reservation: {str(e)}")


@receiver(pre_delete, sender='orders.OrderItem')
def handle_order_item_delete(sender, instance, **kwargs):
    """Cancel reservations when order item is deleted."""
    from .models import StockReservation

    try:
        reservations = StockReservation.objects.filter(
            order_item=instance,
            status__in=['pending', 'confirmed']
        )
        for reservation in reservations:
            reservation.cancel('Order item deleted')
        logger.info(f"Cancelled reservations for deleted order item {instance.id}")

    except Exception as e:
        logger.error(f"Error cancelling reservations on item delete: {str(e)}")


@receiver(post_save, sender='stock_keeper.WarehouseInventory')
def handle_inventory_change(sender, instance, **kwargs):
    """Check alerts when inventory changes."""
    from .services import InventoryAlertService

    try:
        InventoryAlertService.check_stock_levels(instance.product, instance.warehouse)
    except Exception as e:
        logger.error(f"Error checking stock after inventory change: {str(e)}")
