# delivery/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.conf import settings
import uuid

User = get_user_model()

class DeliveryCompany(models.Model):
    """Delivery company model for third-party delivery providers"""
    name_en = models.CharField(max_length=100, verbose_name="Company Name (English)")
    name_ar = models.CharField(max_length=100, verbose_name="Company Name (Arabic)")
    countries = models.ManyToManyField('settings.Country', blank=True)
    base_cost = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Base Delivery Cost")
    api_key = models.CharField(max_length=255, blank=True, verbose_name="API Key")
    api_secret = models.CharField(max_length=255, blank=True, verbose_name="API Secret")
    webhook_url = models.URLField(blank=True, verbose_name="Webhook URL")
    is_active = models.BooleanField(default=True, verbose_name="Active")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Delivery Company"
        verbose_name_plural = "Delivery Companies"
        ordering = ['name_en']

    def __str__(self):
        return self.name_en

class Courier(models.Model):
    """Courier/Delivery agent model"""
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('inactive', 'Inactive'),
        ('suspended', 'Suspended'),
        ('on_leave', 'On Leave'),
    )
    
    AVAILABILITY_CHOICES = (
        ('available', 'Available'),
        ('busy', 'Busy'),
        ('offline', 'Offline'),
        ('break', 'On Break'),
    )
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='courier_profile')
    employee_id = models.CharField(max_length=50, unique=True, verbose_name="Employee ID")
    delivery_company = models.ForeignKey(DeliveryCompany, on_delete=models.CASCADE, related_name='couriers')
    phone_number = models.CharField(max_length=20, verbose_name="Phone Number")
    vehicle_type = models.CharField(max_length=50, blank=True, verbose_name="Vehicle Type")
    vehicle_number = models.CharField(max_length=20, blank=True, verbose_name="Vehicle Number")
    license_number = models.CharField(max_length=50, blank=True, verbose_name="License Number")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Status")
    availability = models.CharField(max_length=20, choices=AVAILABILITY_CHOICES, default='offline', verbose_name="Availability")
    max_daily_deliveries = models.PositiveIntegerField(default=50, verbose_name="Max Daily Deliveries")
    current_location_lat = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True, verbose_name="Current Latitude")
    current_location_lng = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True, verbose_name="Current Longitude")
    last_location_update = models.DateTimeField(null=True, blank=True, verbose_name="Last Location Update")
    rating = models.DecimalField(max_digits=3, decimal_places=2, default=5.00, validators=[MinValueValidator(0), MaxValueValidator(5)], verbose_name="Rating")
    total_deliveries = models.PositiveIntegerField(default=0, verbose_name="Total Deliveries")
    successful_deliveries = models.PositiveIntegerField(default=0, verbose_name="Successful Deliveries")
    failed_deliveries = models.PositiveIntegerField(default=0, verbose_name="Failed Deliveries")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Courier"
        verbose_name_plural = "Couriers"
        ordering = ['user__full_name']

    def __str__(self):
        return f"{self.user.get_full_name()} - {self.employee_id}"

    def get_success_rate(self):
        """Calculate delivery success rate"""
        if self.total_deliveries == 0:
            return 0
        return (self.successful_deliveries / self.total_deliveries) * 100

    def get_daily_delivery_count(self, date=None):
        """Get delivery count for a specific date"""
        if date is None:
            date = timezone.now().date()
        return self.deliveries.filter(
            assigned_at__date=date
        ).count()

