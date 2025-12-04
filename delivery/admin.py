from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    DeliveryCompany, Courier, DeliveryRecord, DeliveryStatusHistory,
    DeliveryAttempt, CourierSession, CourierLocation, DeliveryProof,
    DeliveryRoute, DeliveryPerformance
)

# Import security admin configurations
from .security_admin import (
    DeliveryOTPAdmin,
    DeliveryPINAdmin,
    GeofenceZoneAdmin,
    DeliverySecurityEventAdmin,
    FraudDetectionAdmin,
    DeliverySecuritySettingsAdmin
)

@admin.register(DeliveryCompany)
class DeliveryCompanyAdmin(admin.ModelAdmin):
    list_display = ['name_en', 'name_ar', 'base_cost', 'is_active', 'created_at']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name_en', 'name_ar']
    readonly_fields = ['created_at', 'updated_at']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name_en', 'name_ar', 'countries', 'base_cost')
        }),
        ('API Configuration', {
            'fields': ('api_key', 'api_secret', 'webhook_url'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(Courier)
class CourierAdmin(admin.ModelAdmin):
    list_display = ['user', 'employee_id', 'delivery_company', 'status', 'availability', 'rating', 'total_deliveries', 'success_rate']
    list_filter = ['status', 'availability', 'delivery_company', 'created_at']
    search_fields = ['user__full_name', 'employee_id', 'phone_number']
    readonly_fields = ['created_at', 'updated_at', 'last_location_update']
    list_editable = ['status', 'availability']
    
    fieldsets = (
        ('User Information', {
            'fields': ('user', 'employee_id', 'delivery_company', 'phone_number')
        }),
        ('Vehicle Information', {
            'fields': ('vehicle_type', 'vehicle_number', 'license_number'),
            'classes': ('collapse',)
        }),
        ('Status & Availability', {
            'fields': ('status', 'availability', 'max_daily_deliveries')
        }),
        ('Location', {
            'fields': ('current_location_lat', 'current_location_lng', 'last_location_update'),
            'classes': ('collapse',)
        }),
        ('Performance', {
            'fields': ('rating', 'total_deliveries', 'successful_deliveries', 'failed_deliveries'),
            'classes': ('collapse',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def success_rate(self, obj):
        return f"{obj.get_success_rate():.1f}%"
    success_rate.short_description = "Success Rate"

@admin.register(DeliveryRecord)
class DeliveryRecordAdmin(admin.ModelAdmin):
    list_display = ['tracking_number', 'order_link', 'courier', 'status', 'priority', 'delivery_cost', 'assigned_at']
    list_filter = ['status', 'priority', 'delivery_company', 'assigned_at', 'delivered_at']
    search_fields = ['tracking_number', 'order__order_number', 'courier__user__full_name']
    readonly_fields = ['id', 'assigned_at', 'created_at', 'updated_at']
    list_editable = ['status', 'priority']
    date_hierarchy = 'assigned_at'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('id', 'order', 'delivery_company', 'courier', 'tracking_number')
        }),
        ('Status & Priority', {
            'fields': ('status', 'priority')
        }),
        ('Timestamps', {
            'fields': ('assigned_at', 'accepted_at', 'picked_up_at', 'out_for_delivery_at', 'delivered_at', 'failed_at'),
            'classes': ('collapse',)
        }),
        ('Delivery Details', {
            'fields': ('delivery_cost', 'delivery_notes', 'customer_signature', 'delivery_proof_photo')
        }),
        ('Customer Feedback', {
            'fields': ('customer_rating', 'customer_feedback'),
            'classes': ('collapse',)
        }),
        ('Estimated Times', {
            'fields': ('estimated_pickup_time', 'estimated_delivery_time', 'actual_delivery_time'),
            'classes': ('collapse',)
        }),
        ('System', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def order_link(self, obj):
        if obj.order:
            url = reverse('admin:orders_order_change', args=[obj.order.id])
            return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
        return "-"
    order_link.short_description = "Order"

@admin.register(DeliveryStatusHistory)
class DeliveryStatusHistoryAdmin(admin.ModelAdmin):
    list_display = ['delivery', 'status', 'changed_by', 'timestamp', 'location_display']
    list_filter = ['status', 'timestamp']
    search_fields = ['delivery__tracking_number', 'changed_by__full_name']
    readonly_fields = ['timestamp']
    date_hierarchy = 'timestamp'

    def location_display(self, obj):
        if obj.location_lat and obj.location_lng:
            return f"{obj.location_lat}, {obj.location_lng}"
        return "-"
    location_display.short_description = "Location"

@admin.register(DeliveryAttempt)
class DeliveryAttemptAdmin(admin.ModelAdmin):
    list_display = ['delivery', 'courier', 'attempt_number', 'result', 'attempt_time', 'failure_reason']
    list_filter = ['result', 'failure_reason', 'attempt_time']
    search_fields = ['delivery__tracking_number', 'courier__user__full_name']
    readonly_fields = ['attempt_time', 'created_at']
    date_hierarchy = 'attempt_time'

@admin.register(CourierSession)
class CourierSessionAdmin(admin.ModelAdmin):
    list_display = ['courier', 'login_time', 'logout_time', 'status', 'session_duration', 'ip_address']
    list_filter = ['status', 'login_time']
    search_fields = ['courier__user__full_name', 'ip_address']
    readonly_fields = ['login_time', 'last_activity', 'created_at']
    date_hierarchy = 'login_time'

    def session_duration(self, obj):
        duration = obj.get_session_duration()
        if duration:
            hours = duration.total_seconds() // 3600
            minutes = (duration.total_seconds() % 3600) // 60
            return f"{int(hours)}h {int(minutes)}m"
        return "Active"
    session_duration.short_description = "Duration"

@admin.register(CourierLocation)
class CourierLocationAdmin(admin.ModelAdmin):
    list_display = ['courier', 'latitude', 'longitude', 'timestamp', 'battery_level', 'connection_type']
    list_filter = ['connection_type', 'timestamp']
    search_fields = ['courier__user__full_name']
    readonly_fields = ['timestamp', 'created_at']
    date_hierarchy = 'timestamp'

@admin.register(DeliveryProof)
class DeliveryProofAdmin(admin.ModelAdmin):
    list_display = ['delivery', 'courier', 'proof_type', 'capture_time', 'verified', 'verified_by']
    list_filter = ['proof_type', 'verified', 'capture_time']
    search_fields = ['delivery__tracking_number', 'courier__user__full_name']
    readonly_fields = ['capture_time', 'verified_at', 'created_at']
    date_hierarchy = 'capture_time'

@admin.register(DeliveryRoute)
class DeliveryRouteAdmin(admin.ModelAdmin):
    list_display = ['courier', 'route_date', 'route_name', 'total_distance', 'estimated_duration', 'is_optimized']
    list_filter = ['route_date', 'is_optimized']
    search_fields = ['courier__user__full_name', 'route_name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'route_date'

@admin.register(DeliveryPerformance)
class DeliveryPerformanceAdmin(admin.ModelAdmin):
    list_display = ['courier', 'date', 'total_deliveries', 'successful_deliveries', 'success_rate', 'average_delivery_time', 'customer_rating']
    list_filter = ['date']
    search_fields = ['courier__user__full_name']
    readonly_fields = ['created_at', 'updated_at']
    date_hierarchy = 'date'

    def success_rate(self, obj):
        return f"{obj.get_success_rate():.1f}%"
    success_rate.short_description = "Success Rate"
