# orders/models.py
from django.db import models
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
import uuid

def generate_order_code():
    """Generate a shorter order code with # prefix"""
    from django.db.utils import OperationalError, ProgrammingError, InternalError
    from django.db import connection
    from django.utils import timezone
    import random

    today = timezone.now().date()
    date_part = f"{today.year % 100:02d}{today.month:02d}{today.day:02d}"

    try:
        # Check if we're in a migration context or if the table exists
        from django.apps import apps
        if not apps.ready:
            # During migrations, just return a unique code
            return f"#{date_part}{random.randint(1, 999):03d}"

        from .models import Order

        existing_orders_today = Order.objects.filter(
            order_code__startswith=f"#{date_part}"
        ).count()
    except (OperationalError, ProgrammingError, InternalError, Exception):
        # During migrations or if table doesn't exist, return unique code
        return f"#{date_part}{random.randint(1, 999):03d}"

    order_number = existing_orders_today + 1
    code = f"#{date_part}{order_number:03d}"

    try:
        while Order.objects.filter(order_code=code).exists():
            order_number += 1
            code = f"#{date_part}{order_number:03d}"
    except (OperationalError, ProgrammingError, InternalError, Exception):
        pass

    return code

class Order(models.Model):
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('processing', _('Processing')),
        ('confirmed', _('Confirmed')),
        ('packaged', _('Packaged')),
        ('shipped', _('Shipped')),
        ('delivered', _('Delivered')),
        ('cancelled', _('Cancelled')),
        ('returned', _('Returned')),
        # Call center specific statuses
        ('no_answer_1st', _('No Answer - 1st Attempt')),
        ('no_answer_2nd', _('No Answer - 2nd Attempt')),
        ('no_answer_final', _('No Answer - Final Attempt')),
        ('postponed', _('Postponed')),
        ('invalid_number', _('Invalid Number')),
        ('call_back_later', _('Call Back Later')),
        ('escalate_manager', _('Escalate to Manager')),
    ]

    # Workflow status choices
    WORKFLOW_STATUS_CHOICES = [
        ('seller_submitted', _('Seller Submitted')),
        ('callcenter_review', _('Call Center Review')),
        ('callcenter_approved', _('Call Center Approved')),
        ('pick_and_pack', _('Pick and Pack')),
        ('stockkeeper_approved', _('Stock Keeper Approved')),
        ('packaging_in_progress', _('Packaging In Progress')),
        ('packaging_completed', _('Packaging Completed')),
        ('ready_for_delivery', _('Ready for Delivery')),
        ('delivery_in_progress', _('Delivery In Progress')),
        ('delivery_completed', _('Delivery Completed')),
        ('cancelled', _('Cancelled')),
    ]

    order_code = models.CharField(max_length=50, unique=True, verbose_name=_('Order Code'), default=generate_order_code)
    customer = models.CharField(max_length=255, verbose_name=_('Customer'), help_text=_('Customer full name'), default='Unknown Customer')
    date = models.DateTimeField(default=timezone.now, verbose_name=_('Order Date'))
    # Deprecated direct product relationship - use OrderItem instead
    product = models.ForeignKey('sellers.Product', on_delete=models.PROTECT, related_name='direct_orders', verbose_name=_('Legacy Product'), null=True, blank=True)
    quantity = models.PositiveIntegerField(verbose_name=_('Quantity'), default=1)
    price_per_unit = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Price Per Unit (AED)'), default=0, help_text=_('Price in UAE Dirhams'))
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name=_('Status'))
    
    # Workflow tracking
    workflow_status = models.CharField(max_length=30, choices=WORKFLOW_STATUS_CHOICES, default='seller_submitted', verbose_name=_('Workflow Status'))
    
    # Additional fields for detailed view
    customer_phone = models.CharField(max_length=20, blank=True, verbose_name=_('Customer Phone'))
    seller_email = models.EmailField(blank=True, verbose_name=_('Seller Email'))
    seller = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='orders', verbose_name=_('Seller'), null=True, blank=True)
    store_link = models.URLField(verbose_name=_('Store Link'), help_text=_('Product link is required'))
    
    # Shipping information
    street_address = models.CharField(max_length=255, blank=True, verbose_name=_('Street Address'), help_text=_('Street address and building number'))
    shipping_address = models.TextField(blank=True, verbose_name=_('Shipping Address'))
    city = models.CharField(max_length=100, blank=True, verbose_name=_('City'))
    state = models.CharField(max_length=100, blank=True, verbose_name=_('Area'), help_text=_('Area/Region within city'))
    zip_code = models.CharField(max_length=20, blank=True, verbose_name=_('ZIP Code'))
    country = models.CharField(max_length=100, blank=True, verbose_name=_('Country'))
    delivery_area = models.CharField(max_length=100, blank=True, verbose_name=_('Delivery Area'), help_text=_('Confirmed delivery area by call center'))
    
    # UAE specific fields
    emirate = models.CharField(max_length=50, blank=True, verbose_name=_('Emirate'), help_text=_('UAE Emirate'))
    region = models.CharField(max_length=50, blank=True, verbose_name=_('Region'), help_text=_('UAE Region within Emirate'))
    
    # Order details
    notes = models.TextField(blank=True, verbose_name=_('Order Notes'))
    internal_notes = models.TextField(blank=True, verbose_name=_('Internal Notes'))
    
    # Call center agent assignment
    agent = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_orders', verbose_name=_('Call Center Agent'))
    assigned_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Assigned At'))
    
    # Manager escalation tracking
    escalated_to_manager = models.BooleanField(default=False, verbose_name=_('Escalated to Manager'))
    escalated_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Escalated At'))
    escalated_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='escalated_orders', verbose_name=_('Escalated By'))
    escalation_reason = models.TextField(blank=True, verbose_name=_('Escalation Reason'), help_text=_('Reason for escalating to manager'))
    postponed_until = models.DateTimeField(null=True, blank=True, verbose_name=_('Postponed Until'), help_text=_('Date and time when order should be processed'))
    call_back_time = models.DateTimeField(null=True, blank=True, verbose_name=_('Call Back Time'), help_text=_('Date and time for call back set by call center'))
    no_answer_time = models.DateTimeField(null=True, blank=True, verbose_name=_('No Answer Time'), help_text=_('Date and time for next call attempt when customer did not answer'))
    
    # Tracking and delivery information
    tracking_number = models.CharField(max_length=100, blank=True, verbose_name=_('Tracking Number'))
    cancelled_reason = models.TextField(blank=True, verbose_name=_('Cancellation Reason'))
    
    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, verbose_name=_('Created At'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Updated At'))

    class Meta:
        verbose_name = _('Order')
        verbose_name_plural = _('Orders')
        ordering = ['-date']

    def __str__(self):
        return f"{self.order_code} - {self.customer}"

    @property
    def total_price(self):
        """Calculate total price in AED"""
        # If we have order items, calculate based on them
        if hasattr(self, 'items') and self.items.exists():
            return sum(item.total_price for item in self.items.all())
        # Fall back to legacy calculation
        return self.quantity * self.price_per_unit

    @property
    def total_price_aed(self):
        """Get total price formatted in AED"""
        return f"AED {self.total_price:,.2f}"

    @property
    def price_per_unit_aed(self):
        """Get price per unit formatted in AED"""
        return f"AED {self.price_per_unit:,.2f}"

    def advance_workflow(self, new_status, user, notes=""):
        """Advance the order workflow to the next stage"""
        workflow_progression = {
            'seller_submitted': 'callcenter_review',
            'callcenter_review': 'callcenter_approved',
            'callcenter_approved': 'packaging_in_progress',
            'packaging_in_progress': 'packaging_completed',
            'packaging_completed': 'ready_for_delivery',
            'ready_for_delivery': 'delivery_in_progress',
            'delivery_in_progress': 'delivery_completed',
        }
        
        if self.workflow_status in workflow_progression:
            self.workflow_status = workflow_progression[self.workflow_status]
            self.save()
            
            # Create workflow log entry
            OrderWorkflowLog.objects.create(
                order=self,
                from_status=workflow_progression[self.workflow_status],
                to_status=new_status,
                user=user,
                notes=notes
            )
            
            return True
        return False

class OrderWorkflowLog(models.Model):
    """Log of order workflow transitions"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='workflow_logs')
    from_status = models.CharField(max_length=30, choices=Order.WORKFLOW_STATUS_CHOICES)
    to_status = models.CharField(max_length=30, choices=Order.WORKFLOW_STATUS_CHOICES)
    user = models.ForeignKey('users.User', on_delete=models.CASCADE, verbose_name=_('User who made the change'))
    notes = models.TextField(blank=True, verbose_name=_('Notes about the transition'))
    timestamp = models.DateTimeField(default=timezone.now, verbose_name=_('Timestamp'))
    
    class Meta:
        verbose_name = _('Order Workflow Log')
        verbose_name_plural = _('Order Workflow Logs')
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.order.order_code} - {self.from_status} → {self.to_status} by {self.user.get_full_name() or self.user.email}"

class OrderItem(models.Model):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey('sellers.Product', on_delete=models.CASCADE)
    quantity = models.IntegerField()
    price = models.DecimalField(max_digits=10, decimal_places=2, verbose_name=_('Price (AED)'))
    
    class Meta:
        verbose_name = _('Order Item')
        verbose_name_plural = _('Order Items')
    
    def __str__(self):
        return f"{self.order.order_code} - {self.product.name_en} x {self.quantity}"
    
    @property
    def total_price(self):
        return self.quantity * self.price
    
    @property
    def total_price_aed(self):
        return f"AED {self.total_price:,.2f}"


class StatusLog(models.Model):
    """Track status changes for orders"""
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='status_logs', verbose_name=_('Order'))
    old_status = models.CharField(max_length=50, verbose_name=_('Old Status'), blank=True, null=True)
    new_status = models.CharField(max_length=50, verbose_name=_('New Status'))
    changed_by = models.ForeignKey('users.User', on_delete=models.CASCADE, verbose_name=_('Changed By'))
    change_reason = models.TextField(blank=True, null=True, verbose_name=_('Change Reason'))
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name=_('Timestamp'))
    is_manager_change = models.BooleanField(default=False, verbose_name=_('Is Manager Change'))
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = _('Status Log')
        verbose_name_plural = _('Status Logs')
    
    def __str__(self):
        return f"{self.order.order_code} - {self.old_status} → {self.new_status} by {self.changed_by.username}"


class Return(models.Model):
    """Comprehensive return management for orders"""

    RETURN_REASON_CHOICES = [
        ('damaged', _('Product Damaged')),
        ('defective', _('Product Defective/Not Working')),
        ('wrong_item', _('Wrong Item Delivered')),
        ('not_as_described', _('Not As Described')),
        ('size_issue', _('Size/Fit Issue')),
        ('quality_issue', _('Quality Issue')),
        ('customer_regret', _('Customer Changed Mind')),
        ('duplicate_order', _('Duplicate Order')),
        ('late_delivery', _('Late Delivery')),
        ('other', _('Other Reason')),
    ]

    RETURN_STATUS_CHOICES = [
        ('requested', _('Return Requested')),
        ('pending_approval', _('Pending Approval')),
        ('approved', _('Approved')),
        ('rejected', _('Rejected')),
        ('pickup_scheduled', _('Pickup Scheduled')),
        ('in_transit', _('In Transit to Warehouse')),
        ('received', _('Received at Warehouse')),
        ('inspecting', _('Under Inspection')),
        ('inspected', _('Inspection Completed')),
        ('approved_for_refund', _('Approved for Refund')),
        ('refund_processing', _('Refund Processing')),
        ('refund_completed', _('Refund Completed')),
        ('restocked', _('Item Restocked')),
        ('completed', _('Return Completed')),
        ('cancelled', _('Return Cancelled')),
    ]

    ITEM_CONDITION_CHOICES = [
        ('excellent', _('Excellent - Like New')),
        ('good', _('Good - Minor Wear')),
        ('fair', _('Fair - Noticeable Wear')),
        ('poor', _('Poor - Significant Damage')),
        ('damaged', _('Damaged - Not Resellable')),
        ('defective', _('Defective/Not Working')),
        ('opened', _('Opened Package Only')),
        ('unopened', _('Unopened Package')),
    ]

    REFUND_METHOD_CHOICES = [
        ('original_payment', _('Original Payment Method')),
        ('bank_transfer', _('Bank Transfer')),
        ('store_credit', _('Store Credit')),
        ('cash', _('Cash')),
        ('wallet', _('Wallet/Account Balance')),
    ]

    REFUND_STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('approved', _('Approved')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
        ('cancelled', _('Cancelled')),
        ('partial', _('Partial Refund')),
    ]

    # Basic Information
    return_code = models.CharField(max_length=50, unique=True, verbose_name=_('Return Code'))
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name='returns', verbose_name=_('Order'))
    customer = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='returns', verbose_name=_('Customer'), null=True, blank=True)

    # Return Request Details
    return_reason = models.CharField(max_length=30, choices=RETURN_REASON_CHOICES, verbose_name=_('Return Reason'))
    return_description = models.TextField(verbose_name=_('Detailed Description'), help_text=_('Detailed explanation of the return reason'))
    return_status = models.CharField(max_length=30, choices=RETURN_STATUS_CHOICES, default='requested', verbose_name=_('Return Status'))

    # Evidence and Documentation
    return_photo_1 = models.ImageField(upload_to='returns/photos/', blank=True, null=True, verbose_name=_('Return Photo 1'))
    return_photo_2 = models.ImageField(upload_to='returns/photos/', blank=True, null=True, verbose_name=_('Return Photo 2'))
    return_photo_3 = models.ImageField(upload_to='returns/photos/', blank=True, null=True, verbose_name=_('Return Photo 3'))
    return_video = models.FileField(upload_to='returns/videos/', blank=True, null=True, verbose_name=_('Return Video Evidence'))

    # Approval Workflow
    approved_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_returns', verbose_name=_('Approved By'))
    approved_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Approved At'))
    rejection_reason = models.TextField(blank=True, verbose_name=_('Rejection Reason'))

    # Return Shipping Information
    return_tracking_number = models.CharField(max_length=100, blank=True, verbose_name=_('Return Tracking Number'))
    return_carrier = models.CharField(max_length=100, blank=True, verbose_name=_('Return Carrier'))
    pickup_scheduled_date = models.DateTimeField(null=True, blank=True, verbose_name=_('Pickup Scheduled Date'))
    pickup_address = models.TextField(blank=True, verbose_name=_('Pickup Address'))

    # Warehouse Receipt
    received_at_warehouse = models.DateTimeField(null=True, blank=True, verbose_name=_('Received at Warehouse'))
    received_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='received_returns', verbose_name=_('Received By'))

    # Inspection Details
    inspector = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='inspected_returns', verbose_name=_('Inspector'))
    inspection_started_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Inspection Started'))
    inspection_completed_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Inspection Completed'))
    item_condition = models.CharField(max_length=20, choices=ITEM_CONDITION_CHOICES, blank=True, verbose_name=_('Item Condition'))
    inspection_notes = models.TextField(blank=True, verbose_name=_('Inspection Notes'))
    inspection_photos = models.JSONField(default=list, blank=True, verbose_name=_('Inspection Photos URLs'))

    # Restocking Decision
    can_restock = models.BooleanField(default=False, verbose_name=_('Can Be Restocked'))
    restocked = models.BooleanField(default=False, verbose_name=_('Item Restocked'))
    restocked_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Restocked At'))
    restocked_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='restocked_returns', verbose_name=_('Restocked By'))

    # Refund Information
    refund_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Refund Amount (AED)'))
    refund_method = models.CharField(max_length=30, choices=REFUND_METHOD_CHOICES, blank=True, verbose_name=_('Refund Method'))
    refund_status = models.CharField(max_length=20, choices=REFUND_STATUS_CHOICES, default='pending', verbose_name=_('Refund Status'))
    refund_processed_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='processed_refunds', verbose_name=_('Refund Processed By'))
    refund_processed_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Refund Processed At'))
    refund_reference = models.CharField(max_length=100, blank=True, verbose_name=_('Refund Reference Number'))
    refund_notes = models.TextField(blank=True, verbose_name=_('Refund Notes'))

    # Deductions
    restocking_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Restocking Fee (AED)'))
    damage_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Damage Deduction (AED)'))
    shipping_cost_deduction = models.DecimalField(max_digits=10, decimal_places=2, default=0, verbose_name=_('Shipping Cost Deduction (AED)'))

    # Additional Fields
    priority = models.IntegerField(default=0, verbose_name=_('Priority Level'), help_text=_('Higher number = higher priority'))
    requires_manager_approval = models.BooleanField(default=False, verbose_name=_('Requires Manager Approval'))
    customer_contacted = models.BooleanField(default=False, verbose_name=_('Customer Contacted'))
    customer_contact_notes = models.TextField(blank=True, verbose_name=_('Customer Contact Notes'))

    # Timestamps
    created_at = models.DateTimeField(default=timezone.now, verbose_name=_('Return Requested At'))
    updated_at = models.DateTimeField(auto_now=True, verbose_name=_('Last Updated'))
    completed_at = models.DateTimeField(null=True, blank=True, verbose_name=_('Return Completed At'))

    class Meta:
        verbose_name = _('Return')
        verbose_name_plural = _('Returns')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['return_code']),
            models.Index(fields=['return_status']),
            models.Index(fields=['refund_status']),
            models.Index(fields=['created_at']),
            models.Index(fields=['order']),
        ]

    def __str__(self):
        return f"{self.return_code} - {self.order.order_code}"

    def save(self, *args, **kwargs):
        # Generate return code if not exists
        if not self.return_code:
            import random
            from django.utils import timezone
            today = timezone.now().date()
            date_part = f"RET{today.year % 100:02d}{today.month:02d}{today.day:02d}"

            # Get count of returns today
            existing_returns_today = Return.objects.filter(
                return_code__startswith=date_part
            ).count()

            return_number = existing_returns_today + 1
            self.return_code = f"{date_part}{return_number:04d}"

            # Ensure uniqueness
            while Return.objects.filter(return_code=self.return_code).exists():
                return_number += 1
                self.return_code = f"{date_part}{return_number:04d}"

        super().save(*args, **kwargs)

    @property
    def total_deductions(self):
        """Calculate total deductions"""
        return self.restocking_fee + self.damage_deduction + self.shipping_cost_deduction

    @property
    def net_refund_amount(self):
        """Calculate net refund amount after deductions"""
        return self.refund_amount - self.total_deductions

    @property
    def net_refund_amount_aed(self):
        """Get net refund amount formatted in AED"""
        return f"AED {self.net_refund_amount:,.2f}"

    @property
    def refund_amount_aed(self):
        """Get refund amount formatted in AED"""
        return f"AED {self.refund_amount:,.2f}"

    @property
    def is_pending_approval(self):
        """Check if return is awaiting approval"""
        return self.return_status in ['requested', 'pending_approval']

    @property
    def is_approved(self):
        """Check if return is approved"""
        return self.return_status not in ['requested', 'pending_approval', 'rejected', 'cancelled']

    @property
    def is_completed(self):
        """Check if return process is completed"""
        return self.return_status == 'completed'

    @property
    def days_since_request(self):
        """Calculate days since return was requested"""
        from django.utils import timezone
        delta = timezone.now() - self.created_at
        return delta.days


class ReturnItem(models.Model):
    """Individual items in a return (for orders with multiple items)"""
    return_request = models.ForeignKey(Return, on_delete=models.CASCADE, related_name='items', verbose_name=_('Return'))
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, verbose_name=_('Order Item'))
    quantity = models.PositiveIntegerField(verbose_name=_('Quantity to Return'))
    reason = models.CharField(max_length=30, choices=Return.RETURN_REASON_CHOICES, verbose_name=_('Item Return Reason'))
    condition = models.CharField(max_length=20, choices=Return.ITEM_CONDITION_CHOICES, blank=True, verbose_name=_('Item Condition'))
    notes = models.TextField(blank=True, verbose_name=_('Item Notes'))

    class Meta:
        verbose_name = _('Return Item')
        verbose_name_plural = _('Return Items')

    def __str__(self):
        return f"{self.return_request.return_code} - {self.order_item.product.name_en} x {self.quantity}"

    @property
    def refund_value(self):
        """Calculate refund value for this item"""
        return self.order_item.price * self.quantity


class ReturnStatusLog(models.Model):
    """Track status changes for returns"""
    return_request = models.ForeignKey(Return, on_delete=models.CASCADE, related_name='status_logs', verbose_name=_('Return'))
    old_status = models.CharField(max_length=30, verbose_name=_('Old Status'), blank=True)
    new_status = models.CharField(max_length=30, verbose_name=_('New Status'))
    changed_by = models.ForeignKey('users.User', on_delete=models.CASCADE, verbose_name=_('Changed By'))
    notes = models.TextField(blank=True, verbose_name=_('Notes'))
    timestamp = models.DateTimeField(default=timezone.now, verbose_name=_('Timestamp'))

    class Meta:
        ordering = ['-timestamp']
        verbose_name = _('Return Status Log')
        verbose_name_plural = _('Return Status Logs')

    def __str__(self):
        return f"{self.return_request.return_code} - {self.old_status} → {self.new_status}"