class DeliveryRecord(models.Model):
    """Main delivery record model"""
    STATUS_CHOICES = (
        ('assigned', 'Assigned'),
        ('accepted', 'Accepted'),
        ('picked_up', 'Picked Up'),
        ('in_transit', 'In Transit'),
        ('out_for_delivery', 'Out for Delivery'),
        ('attempted', 'Delivery Attempted'),
        ('delivered', 'Delivered'),
        ('failed', 'Failed'),
        ('returned', 'Returned'),
        ('cancelled', 'Cancelled'),
    )
    
    PRIORITY_CHOICES = (
        ('low', 'Low'),
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    
    # Using default BigAutoField to maintain migration compatibility
    order = models.OneToOneField('orders.Order', on_delete=models.CASCADE, related_name='delivery')
    delivery_company = models.ForeignKey(DeliveryCompany, on_delete=models.CASCADE, related_name='deliveries')
    courier = models.ForeignKey(Courier, on_delete=models.SET_NULL, null=True, blank=True, related_name='deliveries')
    tracking_number = models.CharField(max_length=100, unique=True, verbose_name="Tracking Number")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='assigned', verbose_name="Status")
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='normal', verbose_name="Priority")
    
    # Timestamps
    assigned_at = models.DateTimeField(default=timezone.now, verbose_name="Assigned At")
    accepted_at = models.DateTimeField(null=True, blank=True, verbose_name="Accepted At")
    picked_up_at = models.DateTimeField(null=True, blank=True, verbose_name="Picked Up At")
    out_for_delivery_at = models.DateTimeField(null=True, blank=True, verbose_name="Out for Delivery At")
    delivered_at = models.DateTimeField(null=True, blank=True, verbose_name="Delivered At")
    failed_at = models.DateTimeField(null=True, blank=True, verbose_name="Failed At")
    
    # Delivery details
    delivery_cost = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Delivery Cost")
    delivery_notes = models.TextField(blank=True, verbose_name="Delivery Notes")
    customer_signature = models.TextField(blank=True, verbose_name="Customer Signature")
    delivery_proof_photo = models.ImageField(upload_to='delivery_proof/', null=True, blank=True, verbose_name="Delivery Proof Photo")
    
    # Customer feedback
    customer_rating = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name="Customer Rating")
    customer_feedback = models.TextField(blank=True, verbose_name="Customer Feedback")
    
    # Estimated times
    estimated_pickup_time = models.DateTimeField(null=True, blank=True, verbose_name="Estimated Pickup Time")
    estimated_delivery_time = models.DateTimeField(null=True, blank=True, verbose_name="Estimated Delivery Time")
    actual_delivery_time = models.DateTimeField(null=True, blank=True, verbose_name="Actual Delivery Time")
    
    # Manager confirmation
    MANAGER_CONFIRMATION_CHOICES = (
        ('pending', 'Pending Confirmation'),
        ('confirmed', 'Confirmed'),
        ('rejected', 'Rejected'),
    )
    manager_confirmation_status = models.CharField(
        max_length=20, 
        choices=MANAGER_CONFIRMATION_CHOICES, 
        null=True, 
        blank=True, 
        verbose_name="Manager Confirmation Status"
    )
    manager_confirmed_at = models.DateTimeField(null=True, blank=True, verbose_name="Manager Confirmed At")
    manager_confirmed_by = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True, 
        blank=True, 
        related_name='confirmed_deliveries',
        verbose_name="Manager Confirmed By"
    )
    manager_rejection_reason = models.TextField(blank=True, verbose_name="Manager Rejection Reason")
    
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Delivery Record"
        verbose_name_plural = "Delivery Records"
        ordering = ['-assigned_at']

    def __str__(self):
        return f"Delivery {self.tracking_number} - {self.order.order_number}"

    def get_delivery_time(self):
        """Calculate actual delivery time"""
        if self.delivered_at and self.picked_up_at:
            return self.delivered_at - self.picked_up_at
        return None

    def get_estimated_delivery_time(self):
        """Calculate estimated delivery time"""
        if self.estimated_delivery_time and self.estimated_pickup_time:
            return self.estimated_delivery_time - self.estimated_pickup_time
        return None

