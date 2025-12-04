# delivery/security_models.py
"""
Delivery Security Layer Models
Comprehensive security features for delivery verification and fraud prevention
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
from django.core.exceptions import ValidationError
import random
import string
import hashlib
import hmac
from datetime import timedelta

User = get_user_model()


def generate_otp():
    """Generate 6-digit OTP"""
    return ''.join(random.choices(string.digits, k=6))


def generate_delivery_pin():
    """Generate 4-digit delivery PIN"""
    return ''.join(random.choices(string.digits, k=4))


class DeliveryOTP(models.Model):
    """
    One-Time Password for Delivery Verification
    Sent to customer for secure delivery confirmation
    """

    OTP_STATUS_CHOICES = (
        ('pending', _('Pending Verification')),
        ('verified', _('Verified')),
        ('expired', _('Expired')),
        ('failed', _('Failed Verification')),
        ('cancelled', _('Cancelled')),
    )

    delivery = models.ForeignKey('delivery.DeliveryRecord', on_delete=models.CASCADE,
                                 related_name='otp_verifications')
    otp_code = models.CharField(_('OTP Code'), max_length=6)
    otp_hash = models.CharField(_('OTP Hash'), max_length=128, blank=True)

    # Customer info
    customer_phone = models.CharField(_('Customer Phone'), max_length=20)
    customer_email = models.EmailField(_('Customer Email'), blank=True)

    # OTP lifecycle
    generated_at = models.DateTimeField(_('Generated At'), default=timezone.now)
    expires_at = models.DateTimeField(_('Expires At'))
    verified_at = models.DateTimeField(_('Verified At'), null=True, blank=True)

    # Status tracking
    status = models.CharField(_('Status'), max_length=20, choices=OTP_STATUS_CHOICES,
                             default='pending')
    verification_attempts = models.PositiveIntegerField(_('Verification Attempts'), default=0)
    max_attempts = models.PositiveIntegerField(_('Max Attempts'), default=3)

    # Delivery context
    delivery_latitude = models.DecimalField(_('Delivery Latitude'), max_digits=10,
                                           decimal_places=8, null=True, blank=True)
    delivery_longitude = models.DecimalField(_('Delivery Longitude'), max_digits=11,
                                            decimal_places=8, null=True, blank=True)

    # Verification metadata
    verified_by_device = models.CharField(_('Verified By Device'), max_length=255, blank=True)
    verified_ip_address = models.GenericIPAddressField(_('Verified IP'), null=True, blank=True)

    # Security flags
    is_suspicious = models.BooleanField(_('Is Suspicious'), default=False)
    suspicious_reason = models.TextField(_('Suspicious Reason'), blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Delivery OTP')
        verbose_name_plural = _('Delivery OTPs')
        ordering = ['-generated_at']
        indexes = [
            models.Index(fields=['delivery', 'status']),
            models.Index(fields=['customer_phone', 'generated_at']),
            models.Index(fields=['expires_at', 'status']),
        ]

    def __str__(self):
        return f"OTP for {self.delivery.tracking_number} - {self.status}"

    def save(self, *args, **kwargs):
        # Set expiry if not set (default 15 minutes)
        if not self.expires_at:
            self.expires_at = self.generated_at + timedelta(minutes=15)

        # Hash OTP before saving (only if not already hashed)
        if self.otp_code and not self.otp_hash:
            self.otp_hash = hashlib.sha256(self.otp_code.encode()).hexdigest()

        super().save(*args, **kwargs)

    def verify_otp(self, provided_otp, latitude=None, longitude=None, device_info=None, ip_address=None):
        """Verify OTP code"""
        # Check if already verified
        if self.status == 'verified':
            return False, _('OTP already verified')

        # Check if expired
        if timezone.now() > self.expires_at:
            self.status = 'expired'
            self.save()
            return False, _('OTP has expired')

        # Check max attempts
        if self.verification_attempts >= self.max_attempts:
            self.status = 'failed'
            self.save()
            return False, _('Maximum verification attempts exceeded')

        # Increment attempts
        self.verification_attempts += 1

        # Verify OTP
        provided_hash = hashlib.sha256(provided_otp.encode()).hexdigest()
        if hmac.compare_digest(self.otp_hash, provided_hash):
            # OTP is correct
            self.status = 'verified'
            self.verified_at = timezone.now()
            self.delivery_latitude = latitude
            self.delivery_longitude = longitude
            self.verified_by_device = device_info or ''
            self.verified_ip_address = ip_address
            self.save()
            return True, _('OTP verified successfully')
        else:
            # OTP is incorrect
            if self.verification_attempts >= self.max_attempts:
                self.status = 'failed'
            self.save()
            return False, _('Invalid OTP code')

    @property
    def is_expired(self):
        """Check if OTP is expired"""
        return timezone.now() > self.expires_at

    @property
    def is_valid(self):
        """Check if OTP is still valid for verification"""
        return (self.status == 'pending' and
                not self.is_expired and
                self.verification_attempts < self.max_attempts)


class DeliveryPIN(models.Model):
    """
    Delivery PIN System
    Alternative to OTP - PIN shared with customer at order placement
    """

    PIN_STATUS_CHOICES = (
        ('active', _('Active')),
        ('used', _('Used')),
        ('expired', _('Expired')),
        ('cancelled', _('Cancelled')),
    )

    delivery = models.OneToOneField('delivery.DeliveryRecord', on_delete=models.CASCADE,
                                   related_name='delivery_pin')
    pin_code = models.CharField(_('PIN Code'), max_length=4)
    pin_hash = models.CharField(_('PIN Hash'), max_length=128)

    # PIN lifecycle
    generated_at = models.DateTimeField(_('Generated At'), default=timezone.now)
    valid_until = models.DateTimeField(_('Valid Until'))
    used_at = models.DateTimeField(_('Used At'), null=True, blank=True)

    # Status
    status = models.CharField(_('Status'), max_length=20, choices=PIN_STATUS_CHOICES,
                             default='active')
    verification_attempts = models.PositiveIntegerField(_('Verification Attempts'), default=0)
    max_attempts = models.PositiveIntegerField(_('Max Attempts'), default=5)

    # Customer notification
    sent_via_sms = models.BooleanField(_('Sent via SMS'), default=False)
    sent_via_email = models.BooleanField(_('Sent via Email'), default=False)
    sms_sent_at = models.DateTimeField(_('SMS Sent At'), null=True, blank=True)
    email_sent_at = models.DateTimeField(_('Email Sent At'), null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Delivery PIN')
        verbose_name_plural = _('Delivery PINs')
        ordering = ['-generated_at']

    def __str__(self):
        return f"PIN for {self.delivery.tracking_number}"

    def save(self, *args, **kwargs):
        # Set validity (default 7 days)
        if not self.valid_until:
            self.valid_until = self.generated_at + timedelta(days=7)

        # Hash PIN before saving
        if self.pin_code and not self.pin_hash:
            self.pin_hash = hashlib.sha256(self.pin_code.encode()).hexdigest()

        super().save(*args, **kwargs)

    def verify_pin(self, provided_pin):
        """Verify PIN code"""
        # Check if already used
        if self.status == 'used':
            return False, _('PIN already used')

        # Check if expired
        if timezone.now() > self.valid_until:
            self.status = 'expired'
            self.save()
            return False, _('PIN has expired')

        # Check max attempts
        if self.verification_attempts >= self.max_attempts:
            return False, _('Maximum verification attempts exceeded')

        # Increment attempts
        self.verification_attempts += 1

        # Verify PIN
        provided_hash = hashlib.sha256(provided_pin.encode()).hexdigest()
        if hmac.compare_digest(self.pin_hash, provided_hash):
            # PIN is correct
            self.status = 'used'
            self.used_at = timezone.now()
            self.save()
            return True, _('PIN verified successfully')
        else:
            # PIN is incorrect
            self.save()
            return False, _('Invalid PIN code')


class GeofenceZone(models.Model):
    """
    Geofencing zones for delivery verification
    Ensures delivery happens within acceptable radius of delivery address
    """

    delivery = models.ForeignKey('delivery.DeliveryRecord', on_delete=models.CASCADE,
                                related_name='geofence_zones')

    # Center point (delivery address)
    center_latitude = models.DecimalField(_('Center Latitude'), max_digits=10, decimal_places=8)
    center_longitude = models.DecimalField(_('Center Longitude'), max_digits=11, decimal_places=8)

    # Geofence parameters
    radius_meters = models.PositiveIntegerField(_('Radius (meters)'), default=100,
                                               help_text=_('Acceptable delivery radius'))
    strict_mode = models.BooleanField(_('Strict Mode'), default=False,
                                     help_text=_('Require delivery within zone'))

    # Zone metadata
    zone_name = models.CharField(_('Zone Name'), max_length=255, blank=True)
    zone_description = models.TextField(_('Zone Description'), blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Geofence Zone')
        verbose_name_plural = _('Geofence Zones')
        ordering = ['-created_at']

    def __str__(self):
        return f"Geofence for {self.delivery.tracking_number}"

    def is_within_zone(self, latitude, longitude):
        """
        Check if coordinates are within geofence zone
        Uses Haversine formula for distance calculation
        """
        from math import radians, sin, cos, sqrt, atan2

        # Earth radius in meters
        R = 6371000

        lat1 = radians(float(self.center_latitude))
        lon1 = radians(float(self.center_longitude))
        lat2 = radians(float(latitude))
        lon2 = radians(float(longitude))

        dlat = lat2 - lat1
        dlon = lon2 - lon1

        a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
        c = 2 * atan2(sqrt(a), sqrt(1-a))
        distance = R * c

        return distance <= self.radius_meters, distance

    def get_distance_from_center(self, latitude, longitude):
        """Calculate distance from zone center"""
        _, distance = self.is_within_zone(latitude, longitude)
        return distance


class DeliverySecurityEvent(models.Model):
    """
    Security event log for deliveries
    Tracks all security-related events and potential fraud
    """

    EVENT_TYPE_CHOICES = (
        ('otp_generated', _('OTP Generated')),
        ('otp_verified', _('OTP Verified')),
        ('otp_failed', _('OTP Verification Failed')),
        ('pin_verified', _('PIN Verified')),
        ('pin_failed', _('PIN Verification Failed')),
        ('geofence_violation', _('Geofence Violation')),
        ('geofence_success', _('Geofence Verification Success')),
        ('photo_uploaded', _('Delivery Photo Uploaded')),
        ('signature_captured', _('Signature Captured')),
        ('suspicious_activity', _('Suspicious Activity Detected')),
        ('fraud_alert', _('Fraud Alert')),
        ('security_override', _('Security Check Override')),
        ('unauthorized_access', _('Unauthorized Access Attempt')),
    )

    SEVERITY_CHOICES = (
        ('info', _('Information')),
        ('warning', _('Warning')),
        ('error', _('Error')),
        ('critical', _('Critical')),
    )

    delivery = models.ForeignKey('delivery.DeliveryRecord', on_delete=models.CASCADE,
                                related_name='security_events')
    event_type = models.CharField(_('Event Type'), max_length=30, choices=EVENT_TYPE_CHOICES)
    severity = models.CharField(_('Severity'), max_length=20, choices=SEVERITY_CHOICES,
                               default='info')

    # Event details
    description = models.TextField(_('Description'))
    event_data = models.JSONField(_('Event Data'), default=dict, blank=True)

    # Context
    triggered_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='triggered_security_events')
    courier = models.ForeignKey('delivery.Courier', on_delete=models.SET_NULL, null=True,
                               blank=True, related_name='security_events')

    # Location at event time
    event_latitude = models.DecimalField(_('Event Latitude'), max_digits=10, decimal_places=8,
                                        null=True, blank=True)
    event_longitude = models.DecimalField(_('Event Longitude'), max_digits=11, decimal_places=8,
                                         null=True, blank=True)

    # Device/Network info
    device_info = models.TextField(_('Device Information'), blank=True)
    ip_address = models.GenericIPAddressField(_('IP Address'), null=True, blank=True)
    user_agent = models.TextField(_('User Agent'), blank=True)

    # Resolution
    is_resolved = models.BooleanField(_('Is Resolved'), default=False)
    resolved_at = models.DateTimeField(_('Resolved At'), null=True, blank=True)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='resolved_security_events')
    resolution_notes = models.TextField(_('Resolution Notes'), blank=True)

    timestamp = models.DateTimeField(default=timezone.now)

    class Meta:
        verbose_name = _('Delivery Security Event')
        verbose_name_plural = _('Delivery Security Events')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['delivery', 'event_type']),
            models.Index(fields=['severity', 'is_resolved']),
            models.Index(fields=['timestamp', 'event_type']),
        ]

    def __str__(self):
        return f"{self.get_event_type_display()} - {self.delivery.tracking_number}"


class FraudDetection(models.Model):
    """
    Fraud Detection System
    Analyzes delivery patterns to detect potential fraud
    """

    RISK_LEVEL_CHOICES = (
        ('low', _('Low Risk')),
        ('medium', _('Medium Risk')),
        ('high', _('High Risk')),
        ('critical', _('Critical Risk')),
    )

    FRAUD_TYPE_CHOICES = (
        ('location_mismatch', _('Location Mismatch')),
        ('time_anomaly', _('Time Anomaly')),
        ('multiple_failures', _('Multiple Failed Attempts')),
        ('suspicious_pattern', _('Suspicious Pattern')),
        ('identity_verification_failed', _('Identity Verification Failed')),
        ('geofence_violation', _('Repeated Geofence Violations')),
        ('duplicate_delivery', _('Duplicate Delivery Attempt')),
        ('unauthorized_recipient', _('Unauthorized Recipient')),
    )

    delivery = models.ForeignKey('delivery.DeliveryRecord', on_delete=models.CASCADE,
                                related_name='fraud_detections')
    fraud_type = models.CharField(_('Fraud Type'), max_length=40, choices=FRAUD_TYPE_CHOICES)
    risk_level = models.CharField(_('Risk Level'), max_length=20, choices=RISK_LEVEL_CHOICES)

    # Detection details
    confidence_score = models.DecimalField(_('Confidence Score'), max_digits=5, decimal_places=2,
                                          validators=[MinValueValidator(0), MaxValueValidator(100)],
                                          help_text=_('Fraud detection confidence (0-100%)'))
    description = models.TextField(_('Description'))
    evidence = models.JSONField(_('Evidence'), default=dict, blank=True)

    # ML/AI detection metadata
    detection_algorithm = models.CharField(_('Detection Algorithm'), max_length=100, blank=True)
    model_version = models.CharField(_('Model Version'), max_length=50, blank=True)

    # Investigation
    is_investigated = models.BooleanField(_('Is Investigated'), default=False)
    investigated_at = models.DateTimeField(_('Investigated At'), null=True, blank=True)
    investigated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='investigated_frauds')
    investigation_notes = models.TextField(_('Investigation Notes'), blank=True)

    # Outcome
    is_confirmed_fraud = models.BooleanField(_('Confirmed Fraud'), default=False)
    is_false_positive = models.BooleanField(_('False Positive'), default=False)
    action_taken = models.TextField(_('Action Taken'), blank=True)

    # Reporting
    reported_to_authorities = models.BooleanField(_('Reported to Authorities'), default=False)
    report_reference = models.CharField(_('Report Reference'), max_length=100, blank=True)

    detected_at = models.DateTimeField(default=timezone.now)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Fraud Detection')
        verbose_name_plural = _('Fraud Detections')
        ordering = ['-detected_at']
        indexes = [
            models.Index(fields=['risk_level', 'is_investigated']),
            models.Index(fields=['is_confirmed_fraud', 'detected_at']),
        ]

    def __str__(self):
        return f"{self.get_fraud_type_display()} - {self.delivery.tracking_number} ({self.risk_level})"


class DeliverySecuritySettings(models.Model):
    """
    Global security settings for delivery system
    Configurable security parameters
    """

    # OTP Settings
    otp_enabled = models.BooleanField(_('OTP Enabled'), default=True)
    otp_length = models.PositiveIntegerField(_('OTP Length'), default=6,
                                            validators=[MinValueValidator(4), MaxValueValidator(8)])
    otp_expiry_minutes = models.PositiveIntegerField(_('OTP Expiry (minutes)'), default=15)
    otp_max_attempts = models.PositiveIntegerField(_('OTP Max Attempts'), default=3)

    # PIN Settings
    pin_enabled = models.BooleanField(_('PIN Enabled'), default=True)
    pin_length = models.PositiveIntegerField(_('PIN Length'), default=4,
                                            validators=[MinValueValidator(4), MaxValueValidator(6)])
    pin_validity_days = models.PositiveIntegerField(_('PIN Validity (days)'), default=7)

    # Geofencing Settings
    geofencing_enabled = models.BooleanField(_('Geofencing Enabled'), default=True)
    default_geofence_radius = models.PositiveIntegerField(_('Default Geofence Radius (meters)'),
                                                          default=100)
    strict_geofencing = models.BooleanField(_('Strict Geofencing'), default=False,
                                           help_text=_('Block deliveries outside geofence'))

    # Photo Verification Settings
    photo_verification_required = models.BooleanField(_('Photo Verification Required'), default=True)
    photo_max_size_mb = models.PositiveIntegerField(_('Photo Max Size (MB)'), default=10)

    # Fraud Detection Settings
    fraud_detection_enabled = models.BooleanField(_('Fraud Detection Enabled'), default=True)
    fraud_alert_threshold = models.DecimalField(_('Fraud Alert Threshold'), max_digits=5,
                                               decimal_places=2, default=70.00,
                                               help_text=_('Alert when confidence > this %'))
    auto_block_high_risk = models.BooleanField(_('Auto-block High Risk Deliveries'), default=False)

    # Notification Settings
    notify_security_team = models.BooleanField(_('Notify Security Team'), default=True)
    security_team_email = models.EmailField(_('Security Team Email'), blank=True)

    # Audit Settings
    log_all_events = models.BooleanField(_('Log All Security Events'), default=True)
    retention_days = models.PositiveIntegerField(_('Log Retention (days)'), default=90)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _('Delivery Security Settings')
        verbose_name_plural = _('Delivery Security Settings')

    def __str__(self):
        return f"Security Settings (Updated: {self.updated_at})"
