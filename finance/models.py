# finance/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from decimal import Decimal
import uuid

User = get_user_model()

def generate_payment_id():
    """Generate a unique payment ID for Truvo payments."""
    return f"TRU-{uuid.uuid4().hex[:12].upper()}"

class Payment(models.Model):
    PAYMENT_METHODS = (
        ('cash', 'Cash'),
        ('cod', 'Cash on Delivery (COD)'),
        ('credit_card', 'Credit Card'),
        ('bank_transfer', 'Bank Transfer'),
        ('paypal', 'PayPal'),
        ('truvo', 'Truvo Payment'),
    )
    
    PAYMENT_STATUS = (
        ('pending', 'Pending'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('refunded', 'Refunded'),
        ('processing', 'Processing'),
    )
    
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=20, choices=PAYMENT_METHODS)
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='pending')
    transaction_id = models.CharField(max_length=100, blank=True)
    payment_date = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)
    
    # Additional fields for better payment tracking
    seller = models.ForeignKey('users.User', on_delete=models.CASCADE, null=True, blank=True, related_name='seller_payments')
    customer_name = models.CharField(max_length=255, blank=True)
    customer_email = models.EmailField(blank=True)
    customer_phone = models.CharField(max_length=20, blank=True)
    
    # Payment processing details
    processor_fee = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'))
    currency = models.CharField(max_length=3, default='AED')
    
    # Payment verification
    is_verified = models.BooleanField(default=False)
    verified_at = models.DateTimeField(null=True, blank=True)
    verified_by = models.ForeignKey('users.User', on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_payments')
    
    class Meta:
        ordering = ['-payment_date']
        verbose_name = 'Payment'
        verbose_name_plural = 'Payments'
    
    def __str__(self):
        return f"Payment {self.transaction_id or self.id} - {self.amount} {self.currency}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate net amount if not set
        if not self.net_amount:
            self.net_amount = self.amount - self.processor_fee
        super().save(*args, **kwargs)

class TruvoPayment(models.Model):
    """Truvo Payment Integration Model"""
    
    PAYMENT_STATUS = (
        ('initiated', 'Initiated'),
        ('processing', 'Processing'),
        ('completed', 'Completed'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
        ('refunded', 'Refunded'),
    )
    
    # Payment identification
    payment_id = models.CharField(max_length=100, unique=True, default=generate_payment_id)
    truvo_transaction_id = models.CharField(max_length=100, blank=True)
    
    # Payment details
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    currency = models.CharField(max_length=3, default='AED')
    payment_status = models.CharField(max_length=20, choices=PAYMENT_STATUS, default='initiated')
    
    # Customer information
    customer_name = models.CharField(max_length=255)
    customer_email = models.EmailField()
    customer_phone = models.CharField(max_length=20)
    
    # Order reference
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='truvo_payments', null=True, blank=True)
    seller = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='truvo_payments')
    
    # Payment processing
    payment_method = models.CharField(max_length=50, default='truvo')
    processor_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    net_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    
    # Additional data
    payment_url = models.URLField(blank=True)
    callback_url = models.URLField(blank=True)
    metadata = models.JSONField(default=dict, blank=True)
    error_message = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Truvo Payment'
        verbose_name_plural = 'Truvo Payments'
    
    def __str__(self):
        return f"Truvo Payment {self.payment_id} - {self.amount} {self.currency}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate net amount
        if not self.net_amount:
            self.net_amount = self.amount - self.processor_fee
        
        # Update completed_at when status changes to completed
        if self.payment_status == 'completed' and not self.completed_at:
            self.completed_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    @property
    def is_successful(self):
        return self.payment_status == 'completed'
    
    @property
    def is_failed(self):
        return self.payment_status in ['failed', 'cancelled']
    
    @property
    def is_pending(self):
        return self.payment_status in ['initiated', 'processing']

class Invoice(models.Model):
    INVOICE_STATUS = (
        ('draft', 'Draft'),
        ('sent', 'Sent'),
        ('paid', 'Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    )
    
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='invoices')
    invoice_number = models.CharField(max_length=50, unique=True)
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    status = models.CharField(max_length=20, choices=INVOICE_STATUS, default='draft')
    due_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(blank=True)
    
    def __str__(self):
        return f"Invoice {self.invoice_number} - {self.order.order_code}"

class SellerFee(models.Model):
    seller = models.ForeignKey('users.User', on_delete=models.CASCADE)
    fee_percentage = models.DecimalField(max_digits=5, decimal_places=2)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.seller.get_full_name()} - {self.fee_percentage}%"