class DeliveryStatusHistory(models.Model):
    """Track all status changes for deliveries"""
    delivery = models.ForeignKey(DeliveryRecord, on_delete=models.CASCADE, related_name='status_history')
    status = models.CharField(max_length=20, choices=DeliveryRecord.STATUS_CHOICES)
    changed_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    location_lat = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True)
    location_lng = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True)
    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Delivery Status History"
        verbose_name_plural = "Delivery Status Histories"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.delivery.tracking_number} - {self.status} at {self.timestamp}"

class DeliveryAttempt(models.Model):
    """Record delivery attempts (successful and failed)"""
    RESULT_CHOICES = (
        ('successful', 'Successful'),
        ('failed', 'Failed'),
        ('rescheduled', 'Rescheduled'),
    )
    
    FAILURE_REASON_CHOICES = (
        ('customer_not_available', 'Customer Not Available'),
        ('wrong_address', 'Wrong Address'),
        ('customer_refused', 'Customer Refused'),
        ('package_damaged', 'Package Damaged'),
        ('weather_conditions', 'Weather Conditions'),
        ('vehicle_breakdown', 'Vehicle Breakdown'),
        ('traffic_delay', 'Traffic Delay'),
        ('other', 'Other'),
    )
    
    delivery = models.ForeignKey(DeliveryRecord, on_delete=models.CASCADE, related_name='attempts')
    courier = models.ForeignKey(Courier, on_delete=models.CASCADE, related_name='delivery_attempts')
    attempt_number = models.PositiveIntegerField(default=1, verbose_name="Attempt Number")
    attempt_time = models.DateTimeField(default=timezone.now, verbose_name="Attempt Time")
    result = models.CharField(max_length=20, choices=RESULT_CHOICES, verbose_name="Result")
    failure_reason = models.CharField(max_length=30, choices=FAILURE_REASON_CHOICES, null=True, blank=True, verbose_name="Failure Reason")
    customer_feedback = models.TextField(blank=True, verbose_name="Customer Feedback")
    proof_image = models.ImageField(upload_to='delivery_attempts/', null=True, blank=True, verbose_name="Proof Image")
    signature_data = models.TextField(blank=True, verbose_name="Signature Data")
    notes = models.TextField(blank=True, verbose_name="Notes")
    next_attempt_date = models.DateTimeField(null=True, blank=True, verbose_name="Next Attempt Date")
    location_lat = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True, verbose_name="Location Latitude")
    location_lng = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True, verbose_name="Location Longitude")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Delivery Attempt"
        verbose_name_plural = "Delivery Attempts"
        ordering = ['-attempt_time']

    def __str__(self):
        return f"Attempt {self.attempt_number} - {self.delivery.tracking_number}"

class CourierSession(models.Model):
    """Track courier login sessions"""
    STATUS_CHOICES = (
        ('active', 'Active'),
        ('break', 'Break'),
        ('offline', 'Offline'),
    )
    
    courier = models.ForeignKey(Courier, on_delete=models.CASCADE, related_name='sessions')
    login_time = models.DateTimeField(default=timezone.now, verbose_name="Login Time")
    logout_time = models.DateTimeField(null=True, blank=True, verbose_name="Logout Time")
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active', verbose_name="Status")
    location_lat = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True, verbose_name="Location Latitude")
    location_lng = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True, verbose_name="Location Longitude")
    last_activity = models.DateTimeField(auto_now=True, verbose_name="Last Activity")
    device_info = models.TextField(blank=True, verbose_name="Device Information")
    ip_address = models.GenericIPAddressField(null=True, blank=True, verbose_name="IP Address")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Courier Session"
        verbose_name_plural = "Courier Sessions"
        ordering = ['-login_time']

    def __str__(self):
        return f"{self.courier.user.get_full_name()} - {self.login_time}"

    def get_session_duration(self):
        """Calculate session duration"""
        end_time = self.logout_time or timezone.now()
        return end_time - self.login_time

