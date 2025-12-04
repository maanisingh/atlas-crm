# finance/cod_models.py
"""
Cash on Delivery (COD) Models for Atlas CRM
Handles COD payments with delivery agent collection tracking
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError

User = get_user_model()


class CODPayment(models.Model):
    """
    Cash on Delivery Payment Model
    Tracks COD payments collected by delivery agents
    """

    COD_STATUS_CHOICES = (
        ('pending', _('Pending Collection')),
        ('collected', _('Collected from Customer')),
        ('deposited', _('Deposited to Company')),
        ('verified', _('Verified by Finance')),
        ('disputed', _('Disputed')),
        ('cancelled', _('Cancelled')),
    )

    # Payment Reference
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='cod_payment')
    payment = models.OneToOneField('finance.Payment', on_delete=models.CASCADE, related_name='cod_details',
                                   null=True, blank=True)

    # Amount Details
    cod_amount = models.DecimalField(_('COD Amount'), max_digits=10, decimal_places=2)
    collected_amount = models.DecimalField(_('Collected Amount'), max_digits=10, decimal_places=2,
                                          default=0.00)
    currency = models.CharField(_('Currency'), max_length=3, default='AED')

    # Collection Details
    collection_status = models.CharField(_('Collection Status'), max_length=20,
                                        choices=COD_STATUS_CHOICES, default='pending')
    collected_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='cod_collections',
                                    verbose_name=_('Collected By'))
    collected_at = models.DateTimeField(_('Collection Date'), null=True, blank=True)

    # Deposit Details
    deposited_at = models.DateTimeField(_('Deposit Date'), null=True, blank=True)
    deposit_reference = models.CharField(_('Deposit Reference'), max_length=100, blank=True)

    # Verification
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='verified_cod_payments',
                                   verbose_name=_('Verified By'))
    verified_at = models.DateTimeField(_('Verification Date'), null=True, blank=True)

    # Proof of Collection
    collection_proof_image = models.ImageField(_('Collection Proof'), upload_to='cod_proofs/',
                                              null=True, blank=True)
    customer_signature = models.ImageField(_('Customer Signature'), upload_to='cod_signatures/',
                                          null=True, blank=True)
    receipt_number = models.CharField(_('Receipt Number'), max_length=50, unique=True,
                                     null=True, blank=True)

    # Customer Details
    customer_name = models.CharField(_('Customer Name'), max_length=255)
    customer_phone = models.CharField(_('Customer Phone'), max_length=20)
    delivery_address = models.TextField(_('Delivery Address'))

    # Dispute Handling
    dispute_reason = models.TextField(_('Dispute Reason'), blank=True)
    dispute_date = models.DateTimeField(_('Dispute Date'), null=True, blank=True)
    dispute_resolved_at = models.DateTimeField(_('Dispute Resolved Date'), null=True, blank=True)

    # Metadata
    notes = models.TextField(_('Notes'), blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('COD Payment')
        verbose_name_plural = _('COD Payments')
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['collection_status', 'collected_at']),
            models.Index(fields=['collected_by', 'collected_at']),
            models.Index(fields=['collection_status', 'verified_at']),
        ]

    def __str__(self):
        return f"COD-{self.order.order_code} - {self.cod_amount} {self.currency}"

    def clean(self):
        """Validate COD payment data"""
        super().clean()

        # Collected amount cannot exceed COD amount
        if self.collected_amount > self.cod_amount:
            raise ValidationError({
                'collected_amount': _('Collected amount cannot exceed COD amount')
            })

        # If status is collected, must have collection date and collector
        if self.collection_status in ['collected', 'deposited', 'verified']:
            if not self.collected_at:
                raise ValidationError({
                    'collected_at': _('Collection date is required when status is collected')
                })
            if not self.collected_by:
                raise ValidationError({
                    'collected_by': _('Collector is required when status is collected')
                })

        # If status is deposited, must have deposit reference
        if self.collection_status in ['deposited', 'verified']:
            if not self.deposit_reference:
                raise ValidationError({
                    'deposit_reference': _('Deposit reference is required when deposited')
                })

    def save(self, *args, **kwargs):
        # Auto-set collected_at if status changes to collected
        if self.collection_status == 'collected' and not self.collected_at:
            self.collected_at = timezone.now()

        # Auto-set deposited_at if status changes to deposited
        if self.collection_status == 'deposited' and not self.deposited_at:
            self.deposited_at = timezone.now()

        # Auto-set verified_at if status changes to verified
        if self.collection_status == 'verified' and not self.verified_at:
            self.verified_at = timezone.now()

        super().save(*args, **kwargs)

    @property
    def is_collected(self):
        """Check if COD has been collected"""
        return self.collection_status in ['collected', 'deposited', 'verified']

    @property
    def is_pending(self):
        """Check if COD is still pending collection"""
        return self.collection_status == 'pending'

    @property
    def is_verified(self):
        """Check if COD has been verified by finance"""
        return self.collection_status == 'verified'

    @property
    def variance(self):
        """Calculate variance between expected and collected amount"""
        return self.collected_amount - self.cod_amount

    @property
    def has_variance(self):
        """Check if there's a variance in collection"""
        return abs(self.variance) > 0.01  # Allow 1 cent difference for rounding

    def mark_collected(self, user, amount, collection_date=None):
        """Mark COD as collected by delivery agent"""
        self.collection_status = 'collected'
        self.collected_by = user
        self.collected_amount = amount
        self.collected_at = collection_date or timezone.now()
        self.save()

    def mark_deposited(self, deposit_reference, deposit_date=None):
        """Mark COD as deposited to company account"""
        if not self.is_collected:
            raise ValidationError(_('COD must be collected before it can be deposited'))

        self.collection_status = 'deposited'
        self.deposit_reference = deposit_reference
        self.deposited_at = deposit_date or timezone.now()
        self.save()

    def mark_verified(self, user, verification_date=None):
        """Mark COD as verified by finance team"""
        if self.collection_status != 'deposited':
            raise ValidationError(_('COD must be deposited before verification'))

        self.collection_status = 'verified'
        self.verified_by = user
        self.verified_at = verification_date or timezone.now()
        self.save()

    def create_dispute(self, reason, user=None):
        """Create a dispute for this COD payment"""
        self.collection_status = 'disputed'
        self.dispute_reason = reason
        self.dispute_date = timezone.now()
        if user:
            self.notes += f"\nDispute created by {user.get_full_name()} at {timezone.now()}: {reason}"
        self.save()


