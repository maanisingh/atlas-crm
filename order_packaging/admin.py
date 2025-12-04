# packaging/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.urls import reverse
from django.utils.safestring import mark_safe
from .models import (
    PackagingRecord, PackagingMaterial, PackagingTask, PackagingQualityCheck
)

@admin.register(PackagingRecord)
class PackagingRecordAdmin(admin.ModelAdmin):
    list_display = ['barcode', 'order', 'packager', 'package_type', 'status', 'packaging_started', 'quality_check_passed', 'shipping_label_generated']
    list_filter = ['status', 'package_type', 'quality_check_passed', 'shipping_label_generated', 'packaging_started', 'packaging_completed']
    search_fields = ['barcode', 'tracking_number', 'order__order_code', 'packager__first_name', 'packager__last_name', 'packager__email']
    readonly_fields = ['barcode', 'packaging_started']
    ordering = ['-packaging_started']
    
    fieldsets = (
        ('Order Information', {
            'fields': ('order', 'packager')
        }),
        ('Package Details', {
            'fields': ('package_type', 'package_weight', 'dimensions', 'barcode', 'tracking_number')
        }),
        ('Status & Timing', {
            'fields': ('status', 'packaging_started', 'packaging_completed')
        }),
        ('Quality Control', {
            'fields': ('quality_check_passed', 'quality_check_by', 'quality_check_date')
        }),
        ('Materials & Shipping', {
            'fields': ('materials_used', 'shipping_label_generated', 'shipping_label_url', 'courier_assigned')
        }),
        ('Notes', {
            'fields': ('packaging_notes',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('order', 'packager', 'quality_check_by', 'courier_assigned')

@admin.register(PackagingMaterial)
class PackagingMaterialAdmin(admin.ModelAdmin):
    list_display = ['name', 'material_type', 'current_stock', 'unit', 'min_stock_level', 'stock_status_display', 'cost_per_unit', 'is_active']
    list_filter = ['material_type', 'is_active', 'created_at']
    search_fields = ['name', 'description', 'supplier']
    readonly_fields = ['created_at', 'updated_at']
    ordering = ['material_type', 'name']
    
    def stock_status_display(self, obj):
        status_colors = {
            'out_of_stock': 'red',
            'low_stock': 'orange',
            'normal': 'green'
        }
        color = status_colors.get(obj.stock_status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.stock_status.replace('_', ' ').title()
        )
    stock_status_display.short_description = 'Stock Status'
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'material_type', 'description')
        }),
        ('Stock Management', {
            'fields': ('current_stock', 'min_stock_level', 'unit')
        }),
        ('Cost & Supplier', {
            'fields': ('cost_per_unit', 'supplier')
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(PackagingTask)
class PackagingTaskAdmin(admin.ModelAdmin):
    list_display = ['order', 'assigned_to', 'priority', 'status_display', 'estimated_duration', 'actual_duration', 'created_at']
    list_filter = ['priority', 'status', 'created_at', 'started_at', 'completed_at']
    search_fields = ['order__order_code', 'assigned_to__first_name', 'assigned_to__last_name', 'assigned_to__email', 'notes']
    readonly_fields = ['created_at']
    ordering = ['-priority', '-created_at']
    
    def status_display(self, obj):
        status_colors = {
            'completed': 'green',
            'in_progress': 'orange',
            'pending': 'gray'
        }
        color = status_colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.status.replace('_', ' ').title()
        )
    status_display.short_description = 'Status'
    
    fieldsets = (
        ('Task Information', {
            'fields': ('order', 'assigned_to', 'priority', 'status')
        }),
        ('Duration', {
            'fields': ('estimated_duration', 'actual_duration')
        }),
        ('Timing', {
            'fields': ('created_at', 'started_at', 'completed_at')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('order', 'assigned_to')

@admin.register(PackagingQualityCheck)
class PackagingQualityCheckAdmin(admin.ModelAdmin):
    list_display = ['packaging_record', 'checker', 'check_type', 'result_display', 'checked_at']
    list_filter = ['check_type', 'result', 'checked_at']
    search_fields = ['packaging_record__barcode', 'checker__first_name', 'checker__last_name', 'checker__email', 'notes']
    readonly_fields = ['checked_at']
    ordering = ['-checked_at']
    
    def result_display(self, obj):
        result_colors = {
            'pass': 'green',
            'fail': 'red',
            'conditional': 'orange'
        }
        color = result_colors.get(obj.result, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.result.title()
        )
    result_display.short_description = 'Result'
    
    fieldsets = (
        ('Check Information', {
            'fields': ('packaging_record', 'checker', 'check_type')
        }),
        ('Results', {
            'fields': ('result', 'notes')
        }),
        ('Timing', {
            'fields': ('checked_at',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        return qs.select_related('packaging_record', 'checker')