class OrderFee(models.Model):
    """Model to store fees for each order"""
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='order_fees')
    
    # Fee amounts
    seller_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    upsell_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    confirmation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    cancellation_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    fulfillment_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    shipping_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    return_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    warehouse_fee = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Calculated totals
    total_fees = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=5.00)  # 5% VAT
    tax_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    final_total = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='updated_fees')
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Order Fee'
        verbose_name_plural = 'Order Fees'
        ordering = ['-updated_at']
    
    def __str__(self):
        return f"Fees for Order {self.order.order_code}"
    
    def save(self, *args, **kwargs):
        # Auto-calculate totals
        self.total_fees = (
            self.seller_fee + self.upsell_fee + self.confirmation_fee + 
            self.cancellation_fee + self.fulfillment_fee + self.shipping_fee + 
            self.return_fee + self.warehouse_fee
        )
        
        # Calculate tax
        base_price = float(self.order.price_per_unit * self.order.quantity)
        self.tax_amount = (base_price + float(self.total_fees)) * (float(self.tax_rate) / 100.0)
        
        # Calculate final total
        self.final_total = base_price + float(self.total_fees) + float(self.tax_amount)
        
        super().save(*args, **kwargs)
    
    def get_fees_dict(self):
        """Return fees as dictionary"""
        return {
            'seller_fee': float(self.seller_fee),
            'upsell': float(self.upsell_fee),
            'confirmation': float(self.confirmation_fee),
            'cancellation': float(self.cancellation_fee),
            'fulfillment': float(self.fulfillment_fee),
            'shipping': float(self.shipping_fee),
            'return': float(self.return_fee),
            'warehouse': float(self.warehouse_fee),
        }

class PaymentPlatform(models.Model):
    """Model to store payment platform integrations"""
    
    PLATFORM_CHOICES = [
        ('amazon_seller', 'Amazon Seller Central'),
        ('shopify', 'Shopify'),
        ('magento', 'Magento'),
        ('woocommerce', 'WooCommerce'),
        ('etsy', 'Etsy'),
        ('ebay', 'eBay'),
        ('other', 'Other'),
    ]
    
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('pending', 'Pending Verification'),
        ('error', 'Connection Error'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payment_platforms')
    platform_name = models.CharField(_('platform name'), max_length=50, choices=PLATFORM_CHOICES)
    store_name = models.CharField(_('store name'), max_length=200)
    store_url = models.URLField(_('store URL'), blank=True, null=True)
    api_key = models.CharField(_('API key'), max_length=255, blank=True, null=True)
    api_secret = models.CharField(_('API secret'), max_length=255, blank=True, null=True)
    access_token = models.TextField(_('access token'), blank=True, null=True)
    refresh_token = models.TextField(_('refresh token'), blank=True, null=True)
    merchant_id = models.CharField(_('merchant ID'), max_length=100, blank=True, null=True)
    webhook_url = models.URLField(_('webhook URL'), blank=True, null=True)
    
    # Connection status
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES, default='pending')
    last_sync = models.DateTimeField(_('last sync'), null=True, blank=True)
    sync_frequency = models.CharField(_('sync frequency'), max_length=20, 
                                    choices=[('daily', 'Daily'), ('weekly', 'Weekly'), ('monthly', 'Monthly')], 
                                    default='daily')
    
    # Additional settings
    auto_sync = models.BooleanField(_('auto sync'), default=True)
    sync_orders = models.BooleanField(_('sync orders'), default=True)
    sync_payments = models.BooleanField(_('sync payments'), default=True)
    sync_inventory = models.BooleanField(_('sync inventory'), default=False)
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    notes = models.TextField(_('notes'), blank=True, null=True)
    
    class Meta:
        verbose_name = _('payment platform')
        verbose_name_plural = _('payment platforms')
        unique_together = ('user', 'platform_name', 'store_name')
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.user.email} - {self.get_platform_name_display()} - {self.store_name}"
    
    def get_platform_display_name(self):
        """Get the display name for the platform"""
        return self.get_platform_name_display()
    
    def is_connected(self):
        """Check if the platform is properly connected"""
        return self.status == 'active' and (self.api_key or self.access_token)
    
    def needs_refresh(self):
        """Check if the connection needs to be refreshed"""
        if not self.last_sync:
            return True
        # Check if sync is overdue based on frequency
        now = timezone.now()
        if self.sync_frequency == 'daily':
            return (now - self.last_sync).days >= 1
        elif self.sync_frequency == 'weekly':
            return (now - self.last_sync).days >= 7
        elif self.sync_frequency == 'monthly':
            return (now - self.last_sync).days >= 30
        return False

