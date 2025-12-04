# packaging/models.py
from django.db import models
from django.conf import settings
from django.utils import timezone
from django.core.validators import MinValueValidator
import uuid

def generate_package_barcode():
    """Generate unique barcode for packages."""
    return f"PKG-{uuid.uuid4().hex[:12].upper()}"

class PackagingRecord(models.Model):
    PACKAGE_TYPES = (
        ('box', 'Box'),
        ('envelope', 'Envelope'),
        ('polybag', 'Polybag'),
        ('tube', 'Tube'),
        ('custom', 'Custom'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
        ('cancelled', 'Cancelled'),
    )
    
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='packaging')
    packager = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='packaged_orders')
    packaging_started = models.DateTimeField(auto_now_add=True)
    packaging_completed = models.DateTimeField(null=True, blank=True)
    packaging_notes = models.TextField(blank=True)
    
    # Package details
    package_type = models.CharField(max_length=20, choices=PACKAGE_TYPES, default='box')
    package_weight = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)  # in kg
    dimensions = models.CharField(max_length=50, blank=True)  # format: LxWxH in cm
    length = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)  # length in cm
    width = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)   # width in cm
    height = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)  # height in cm
    barcode = models.CharField(max_length=100, unique=True, default=generate_package_barcode)
    tracking_number = models.CharField(max_length=100, unique=True, blank=True)
    
    # Status and quality control
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    quality_check_passed = models.BooleanField(default=False)
    quality_check_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='quality_checked_packages')
    quality_check_date = models.DateTimeField(null=True, blank=True)
    
    # Packaging materials used
    materials_used = models.JSONField(default=dict, blank=True)  # Store materials and quantities
    
    # Shipping details
    shipping_label_generated = models.BooleanField(default=False)
    shipping_label_url = models.URLField(blank=True)
    courier_assigned = models.ForeignKey('delivery.Courier', on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        db_table = 'packaging_packagingrecord'  # Keep existing table name after app rename
        verbose_name = "Packaging Record"
        verbose_name_plural = "Packaging Records"
        ordering = ['-packaging_started']
    
    def __str__(self):
        return f"Package {self.barcode} - Order {self.order.order_code}"
    
    @property
    def packaging_duration(self):
        """Calculate packaging duration in minutes."""
        if self.packaging_completed and self.packaging_started:
            return (self.packaging_completed - self.packaging_started).total_seconds() / 60
        return None
    
    @property
    def is_completed(self):
        """Check if packaging is completed."""
        return self.status == 'completed'
    
    def complete_packaging(self, user):
        """Mark packaging as completed."""
        self.status = 'completed'
        self.packaging_completed = timezone.now()
        self.packager = user
        self.save()

class PackagingMaterial(models.Model):
    """Track packaging materials inventory."""
    MATERIAL_TYPES = (
        ('box', 'Box'),
        ('envelope', 'Envelope'),
        ('polybag', 'Polybag'),
        ('tape', 'Tape'),
        ('bubble_wrap', 'Bubble Wrap'),
        ('filler', 'Filler Material'),
        ('label', 'Label'),
        ('other', 'Other'),
    )
    
    name = models.CharField(max_length=100)
    material_type = models.CharField(max_length=20, choices=MATERIAL_TYPES)
    description = models.TextField(blank=True)
    current_stock = models.PositiveIntegerField(default=0)
    min_stock_level = models.PositiveIntegerField(default=10)
    unit = models.CharField(max_length=20, default='pieces')  # pieces, meters, kg, etc.
    cost_per_unit = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    supplier = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'packaging_packagingmaterial'  # Keep existing table name after app rename
        verbose_name = "Packaging Material"
        verbose_name_plural = "Packaging Materials"
        ordering = ['material_type', 'name']
    
    def __str__(self):
        return f"{self.name} ({self.current_stock} {self.unit})"
    
    @property
    def is_low_stock(self):
        """Check if material is low in stock."""
        return self.current_stock <= self.min_stock_level
    
    @property
    def stock_status(self):
        """Get stock status for display."""
        if self.current_stock == 0:
            return "out_of_stock"
        elif self.is_low_stock:
            return "low_stock"
        else:
            return "normal"

class PackagingTask(models.Model):
    """Track packaging tasks and assignments."""
    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    
    STATUS_CHOICES = (
        ('pending', 'Pending'),
        ('in_progress', 'In Progress'),
        ('completed', 'Completed'),
    )
    
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='packaging_tasks')
    assigned_to = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='assigned_packaging_tasks')
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal')
    status = models.CharField(max_length=15, choices=STATUS_CHOICES, default='pending')
    estimated_duration = models.PositiveIntegerField(default=15)  # in minutes
    actual_duration = models.PositiveIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        db_table = 'packaging_packagingtask'  # Keep existing table name after app rename
        verbose_name = "Packaging Task"
        verbose_name_plural = "Packaging Tasks"
        ordering = ['-priority', 'created_at']
    
    def __str__(self):
        return f"Packaging Task - Order {self.order.order_code}"
    
    @property
    def duration(self):
        """Get actual duration in minutes."""
        if self.actual_duration:
            return self.actual_duration
        elif self.started_at and self.completed_at:
            return int((self.completed_at - self.started_at).total_seconds() / 60)
        return None

class PackagingQualityCheck(models.Model):
    """Quality control records for packaging."""
    CHECK_TYPES = (
        ('visual', 'Visual Inspection'),
        ('weight', 'Weight Verification'),
        ('dimensions', 'Dimensions Check'),
        ('label', 'Label Verification'),
        ('seal', 'Seal Integrity'),
        ('other', 'Other'),
    )
    
    RESULT_CHOICES = (
        ('pass', 'Pass'),
        ('fail', 'Fail'),
        ('conditional', 'Conditional Pass'),
    )
    
    packaging_record = models.ForeignKey(PackagingRecord, on_delete=models.CASCADE, related_name='quality_checks')
    checker = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='performed_quality_checks')
    check_type = models.CharField(max_length=20, choices=CHECK_TYPES)
    result = models.CharField(max_length=15, choices=RESULT_CHOICES)
    notes = models.TextField(blank=True)
    checked_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'packaging_packagingqualitycheck'  # Keep existing table name after app rename
        verbose_name = "Packaging Quality Check"
        verbose_name_plural = "Packaging Quality Checks"
        ordering = ['-checked_at']
    
    def __str__(self):
        return f"QC {self.check_type} - {self.result} - {self.packaging_record.barcode}"