class CODReconciliation(models.Model):
    """
    COD Reconciliation Model
    Tracks daily/weekly COD reconciliation by delivery agents
    """

    RECONCILIATION_STATUS = (
        ('pending', _('Pending')),
        ('in_progress', _('In Progress')),
        ('completed', _('Completed')),
        ('discrepancy', _('Has Discrepancy')),
    )

    # Reconciliation Details
    reconciliation_date = models.DateField(_('Reconciliation Date'))
    agent = models.ForeignKey(User, on_delete=models.CASCADE, related_name='cod_reconciliations',
                             verbose_name=_('Delivery Agent'))

    # Amount Summary
    expected_amount = models.DecimalField(_('Expected Amount'), max_digits=10, decimal_places=2,
                                         default=0.00)
    collected_amount = models.DecimalField(_('Collected Amount'), max_digits=10, decimal_places=2,
                                          default=0.00)
    variance = models.DecimalField(_('Variance'), max_digits=10, decimal_places=2, default=0.00)

    # Payment Counts
    total_cod_count = models.IntegerField(_('Total COD Count'), default=0)
    collected_count = models.IntegerField(_('Collected Count'), default=0)
    pending_count = models.IntegerField(_('Pending Count'), default=0)

    # Status
    status = models.CharField(_('Status'), max_length=20, choices=RECONCILIATION_STATUS,
                             default='pending')

    # Verification
    reconciled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='reconciled_cods',
                                     verbose_name=_('Reconciled By'))
    reconciled_at = models.DateTimeField(_('Reconciled At'), null=True, blank=True)

    # Notes
    notes = models.TextField(_('Notes'), blank=True)
    discrepancy_notes = models.TextField(_('Discrepancy Notes'), blank=True)

    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('COD Reconciliation')
        verbose_name_plural = _('COD Reconciliations')
        ordering = ['-reconciliation_date']
        unique_together = ('agent', 'reconciliation_date')

    def __str__(self):
        return f"Reconciliation - {self.agent.get_full_name()} - {self.reconciliation_date}"

    def save(self, *args, **kwargs):
        # Auto-calculate variance
        self.variance = self.collected_amount - self.expected_amount

        # Auto-set status based on variance
        if self.collected_count == self.total_cod_count and abs(self.variance) < 0.01:
            if self.status != 'completed':
                self.status = 'completed'
        elif abs(self.variance) > 0.01:
            self.status = 'discrepancy'

        super().save(*args, **kwargs)

    @property
    def has_discrepancy(self):
        """Check if there's a discrepancy in reconciliation"""
        return abs(self.variance) > 0.01 or self.collected_count != self.total_cod_count

    @property
    def completion_rate(self):
        """Calculate completion rate percentage"""
        if self.total_cod_count == 0:
            return 0.0
        return (self.collected_count / self.total_cod_count) * 100

    def calculate_totals(self):
        """Calculate totals from associated COD payments"""
        cod_payments = CODPayment.objects.filter(
            collected_by=self.agent,
            collected_at__date=self.reconciliation_date
        )

        self.total_cod_count = cod_payments.count()
        self.collected_count = cod_payments.filter(
            collection_status__in=['collected', 'deposited', 'verified']
        ).count()
        self.pending_count = cod_payments.filter(collection_status='pending').count()

        self.expected_amount = sum(float(cod.cod_amount) for cod in cod_payments)
        self.collected_amount = sum(float(cod.collected_amount) for cod in cod_payments)

        self.save()