class CourierLocation(models.Model):
    """Store real-time courier location data"""
    courier = models.ForeignKey(Courier, on_delete=models.CASCADE, related_name='locations')
    latitude = models.DecimalField(max_digits=10, decimal_places=8, verbose_name="Latitude")
    longitude = models.DecimalField(max_digits=11, decimal_places=8, verbose_name="Longitude")
    accuracy = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True, verbose_name="Accuracy (meters)")
    timestamp = models.DateTimeField(default=timezone.now, verbose_name="Timestamp")
    battery_level = models.PositiveIntegerField(null=True, blank=True, validators=[MinValueValidator(0), MaxValueValidator(100)], verbose_name="Battery Level (%)")
    connection_type = models.CharField(max_length=20, choices=(
        ('wifi', 'WiFi'),
        ('cellular', 'Cellular'),
        ('offline', 'Offline'),
    ), default='cellular', verbose_name="Connection Type")
    speed = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Speed (km/h)")
    heading = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True, verbose_name="Heading (degrees)")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Courier Location"
        verbose_name_plural = "Courier Locations"
        ordering = ['-timestamp']

    def __str__(self):
        return f"{self.courier.user.get_full_name()} - {self.timestamp}"

class DeliveryProof(models.Model):
    """Store delivery verification data"""
    PROOF_TYPE_CHOICES = (
        ('photo', 'Photo'),
        ('signature', 'Signature'),
        ('barcode', 'Barcode Scan'),
        ('otp', 'OTP Verification'),
        ('gps', 'GPS Location'),
    )
    
    delivery = models.ForeignKey(DeliveryRecord, on_delete=models.CASCADE, related_name='proofs')
    courier = models.ForeignKey(Courier, on_delete=models.CASCADE, related_name='delivery_proofs')
    proof_type = models.CharField(max_length=20, choices=PROOF_TYPE_CHOICES, verbose_name="Proof Type")
    proof_data = models.TextField(verbose_name="Proof Data")
    capture_time = models.DateTimeField(default=timezone.now, verbose_name="Capture Time")
    location_lat = models.DecimalField(max_digits=10, decimal_places=8, null=True, blank=True, verbose_name="Location Latitude")
    location_lng = models.DecimalField(max_digits=11, decimal_places=8, null=True, blank=True, verbose_name="Location Longitude")
    verified = models.BooleanField(default=False, verbose_name="Verified")
    verified_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='verified_proofs', verbose_name="Verified By")
    verified_at = models.DateTimeField(null=True, blank=True, verbose_name="Verified At")
    created_at = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = "Delivery Proof"
        verbose_name_plural = "Delivery Proofs"
        ordering = ['-capture_time']

    def __str__(self):
        return f"{self.delivery.tracking_number} - {self.get_proof_type_display()}"

class DeliveryRoute(models.Model):
    """Optimized delivery routes for couriers"""
    courier = models.ForeignKey(Courier, on_delete=models.CASCADE, related_name='routes')
    route_date = models.DateField(verbose_name="Route Date")
    route_name = models.CharField(max_length=100, verbose_name="Route Name")
    total_distance = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True, verbose_name="Total Distance (km)")
    estimated_duration = models.PositiveIntegerField(null=True, blank=True, verbose_name="Estimated Duration (minutes)")
    route_data = models.JSONField(default=dict, verbose_name="Route Data")
    is_optimized = models.BooleanField(default=False, verbose_name="Optimized")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Delivery Route"
        verbose_name_plural = "Delivery Routes"
        ordering = ['-route_date']
        unique_together = ['courier', 'route_date']

    def __str__(self):
        return f"{self.courier.user.get_full_name()} - {self.route_date}"

