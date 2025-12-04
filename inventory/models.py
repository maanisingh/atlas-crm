# inventory/models.py
from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator


class Warehouse(models.Model):
    name = models.CharField(max_length=100)
    location = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return self.name

class WarehouseLocation(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='locations')
    zone = models.CharField(max_length=20)
    shelf = models.CharField(max_length=20)
    description = models.TextField(blank=True)
    
    def __str__(self):
        return f"{self.warehouse.name} - Zone {self.zone}, Shelf {self.shelf}"

class Stock(models.Model):
    """Model to track product stock levels and thresholds."""
    product = models.ForeignKey('sellers.Product', on_delete=models.CASCADE, related_name='stock')
    min_quantity = models.PositiveIntegerField(default=10, help_text="Minimum stock level before reordering")
    max_quantity = models.PositiveIntegerField(default=100, help_text="Maximum stock level to maintain")
    reorder_quantity = models.PositiveIntegerField(default=50, help_text="Quantity to reorder when stock is low")
    last_reorder_date = models.DateField(null=True, blank=True)
    
    def __str__(self):
        return f"Stock settings for {self.product.name_en}"
    
    @property
    def is_low_stock(self):
        """Check if the product has low stock in any warehouse."""
        total_quantity = sum(record.quantity for record in self.product.inventoryrecord_set.all())
        return total_quantity <= self.min_quantity
    
    @property
    def total_quantity(self):
        """Get the total quantity across all warehouses."""
        return sum(record.quantity for record in self.product.inventoryrecord_set.all())

class InventoryRecord(models.Model):
    product = models.ForeignKey('sellers.Product', on_delete=models.CASCADE)
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    location = models.ForeignKey(WarehouseLocation, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.IntegerField()
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('product', 'warehouse', 'location')
    
    def __str__(self):
        return f"{self.product.name_en} - {self.warehouse.name} - {self.quantity} units"

class InventoryMovement(models.Model):
    MOVEMENT_TYPES = (
        ('receive', 'Receive'),
        ('transfer', 'Transfer'),
        ('adjustment', 'Adjustment'),
        ('order', 'Order'),
        ('return', 'Return'),
    )
    
    product = models.ForeignKey('sellers.Product', on_delete=models.CASCADE)
    from_warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='outgoing_movements')
    to_warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='incoming_movements', null=True, blank=True)
    quantity = models.IntegerField()
    movement_type = models.CharField(max_length=20, choices=MOVEMENT_TYPES)
    reference = models.CharField(max_length=100, blank=True)  # Order number, sourcing request, etc.
    created_by = models.ForeignKey('users.User', on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    def __str__(self):
        if self.movement_type == 'transfer' and self.to_warehouse:
            return f"{self.movement_type.capitalize()}: {self.quantity} of {self.product.name_en} from {self.from_warehouse.name} to {self.to_warehouse.name}"
        else:
            return f"{self.movement_type.capitalize()}: {self.quantity} of {self.product.name_en} at {self.from_warehouse.name}"


class StockReservation(models.Model):
    """
    Model to reserve stock for pending orders.
    When an order is created/confirmed, stock is reserved to prevent overselling.
    Reservation is released when order is shipped, cancelled, or expires.
    """
    RESERVATION_STATUS = (
        ('pending', 'Pending'),
        ('confirmed', 'Confirmed'),
        ('fulfilled', 'Fulfilled'),
        ('cancelled', 'Cancelled'),
        ('expired', 'Expired'),
    )

    product = models.ForeignKey('sellers.Product', on_delete=models.CASCADE, related_name='reservations')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='reservations')
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='stock_reservations')
    order_item = models.ForeignKey('orders.OrderItem', on_delete=models.CASCADE, related_name='reservations', null=True, blank=True)

    quantity = models.PositiveIntegerField(validators=[MinValueValidator(1)])
    status = models.CharField(max_length=20, choices=RESERVATION_STATUS, default='pending')

    # Timing
    reserved_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField(null=True, blank=True, help_text="Reservation auto-expires if not fulfilled")
    fulfilled_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)

    # User tracking
    reserved_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, related_name='stock_reservations')

    # Notes
    notes = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)

    class Meta:
        ordering = ['-reserved_at']
        verbose_name = 'Stock Reservation'
        verbose_name_plural = 'Stock Reservations'
        indexes = [
            models.Index(fields=['product', 'warehouse', 'status']),
            models.Index(fields=['order', 'status']),
            models.Index(fields=['expires_at', 'status']),
        ]

    def __str__(self):
        return f"Reservation: {self.quantity}x {self.product.name_en} for {self.order.order_code}"

    @property
    def is_active(self):
        """Check if reservation is still active (not fulfilled, cancelled, or expired)."""
        return self.status in ('pending', 'confirmed')

    @property
    def is_expired(self):
        """Check if reservation has expired."""
        if self.expires_at and timezone.now() > self.expires_at:
            return True
        return False

    def confirm(self):
        """Confirm the reservation."""
        if self.status == 'pending':
            self.status = 'confirmed'
            self.save(update_fields=['status'])
            return True
        return False

    def fulfill(self):
        """Mark reservation as fulfilled (stock shipped)."""
        if self.status in ('pending', 'confirmed'):
            self.status = 'fulfilled'
            self.fulfilled_at = timezone.now()
            self.save(update_fields=['status', 'fulfilled_at'])
            return True
        return False

    def cancel(self, reason=''):
        """Cancel the reservation and release stock."""
        if self.is_active:
            self.status = 'cancelled'
            self.cancelled_at = timezone.now()
            self.cancellation_reason = reason
            self.save(update_fields=['status', 'cancelled_at', 'cancellation_reason'])
            return True
        return False

    def expire(self):
        """Mark reservation as expired."""
        if self.status in ('pending', 'confirmed') and self.is_expired:
            self.status = 'expired'
            self.save(update_fields=['status'])
            return True
        return False

    @classmethod
    def get_reserved_quantity(cls, product, warehouse=None):
        """Get total reserved quantity for a product (optionally in a specific warehouse)."""
        queryset = cls.objects.filter(
            product=product,
            status__in=['pending', 'confirmed']
        )
        if warehouse:
            queryset = queryset.filter(warehouse=warehouse)

        return queryset.aggregate(
            total=models.Sum('quantity')
        )['total'] or 0

    @classmethod
    def get_available_quantity(cls, product, warehouse):
        """Get available quantity (total stock minus reservations)."""
        from stock_keeper.models import WarehouseInventory

        inventory = WarehouseInventory.objects.filter(
            product=product,
            warehouse=warehouse
        ).first()

        if not inventory:
            return 0

        reserved = cls.get_reserved_quantity(product, warehouse)
        return max(0, inventory.quantity - reserved)