class PlatformSyncLog(models.Model):
    """Model to track synchronization logs for payment platforms"""
    
    SYNC_TYPE_CHOICES = [
        ('orders', 'Orders'),
        ('payments', 'Payments'),
        ('inventory', 'Inventory'),
        ('products', 'Products'),
        ('customers', 'Customers'),
    ]
    
    STATUS_CHOICES = [
        ('success', 'Success'),
        ('error', 'Error'),
        ('partial', 'Partial Success'),
        ('pending', 'Pending'),
    ]
    
    platform = models.ForeignKey(PaymentPlatform, on_delete=models.CASCADE, related_name='sync_logs')
    sync_type = models.CharField(_('sync type'), max_length=20, choices=SYNC_TYPE_CHOICES)
    status = models.CharField(_('status'), max_length=20, choices=STATUS_CHOICES)
    records_processed = models.IntegerField(_('records processed'), default=0)
    records_synced = models.IntegerField(_('records synced'), default=0)
    error_message = models.TextField(_('error message'), blank=True, null=True)
    started_at = models.DateTimeField(_('started at'), auto_now_add=True)
    completed_at = models.DateTimeField(_('completed at'), null=True, blank=True)
    
    class Meta:
        verbose_name = _('platform sync log')
        verbose_name_plural = _('platform sync logs')
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.platform.store_name} - {self.get_sync_type_display()} - {self.status}"
    
    def duration(self):
        """Calculate the duration of the sync operation"""
        if self.completed_at:
            return self.completed_at - self.started_at
        return timezone.now() - self.started_at


# Import COD models
from .cod_models import CODPayment, CODReconciliation


class SellerPayout(models.Model):
    """
    Seller Payout Model - Tracks payouts to sellers for their orders
    """

    PAYOUT_STATUS = (
        ('pending', _('Pending')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('failed', _('Failed')),
        ('cancelled', _('Cancelled')),
    )

    PAYOUT_METHOD = (
        ('bank_transfer', _('Bank Transfer')),
        ('cash', _('Cash')),
        ('cheque', _('Cheque')),
        ('wallet', _('Wallet')),
    )

    # Payout Reference
    payout_reference = models.CharField(_('Payout Reference'), max_length=50, unique=True)
    seller = models.ForeignKey(User, on_delete=models.CASCADE, related_name='payouts',
                               verbose_name=_('Seller'))

    # Amount Details
    gross_amount = models.DecimalField(_('Gross Amount'), max_digits=10, decimal_places=2)
    commission_amount = models.DecimalField(_('Commission Amount'), max_digits=10, decimal_places=2, default=0.00)
    fees_amount = models.DecimalField(_('Fees Amount'), max_digits=10, decimal_places=2, default=0.00)
    net_amount = models.DecimalField(_('Net Amount'), max_digits=10, decimal_places=2)
    currency = models.CharField(_('Currency'), max_length=3, default='AED')

    # Period Details
    period_start = models.DateField(_('Period Start'))
    period_end = models.DateField(_('Period End'))
    orders_count = models.PositiveIntegerField(_('Orders Count'), default=0)

    # Payment Details
    payout_method = models.CharField(_('Payout Method'), max_length=20, choices=PAYOUT_METHOD,
                                    default='bank_transfer')
    status = models.CharField(_('Status'), max_length=20, choices=PAYOUT_STATUS, default='pending')

    # Bank Details (optional)
    bank_name = models.CharField(_('Bank Name'), max_length=100, blank=True)
    account_number = models.CharField(_('Account Number'), max_length=50, blank=True)
    iban = models.CharField(_('IBAN'), max_length=50, blank=True)

    # Processing Details
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='processed_payouts', verbose_name=_('Processed By'))
    processed_at = models.DateTimeField(_('Processed At'), null=True, blank=True)
    transaction_reference = models.CharField(_('Transaction Reference'), max_length=100, blank=True)

    # Notes
    notes = models.TextField(_('Notes'), blank=True)
    failure_reason = models.TextField(_('Failure Reason'), blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Seller Payout')
        verbose_name_plural = _('Seller Payouts')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.payout_reference} - {self.seller.get_full_name()} - {self.net_amount} {self.currency}"

    def save(self, *args, **kwargs):
        # Generate payout reference if not set
        if not self.payout_reference:
            import uuid
            self.payout_reference = f"PAY-{uuid.uuid4().hex[:8].upper()}"

        # Calculate net amount if not set
        if not self.net_amount:
            self.net_amount = self.gross_amount - self.commission_amount - self.fees_amount

        super().save(*args, **kwargs)

    def mark_processing(self, processed_by):
        """Mark payout as processing"""
        self.status = 'processing'
        self.processed_by = processed_by
        self.save()

    def mark_completed(self, transaction_reference=None):
        """Mark payout as completed"""
        self.status = 'completed'
        self.processed_at = timezone.now()
        if transaction_reference:
            self.transaction_reference = transaction_reference
        self.save()

    def mark_failed(self, reason):
        """Mark payout as failed"""
        self.status = 'failed'
        self.failure_reason = reason
        self.save()


