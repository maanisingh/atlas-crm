# delivery/security_admin.py
"""
Django Admin Configuration for Security Models
"""
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from .security_models import (
    DeliveryOTP,
    DeliveryPIN,
    GeofenceZone,
    DeliverySecurityEvent,
    FraudDetection,
    DeliverySecuritySettings
)


@admin.register(DeliveryOTP)
class DeliveryOTPAdmin(admin.ModelAdmin):
    """Admin interface for DeliveryOTP"""

    list_display = [
        'id',
        'delivery_link',
        'customer_phone',
        'status_badge',
        'attempts',
        'max_attempts',
        'created_at',
        'expires_at',
        'verified_at'
    ]
    list_filter = [
        'status',
        'created_at',
        'expires_at',
        'verified_at'
    ]
    search_fields = [
        'delivery__tracking_number',
        'customer_phone',
        'customer_email',
        'otp_code'
    ]
    readonly_fields = [
        'id',
        'otp_hash',
        'created_at',
        'updated_at',
        'verified_at',
        'attempts'
    ]
    fieldsets = (
        (_('Delivery Information'), {
            'fields': ('delivery', 'customer_phone', 'customer_email')
        }),
        (_('OTP Details'), {
            'fields': ('otp_code', 'otp_hash', 'status', 'attempts', 'max_attempts')
        }),
        (_('Timing'), {
            'fields': ('created_at', 'expires_at', 'verified_at')
        }),
    )

    def delivery_link(self, obj):
        """Display delivery as clickable link"""
        url = reverse('admin:delivery_deliveryrecord_change', args=[obj.delivery.id])
        return format_html('<a href="{}">{}</a>', url, obj.delivery.tracking_number)
    delivery_link.short_description = 'Delivery'

    def status_badge(self, obj):
        """Display status with color badge"""
        colors = {
            'pending': 'orange',
            'verified': 'green',
            'failed': 'red',
            'expired': 'gray',
            'cancelled': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of verified OTPs"""
        if obj and obj.status == 'verified':
            return False
        return super().has_delete_permission(request, obj)


@admin.register(DeliveryPIN)
class DeliveryPINAdmin(admin.ModelAdmin):
    """Admin interface for DeliveryPIN"""

    list_display = [
        'id',
        'delivery_link',
        'pin_code_masked',
        'status_badge',
        'attempts',
        'created_at',
        'valid_until',
        'verified_at'
    ]
    list_filter = [
        'status',
        'created_at',
        'valid_until'
    ]
    search_fields = [
        'delivery__tracking_number',
        'pin_code'
    ]
    readonly_fields = [
        'id',
        'pin_hash',
        'created_at',
        'updated_at',
        'verified_at',
        'attempts'
    ]
    fieldsets = (
        (_('Delivery Information'), {
            'fields': ('delivery',)
        }),
        (_('PIN Details'), {
            'fields': ('pin_code', 'pin_hash', 'status', 'attempts', 'max_attempts')
        }),
        (_('Validity'), {
            'fields': ('created_at', 'valid_until', 'verified_at')
        }),
    )

    def delivery_link(self, obj):
        """Display delivery as clickable link"""
        url = reverse('admin:delivery_deliveryrecord_change', args=[obj.delivery.id])
        return format_html('<a href="{}">{}</a>', url, obj.delivery.tracking_number)
    delivery_link.short_description = 'Delivery'

    def pin_code_masked(self, obj):
        """Display masked PIN code"""
        return '****'
    pin_code_masked.short_description = 'PIN Code'

    def status_badge(self, obj):
        """Display status with color badge"""
        colors = {
            'active': 'green',
            'verified': 'blue',
            'expired': 'gray',
            'locked': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(GeofenceZone)
class GeofenceZoneAdmin(admin.ModelAdmin):
    """Admin interface for GeofenceZone"""

    list_display = [
        'id',
        'delivery_link',
        'name',
        'radius_meters',
        'status_badge',
        'is_active',
        'created_at'
    ]
    list_filter = [
        'status',
        'is_active',
        'created_at'
    ]
    search_fields = [
        'delivery__tracking_number',
        'name',
        'description'
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at'
    ]
    fieldsets = (
        (_('Delivery Information'), {
            'fields': ('delivery', 'name', 'description')
        }),
        (_('Location'), {
            'fields': ('center_latitude', 'center_longitude', 'radius_meters')
        }),
        (_('Status'), {
            'fields': ('status', 'is_active', 'created_by')
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def delivery_link(self, obj):
        """Display delivery as clickable link"""
        url = reverse('admin:delivery_deliveryrecord_change', args=[obj.delivery.id])
        return format_html('<a href="{}">{}</a>', url, obj.delivery.tracking_number)
    delivery_link.short_description = 'Delivery'

    def status_badge(self, obj):
        """Display status with color badge"""
        colors = {
            'active': 'green',
            'breached': 'red',
            'inactive': 'gray'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'


@admin.register(DeliverySecurityEvent)
class DeliverySecurityEventAdmin(admin.ModelAdmin):
    """Admin interface for DeliverySecurityEvent"""

    list_display = [
        'id',
        'delivery_link',
        'event_type_badge',
        'severity_badge',
        'timestamp',
        'courier_name',
        'triggered_by_name'
    ]
    list_filter = [
        'event_type',
        'severity',
        'timestamp'
    ]
    search_fields = [
        'delivery__tracking_number',
        'description',
        'courier__user__username',
        'ip_address'
    ]
    readonly_fields = [
        'id',
        'timestamp',
        'event_data',
        'ip_address',
        'user_agent',
        'device_info'
    ]
    fieldsets = (
        (_('Event Information'), {
            'fields': (
                'delivery',
                'event_type',
                'severity',
                'description',
                'timestamp'
            )
        }),
        (_('Participants'), {
            'fields': ('courier', 'triggered_by')
        }),
        (_('Location'), {
            'fields': ('event_latitude', 'event_longitude')
        }),
        (_('Technical Details'), {
            'fields': ('device_info', 'ip_address', 'user_agent', 'event_data'),
            'classes': ('collapse',)
        }),
    )
    date_hierarchy = 'timestamp'

    def delivery_link(self, obj):
        """Display delivery as clickable link"""
        url = reverse('admin:delivery_deliveryrecord_change', args=[obj.delivery.id])
        return format_html('<a href="{}">{}</a>', url, obj.delivery.tracking_number)
    delivery_link.short_description = 'Delivery'

    def event_type_badge(self, obj):
        """Display event type with badge"""
        return format_html(
            '<span style="background-color: #3b82f6; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            obj.get_event_type_display()
        )
    event_type_badge.short_description = 'Event Type'

    def severity_badge(self, obj):
        """Display severity with color badge"""
        colors = {
            'info': '#10b981',
            'warning': '#f59e0b',
            'error': '#ef4444',
            'critical': '#dc2626'
        }
        color = colors.get(obj.severity, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_severity_display().upper()
        )
    severity_badge.short_description = 'Severity'

    def courier_name(self, obj):
        """Display courier name"""
        return obj.courier.user.get_full_name() if obj.courier else '-'
    courier_name.short_description = 'Courier'

    def triggered_by_name(self, obj):
        """Display user who triggered the event"""
        return obj.triggered_by.get_full_name() if obj.triggered_by else '-'
    triggered_by_name.short_description = 'Triggered By'


@admin.register(FraudDetection)
class FraudDetectionAdmin(admin.ModelAdmin):
    """Admin interface for FraudDetection"""

    list_display = [
        'id',
        'delivery_link',
        'fraud_type_badge',
        'risk_level_badge',
        'confidence_score',
        'status_badge',
        'detected_at'
    ]
    list_filter = [
        'fraud_type',
        'risk_level',
        'status',
        'detected_at'
    ]
    search_fields = [
        'delivery__tracking_number',
        'description'
    ]
    readonly_fields = [
        'id',
        'detected_at',
        'investigation_started_at',
        'resolved_at',
        'evidence'
    ]
    fieldsets = (
        (_('Fraud Information'), {
            'fields': (
                'delivery',
                'fraud_type',
                'risk_level',
                'confidence_score',
                'description',
                'detected_at'
            )
        }),
        (_('Investigation'), {
            'fields': (
                'status',
                'investigated_by',
                'investigation_started_at',
                'investigation_notes'
            )
        }),
        (_('Resolution'), {
            'fields': (
                'resolved_by',
                'resolved_at',
                'resolution_notes',
                'action_taken'
            )
        }),
        (_('Evidence'), {
            'fields': ('evidence',),
            'classes': ('collapse',)
        }),
    )
    date_hierarchy = 'detected_at'

    def delivery_link(self, obj):
        """Display delivery as clickable link"""
        url = reverse('admin:delivery_deliveryrecord_change', args=[obj.delivery.id])
        return format_html('<a href="{}">{}</a>', url, obj.delivery.tracking_number)
    delivery_link.short_description = 'Delivery'

    def fraud_type_badge(self, obj):
        """Display fraud type with badge"""
        return format_html(
            '<span style="background-color: #dc2626; color: white; padding: 3px 8px; border-radius: 3px; font-size: 11px;">{}</span>',
            obj.get_fraud_type_display()
        )
    fraud_type_badge.short_description = 'Fraud Type'

    def risk_level_badge(self, obj):
        """Display risk level with color badge"""
        colors = {
            'low': '#10b981',
            'medium': '#f59e0b',
            'high': '#ef4444'
        }
        color = colors.get(obj.risk_level, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px; font-weight: bold;">{}</span>',
            color,
            obj.get_risk_level_display().upper()
        )
    risk_level_badge.short_description = 'Risk Level'

    def status_badge(self, obj):
        """Display status with color badge"""
        colors = {
            'detected': 'orange',
            'under_investigation': 'blue',
            'confirmed': 'red',
            'false_positive': 'green'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="background-color: {}; color: white; padding: 3px 10px; border-radius: 3px;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = 'Status'

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of confirmed fraud cases"""
        if obj and obj.status == 'confirmed':
            return False
        return super().has_delete_permission(request, obj)


@admin.register(DeliverySecuritySettings)
class DeliverySecuritySettingsAdmin(admin.ModelAdmin):
    """Admin interface for DeliverySecuritySettings (Singleton)"""

    list_display = [
        'id',
        'otp_enabled',
        'pin_enabled',
        'geofencing_enabled',
        'fraud_detection_enabled',
        'updated_at'
    ]
    readonly_fields = [
        'id',
        'created_at',
        'updated_at'
    ]
    fieldsets = (
        (_('OTP Settings'), {
            'fields': (
                'otp_enabled',
                'otp_length',
                'otp_expiry_minutes',
                'otp_max_attempts'
            )
        }),
        (_('PIN Settings'), {
            'fields': (
                'pin_enabled',
                'pin_length',
                'pin_validity_days'
            )
        }),
        (_('Geofencing Settings'), {
            'fields': (
                'geofencing_enabled',
                'geofence_radius_meters',
                'geofence_strict_mode'
            )
        }),
        (_('Photo Verification'), {
            'fields': (
                'require_photo_verification',
                'require_signature',
                'min_photo_quality'
            )
        }),
        (_('Fraud Detection'), {
            'fields': (
                'fraud_detection_enabled',
                'fraud_alert_threshold',
                'auto_block_high_risk'
            )
        }),
        (_('Notifications'), {
            'fields': (
                'notify_security_team',
                'security_team_email'
            )
        }),
        (_('Audit Logging'), {
            'fields': (
                'log_all_events',
                'event_retention_days'
            )
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at')
        }),
    )

    def has_add_permission(self, request):
        """Only allow one instance (singleton)"""
        return not DeliverySecuritySettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of settings"""
        return False