class InventoryAlert(models.Model):
    """
    Model to track inventory alerts for products.
    Alerts are created when stock falls below thresholds or other conditions are met.
    """
    ALERT_TYPES = (
        ('low_stock', 'Low Stock'),
        ('out_of_stock', 'Out of Stock'),
        ('overstock', 'Overstock'),
        ('expiring_soon', 'Expiring Soon'),
        ('expired', 'Expired'),
        ('reorder_needed', 'Reorder Needed'),
        ('reservation_expired', 'Reservation Expired'),
    )

    PRIORITY_LEVELS = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    )

    product = models.ForeignKey('sellers.Product', on_delete=models.CASCADE, related_name='inventory_alerts')
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE, related_name='inventory_alerts', null=True, blank=True)

    alert_type = models.CharField(max_length=30, choices=ALERT_TYPES)
    priority = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')

    title = models.CharField(max_length=255)
    message = models.TextField()

    # Threshold tracking
    current_quantity = models.IntegerField(null=True, blank=True)
    threshold_quantity = models.IntegerField(null=True, blank=True)

    # Status
    is_resolved = models.BooleanField(default=False)
    is_acknowledged = models.BooleanField(default=False)
    acknowledged_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='acknowledged_alerts')
    acknowledged_at = models.DateTimeField(null=True, blank=True)
    resolved_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_alerts')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolution_notes = models.TextField(blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Notification tracking
    notification_sent = models.BooleanField(default=False)
    notification_sent_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Inventory Alert'
        verbose_name_plural = 'Inventory Alerts'
        indexes = [
            models.Index(fields=['product', 'alert_type', 'is_resolved']),
            models.Index(fields=['warehouse', 'alert_type', 'is_resolved']),
            models.Index(fields=['priority', 'is_resolved', 'created_at']),
        ]

    def __str__(self):
        return f"{self.get_alert_type_display()}: {self.product.name_en}"

    def acknowledge(self, user):
        """Mark alert as acknowledged."""
        if not self.is_acknowledged:
            self.is_acknowledged = True
            self.acknowledged_by = user
            self.acknowledged_at = timezone.now()
            self.save(update_fields=['is_acknowledged', 'acknowledged_by', 'acknowledged_at'])
            return True
        return False

    def resolve(self, user, notes=''):
        """Mark alert as resolved."""
        if not self.is_resolved:
            self.is_resolved = True
            self.resolved_by = user
            self.resolved_at = timezone.now()
            self.resolution_notes = notes
            self.save(update_fields=['is_resolved', 'resolved_by', 'resolved_at', 'resolution_notes'])
            return True
        return False

    @classmethod
    def create_low_stock_alert(cls, product, warehouse, current_qty, threshold_qty):
        """Create a low stock alert if one doesn't already exist."""
        existing = cls.objects.filter(
            product=product,
            warehouse=warehouse,
            alert_type='low_stock',
            is_resolved=False
        ).exists()

        if not existing:
            priority = 'critical' if current_qty == 0 else 'high' if current_qty <= threshold_qty // 2 else 'medium'
            alert_type = 'out_of_stock' if current_qty == 0 else 'low_stock'

            return cls.objects.create(
                product=product,
                warehouse=warehouse,
                alert_type=alert_type,
                priority=priority,
                title=f"{'Out of Stock' if current_qty == 0 else 'Low Stock'}: {product.name_en}",
                message=f"{product.name_en} at {warehouse.name} has {'no stock remaining' if current_qty == 0 else f'only {current_qty} units remaining'} (threshold: {threshold_qty})",
                current_quantity=current_qty,
                threshold_quantity=threshold_qty
            )
        return None

    @classmethod
    def get_active_alerts(cls, warehouse=None, priority=None, alert_type=None):
        """Get active (unresolved) alerts with optional filters."""
        queryset = cls.objects.filter(is_resolved=False)

        if warehouse:
            queryset = queryset.filter(warehouse=warehouse)
        if priority:
            queryset = queryset.filter(priority=priority)
        if alert_type:
            queryset = queryset.filter(alert_type=alert_type)

        return queryset