class Refund(models.Model):
    """
    Refund Model - Tracks refunds for orders/payments
    """

    REFUND_STATUS = (
        ('pending', _('Pending')),
        ('approved', _('Approved')),
        ('processing', _('Processing')),
        ('completed', _('Completed')),
        ('rejected', _('Rejected')),
    )

    REFUND_REASON = (
        ('customer_request', _('Customer Request')),
        ('defective_product', _('Defective Product')),
        ('wrong_item', _('Wrong Item Delivered')),
        ('not_as_described', _('Not as Described')),
        ('delivery_issue', _('Delivery Issue')),
        ('duplicate_order', _('Duplicate Order')),
        ('cancelled_order', _('Cancelled Order')),
        ('other', _('Other')),
    )

    REFUND_METHOD = (
        ('original_payment', _('Original Payment Method')),
        ('bank_transfer', _('Bank Transfer')),
        ('store_credit', _('Store Credit')),
        ('cash', _('Cash')),
    )

    # Refund Reference
    refund_reference = models.CharField(_('Refund Reference'), max_length=50, unique=True)

    # Related Objects
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='refunds',
                             verbose_name=_('Order'))
    payment = models.ForeignKey('finance.Payment', on_delete=models.SET_NULL, null=True, blank=True,
                               related_name='refunds', verbose_name=_('Original Payment'))

    # Amount Details
    refund_amount = models.DecimalField(_('Refund Amount'), max_digits=10, decimal_places=2)
    currency = models.CharField(_('Currency'), max_length=3, default='AED')

    # Refund Details
    reason = models.CharField(_('Reason'), max_length=30, choices=REFUND_REASON)
    reason_details = models.TextField(_('Reason Details'), blank=True)
    refund_method = models.CharField(_('Refund Method'), max_length=20, choices=REFUND_METHOD,
                                    default='original_payment')
    status = models.CharField(_('Status'), max_length=20, choices=REFUND_STATUS, default='pending')

    # Customer Details
    customer_name = models.CharField(_('Customer Name'), max_length=255)
    customer_email = models.EmailField(_('Customer Email'), blank=True)
    customer_phone = models.CharField(_('Customer Phone'), max_length=20, blank=True)

    # Approval Details
    requested_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='requested_refunds', verbose_name=_('Requested By'))
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='approved_refunds', verbose_name=_('Approved By'))
    approved_at = models.DateTimeField(_('Approved At'), null=True, blank=True)

    # Processing Details
    processed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='finance_processed_refunds', verbose_name=_('Processed By'))
    processed_at = models.DateTimeField(_('Processed At'), null=True, blank=True)
    transaction_reference = models.CharField(_('Transaction Reference'), max_length=100, blank=True)

    # Notes
    notes = models.TextField(_('Notes'), blank=True)
    rejection_reason = models.TextField(_('Rejection Reason'), blank=True)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Refund')
        verbose_name_plural = _('Refunds')
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.refund_reference} - {self.order.order_code} - {self.refund_amount} {self.currency}"

    def save(self, *args, **kwargs):
        # Generate refund reference if not set
        if not self.refund_reference:
            import uuid
            self.refund_reference = f"REF-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)

    def approve(self, approved_by):
        """Approve the refund"""
        self.status = 'approved'
        self.approved_by = approved_by
        self.approved_at = timezone.now()
        self.save()

    def reject(self, rejected_by, reason):
        """Reject the refund"""
        self.status = 'rejected'
        self.approved_by = rejected_by
        self.approved_at = timezone.now()
        self.rejection_reason = reason
        self.save()

    def process(self, processed_by, transaction_reference=None):
        """Process the refund"""
        self.status = 'processing'
        self.processed_by = processed_by
        if transaction_reference:
            self.transaction_reference = transaction_reference
        self.save()

    def complete(self, transaction_reference=None):
        """Complete the refund"""
        self.status = 'completed'
        self.processed_at = timezone.now()
        if transaction_reference:
            self.transaction_reference = transaction_reference
        self.save()

        # Update original payment status
        if self.payment:
            self.payment.payment_status = 'refunded'
            self.payment.save()