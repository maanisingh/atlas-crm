from django.contrib import admin
from .models import Order, OrderItem, OrderWorkflowLog, Return, ReturnItem, ReturnStatusLog

class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 1

@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('order_code', 'customer', 'status', 'workflow_status', 'seller_email', 'agent', 'total_price_aed', 'date')
    list_filter = ('status', 'workflow_status', 'seller_email', 'agent', 'date')
    search_fields = ('order_code', 'customer', 'customer_phone', 'seller_email')
    readonly_fields = ('order_code', 'created_at', 'updated_at', 'assigned_at')
    inlines = [OrderItemInline]
    actions = ['assign_to_agent', 'unassign_agent', 'change_seller']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('order_code', 'customer', 'customer_phone', 'date', 'status')
        }),
        ('Workflow Status', {
            'fields': ('workflow_status',)
        }),
        ('Product Details', {
            'fields': ('product', 'quantity', 'price_per_unit')
        }),
        ('Seller Information', {
            'fields': ('seller_email', 'store_link', 'seller')
        }),
        ('Call Center Assignment', {
            'fields': ('agent', 'assigned_at')
        }),
        ('Escalation Information', {
            'fields': ('escalated_to_manager', 'escalated_at', 'escalated_by', 'escalation_reason'),
            'classes': ('collapse',)
        }),
        ('Shipping Information', {
            'fields': ('shipping_address', 'city', 'state', 'zip_code', 'country')
        }),
        ('Notes', {
            'fields': ('notes', 'internal_notes')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def assign_to_agent(self, request, queryset):
        from django.utils import timezone
        # Get available agents (users with Call Center role)
        from users.models import User
        agents = User.objects.filter(user_roles__role__name='Call Center Agent', user_roles__is_active=True).distinct()
        
        if not agents.exists():
            self.message_user(request, 'No call center agents found. Please create users with Call Center role.')
            return
        
        # Assign orders to agents in round-robin fashion
        agent_list = list(agents)
        for i, order in enumerate(queryset):
            agent = agent_list[i % len(agent_list)]
            order.agent = agent
            order.assigned_at = timezone.now()
            order.save()
        
        self.message_user(request, f'{queryset.count()} orders have been assigned to call center agents.')
    assign_to_agent.short_description = "Assign orders to call center agents"
    
    def unassign_agent(self, request, queryset):
        updated = queryset.update(agent=None, assigned_at=None)
        self.message_user(request, f'{queryset.count()} orders have been unassigned from agents.')
    unassign_agent.short_description = "Unassign orders from agents"
    
    def change_seller(self, request, queryset):
        from django.contrib import messages
        from django.shortcuts import render
        from users.models import User
        
        if 'apply' in request.POST:
            new_seller_id = request.POST.get('new_seller')
            if new_seller_id:
                try:
                    new_seller = User.objects.get(id=new_seller_id)
                    updated_count = 0
                    
                    for order in queryset:
                        old_seller = order.seller
                        order.seller = new_seller
                        order.seller_email = new_seller.email
                        order.save()
                        
                        # Create workflow log
                        OrderWorkflowLog.objects.create(
                            order=order,
                            from_status=order.workflow_status,
                            to_status=order.workflow_status,
                            user=request.user,
                            notes=f'Seller changed from {old_seller.get_full_name() if old_seller else "None"} to {new_seller.get_full_name()}'
                        )
                        updated_count += 1
                    
                    self.message_user(request, f'Successfully changed seller for {updated_count} orders to {new_seller.get_full_name()}.')
                    return
                except User.DoesNotExist:
                    messages.error(request, 'Selected seller not found.')
            else:
                messages.error(request, 'Please select a seller.')
        
        # Get all sellers (users with Seller role)
        sellers = User.objects.filter(user_roles__role__name='Seller', user_roles__is_active=True).distinct().order_by('first_name', 'last_name')
        
        context = {
            'orders': queryset,
            'sellers': sellers,
            'action_name': 'change_seller',
            'title': 'Change Seller for Selected Orders'
        }
        
        return render(request, 'admin/change_seller.html', context)
    change_seller.short_description = "Change seller for selected orders"

@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'product', 'quantity', 'price', 'total_price_aed')
    list_filter = ('order__status',)
    search_fields = ('order__order_code', 'product__name')

@admin.register(OrderWorkflowLog)
class OrderWorkflowLogAdmin(admin.ModelAdmin):
    list_display = ('order', 'from_status', 'to_status', 'user', 'timestamp')
    list_filter = ('from_status', 'to_status', 'timestamp')
    search_fields = ('order__order_code', 'user__first_name', 'user__last_name', 'user__email', 'notes')
    readonly_fields = ('timestamp',)
    ordering = ('-timestamp',)

# Return Management Admin Classes

class ReturnItemInline(admin.TabularInline):
    model = ReturnItem
    extra = 1
    fields = ('order_item', 'quantity', 'reason', 'condition', 'notes')
    readonly_fields = ('refund_value',)

@admin.register(Return)
class ReturnAdmin(admin.ModelAdmin):
    list_display = ('return_code', 'order', 'customer', 'return_reason', 'return_status', 'refund_status', 'refund_amount_aed', 'created_at')
    list_filter = ('return_status', 'refund_status', 'return_reason', 'requires_manager_approval', 'customer_contacted', 'created_at')
    search_fields = ('return_code', 'order__order_code', 'customer__email', 'customer__first_name', 'customer__last_name')
    readonly_fields = ('return_code', 'created_at', 'updated_at', 'approved_at', 'received_at_warehouse',
                      'inspection_started_at', 'inspection_completed_at', 'refund_processed_at',
                      'restocked_at', 'completed_at', 'total_deductions', 'net_refund_amount',
                      'net_refund_amount_aed', 'days_since_request')
    inlines = [ReturnItemInline]
    actions = ['approve_returns', 'reject_returns', 'mark_as_received', 'process_refunds']
    date_hierarchy = 'created_at'

    fieldsets = (
        ('Basic Information', {
            'fields': ('return_code', 'order', 'customer', 'created_at', 'updated_at')
        }),
        ('Return Details', {
            'fields': ('return_reason', 'return_description', 'return_status', 'priority', 'requires_manager_approval')
        }),
        ('Evidence & Documentation', {
            'fields': ('return_photo_1', 'return_photo_2', 'return_photo_3', 'return_video'),
            'classes': ('collapse',)
        }),
        ('Approval Information', {
            'fields': ('approved_by', 'approved_at', 'rejection_reason'),
            'classes': ('collapse',)
        }),
        ('Return Shipping', {
            'fields': ('return_tracking_number', 'return_carrier', 'pickup_scheduled_date', 'pickup_address'),
            'classes': ('collapse',)
        }),
        ('Warehouse Receipt', {
            'fields': ('received_by', 'received_at_warehouse'),
            'classes': ('collapse',)
        }),
        ('Inspection', {
            'fields': ('inspector', 'inspection_started_at', 'inspection_completed_at',
                      'item_condition', 'inspection_notes', 'inspection_photos'),
            'classes': ('collapse',)
        }),
        ('Restocking Decision', {
            'fields': ('can_restock', 'restocked', 'restocked_by', 'restocked_at'),
            'classes': ('collapse',)
        }),
        ('Refund Information', {
            'fields': ('refund_amount', 'refund_method', 'refund_status', 'refund_processed_by',
                      'refund_processed_at', 'refund_reference', 'refund_notes')
        }),
        ('Deductions', {
            'fields': ('restocking_fee', 'damage_deduction', 'shipping_cost_deduction',
                      'total_deductions', 'net_refund_amount', 'net_refund_amount_aed'),
            'classes': ('collapse',)
        }),
        ('Customer Contact', {
            'fields': ('customer_contacted', 'customer_contact_notes'),
            'classes': ('collapse',)
        }),
        ('Timeline', {
            'fields': ('days_since_request', 'completed_at'),
            'classes': ('collapse',)
        }),
    )

    def approve_returns(self, request, queryset):
        from django.utils import timezone
        updated_count = 0

        for return_obj in queryset.filter(return_status='pending_approval'):
            # Create status log
            ReturnStatusLog.objects.create(
                return_request=return_obj,
                old_status=return_obj.return_status,
                new_status='approved',
                changed_by=request.user,
                notes='Return approved by admin'
            )

            return_obj.return_status = 'approved'
            return_obj.approved_by = request.user
            return_obj.approved_at = timezone.now()
            return_obj.save()
            updated_count += 1

        self.message_user(request, f'{updated_count} returns have been approved.')
    approve_returns.short_description = "Approve selected returns"

    def reject_returns(self, request, queryset):
        from django.utils import timezone
        updated_count = 0

        for return_obj in queryset.filter(return_status='pending_approval'):
            # Create status log
            ReturnStatusLog.objects.create(
                return_request=return_obj,
                old_status=return_obj.return_status,
                new_status='rejected',
                changed_by=request.user,
                notes='Return rejected by admin'
            )

            return_obj.return_status = 'rejected'
            return_obj.approved_by = request.user
            return_obj.approved_at = timezone.now()
            return_obj.rejection_reason = 'Rejected by administrator'
            return_obj.save()
            updated_count += 1

        self.message_user(request, f'{updated_count} returns have been rejected.')
    reject_returns.short_description = "Reject selected returns"

    def mark_as_received(self, request, queryset):
        from django.utils import timezone
        updated_count = 0

        for return_obj in queryset.filter(return_status='in_transit'):
            # Create status log
            ReturnStatusLog.objects.create(
                return_request=return_obj,
                old_status=return_obj.return_status,
                new_status='received',
                changed_by=request.user,
                notes='Return marked as received at warehouse'
            )

            return_obj.return_status = 'received'
            return_obj.received_by = request.user
            return_obj.received_at_warehouse = timezone.now()
            return_obj.save()
            updated_count += 1

        self.message_user(request, f'{updated_count} returns have been marked as received.')
    mark_as_received.short_description = "Mark as received at warehouse"

    def process_refunds(self, request, queryset):
        from django.utils import timezone
        updated_count = 0

        for return_obj in queryset.filter(return_status='approved_for_refund', refund_status='approved'):
            # Create status log
            ReturnStatusLog.objects.create(
                return_request=return_obj,
                old_status=return_obj.refund_status,
                new_status='completed',
                changed_by=request.user,
                notes='Refund processed by admin'
            )

            return_obj.refund_status = 'completed'
            return_obj.refund_processed_by = request.user
            return_obj.refund_processed_at = timezone.now()
            return_obj.return_status = 'refund_completed'
            return_obj.save()
            updated_count += 1

        self.message_user(request, f'{updated_count} refunds have been processed.')
    process_refunds.short_description = "Process approved refunds"

@admin.register(ReturnItem)
class ReturnItemAdmin(admin.ModelAdmin):
    list_display = ('return_request', 'order_item', 'quantity', 'reason', 'condition', 'refund_value')
    list_filter = ('reason', 'condition')
    search_fields = ('return_request__return_code', 'order_item__product__name_en', 'order_item__product__name_ar')
    readonly_fields = ('refund_value',)

    def refund_value(self, obj):
        return f"AED {obj.refund_value:,.2f}"
    refund_value.short_description = 'Refund Value'

@admin.register(ReturnStatusLog)
class ReturnStatusLogAdmin(admin.ModelAdmin):
    list_display = ('return_request', 'old_status', 'new_status', 'changed_by', 'timestamp')
    list_filter = ('old_status', 'new_status', 'timestamp')
    search_fields = ('return_request__return_code', 'changed_by__email', 'changed_by__first_name', 'changed_by__last_name', 'notes')
    readonly_fields = ('timestamp',)
    ordering = ('-timestamp',)

    def has_add_permission(self, request):
        # Status logs should only be created automatically, not manually
        return False

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of audit logs
        return False