class DeliveryPerformance(models.Model):
    """Courier performance metrics"""
    courier = models.ForeignKey(Courier, on_delete=models.CASCADE, related_name='performance_records')
    date = models.DateField(verbose_name="Date")
    total_deliveries = models.PositiveIntegerField(default=0, verbose_name="Total Deliveries")
    successful_deliveries = models.PositiveIntegerField(default=0, verbose_name="Successful Deliveries")
    failed_deliveries = models.PositiveIntegerField(default=0, verbose_name="Failed Deliveries")
    total_distance = models.DecimalField(max_digits=8, decimal_places=2, default=0, verbose_name="Total Distance (km)")
    total_time = models.PositiveIntegerField(default=0, verbose_name="Total Time (minutes)")
    average_delivery_time = models.PositiveIntegerField(default=0, verbose_name="Average Delivery Time (minutes)")
    customer_rating = models.DecimalField(max_digits=3, decimal_places=2, default=0, validators=[MinValueValidator(0), MaxValueValidator(5)], verbose_name="Average Customer Rating")
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Delivery Performance"
        verbose_name_plural = "Delivery Performances"
        ordering = ['-date']
        unique_together = ['courier', 'date']

    def __str__(self):
        return f"{self.courier.user.get_full_name()} - {self.date}"

    def get_success_rate(self):
        """Calculate success rate for the day"""
        if self.total_deliveries == 0:
            return 0
        return (self.successful_deliveries / self.total_deliveries) * 100

class DeliveryPreferences(models.Model):
    """Delivery agent preferences and settings"""
    AREA_CHOICES = (
        ('all', 'All Areas'),
        ('downtown', 'Downtown'),
        ('suburbs', 'Suburbs'),
        ('industrial', 'Industrial Zone'),
        ('residential', 'Residential'),
        ('commercial', 'Commercial'),
    )
    
    VEHICLE_CHOICES = (
        ('motorcycle', 'Motorcycle'),
        ('bicycle', 'Bicycle'),
        ('car', 'Car'),
        ('van', 'Van'),
        ('truck', 'Truck'),
    )
    
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='delivery_preferences')
    preferred_areas = models.JSONField(default=list, help_text="List of preferred delivery areas")
    vehicle_type = models.CharField(max_length=20, choices=VEHICLE_CHOICES, default='motorcycle')
    max_package_weight = models.DecimalField(max_digits=5, decimal_places=2, default=50.00, help_text="Maximum package weight in kg")
    start_time = models.TimeField(default='08:00', help_text="Preferred start time")
    end_time = models.TimeField(default='18:00', help_text="Preferred end time")
    accept_urgent_deliveries = models.BooleanField(default=True, help_text="Accept urgent deliveries outside normal hours")
    notification_enabled = models.BooleanField(default=True, help_text="Enable notifications for new orders")
    auto_accept_orders = models.BooleanField(default=False, help_text="Automatically accept assigned orders")
    max_daily_deliveries = models.PositiveIntegerField(default=20, help_text="Maximum deliveries per day")
    preferred_delivery_radius = models.PositiveIntegerField(default=10, help_text="Preferred delivery radius in km")
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Delivery Preferences"
        verbose_name_plural = "Delivery Preferences"
    
    def __str__(self):
        return f"{self.user.get_full_name() or self.user.email} - Delivery Preferences"

class OrderAssignment(models.Model):
    """Assign orders to delivery agents by area"""
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='delivery_assignments')
    delivery_agent = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='delivery_assignments')
    assigned_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='assigned_orders_admin')
    assigned_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True, help_text="Assignment notes")
    is_active = models.BooleanField(default=True, help_text="Whether this assignment is active")
    
    class Meta:
        verbose_name = "Order Assignment"
        verbose_name_plural = "Order Assignments"
        unique_together = ('order', 'delivery_agent')
    
    def __str__(self):
        return f"Order {self.order.id} assigned to {self.delivery_agent.get_full_name() or self.delivery_agent.email}"


# Import Security Models
from .security_models import (
    DeliveryOTP,
    DeliveryPIN,
    GeofenceZone,
    DeliverySecurityEvent,
    FraudDetection,
    DeliverySecuritySettings
)