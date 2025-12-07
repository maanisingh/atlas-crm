from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_http_methods
from django.db.models import Q, Count, Avg, Sum, F
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib.auth import get_user_model
from datetime import datetime, timedelta
from django.db import transaction
import json
import uuid
from decimal import Decimal

from .models import (
    DeliveryCompany, Courier, DeliveryRecord, DeliveryStatusHistory,
    DeliveryAttempt, CourierSession, CourierLocation, DeliveryProof,
    DeliveryRoute, DeliveryPerformance, DeliveryPreferences, OrderAssignment
)
from orders.models import Order, OrderItem
from users.models import User

User = get_user_model()

# Delivery Manager specific permission check
def is_delivery_manager(user):
    """Check if user is Delivery Manager (not Delivery Agent)"""
    return (
        user.is_superuser or 
        user.has_role('Super Admin') or 
        user.has_role('Admin') or
        user.has_role('Delivery Manager')
    )

@login_required
def assign_orders(request):
    """Assign orders to delivery agents."""
    if not (request.user.is_superuser or request.user.has_role('Super Admin') or request.user.has_role('Admin')):
        messages.error(request, "ليس لديك صلاحية للدخول لهذه الصفحة.")
        return redirect('delivery:dashboard')
    
    # Get available delivery agents
    delivery_agents = User.objects.filter(
        user_roles__role__name__in=['Delivery Agent', 'Delivery'], user_roles__is_active=True
    ).distinct()
    
    # If no delivery agents, show all users as fallback
    if not delivery_agents:
        delivery_agents = User.objects.all()[:10]
    
    # Get unassigned orders that are ready for delivery
    unassigned_orders = Order.objects.filter(
        workflow_status='ready_for_delivery',
        status='packaged'
    ).exclude(
        delivery_assignments__is_active=True
    ).select_related('product', 'seller').prefetch_related('items__product').order_by('-date')
    
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        agent_id = request.POST.get('agent_id')
        
        if order_id and agent_id:
            try:
                order = Order.objects.get(id=order_id)
                agent = User.objects.get(id=agent_id)
                
                # Create assignment
                assignment, created = OrderAssignment.objects.get_or_create(
                    order=order,
                    defaults={
                        'delivery_agent': agent,
                        'assigned_by': request.user
                    }
                )
                
                if created:
                    messages.success(request, f'تم تعيين الطلب #{order.id} للموصل {agent.get_full_name()}')
                else:
                    messages.info(request, f'الطلب #{order.id} مُعين بالفعل')
                
                return redirect('delivery:assign_orders')
                
            except (Order.DoesNotExist, User.DoesNotExist):
                messages.error(request, 'خطأ في البيانات المحددة')
    
    context = {
        'delivery_agents': delivery_agents,
        'unassigned_orders': unassigned_orders,
    }
    
    return render(request, 'delivery/assign_orders.html', context)

def is_delivery_user(user):
    """Check if user has delivery role or is super admin"""
    return (
        user.is_superuser or 
        user.has_role('Super Admin') or 
        user.has_role('Admin') or
        user.has_role('Delivery Agent') or
        user.has_role('Delivery Manager') or
        (hasattr(user, 'primary_role') and user.primary_role and 'delivery' in user.primary_role.name.lower())
    )

def is_courier(user):
    """Check if user is a courier"""
    return hasattr(user, 'courier_profile') and user.courier_profile is not None

def has_delivery_role(user):
    return (
        user.is_superuser or
        user.has_role('Super Admin') or
        user.has_role('Delivery Agent') or
        user.has_role('Delivery Manager')
    )

@login_required
def dashboard(request):
    """Delivery dashboard with real statistics and current tasks"""
    # Redirect Delivery Manager to manager dashboard
    if is_delivery_manager(request.user):
        return redirect('delivery:manager_dashboard')
    
    today = timezone.now().date()
    
    # Get date range from request
    start_date = request.GET.get('start_date', today)
    end_date = request.GET.get('end_date', today)
    
    try:
        if isinstance(start_date, str):
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
        if isinstance(end_date, str):
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
    except ValueError:
        start_date = today
        end_date = today
    
    # Get user's courier profile if exists
    courier = None
    if hasattr(request.user, 'courier_profile'):
        courier = request.user.courier_profile
    
    # Get delivery statistics for the date range
    if courier:
        # Courier-specific statistics
        deliveries = DeliveryRecord.objects.filter(courier=courier)
        date_range_deliveries = deliveries.filter(assigned_at__date__range=[start_date, end_date])
        
        # Calculate real statistics
        total_deliveries = date_range_deliveries.count()
        successful_deliveries = date_range_deliveries.filter(status='delivered').count()
        failed_deliveries = date_range_deliveries.filter(status='failed').count()
        success_rate = (successful_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0
        
        # Get courier's average rating
        avg_rating = courier.rating or 0
        
        # Get courier's performance data
        performance_data = DeliveryPerformance.objects.filter(
            courier=courier,
            date__range=[start_date, end_date]
        ).aggregate(
            total_distance=Sum('total_distance'),
            total_time=Sum('total_time'),
            avg_delivery_time=Avg('average_delivery_time')
        )
        
        avg_delivery_time = performance_data['avg_delivery_time'] or 0
        total_distance = performance_data['total_distance'] or 0
        
        # Current task (next delivery)
        current_task = date_range_deliveries.filter(
            status__in=['assigned', 'accepted', 'picked_up']
        ).order_by('estimated_delivery_time').first()
        
        # Next deliveries
        next_deliveries = date_range_deliveries.filter(
            status__in=['assigned', 'accepted']
        ).order_by('estimated_delivery_time')[:7]
        
    else:
        # Admin/Manager/Delivery Agent statistics - all deliveries
        deliveries = DeliveryRecord.objects.all()
        date_range_deliveries = deliveries.filter(assigned_at__date__range=[start_date, end_date])
        
        # Calculate real statistics
        total_deliveries = date_range_deliveries.count()
        successful_deliveries = date_range_deliveries.filter(status='delivered').count()
        failed_deliveries = date_range_deliveries.filter(status='failed').count()
        success_rate = (successful_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0
        
        # Get average rating across all couriers
        avg_rating = Courier.objects.aggregate(avg_rating=Avg('rating'))['avg_rating'] or 0
        
        # Get overall performance data - handle case when no data exists
        try:
            performance_data = DeliveryPerformance.objects.filter(
                date__range=[start_date, end_date]
            ).aggregate(
                total_distance=Sum('total_distance'),
                total_time=Sum('total_time'),
                avg_delivery_time=Avg('average_delivery_time')
            )
            
            avg_delivery_time = performance_data['avg_delivery_time'] or 0
            total_distance = performance_data['total_distance'] or 0
        except:
            avg_delivery_time = 0
            total_distance = 0
        
        # Get current tasks for delivery agents
        if request.user.has_role('Delivery Agent'):
            # Get orders ready for delivery - handle case when workflow_status doesn't exist
            try:
                orders_ready_for_delivery = Order.objects.filter(
                    workflow_status='ready_for_delivery',
                    status='packaged'
                ).select_related('product').order_by('-date')[:5]
                
                orders_in_delivery = Order.objects.filter(
                    workflow_status='delivery_in_progress'
                ).select_related('product').order_by('-date')[:5]
            except:
                # Fallback to status-based filtering
                orders_ready_for_delivery = Order.objects.filter(
                    status='packaged'
                ).select_related('product').order_by('-date')[:5]
                
                orders_in_delivery = Order.objects.filter(
                    status='processing'
                ).select_related('product').order_by('-date')[:5]
            
            current_task = orders_ready_for_delivery.first()
            next_deliveries = orders_ready_for_delivery
        else:
            current_task = None
            next_deliveries = []
    
    # Calculate active deliveries (in progress)
    active_deliveries = date_range_deliveries.filter(
        status__in=['assigned', 'accepted', 'picked_up', 'in_transit', 'out_for_delivery']
    ).count()
    
    # Calculate completed today
    completed_today = date_range_deliveries.filter(status='delivered').count()
    
    # Get recent deliveries for the table
    recent_deliveries = DeliveryRecord.objects.select_related(
        'order', 'courier'
    ).order_by('-assigned_at')[:10]
    
    # Get recent activity
    recent_activity = DeliveryStatusHistory.objects.select_related(
        'delivery', 'changed_by'
    ).order_by('-timestamp')[:10]
    
    # Get delivery companies count
    delivery_companies_count = DeliveryCompany.objects.filter(is_active=True).count()
    
    # Get active couriers count
    active_couriers_count = Courier.objects.filter(status='active').count()
    
    # Get real order data for delivery dashboard
    # Get all orders that are ready for delivery (status=packaged and workflow_status=ready_for_delivery)
    orders_for_delivery = Order.objects.filter(
        status='packaged',
        workflow_status='ready_for_delivery'
    ).select_related('product').order_by('-date')[:10]
    
    # Get order statistics
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status='pending').count()
    confirmed_orders = Order.objects.filter(status='confirmed').count()
    processing_orders = Order.objects.filter(status='processing').count()
    delivered_orders = Order.objects.filter(status='delivered').count()
    
    # Get workflow-based statistics for delivery
    try:
        pending_orders = Order.objects.filter(
            workflow_status='packaging_completed',
            status='packaged'
        ).count()
        
        processing_orders = Order.objects.filter(
            workflow_status='delivery_in_progress'
        ).count()
        
        shipped_orders = Order.objects.filter(
            status='shipped'
        ).count()
    except:
        # Fallback to status-based counting
        pending_orders = Order.objects.filter(status='pending').count()
        processing_orders = Order.objects.filter(status='processing').count()
        shipped_orders = Order.objects.filter(status='shipped').count()
    
    # Get orders assigned to delivery
    orders_in_delivery = Order.objects.filter(
        status='packaged'
    ).count()
    
    # Get workflow-based order statistics for delivery
    try:
        orders_ready_for_delivery_count = Order.objects.filter(
            workflow_status='packaging_completed',
            status='packaged'
        ).count()
        
        orders_in_delivery_count = Order.objects.filter(
            workflow_status='delivery_in_progress'
        ).count()
        
        orders_delivered_count = Order.objects.filter(
            workflow_status='delivery_completed'
        ).count()
    except:
        # Fallback to status-based counting
        orders_ready_for_delivery_count = Order.objects.filter(
            status='packaged'
        ).count()
        
        orders_in_delivery_count = Order.objects.filter(
            status='processing'
        ).count()
        
        orders_delivered_count = Order.objects.filter(
            status='shipped'
        ).count()
    
    # Get recent orders for display
    recent_orders = Order.objects.select_related('product').order_by('-date')[:5]
    
    # Get courier's earnings (if courier)
    courier_earnings = 0
    if courier:
        # Calculate earnings based on successful deliveries and delivery cost
        successful_deliveries_for_earnings = date_range_deliveries.filter(status='delivered')
        courier_earnings = successful_deliveries_for_earnings.aggregate(
            total_earnings=Sum('delivery_cost')
        )['total_earnings'] or 0
    
    # Get additional real data for delivery agents
    if request.user.has_role('Delivery Agent'):
        # Get workflow-based order statistics - handle case when workflow_status doesn't exist
        try:
            orders_ready_for_delivery_count = Order.objects.filter(
                workflow_status='packaging_completed',
                status='packaged'
            ).count()
            
            orders_in_delivery_count = Order.objects.filter(
                workflow_status='delivery_in_progress'
            ).count()
            
            orders_delivered_count = Order.objects.filter(
                workflow_status='delivery_completed'
            ).count()
        except:
            # Fallback to status-based counting
            orders_ready_for_delivery_count = Order.objects.filter(
                status='packaged'
            ).count()
            
            orders_in_delivery_count = Order.objects.filter(
                status='processing'
            ).count()
            
            orders_delivered_count = Order.objects.filter(
                status='shipped'
            ).count()
        
        # Get delivery performance metrics
        delivery_performance = {
            'orders_ready': orders_ready_for_delivery_count,
            'orders_in_progress': orders_in_delivery_count,
            'orders_completed': orders_delivered_count,
            'efficiency_rate': (orders_delivered_count / max(total_orders, 1)) * 100,
        }
    else:
        delivery_performance = None
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    date_range = request.GET.get('date_range', '')
    
    # Get orders for the table - show only orders ready for delivery
    
    orders = Order.objects.filter(
        status='packaged',
        workflow_status='ready_for_delivery'
    ).select_related('product')
    
    # Apply filters
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    if search_query:
        orders = orders.filter(
            Q(order_code__icontains=search_query) |
            Q(customer__icontains=search_query) |
            Q(customer_phone__icontains=search_query)
        )
    
    if date_range:
        today = timezone.now().date()
        if date_range == 'today':
            orders = orders.filter(created_at__date=today)
        elif date_range == 'week':
            week_ago = today - timedelta(days=7)
            orders = orders.filter(created_at__date__gte=week_ago)
        elif date_range == 'month':
            month_ago = today - timedelta(days=30)
            orders = orders.filter(created_at__date__gte=month_ago)
    
    # Order by date and add pagination
    orders = orders.order_by('-date')
    
    # Add pagination
    from django.core.paginator import Paginator
    paginator = Paginator(orders, 10)  # Show 10 orders per page
    page_number = request.GET.get('page')
    orders = paginator.get_page(page_number)
    
    # Get workflow-based statistics
    ready_for_delivery = orders_ready_for_delivery_count
    in_delivery = orders_in_delivery_count
    delivered = orders_delivered_count
    
    # Get shipped orders count
    shipped_orders = Order.objects.filter(status='shipped').count()

    context = {
        'total_deliveries': total_deliveries,
        'successful_deliveries': successful_deliveries,
        'failed_deliveries': failed_deliveries,
        'success_rate': round(success_rate, 1),
        'avg_rating': round(avg_rating, 1),
        'avg_delivery_time': round(avg_delivery_time, 0),
        'total_distance': round(total_distance, 1),
        'courier_earnings': courier_earnings,
        'current_task': current_task,
        'next_deliveries': next_deliveries,
        'delivery_performance': delivery_performance,
        'recent_activity': recent_activity,
        'courier': courier,
        'today': today,
        'start_date': start_date,
        'end_date': end_date,
        'active_deliveries': active_deliveries,
        'completed_today': completed_today,
        'recent_deliveries': recent_deliveries,
        'delivery_companies_count': delivery_companies_count,
        'active_couriers_count': active_couriers_count,
        # Order data
        'orders_for_delivery': orders_for_delivery,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'confirmed_orders': confirmed_orders,
        'processing_orders': processing_orders,
        'delivered_orders': delivered_orders,
        'orders_in_delivery': orders_in_delivery,
        'recent_orders': recent_orders,
        # Workflow-based order statistics
        'orders_ready_for_delivery': orders_ready_for_delivery_count,
        'orders_in_delivery_workflow': orders_in_delivery_count,
        'orders_delivered_workflow': orders_delivered_count,
        # New data for the template
        'orders': orders,
        'ready_for_delivery': ready_for_delivery,
        'in_delivery': in_delivery,
        'delivered': delivered,
        'shipped_orders': shipped_orders,
        # Filter data
        'status_filter': status_filter,
        'search_query': search_query,
        'date_range': date_range,
        # Pagination data
        'paginator': paginator,
    }
    
    return render(request, 'delivery/dashboard.html', context)

@login_required
@user_passes_test(is_delivery_user)
def order_list(request):
    """Display delivery orders with real data"""
    from django.core.paginator import Paginator
    from django.db.models import Count
    from datetime import timedelta
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    date_filter = request.GET.get('date', '')
    
    # Get all orders related to delivery: have delivery record OR in delivery workflow OR in shipping/delivered statuses
    from django.db.models import Q
    delivery_workflows = ['packaging_completed', 'delivery_in_progress', 'delivery_completed']
    delivery_statuses = ['confirmed', 'processing', 'packaged', 'shipped', 'delivered']
    orders = Order.objects.filter(
        Q(delivery__isnull=False) | Q(workflow_status__in=delivery_workflows) | Q(status__in=delivery_statuses)
    ).select_related('product', 'seller').order_by('-date').distinct()
    
    # Apply filters
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    if search_query:
        orders = orders.filter(
            Q(order_code__icontains=search_query) |
            Q(customer__icontains=search_query) |
            Q(customer_phone__icontains=search_query) |
            Q(product__name_en__icontains=search_query)
        )
    
    if date_filter:
        today = timezone.now().date()
        if date_filter == 'today':
            orders = orders.filter(date__date=today)
        elif date_filter == 'week':
            week_ago = today - timedelta(days=7)
            orders = orders.filter(date__date__gte=week_ago)
        elif date_filter == 'month':
            orders = orders.filter(date__month=today.month, date__year=today.year)
    
    # Calculate statistics BEFORE pagination
    total_orders = orders.count()
    pending_orders = orders.filter(status='confirmed').count()
    processing_orders = orders.filter(status='processing').count()
    shipped_orders = orders.filter(status='shipped').count()
    
    # Pagination
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get workflow-based statistics for delivery - handle case when workflow_status doesn't exist
    try:
        orders_ready_for_delivery = orders.filter(workflow_status='packaging_completed').count()
        orders_in_delivery = orders.filter(workflow_status='delivery_in_progress').count()
        orders_delivered = orders.filter(workflow_status='delivery_completed').count()
    except:
        # Fallback to status-based counting
        orders_ready_for_delivery = orders.filter(status='confirmed').count()
        orders_in_delivery = orders.filter(status='processing').count()
        orders_delivered = orders.filter(status='shipped').count()
    
    # Get delivery statistics
    delivery_stats = {
        'total_deliveries': DeliveryRecord.objects.count(),
        'completed_deliveries': DeliveryRecord.objects.filter(status='delivered').count(),
        'pending_deliveries': DeliveryRecord.objects.filter(status='assigned').count(),
        'failed_deliveries': DeliveryRecord.objects.filter(status='failed').count(),
        'orders_ready_for_delivery': orders_ready_for_delivery,
        'orders_in_delivery': orders_in_delivery,
        'orders_delivered': orders_delivered,
    }
    
    # Get additional real data for context
    today = timezone.now().date()
    orders_today = orders.filter(date__date=today).count()
    orders_this_week = orders.filter(date__date__gte=today - timedelta(days=7)).count()
    orders_this_month = orders.filter(date__month=today.month, date__year=today.year).count()
    
    # Get top products being delivered
    top_products = orders.values('product__name_en').annotate(
        count=Count('id')
    ).order_by('-count')[:5]
    
    # Get delivery performance data
    if hasattr(request.user, 'courier_profile'):
        courier = request.user.courier_profile
        courier_deliveries = DeliveryRecord.objects.filter(courier=courier)
        courier_completed = courier_deliveries.filter(status='delivered').count()
        courier_total = courier_deliveries.count()
        courier_success_rate = (courier_completed / courier_total * 100) if courier_total > 0 else 0
    else:
        courier_success_rate = 0
        courier_completed = 0
        courier_total = 0
    
    # Get order status choices for the filter dropdown
    order_status_choices = Order.STATUS_CHOICES
    
    context = {
        'page_obj': page_obj,  # Fixed: template expects page_obj, not orders
        'orders': page_obj,     # Keep both for compatibility
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'processing_orders': processing_orders,
        'shipped_orders': shipped_orders,
        'delivery_stats': delivery_stats,
        'current_status': status_filter,
        'search_query': search_query,
        'date_filter': date_filter,
        'order_status_choices': order_status_choices,  # Added: for filter dropdown
        # Additional real data
        'orders_today': orders_today,
        'orders_this_week': orders_this_week,
        'orders_this_month': orders_this_month,
        'top_products': top_products,
        'courier_success_rate': round(courier_success_rate, 1),
        'courier_completed': courier_completed,
        'courier_total': courier_total,
        # Workflow-based order statistics
        'orders_ready_for_delivery': orders_ready_for_delivery,
        'orders_in_delivery_workflow': orders_in_delivery,
        'orders_delivered_workflow': orders_delivered,
    }
    
    return render(request, 'delivery/order_list.html', context)

@login_required
@user_passes_test(is_delivery_user)
def order_detail(request, order_id):
    """Display detailed order information with real data"""
    try:
        # Get the order first
        order = get_object_or_404(Order, id=order_id)
        
        # Try to get the delivery record, but don't require it
        delivery = None
        try:
            delivery = DeliveryRecord.objects.select_related(
                'courier', 'delivery_company'
            ).get(order=order)
        except DeliveryRecord.DoesNotExist:
            # Order exists but no delivery record yet
            pass
        
        # Check if user has access to this delivery
        courier = None
        if hasattr(request.user, 'courier_profile'):
            courier = request.user.courier_profile
            if delivery and delivery.courier != courier:
                messages.error(request, "You don't have access to this delivery.")
                return redirect('delivery:dashboard')
        
        # Initialize delivery-related data
        status_history = []
        delivery_attempts = []
        delivery_proofs = []
        location_history = []
        related_deliveries = []
        delivery_time = None
        estimated_time = None
        
        if delivery:
            # Get delivery status history
            status_history = DeliveryStatusHistory.objects.filter(
                delivery=delivery
            ).select_related('changed_by').order_by('-timestamp')
        
            # Get delivery attempts
            delivery_attempts = DeliveryAttempt.objects.filter(
                delivery=delivery
            ).order_by('-attempt_time')
        
            # Get delivery proofs
            delivery_proofs = DeliveryProof.objects.filter(
                delivery=delivery
            ).order_by('-capture_time')
            
            # Get courier location history for this delivery
            if courier:
                location_history = CourierLocation.objects.filter(
                    courier=courier,
                    timestamp__gte=delivery.assigned_at
                ).order_by('-timestamp')[:10]
            
            # Calculate delivery statistics
            delivery_time = delivery.get_delivery_time()
            estimated_time = delivery.get_estimated_delivery_time()
            
            # Get related deliveries (same courier, same day)
            if courier:
                related_deliveries = DeliveryRecord.objects.filter(
                    courier=courier,
                    assigned_at__date=delivery.assigned_at.date()
                ).exclude(id=delivery.id).order_by('assigned_at')[:5]
    
        context = {
            'delivery': delivery,
            'order': order,
            'courier': courier,
            'status_history': status_history,
            'delivery_attempts': delivery_attempts,
            'delivery_proofs': delivery_proofs,
            'location_history': location_history,
            'related_deliveries': related_deliveries,
            'delivery_time': delivery_time,
            'estimated_time': estimated_time,
        }
    
        return render(request, 'delivery/order_detail.html', context)
        
    except Order.DoesNotExist:
        messages.error(request, "Order not found.")
        return redirect('delivery:order_list')

@login_required
@user_passes_test(is_courier)
def update_status(request, delivery_id):
    """Update delivery status (AJAX)"""
    if request.method != 'POST':
        return JsonResponse({'error': 'Invalid request method'}, status=400)
    
    delivery = get_object_or_404(DeliveryRecord, id=delivery_id)
    courier = request.user.courier_profile
    
    # Check if courier owns this delivery
    if delivery.courier != courier:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    new_status = request.POST.get('status')
    notes = request.POST.get('notes', '')
    
    if new_status not in dict(DeliveryRecord.STATUS_CHOICES):
        return JsonResponse({'error': 'Invalid status'}, status=400)
    
    try:
        with transaction.atomic():
            # Update delivery status
            old_status = delivery.status
            delivery.status = new_status
            
            # Update timestamps based on status
            now = timezone.now()
            if new_status == 'accepted' and not delivery.accepted_at:
                delivery.accepted_at = now
            elif new_status == 'picked_up' and not delivery.picked_up_at:
                delivery.picked_up_at = now
            elif new_status == 'out_for_delivery' and not delivery.out_for_delivery_at:
                delivery.out_for_delivery_at = now
            elif new_status == 'delivered' and not delivery.delivered_at:
                delivery.delivered_at = now
                delivery.actual_delivery_time = now
            elif new_status == 'failed' and not delivery.failed_at:
                delivery.failed_at = now
            
            delivery.save()
            
            # Create status history
            DeliveryStatusHistory.objects.create(
                delivery=delivery,
                status=new_status,
                changed_by=request.user,
                notes=notes
            )
            
            # Update courier statistics if delivered
            if new_status == 'delivered' and old_status != 'delivered':
                # Set manager confirmation status to pending
                delivery.manager_confirmation_status = 'pending'
                delivery.save()
                
                # Create notification for delivery manager
                try:
                    from notifications.models import Notification
                    Notification.objects.create(
                        recipient_type='role',
                        recipient_role='Delivery Manager',
                        title=f'Delivery Confirmation Required - {delivery.order.order_code}',
                        message=f'Delivery agent has marked order {delivery.order.order_code} as delivered. Please confirm the delivery.',
                        notification_type='delivery_confirmation_required',
                        related_object_id=str(delivery.id),
                        related_object_type='delivery'
                    )
                except Exception as e:
                    print(f"Error creating notification: {e}")
                
                messages.success(request, 'Delivery submitted for manager confirmation!')
                    
            elif new_status == 'failed' and old_status != 'failed':
                courier.total_deliveries += 1
                courier.failed_deliveries += 1
                courier.save()
            
            return JsonResponse({
                'success': True,
                'status': new_status,
                'message': f'Status updated to {new_status}'
            })
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
@user_passes_test(is_courier)
def complete_delivery(request, delivery_id):
    """Complete delivery with proof"""
    delivery = get_object_or_404(DeliveryRecord, id=delivery_id)
    courier = request.user.courier_profile
    
    # Check if courier owns this delivery
    if delivery.courier != courier:
        messages.error(request, "You don't have permission to complete this delivery.")
        return redirect('delivery:order_detail', delivery_id=delivery_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Update delivery status
                delivery.status = 'delivered'
                delivery.delivered_at = timezone.now()
                delivery.actual_delivery_time = timezone.now()
                
                # Get form data
                customer_signature = request.POST.get('customer_signature', '')
                delivery_notes = request.POST.get('delivery_notes', '')
                customer_rating = request.POST.get('customer_rating')
                customer_feedback = request.POST.get('customer_feedback', '')
                
                # Update delivery record
                if customer_signature:
                    delivery.customer_signature = customer_signature
                if delivery_notes:
                    delivery.delivery_notes = delivery_notes
                if customer_rating:
                    delivery.customer_rating = int(customer_rating)
                if customer_feedback:
                    delivery.customer_feedback = customer_feedback
                
                # Handle proof photo
                if 'proof_photo' in request.FILES:
                    delivery.delivery_proof_photo = request.FILES['proof_photo']
                
                delivery.save()
                
                # Create status history
                DeliveryStatusHistory.objects.create(
                    delivery=delivery,
                    status='delivered',
                    changed_by=request.user,
                    notes=delivery_notes
                )
                
                # Create delivery proof
                if customer_signature:
                    DeliveryProof.objects.create(
                        delivery=delivery,
                        courier=courier,
                        proof_type='signature',
                        proof_data=customer_signature
                    )
                
                if 'proof_photo' in request.FILES:
                    DeliveryProof.objects.create(
                        delivery=delivery,
                        courier=courier,
                        proof_type='photo',
                        proof_data='Photo uploaded'
                    )
                
                # Set manager confirmation status to pending
                delivery.manager_confirmation_status = 'pending'
                delivery.save()
                
                # Create notification for delivery manager
                try:
                    from notifications.models import Notification
                    Notification.objects.create(
                        recipient_type='role',
                        recipient_role='Delivery Manager',
                        title=f'Delivery Confirmation Required - {delivery.order.order_code}',
                        message=f'Delivery agent has marked order {delivery.order.order_code} as delivered. Please confirm the delivery.',
                        notification_type='delivery_confirmation_required',
                        related_object_id=str(delivery.id),
                        related_object_type='delivery'
                    )
                except Exception as e:
                    print(f"Error creating notification: {e}")
                
                messages.success(request, 'Delivery submitted for manager confirmation!')
                return redirect('delivery:dashboard')
                
        except Exception as e:
            messages.error(request, f'Error completing delivery: {str(e)}')
    
    context = {
        'delivery': delivery,
        'courier': courier,
    }
    
    return render(request, 'delivery/complete_delivery.html', context)

@login_required
@user_passes_test(is_courier)
def failed_delivery(request, delivery_id):
    """Report failed delivery"""
    delivery = get_object_or_404(DeliveryRecord, id=delivery_id)
    courier = request.user.courier_profile
    
    # Check if courier owns this delivery
    if delivery.courier != courier:
        messages.error(request, "You don't have permission to report this delivery.")
        return redirect('delivery:order_detail', delivery_id=delivery_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Get form data
                failure_reason = request.POST.get('failure_reason')
                customer_feedback = request.POST.get('customer_feedback', '')
                notes = request.POST.get('notes', '')
                next_attempt_date = request.POST.get('next_attempt_date')
                
                # Create delivery attempt
                attempt = DeliveryAttempt.objects.create(
                    delivery=delivery,
                    courier=courier,
                    attempt_number=delivery.attempts.count() + 1,
                    result='failed',
                    failure_reason=failure_reason,
                    customer_feedback=customer_feedback,
                    notes=notes,
                    next_attempt_date=next_attempt_date if next_attempt_date else None
                )
                
                # Handle proof photo if provided
                if 'proof_image' in request.FILES:
                    attempt.proof_image = request.FILES['proof_image']
                    attempt.save()
                
                # Update delivery status
                delivery.status = 'failed'
                delivery.failed_at = timezone.now()
                delivery.save()
                
                # Create status history
                DeliveryStatusHistory.objects.create(
                    delivery=delivery,
                    status='failed',
                    changed_by=request.user,
                    notes=f"Failed: {failure_reason}. {notes}"
                )
                
                # Update courier statistics
                courier.total_deliveries += 1
                courier.failed_deliveries += 1
                courier.save()
                
                messages.success(request, 'Failed delivery reported successfully!')
                return redirect('delivery:dashboard')
                
        except Exception as e:
            messages.error(request, f'Error reporting failed delivery: {str(e)}')
    
    context = {
        'delivery': delivery,
        'courier': courier,
    }
    
    return render(request, 'delivery/failed_delivery.html', context)

@login_required
@user_passes_test(is_delivery_user)
def performance(request):
    """Delivery performance dashboard"""
    today = timezone.now().date()
    courier = None
    if hasattr(request.user, 'courier_profile'):
        courier = request.user.courier_profile
    
    # For admin users and delivery agents, show overall delivery performance
    if (request.user.is_superuser or 
        request.user.has_role('Admin') or 
        request.user.has_role('Super Admin') or
        request.user.has_role('Delivery Manager') or
        request.user.has_role('Delivery Agent')):
        
        # Get overall delivery statistics
        performance_data = DeliveryPerformance.objects.filter(
            date__gte=today - timedelta(days=30)
        ).order_by('-date')
        
        # Calculate overall statistics
        total_deliveries = performance_data.aggregate(total=Sum('total_deliveries'))['total'] or 0
        total_distance = performance_data.aggregate(total=Sum('total_distance'))['total'] or 0
        avg_delivery_time = performance_data.aggregate(avg=Avg('average_delivery_time'))['avg'] or 0
        success_rate = performance_data.aggregate(rate=Avg('successful_deliveries'))['rate'] or 0
        
        # Get recent performance records
        recent_performance = performance_data[:7]
        
        # Get delivery statistics for better context
        delivery_stats = {
            'total_deliveries': DeliveryRecord.objects.count(),
            'completed_deliveries': DeliveryRecord.objects.filter(status='delivered').count(),
            'pending_deliveries': DeliveryRecord.objects.filter(status='assigned').count(),
            'failed_deliveries': DeliveryRecord.objects.filter(status='failed').count(),
        }
        
        # Get courier statistics
        courier_stats = {
            'total_couriers': Courier.objects.count(),
            'active_couriers': Courier.objects.filter(availability='available').count(),
            'avg_courier_rating': Courier.objects.aggregate(avg=Avg('rating'))['avg'] or 0,
        }
        
        # Get order statistics for delivery
        try:
            orders_ready_for_delivery = Order.objects.filter(
                workflow_status='packaging_completed',
                status='packaged'
            ).count()
            
            orders_in_delivery = Order.objects.filter(
                workflow_status='delivery_in_progress'
            ).count()
            
            orders_delivered = Order.objects.filter(
                workflow_status='delivery_completed'
            ).count()
            
            total_orders_for_delivery = Order.objects.filter(
                status__in=['packaged', 'shipped']
            ).count()
        except:
            # Fallback to status-based counting
            orders_ready_for_delivery = Order.objects.filter(
                status='packaged'
            ).count()
            
            orders_in_delivery = Order.objects.filter(
                status='processing'
            ).count()
            
            orders_delivered = Order.objects.filter(
                status='shipped'
            ).count()
            
            total_orders_for_delivery = Order.objects.filter(
                status__in=['packaged', 'shipped']
            ).count()
        
        context = {
            'courier': None,
            'performance_data': performance_data,
            'total_deliveries': total_deliveries,
            'total_distance': total_distance,
            'avg_delivery_time': avg_delivery_time,
            'success_rate': success_rate,
            'recent_performance': recent_performance,
            'delivery_stats': delivery_stats,
            'courier_stats': courier_stats,
            # Order statistics for delivery
            'orders_ready_for_delivery': orders_ready_for_delivery,
            'orders_in_delivery': orders_in_delivery,
            'orders_delivered': orders_delivered,
            'total_orders_for_delivery': total_orders_for_delivery,
            'is_admin': True,
        }
        
        return render(request, 'delivery/performance.html', context)
    
    # For couriers, show their specific performance
    if not courier:
        messages.error(request, 'Courier profile not found.')
        return redirect('delivery:dashboard')
    
    # Get performance data for the current courier
    performance_data = DeliveryPerformance.objects.filter(
        courier=courier,
        date__gte=today - timedelta(days=30)
    ).order_by('-date')
    
    # Calculate statistics
    total_deliveries = performance_data.aggregate(total=Sum('total_deliveries'))['total'] or 0
    total_distance = performance_data.aggregate(total=Sum('total_distance'))['total'] or 0
    avg_delivery_time = performance_data.aggregate(avg=Avg('average_delivery_time'))['avg'] or 0
    success_rate = performance_data.aggregate(rate=Avg('successful_deliveries'))['rate'] or 0
    
    # Get recent performance records
    recent_performance = performance_data[:7]
    
    # Get order statistics for delivery
    try:
        orders_ready_for_delivery = Order.objects.filter(
            workflow_status='packaging_completed',
            status='packaged'
        ).count()
        
        orders_in_delivery = Order.objects.filter(
            workflow_status='delivery_in_progress'
        ).count()
        
        orders_delivered = Order.objects.filter(
            workflow_status='delivery_completed'
        ).count()
        
        total_orders_for_delivery = Order.objects.filter(
            status__in=['packaged', 'shipped']
        ).count()
    except:
        # Fallback to status-based counting
        orders_ready_for_delivery = Order.objects.filter(
            status='packaged'
        ).count()
        
        orders_in_delivery = Order.objects.filter(
            status='processing'
        ).count()
        
        orders_delivered = Order.objects.filter(
            status='shipped'
        ).count()
        
        total_orders_for_delivery = Order.objects.filter(
            status__in=['packaged', 'shipped']
        ).count()
    
    context = {
        'courier': courier,
        'performance_data': performance_data,
        'total_deliveries': total_deliveries,
        'total_distance': total_distance,
        'avg_delivery_time': avg_delivery_time,
        'success_rate': success_rate,
        'recent_performance': recent_performance,
        # Order statistics for delivery
        'orders_ready_for_delivery': orders_ready_for_delivery,
        'orders_in_delivery': orders_in_delivery,
        'orders_delivered': orders_delivered,
        'total_orders_for_delivery': total_orders_for_delivery,
        'is_admin': False,
    }
    
    return render(request, 'delivery/performance.html', context)

@login_required
@user_passes_test(is_delivery_user)
def companies(request):
    """List delivery companies with performance metrics."""
    companies = DeliveryCompany.objects.all().order_by('name_en')
    data = []
    for c in companies:
        total = DeliveryRecord.objects.filter(delivery_company=c).count()
        delivered = DeliveryRecord.objects.filter(delivery_company=c, status='delivered').count()
        returned = DeliveryRecord.objects.filter(delivery_company=c, status='failed').count()
        rate = (delivered / total * 100) if total else 0
        data.append({
            'company': c,
            'total': total,
            'delivered': delivered,
            'returned': returned,
            'success_rate': round(rate, 1),
        })
    return render(request, 'delivery/companies.html', {'companies': data})

@login_required
@user_passes_test(is_delivery_user)
def company_detail(request, company_id):
    """Company detail performance page."""
    company = get_object_or_404(DeliveryCompany, id=company_id)
    records = DeliveryRecord.objects.filter(delivery_company=company).order_by('-assigned_at')[:50]
    total = records.count()
    delivered = records.filter(status='delivered').count()
    returned = records.filter(status='failed').count()
    rate = (delivered / total * 100) if total else 0
    return render(request, 'delivery/company_detail.html', {
        'company': company,
        'records': records,
        'total': total,
        'delivered': delivered,
        'returned': returned,
        'success_rate': round(rate, 1),
    })

@login_required
@user_passes_test(is_delivery_user)
def returns_process(request):
    """Process returned/cancelled/un-checked orders for re-intake."""
    search = request.GET.get('q', '')
    qs = Order.objects.filter(status__in=['cancelled', 'returned'])
    if search:
        qs = qs.filter(Q(order_code__icontains=search) | Q(customer__icontains=search) | Q(customer_phone__icontains=search))
    qs = qs.order_by('-date')[:200]
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        order = get_object_or_404(Order, id=order_id)
        # Move back to packaging queue
        try:
            order.workflow_status = 'packaging_completed'
        except Exception:
            pass
        order.status = 'processing'
        order.save()
        messages.success(request, f"تم استلام الطلب {order.order_code} وإرساله لانتظار التغليف")
        return redirect('delivery:returns_process')
    return render(request, 'delivery/returns_process.html', {'orders': qs, 'search': search})

@login_required
@user_passes_test(is_delivery_user)
def settings(request):
    """Delivery settings page"""
    courier = None
    if hasattr(request.user, 'courier_profile'):
        courier = request.user.courier_profile
    
    # For admin users, show delivery system settings and agent management
    if (request.user.is_superuser or 
        request.user.has_role('Admin') or 
        request.user.has_role('Super Admin') or
        request.user.has_role('Delivery Manager')):
        
        # Get delivery system statistics
        total_couriers = Courier.objects.count()
        active_couriers = Courier.objects.filter(availability='available').count()
        total_deliveries = DeliveryRecord.objects.count()
        completed_deliveries = DeliveryRecord.objects.filter(status='delivered').count()
        
        # Get additional delivery statistics
        delivery_stats = {
            'total_deliveries': total_deliveries,
            'completed_deliveries': completed_deliveries,
            'pending_deliveries': DeliveryRecord.objects.filter(status='assigned').count(),
            'failed_deliveries': DeliveryRecord.objects.filter(status='failed').count(),
            'in_transit': DeliveryRecord.objects.filter(status='in_transit').count(),
        }
        
        # Get courier statistics
        courier_stats = {
            'total_couriers': total_couriers,
            'active_couriers': active_couriers,
            'avg_rating': Courier.objects.aggregate(avg=Avg('rating'))['avg'] or 0,
            'total_distance': 0,  # Will be calculated from performance data
        }
        
        # Get delivery companies
        delivery_companies = DeliveryCompany.objects.all()
        
        # Get all delivery agents and their preferences
        delivery_agents = User.objects.filter(user_roles__role__name='Delivery Agent').select_related('delivery_preferences')
        
        if request.method == 'POST':
            # Handle system-wide settings updates
            messages.success(request, 'Delivery system settings updated successfully!')
            return redirect('delivery:settings')
        
        context = {
            'courier': None,
            'total_couriers': total_couriers,
            'active_couriers': active_couriers,
            'total_deliveries': total_deliveries,
            'completed_deliveries': completed_deliveries,
            'delivery_stats': delivery_stats,
            'courier_stats': courier_stats,
            'delivery_companies': delivery_companies,
            'delivery_agents': delivery_agents,
            'is_admin': True,
        }
        
        return render(request, 'delivery/settings.html', context)
    
    # For delivery agents, show their personal preferences
    if request.user.has_role('Delivery Agent'):
        # Get or create delivery preferences
        preferences, created = DeliveryPreferences.objects.get_or_create(
            user=request.user,
            defaults={
                'preferred_areas': ['all'],
                'vehicle_type': 'motorcycle',
                'max_package_weight': 50.00,
                'start_time': '08:00',
                'end_time': '18:00',
                'accept_urgent_deliveries': True,
                'notification_enabled': True,
                'auto_accept_orders': False,
                'max_daily_deliveries': 20,
                'preferred_delivery_radius': 10,
            }
        )
        
        if request.method == 'POST':
            # Handle preferences updates
            preferences.preferred_areas = request.POST.getlist('preferred_areas')
            preferences.vehicle_type = request.POST.get('vehicle_type', 'motorcycle')
            preferences.max_package_weight = Decimal(request.POST.get('max_package_weight', 50.00))
            preferences.start_time = request.POST.get('start_time', '08:00')
            preferences.end_time = request.POST.get('end_time', '18:00')
            preferences.accept_urgent_deliveries = request.POST.get('accept_urgent_deliveries') == 'on'
            preferences.notification_enabled = request.POST.get('notification_enabled') == 'on'
            preferences.auto_accept_orders = request.POST.get('auto_accept_orders') == 'on'
            preferences.max_daily_deliveries = int(request.POST.get('max_daily_deliveries', 20))
            preferences.preferred_delivery_radius = int(request.POST.get('preferred_delivery_radius', 10))
            preferences.save()
            
            messages.success(request, 'Delivery preferences updated successfully!')
            return redirect('delivery:settings')
        
        context = {
            'preferences': preferences,
            'is_admin': False,
            'is_delivery_agent': True,
        }
        
        return render(request, 'delivery/settings.html', context)
    
    # For couriers, show their personal settings
    if not courier:
        messages.error(request, 'Courier profile not found.')
        return redirect('delivery:dashboard')
    
    if request.method == 'POST':
        # Handle settings updates
        availability = request.POST.get('availability', 'available')
        notification_preferences = request.POST.getlist('notifications')
        auto_accept_orders = request.POST.get('auto_accept_orders', 'off') == 'on'
        
        # Update courier settings
        courier.availability = availability
        courier.auto_accept_orders = auto_accept_orders
        courier.save()
        
        messages.success(request, 'Settings updated successfully!')
        return redirect('delivery:settings')
    
    context = {
        'courier': courier,
        'is_admin': False,
        'is_delivery_agent': False,
    }
    
    return render(request, 'delivery/settings.html', context)

@login_required
@user_passes_test(is_delivery_user)
def update_order_status(request, order_id):
    """Update order status for delivery agents"""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'GET':
        # Show update form
        context = {
            'order': order,
            'status_choices': [
                ('confirmed', 'Confirmed'),
                ('processing', 'Processing'),
                ('shipped', 'Shipped'),
                ('delivered', 'Delivered'),
                ('cancelled', 'Cancelled'),
            ]
        }
        return render(request, 'delivery/update_order_status.html', context)
    
    elif request.method == 'POST':
        try:
            order = get_object_or_404(Order, id=order_id)
            new_status = request.POST.get('status')
            notes = request.POST.get('notes', '')
            
            # Validate status
            valid_statuses = ['confirmed', 'processing', 'shipped', 'delivered', 'cancelled']
            if new_status not in valid_statuses:
                return JsonResponse({'success': False, 'message': 'Invalid status'})
            
            # Update order status
            old_status = order.status
            order.status = new_status
            order.save()
            
            # Create delivery record if it doesn't exist and status is shipped or delivered
            if new_status in ['shipped', 'delivered'] and not hasattr(order, 'delivery'):
                # Get or create delivery company
                delivery_company = DeliveryCompany.objects.first()
                if not delivery_company:
                    delivery_company = DeliveryCompany.objects.create(
                        name_en='Default Delivery Company',
                        name_ar='شركة التوصيل الافتراضية',
                        base_cost=10.00,
                        is_active=True
                    )
                
                # Create delivery record
                delivery_record = DeliveryRecord.objects.create(
                    order=order,
                    delivery_company=delivery_company,
                    tracking_number=f'TRK-{order.id}-{timezone.now().strftime("%Y%m%d")}',
                    status='assigned' if new_status == 'shipped' else 'delivered',
                    delivery_cost=Decimal('10.00'),
                    delivery_notes=notes
                )
            
            # Log status change
            if hasattr(order, 'delivery'):
                DeliveryStatusHistory.objects.create(
                    delivery=order.delivery,
                    old_status=old_status,
                    new_status=new_status,
                    changed_by=request.user,
                    notes=notes
                )
            
            messages.success(request, f'Order status updated to {new_status.title()}')
            
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({
                    'success': True, 
                    'message': f'Order status updated to {new_status.title()}',
                    'new_status': new_status
                })
            
            return redirect('delivery:dashboard')
            
        except Exception as e:
            if request.headers.get('Content-Type') == 'application/json':
                return JsonResponse({'success': False, 'message': str(e)})
            messages.error(request, f'Error updating status: {str(e)}')
            return redirect('delivery:dashboard')
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
@user_passes_test(lambda u: u.is_superuser or u.has_role('Admin') or u.has_role('Super Admin') or u.has_role('Delivery Manager'))
def assign_orders(request):
    """Admin view to assign orders to delivery agents"""
    if request.method == 'POST':
        try:
            order_id = request.POST.get('order_id')
            delivery_agent_id = request.POST.get('delivery_agent_id')
            notes = request.POST.get('notes', '')
            
            order = get_object_or_404(Order, id=order_id)
            delivery_agent = get_object_or_404(User, id=delivery_agent_id)
            
            # Check if delivery agent has the correct role
            if not delivery_agent.has_role('Delivery Agent'):
                return JsonResponse({'success': False, 'message': 'Selected user is not a delivery agent'})
            
            # Create or update assignment
            assignment, created = OrderAssignment.objects.get_or_create(
                order=order,
                delivery_agent=delivery_agent,
                defaults={
                    'assigned_by': request.user,
                    'notes': notes,
                    'is_active': True
                }
            )
            
            if not created:
                assignment.notes = notes
                assignment.is_active = True
                assignment.assigned_by = request.user
                assignment.save()
            
            return JsonResponse({
                'success': True, 
                'message': f'Order {order.order_code} assigned to {delivery_agent.get_full_name() or delivery_agent.username}'
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    # Get unassigned orders and delivery agents
    unassigned_orders = Order.objects.filter(
        workflow_status='ready_for_delivery',
        status='packaged',
        delivery_assignments__isnull=True
    ).select_related('product', 'seller').prefetch_related('items__product').order_by('-date')
    
    delivery_agents = User.objects.filter(
        user_roles__role__name='Delivery Agent'
    ).select_related('delivery_preferences')
    
    # Get assigned orders for display
    assigned_orders = OrderAssignment.objects.filter(
        is_active=True
    ).select_related('order', 'delivery_agent', 'assigned_by').order_by('-assigned_at')
    
    context = {
        'unassigned_orders': unassigned_orders,
        'delivery_agents': delivery_agents,
        'assigned_orders': assigned_orders,
    }
    
    return render(request, 'delivery/assign_orders.html', context)

# API Endpoints for mobile app integration

@csrf_exempt
@require_http_methods(["POST"])
def update_location(request):
    """Update courier location (API endpoint)"""
    try:
        data = json.loads(request.body)
        courier_id = data.get('courier_id')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        battery_level = data.get('battery_level')
        connection_type = data.get('connection_type', 'cellular')
        
        courier = get_object_or_404(Courier, id=courier_id)
        
        # Update courier location
        courier.current_location_lat = Decimal(latitude)
        courier.current_location_lng = Decimal(longitude)
        courier.last_location_update = timezone.now()
        courier.save()
        
        # Create location record
        CourierLocation.objects.create(
            courier=courier,
            latitude=latitude,
            longitude=longitude,
            battery_level=battery_level,
            connection_type=connection_type
        )
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
@require_http_methods(["POST"])
def update_availability(request):
    """Update courier availability (API endpoint)"""
    try:
        data = json.loads(request.body)
        courier_id = data.get('courier_id')
        availability = data.get('availability')
        
        courier = get_object_or_404(Courier, id=courier_id)
        
        if availability in dict(Courier.AVAILABILITY_CHOICES):
            courier.availability = availability
            courier.save()
            return JsonResponse({'success': True})
        else:
            return JsonResponse({'error': 'Invalid availability status'}, status=400)
            
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
@require_http_methods(["GET"])
def get_assigned_orders(request, courier_id):
    """Get assigned orders for courier (API endpoint)"""
    try:
        courier = get_object_or_404(Courier, id=courier_id)
        today = timezone.now().date()
        
        deliveries = DeliveryRecord.objects.filter(
            courier=courier,
            assigned_at__date=today,
            status__in=['assigned', 'accepted', 'picked_up', 'out_for_delivery']
        ).select_related('order').order_by('estimated_delivery_time')
        
        orders_data = []
        for delivery in deliveries:
            orders_data.append({
                'id': str(delivery.id),
                'tracking_number': delivery.tracking_number,
                'order_number': delivery.order.order_number,
                'customer_name': delivery.order.customer_name,
                'customer_phone': delivery.order.customer_phone,
                'customer_address': delivery.order.customer_address,
                'status': delivery.status,
                'priority': delivery.priority,
                'delivery_cost': str(delivery.delivery_cost),
                'estimated_delivery_time': delivery.estimated_delivery_time.isoformat() if delivery.estimated_delivery_time else None,
                'assigned_at': delivery.assigned_at.isoformat(),
            })
        
        return JsonResponse({'orders': orders_data})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@csrf_exempt
@require_http_methods(["POST"])
def upload_proof(request):
    """Upload delivery proof (API endpoint)"""
    try:
        delivery_id = request.POST.get('delivery_id')
        courier_id = request.POST.get('courier_id')
        proof_type = request.POST.get('proof_type')
        proof_data = request.POST.get('proof_data')
        
        delivery = get_object_or_404(DeliveryRecord, id=delivery_id)
        courier = get_object_or_404(Courier, id=courier_id)
        
        # Verify courier owns this delivery
        if delivery.courier != courier:
            return JsonResponse({'error': 'Unauthorized'}, status=403)
        
        # Create proof record
        DeliveryProof.objects.create(
            delivery=delivery,
            courier=courier,
            proof_type=proof_type,
            proof_data=proof_data
        )
        
        return JsonResponse({'success': True})
        
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=400)

@login_required
def assign_order(request, order_id):
    """Assign a specific order to a delivery agent."""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if user has permission
    if not (request.user.is_superuser or request.user.has_role('Super Admin') or request.user.has_role('Admin') or request.user.has_role('Delivery Agent')):
        messages.error(request, "You don't have permission to assign orders.")
        return redirect('orders:detail', order_id=order_id)
    
    # Check if order is ready for delivery
    if order.workflow_status != 'ready_for_delivery' or order.status != 'packaged':
        messages.error(request, f"Order {order.order_code} is not ready for delivery.")
        return redirect('orders:detail', order_id=order_id)
    
    # Get available delivery agents
    delivery_agents = User.objects.filter(
        user_roles__role__name__in=['Delivery Agent', 'Delivery']
    ).distinct()
    
    if request.method == 'POST':
        agent_id = request.POST.get('agent_id')
        if agent_id:
            try:
                agent = User.objects.get(id=agent_id)
                
                # Create delivery assignment
                OrderAssignment.objects.create(
                    order=order,
                    delivery_agent=agent,
                    assigned_by=request.user
                )
                
                # Update order workflow status
                order.workflow_status = 'ready_for_delivery'
                order.save()
                
                messages.success(request, f"Order {order.order_code} assigned to {agent.get_full_name()}")
                return redirect('orders:detail', order_id=order_id)
                
            except User.DoesNotExist:
                messages.error(request, "Selected agent not found.")
        else:
            messages.error(request, "Please select a delivery agent.")
    
    context = {
        'order': order,
        'delivery_agents': delivery_agents,
    }
    
    return render(request, 'delivery/assign_order.html', context)

@login_required
def start_delivery(request, order_id):
    """Start delivery for an order."""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if user has permission
    if not (request.user.is_superuser or request.user.has_role('Super Admin') or request.user.has_role('Admin') or request.user.has_role('Delivery Agent')):
        messages.error(request, "You don't have permission to start delivery.")
        return redirect('orders:detail', order_id=order_id)
    
    # Check if order is ready for delivery
    if order.workflow_status != 'ready_for_delivery':
        messages.error(request, f"Order {order.order_code} is not ready for delivery.")
        return redirect('orders:detail', order_id=order_id)
    
    if request.method == 'POST':
        try:
            # Get or create delivery company if none exists
            delivery_company = DeliveryCompany.objects.first()
            if not delivery_company:
                delivery_company = DeliveryCompany.objects.create(
                    name_en='Default Delivery Company',
                    name_ar='شركة التوصيل الافتراضية',
                    base_cost=10.00,
                    is_active=True
                )
            
            # Get or create courier profile for the user
            courier, created = Courier.objects.get_or_create(
                user=request.user,
                defaults={
                    'employee_id': f"EMP_{request.user.id}",
                    'delivery_company': delivery_company,
                    'phone_number': getattr(request.user, 'phone_number', ''),
                    'status': 'active',
                    'availability': 'available'
                }
            )
            
            # Update order workflow status
            order.workflow_status = 'delivery_in_progress'
            order.status = 'shipped'
            order.save()
            
            # Create delivery record
            DeliveryRecord.objects.create(
                order=order,
                courier=courier,
                delivery_company=courier.delivery_company,
                tracking_number=f"TRK_{order.id}_{timezone.now().strftime('%Y%m%d%H%M%S')}",
                status='in_transit',
                delivery_cost=delivery_company.base_cost or 10.00
            )
            
            messages.success(request, f"Delivery started for order {order.order_code}")
            return redirect('orders:detail', order_id=order_id)
            
        except Exception as e:
            messages.error(request, f"Error starting delivery: {str(e)}")
    
    context = {
        'order': order,
    }
    
    return render(request, 'delivery/start_delivery.html', context)

@login_required
def complete_delivery(request, order_id):
    """Complete delivery for an order."""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if user has permission
    if not (request.user.is_superuser or request.user.has_role('Super Admin') or request.user.has_role('Admin') or request.user.has_role('Delivery Agent')):
        messages.error(request, "You don't have permission to complete delivery.")
        return redirect('orders:detail', order_id=order_id)
    
    # Check if order is in delivery
    if order.workflow_status != 'delivery_in_progress':
        messages.error(request, f"Order {order.order_code} is not in delivery.")
        return redirect('orders:detail', order_id=order_id)
    
    if request.method == 'POST':
        try:
            # Update delivery record
            delivery_record = DeliveryRecord.objects.filter(order=order).first()
            if delivery_record:
                delivery_record.status = 'delivered'
                delivery_record.delivered_at = timezone.now()
                delivery_record.actual_delivery_time = timezone.now()
                # Set manager confirmation status to pending
                delivery_record.manager_confirmation_status = 'pending'
                delivery_record.save()
                
                # Create notification for delivery manager
                try:
                    from notifications.models import Notification
                    Notification.objects.create(
                        recipient_type='role',
                        recipient_role='Delivery Manager',
                        title=f'Delivery Confirmation Required - {order.order_code}',
                        message=f'Delivery agent has marked order {order.order_code} as delivered. Please confirm the delivery.',
                        notification_type='delivery_confirmation_required',
                        related_object_id=str(delivery_record.id),
                        related_object_type='delivery'
                    )
                except Exception as e:
                    print(f"Error creating notification: {e}")
            else:
                # If no delivery record, just update order status
                order.status = 'delivered'
                order.workflow_status = 'delivery_completed'
                order.save()
            
            messages.success(request, f"Delivery submitted for manager confirmation for order {order.order_code}")
            return redirect('orders:detail', order_id=order_id)
            
        except Exception as e:
            messages.error(request, f"Error completing delivery: {str(e)}")
    
    context = {
        'order': order,
    }
    
    return render(request, 'delivery/complete_delivery.html', context)

# ============================================
# DELIVERY MANAGER VIEWS (New Implementation)
# ============================================

@login_required
@user_passes_test(is_delivery_manager)
def manager_dashboard(request):
    """Delivery Manager Dashboard with statistics"""
    # Get order statistics
    total_orders = Order.objects.count()
    completed_orders = Order.objects.filter(status='delivered').count()
    cancelled_orders = Order.objects.filter(status='cancelled').count()
    pending_orders = Order.objects.filter(status='pending').count()
    
    # Get pending delivery confirmations
    pending_confirmations_count = DeliveryRecord.objects.filter(
        status='delivered',
        manager_confirmation_status='pending'
    ).count()
    
    # Get orders grouped by shipping company
    orders_by_company = {}
    for company in DeliveryCompany.objects.filter(is_active=True):
        orders = Order.objects.filter(
            delivery__delivery_company=company
        ).count()
        delivered = Order.objects.filter(
            delivery__delivery_company=company,
            status='delivered'
        ).count()
        orders_by_company[company] = {
            'total': orders,
            'delivered': delivered
        }
    
    # Get returned orders for quick access
    returned_orders_count = Order.objects.filter(status='returned').count()
    unchecked_returns_count = Order.objects.filter(
        status='returned',
        workflow_status__in=['delivery_in_progress', 'delivery_completed']
    ).count()
    
    context = {
        'total_orders': total_orders,
        'completed_orders': completed_orders,
        'cancelled_orders': cancelled_orders,
        'pending_orders': pending_orders,
        'pending_confirmations_count': pending_confirmations_count,
        'orders_by_company': orders_by_company,
        'returned_orders_count': returned_orders_count,
        'unchecked_returns_count': unchecked_returns_count,
    }
    
    return render(request, 'delivery/manager/dashboard.html', context)

@login_required
@user_passes_test(is_delivery_manager)
def manager_all_orders(request):
    """All Orders with comprehensive filters - Only shows packaged, delivered and returned orders"""
    # Only show packaged, delivered and returned orders for Delivery Manager
    orders = Order.objects.select_related('seller', 'product', 'delivery__delivery_company').prefetch_related('items__product', 'delivery').filter(
        status__in=['packaged', 'delivered', 'returned']
    )
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    company_filter = request.GET.get('company', '')
    location_filter = request.GET.get('location', '')
    seller_filter = request.GET.get('seller', '')
    price_min = request.GET.get('price_min', '')
    price_max = request.GET.get('price_max', '')
    quantity_min = request.GET.get('quantity_min', '')
    quantity_max = request.GET.get('quantity_max', '')
    order_type_filter = request.GET.get('order_type', '')
    search_query = request.GET.get('search', '')
    
    # Apply filters
    if status_filter:
        # Only allow filtering by packaged, delivered or returned status
        if status_filter in ['packaged', 'delivered', 'returned']:
            orders = orders.filter(status=status_filter)
    
    if company_filter:
        orders = orders.filter(delivery__delivery_company_id=company_filter)
    
    if location_filter:
        orders = orders.filter(
            Q(city__icontains=location_filter) |
            Q(emirate__icontains=location_filter) |
            Q(delivery_area__icontains=location_filter)
        )
    
    if seller_filter:
        orders = orders.filter(seller_id=seller_filter)
    
    if price_min:
        try:
            orders = orders.filter(total_price__gte=Decimal(price_min))
        except:
            pass
    
    if price_max:
        try:
            orders = orders.filter(total_price__lte=Decimal(price_max))
        except:
            pass
    
    if quantity_min:
        try:
            orders = orders.filter(quantity__gte=int(quantity_min))
        except:
            pass
    
    if quantity_max:
        try:
            orders = orders.filter(quantity__lte=int(quantity_max))
        except:
            pass
    
    if order_type_filter:
        orders = orders.filter(workflow_status=order_type_filter)
    
    if search_query:
        orders = orders.filter(
            Q(order_code__icontains=search_query) |
            Q(customer__icontains=search_query) |
            Q(customer_phone__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(orders.order_by('-date'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    companies = DeliveryCompany.objects.filter(is_active=True)
    sellers = User.objects.filter(user_roles__role__name='Seller').distinct()
    # Only show packaged, delivered and returned statuses for Delivery Manager
    statuses = [choice for choice in Order.STATUS_CHOICES if choice[0] in ['packaged', 'delivered', 'returned']]
    workflow_statuses = Order.WORKFLOW_STATUS_CHOICES
    
    context = {
        'page_obj': page_obj,
        'companies': companies,
        'sellers': sellers,
        'statuses': statuses,
        'workflow_statuses': workflow_statuses,
        'filters': {
            'status': status_filter,
            'company': company_filter,
            'location': location_filter,
            'seller': seller_filter,
            'price_min': price_min,
            'price_max': price_max,
            'quantity_min': quantity_min,
            'quantity_max': quantity_max,
            'order_type': order_type_filter,
            'search': search_query,
        }
    }
    
    return render(request, 'delivery/manager/all_orders.html', context)

@login_required
@user_passes_test(is_delivery_manager)
def manager_shipping_companies(request):
    """Shipping Companies Management"""
    companies = DeliveryCompany.objects.all().order_by('name_en')
    
    # Calculate statistics for each company
    companies_data = []
    for company in companies:
        total_orders = Order.objects.filter(delivery__delivery_company=company).count()
        completed_orders = Order.objects.filter(
            delivery__delivery_company=company,
            status='delivered'
        ).count()
        
        companies_data.append({
            'company': company,
            'total_orders': total_orders,
            'completed_orders': completed_orders,
            'completion_rate': (completed_orders / total_orders * 100) if total_orders > 0 else 0
        })
    
    if request.method == 'POST':
        name_en = request.POST.get('name_en')
        name_ar = request.POST.get('name_ar')
        base_cost = request.POST.get('base_cost')
        is_active = request.POST.get('is_active') == 'on'
        
        if name_en and name_ar:
            DeliveryCompany.objects.create(
                name_en=name_en,
                name_ar=name_ar,
                base_cost=Decimal(base_cost) if base_cost else Decimal('10.00'),
                is_active=is_active
            )
            messages.success(request, 'Shipping company added successfully')
            return redirect('delivery:manager_shipping_companies')
    
    context = {
        'companies_data': companies_data,
    }
    
    return render(request, 'delivery/manager/shipping_companies.html', context)

@login_required
@user_passes_test(is_delivery_manager)
def manager_company_orders(request, company_id):
    """Filter orders by company"""
    company = get_object_or_404(DeliveryCompany, id=company_id)
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    search_query = request.GET.get('search', '')
    
    orders = Order.objects.filter(delivery__delivery_company=company)
    
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    if search_query:
        orders = orders.filter(
            Q(order_code__icontains=search_query) |
            Q(customer__icontains=search_query) |
            Q(customer_phone__icontains=search_query)
        )
    
    paginator = Paginator(orders.order_by('-date'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'company': company,
        'page_obj': page_obj,
        'status_filter': status_filter,
        'search_query': search_query,
    }
    
    return render(request, 'delivery/manager/company_orders.html', context)

@login_required
@user_passes_test(is_delivery_manager)
def manager_assign_orders(request):
    """Assign orders to shipping companies"""
    companies = DeliveryCompany.objects.filter(is_active=True)
    
    # Get unassigned orders ready for delivery
    # Include orders that are packaged and ready, or have completed packaging
    # More flexible: show orders that completed packaging or are ready, and don't have delivery assignment yet
    unassigned_orders = Order.objects.filter(
        Q(workflow_status='ready_for_delivery') | 
        Q(workflow_status='packaging_completed') |
        Q(workflow_status='packaging_in_progress')  # Include orders being packaged
    ).filter(
        delivery__isnull=True  # Not assigned to any delivery company
    ).exclude(
        status='cancelled'
    ).exclude(
        status='delivered'
    ).exclude(
        status='returned'
    ).select_related('seller', 'product').prefetch_related('items__product').order_by('-date')
    
    if request.method == 'POST':
        company_id = request.POST.get('company_id')
        order_ids = request.POST.getlist('order_ids')
        
        if company_id and order_ids:
            company = get_object_or_404(DeliveryCompany, id=company_id)
            
            with transaction.atomic():
                for order_id in order_ids:
                    try:
                        order = Order.objects.get(id=order_id)
                        
                        # Create or update delivery record
                        delivery_record, created = DeliveryRecord.objects.get_or_create(
                            order=order,
                            defaults={
                                'delivery_company': company,
                                'tracking_number': f'TRK-{order.id}-{timezone.now().strftime("%Y%m%d%H%M%S")}',
                                'status': 'assigned',
                                'delivery_cost': company.base_cost or Decimal('10.00'),
                            }
                        )
                        
                        if not created:
                            delivery_record.delivery_company = company
                            delivery_record.status = 'assigned'
                            delivery_record.save()
                        
                        # Update order workflow status
                        order.workflow_status = 'delivery_in_progress'
                        order.save()
                        
                    except Order.DoesNotExist:
                        continue
                
                messages.success(request, f'{len(order_ids)} orders assigned to {company.name_en}')
                return redirect('delivery:manager_assign_orders')
    
    # Debug: Count orders by workflow status
    all_ready_orders = Order.objects.filter(
        Q(workflow_status='ready_for_delivery') | 
        Q(workflow_status='packaging_completed') |
        Q(workflow_status='packaging_in_progress')
    ).exclude(status='cancelled').exclude(status='delivered').exclude(status='returned')
    
    orders_with_delivery = all_ready_orders.filter(delivery__isnull=False).count()
    orders_without_delivery = all_ready_orders.filter(delivery__isnull=True).count()
    
    context = {
        'companies': companies,
        'unassigned_orders': unassigned_orders,
        'total_ready_orders': all_ready_orders.count(),
        'orders_with_delivery': orders_with_delivery,
        'orders_without_delivery': orders_without_delivery,
    }
    
    return render(request, 'delivery/manager/assign_orders.html', context)

@login_required
@user_passes_test(is_delivery_manager)
def manager_update_orders(request):
    """Update order statuses - Only shows packaged, delivered and returned orders"""
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    company_filter = request.GET.get('company', '')
    search_query = request.GET.get('search', '')
    
    # Only show packaged, delivered and returned orders for Delivery Manager
    orders = Order.objects.select_related('seller', 'product', 'delivery__delivery_company').filter(
        status__in=['packaged', 'delivered', 'returned']
    )
    
    # Apply filters
    if status_filter:
        # Only allow filtering by packaged, delivered or returned status
        if status_filter in ['packaged', 'delivered', 'returned']:
            orders = orders.filter(status=status_filter)
    
    if company_filter:
        orders = orders.filter(delivery__delivery_company_id=company_filter)
    
    if search_query:
        orders = orders.filter(
            Q(order_code__icontains=search_query) |
            Q(customer__icontains=search_query) |
            Q(customer_phone__icontains=search_query)
        )
    
    # Handle POST requests
    if request.method == 'POST':
        # Single order update
        order_id = request.POST.get('order_id')
        new_status = request.POST.get('new_status')
        
        if order_id and new_status and not request.POST.get('batch_update'):
            try:
                # Only allow updating to packaged, delivered or returned
                if new_status not in ['packaged', 'delivered', 'returned']:
                    messages.error(request, 'You can only update orders to Packaged, Delivered or Returned status')
                    return redirect('delivery:manager_update_orders')
                
                order = Order.objects.get(id=order_id)
                old_status = order.status
                order.status = new_status
                
                # Update workflow status based on new status
                if new_status == 'delivered':
                    order.workflow_status = 'delivery_completed'
                elif new_status == 'packaged':
                    # Keep current workflow status or set appropriate one
                    if not order.workflow_status or order.workflow_status == 'ready_for_delivery':
                        pass  # Already in correct workflow
                elif new_status == 'returned':
                    # Set workflow status for returned orders
                    order.workflow_status = 'returned'
                
                order.save()
                
                messages.success(request, f'Order {order.order_code} status updated from {old_status} to {new_status}')
                return redirect('delivery:manager_update_orders')
                
            except Order.DoesNotExist:
                messages.error(request, 'Order not found')
        
        # Batch update
        if request.POST.get('batch_update'):
            order_ids = request.POST.getlist('selected_orders')
            new_status = request.POST.get('batch_status')
            
            if order_ids and new_status:
                # Only allow updating to packaged, delivered or returned
                if new_status not in ['packaged', 'delivered', 'returned']:
                    messages.error(request, 'You can only update orders to Packaged, Delivered or Returned status')
                    return redirect('delivery:manager_update_orders')
                
                updated_count = 0
                with transaction.atomic():
                    for order_id in order_ids:
                        try:
                            order = Order.objects.get(id=order_id)
                            order.status = new_status
                            if new_status == 'delivered':
                                order.workflow_status = 'delivery_completed'
                            elif new_status == 'packaged':
                                # Keep current workflow status or set appropriate one
                                if not order.workflow_status or order.workflow_status == 'ready_for_delivery':
                                    pass  # Already in correct workflow
                            elif new_status == 'returned':
                                # Set workflow status for returned orders
                                order.workflow_status = 'returned'
                            order.save()
                            updated_count += 1
                        except Order.DoesNotExist:
                            continue
                
                messages.success(request, f'{updated_count} orders updated successfully')
                return redirect('delivery:manager_update_orders')
    
    # Pagination
    paginator = Paginator(orders.order_by('-date'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    companies = DeliveryCompany.objects.filter(is_active=True)
    # Only show packaged, delivered and returned statuses for Delivery Manager
    statuses = [choice for choice in Order.STATUS_CHOICES if choice[0] in ['packaged', 'delivered', 'returned']]
    
    context = {
        'page_obj': page_obj,
        'companies': companies,
        'statuses': statuses,
        'filters': {
            'status': status_filter,
            'company': company_filter,
            'search': search_query,
        }
    }
    
    return render(request, 'delivery/manager/update_orders.html', context)

@login_required
@user_passes_test(is_delivery_manager)
def manager_process_returns(request):
    """Process returned/cancelled orders"""
    # Get filter parameters
    return_type = request.GET.get('type', 'all')  # all, unchecked, returned, cancelled
    search_query = request.GET.get('search', '')
    
    orders = Order.objects.all()
    
    # Filter by return type
    if return_type == 'unchecked':
        orders = orders.filter(
            status__in=['returned', 'cancelled'],
            workflow_status__in=['delivery_in_progress', 'delivery_completed']
        )
    elif return_type == 'returned':
        orders = orders.filter(status='returned')
    elif return_type == 'cancelled':
        orders = orders.filter(status='cancelled')
    else:
        orders = orders.filter(status__in=['returned', 'cancelled'])
    
    if search_query:
        orders = orders.filter(
            Q(order_code__icontains=search_query) |
            Q(customer__icontains=search_query) |
            Q(customer_phone__icontains=search_query)
        )
    
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        action = request.POST.get('action')  # 'return_to_original' or 're_process'
        
        if order_id and action:
            try:
                order = Order.objects.get(id=order_id)
                
                if action == 'return_to_original':
                    # Return order to its original state before delivery
                    order.status = 'packaged'
                    order.workflow_status = 'packaging_completed'
                    order.save()
                    messages.success(request, f'Order {order.order_code} returned to original state')
                    
                elif action == 're_process':
                    # Send back to packaging queue
                    order.status = 'processing'
                    order.workflow_status = 'packaging_in_progress'
                    order.save()
                    messages.success(request, f'Order {order.order_code} sent for reprocessing')
                
                return redirect('delivery:manager_process_returns')
                
            except Order.DoesNotExist:
                messages.error(request, 'Order not found')
    
    # Pagination
    paginator = Paginator(orders.order_by('-date'), 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Count statistics
    unchecked_count = Order.objects.filter(
        status__in=['returned', 'cancelled'],
        workflow_status__in=['delivery_in_progress', 'delivery_completed']
    ).count()
    returned_count = Order.objects.filter(status='returned').count()
    cancelled_count = Order.objects.filter(status='cancelled').count()
    
    # Get all orders for dropdown (limited to 100 for performance)
    all_return_orders = orders[:100]
    
    context = {
        'page_obj': page_obj,
        'return_type': return_type,
        'search_query': search_query,
        'unchecked_count': unchecked_count,
        'returned_count': returned_count,
        'cancelled_count': cancelled_count,
        'all_return_orders': all_return_orders,
    }
    
    return render(request, 'delivery/manager/process_returns.html', context)

@login_required
@user_passes_test(is_delivery_manager)
def manager_pending_confirmations(request):
    """List deliveries pending manager confirmation"""
    # Get filter parameters
    search_query = request.GET.get('search', '')
    agent_filter = request.GET.get('agent', '')
    date_filter = request.GET.get('date', '')
    
    # Get deliveries pending confirmation
    deliveries = DeliveryRecord.objects.filter(
        status='delivered',
        manager_confirmation_status='pending'
    ).select_related('order', 'courier', 'courier__user', 'delivery_company').order_by('-delivered_at')
    
    # Apply filters
    if search_query:
        deliveries = deliveries.filter(
            Q(order__order_code__icontains=search_query) |
            Q(order__customer__icontains=search_query) |
            Q(order__customer_phone__icontains=search_query) |
            Q(tracking_number__icontains=search_query)
        )
    
    if agent_filter:
        deliveries = deliveries.filter(courier__user_id=agent_filter)
    
    if date_filter:
        today = timezone.now().date()
        if date_filter == 'today':
            deliveries = deliveries.filter(delivered_at__date=today)
        elif date_filter == 'week':
            week_ago = today - timedelta(days=7)
            deliveries = deliveries.filter(delivered_at__date__gte=week_ago)
        elif date_filter == 'month':
            month_ago = today - timedelta(days=30)
            deliveries = deliveries.filter(delivered_at__date__gte=month_ago)
    
    # Pagination
    paginator = Paginator(deliveries, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get delivery agents for filter
    delivery_agents = User.objects.filter(
        user_roles__role__name='Delivery Agent'
    ).distinct()
    
    # Statistics
    total_pending = DeliveryRecord.objects.filter(
        status='delivered',
        manager_confirmation_status='pending'
    ).count()
    
    context = {
        'page_obj': page_obj,
        'deliveries': page_obj,
        'delivery_agents': delivery_agents,
        'total_pending': total_pending,
        'filters': {
            'search': search_query,
            'agent': agent_filter,
            'date': date_filter,
        }
    }
    
    return render(request, 'delivery/manager/pending_confirmations.html', context)

@login_required
@user_passes_test(is_delivery_manager)
def manager_confirm_delivery(request, delivery_id):
    """Confirm or reject a delivery"""
    delivery = get_object_or_404(
        DeliveryRecord.objects.select_related('order', 'courier', 'courier__user'),
        id=delivery_id
    )
    
    # Check if delivery is pending confirmation
    if delivery.manager_confirmation_status != 'pending':
        messages.error(request, 'This delivery is not pending confirmation.')
        return redirect('delivery:manager_pending_confirmations')
    
    if request.method == 'POST':
        action = request.POST.get('action')  # 'confirm' or 'reject'
        rejection_reason = request.POST.get('rejection_reason', '')
        
        try:
            with transaction.atomic():
                if action == 'confirm':
                    # Confirm the delivery
                    delivery.manager_confirmation_status = 'confirmed'
                    delivery.manager_confirmed_at = timezone.now()
                    delivery.manager_confirmed_by = request.user
                    delivery.save()
                    
                    # Update order status
                    order = delivery.order
                    order.status = 'delivered'
                    order.workflow_status = 'delivery_completed'
                    order.save()
                    
                    # Update courier statistics
                    if delivery.courier:
                        delivery.courier.total_deliveries += 1
                        delivery.courier.successful_deliveries += 1
                        delivery.courier.save()
                    
                    # Create notification for accountant
                    try:
                        from notifications.models import Notification
                        Notification.objects.create(
                            recipient_type='role',
                            recipient_role='Accountant',
                            title=f'Order {order.order_code} Delivered',
                            message=f'Order {order.order_code} has been confirmed as delivered and is ready for final accounting.',
                            notification_type='order_delivered',
                            related_object_id=order.id,
                            related_object_type='order'
                        )
                    except Exception as e:
                        print(f"Error creating notification: {e}")
                    
                    messages.success(request, f'Delivery confirmed for order {order.order_code}')
                    
                elif action == 'reject':
                    # Reject the delivery
                    if not rejection_reason:
                        messages.error(request, 'Please provide a reason for rejection.')
                        return redirect('delivery:manager_confirm_delivery', delivery_id=delivery_id)
                    
                    delivery.manager_confirmation_status = 'rejected'
                    delivery.manager_confirmed_at = timezone.now()
                    delivery.manager_confirmed_by = request.user
                    delivery.manager_rejection_reason = rejection_reason
                    delivery.save()
                    
                    # Revert order status back to delivery in progress
                    order = delivery.order
                    order.status = 'shipped'
                    order.workflow_status = 'delivery_in_progress'
                    order.save()
                    
                    # Revert delivery status
                    delivery.status = 'out_for_delivery'
                    delivery.save()
                    
                    # Create status history
                    DeliveryStatusHistory.objects.create(
                        delivery=delivery,
                        status='out_for_delivery',
                        changed_by=request.user,
                        notes=f'Delivery rejected by manager: {rejection_reason}'
                    )
                    
                    # Notify the delivery agent
                    if delivery.courier:
                        try:
                            from notifications.models import Notification
                            Notification.objects.create(
                                recipient=delivery.courier.user,
                                title=f'Delivery Rejected - {order.order_code}',
                                message=f'Your delivery for order {order.order_code} was rejected. Reason: {rejection_reason}',
                                notification_type='delivery_rejected',
                                related_object_id=order.id,
                                related_object_type='order'
                            )
                        except Exception as e:
                            print(f"Error creating notification: {e}")
                    
                    messages.success(request, f'Delivery rejected for order {order.order_code}')
                
                return redirect('delivery:manager_pending_confirmations')
                
        except Exception as e:
            messages.error(request, f'Error processing confirmation: {str(e)}')
    
    context = {
        'delivery': delivery,
        'order': delivery.order,
    }
    
    return render(request, 'delivery/manager/confirm_delivery.html', context)

@login_required
@user_passes_test(is_delivery_manager)
def manager_returned_orders(request):
    """Dedicated page for returned orders management"""
    # Get filter parameters
    search_query = request.GET.get('search', '')
    date_filter = request.GET.get('date', '')
    agent_filter = request.GET.get('agent', '')
    company_filter = request.GET.get('company', '')
    status_filter = request.GET.get('status', 'returned')  # Default to returned
    
    # Get returned orders
    orders = Order.objects.filter(status='returned').select_related(
        'seller', 'product', 'delivery__delivery_company', 'delivery__courier__user'
    ).prefetch_related('items__product', 'delivery').order_by('-date')
    
    # Apply filters
    if search_query:
        orders = orders.filter(
            Q(order_code__icontains=search_query) |
            Q(customer__icontains=search_query) |
            Q(customer_phone__icontains=search_query)
        )
    
    if date_filter:
        today = timezone.now().date()
        if date_filter == 'today':
            orders = orders.filter(date__date=today)
        elif date_filter == 'week':
            week_ago = today - timedelta(days=7)
            orders = orders.filter(date__date__gte=week_ago)
        elif date_filter == 'month':
            month_ago = today - timedelta(days=30)
            orders = orders.filter(date__date__gte=month_ago)
        elif date_filter == 'year':
            year_ago = today - timedelta(days=365)
            orders = orders.filter(date__date__gte=year_ago)
    
    if agent_filter:
        orders = orders.filter(delivery__courier__user_id=agent_filter)
    
    if company_filter:
        orders = orders.filter(delivery__delivery_company_id=company_filter)
    
    # Pagination
    paginator = Paginator(orders, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Statistics
    total_returned = Order.objects.filter(status='returned').count()
    returned_today = Order.objects.filter(
        status='returned',
        date__date=timezone.now().date()
    ).count()
    returned_this_week = Order.objects.filter(
        status='returned',
        date__date__gte=timezone.now().date() - timedelta(days=7)
    ).count()
    returned_this_month = Order.objects.filter(
        status='returned',
        date__date__gte=timezone.now().date() - timedelta(days=30)
    ).count()
    
    # Get delivery agents for filter
    delivery_agents = User.objects.filter(
        user_roles__role__name='Delivery Agent'
    ).distinct()
    
    # Get delivery companies for filter
    companies = DeliveryCompany.objects.filter(is_active=True)
    
    # Handle POST requests for actions
    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        action = request.POST.get('action')
        
        if order_id and action:
            try:
                order = Order.objects.get(id=order_id)
                
                if action == 'reprocess':
                    # Send back to packaging queue
                    order.status = 'processing'
                    order.workflow_status = 'packaging_in_progress'
                    order.save()
                    messages.success(request, f'Order {order.order_code} has been sent for reprocessing')
                    
                elif action == 'return_to_packaging':
                    # Return to packaging completed
                    order.status = 'packaged'
                    order.workflow_status = 'packaging_completed'
                    order.save()
                    messages.success(request, f'Order {order.order_code} has been returned to packaging status')
                    
                elif action == 'cancel':
                    # Cancel the order
                    order.status = 'cancelled'
                    order.workflow_status = 'cancelled'
                    order.save()
                    messages.success(request, f'Order {order.order_code} has been cancelled')
                    
                return redirect('delivery:manager_returned_orders')
                
            except Order.DoesNotExist:
                messages.error(request, 'Order not found')
    
    context = {
        'page_obj': page_obj,
        'orders': page_obj,
        'total_returned': total_returned,
        'returned_today': returned_today,
        'returned_this_week': returned_this_week,
        'returned_this_month': returned_this_month,
        'delivery_agents': delivery_agents,
        'companies': companies,
        'filters': {
            'search': search_query,
            'date': date_filter,
            'agent': agent_filter,
            'company': company_filter,
            'status': status_filter,
        }
    }
    
    return render(request, 'delivery/manager/returned_orders.html', context)


# ============================================
# Couriers Management Views
# ============================================

@login_required
def couriers_list(request):
    """List all delivery couriers"""
    couriers = Courier.objects.select_related(
        'user', 'delivery_company'
    ).annotate(
        order_count=Count('deliveries'),
        completed_count=Count('deliveries', filter=Q(deliveries__status='delivered')),
        pending_count=Count('deliveries', filter=Q(deliveries__status__in=['assigned', 'picked_up', 'out_for_delivery'])),
    ).order_by('-status', 'user__first_name')

    # Filter by status
    status = request.GET.get('status', '')
    if status:
        couriers = couriers.filter(status=status)

    # Filter by company
    company_id = request.GET.get('company', '')
    if company_id:
        couriers = couriers.filter(delivery_company_id=company_id)

    # Filter by availability
    availability = request.GET.get('availability', '')
    if availability:
        couriers = couriers.filter(availability=availability)

    # Statistics
    stats = {
        'total_couriers': Courier.objects.count(),
        'active_couriers': Courier.objects.filter(status='active').count(),
        'available_couriers': Courier.objects.filter(status='active', availability='available').count(),
        'on_delivery': Courier.objects.filter(availability='on_delivery').count(),
    }

    # Get companies for filter
    companies = DeliveryCompany.objects.filter(is_active=True)

    return render(request, 'delivery/couriers_list.html', {
        'couriers': couriers,
        'stats': stats,
        'companies': companies,
        'current_status': status,
        'current_company': company_id,
        'current_availability': availability,
    })


@login_required
def courier_detail(request, courier_id):
    """View courier details"""
    courier = get_object_or_404(
        Courier.objects.select_related('user', 'delivery_company'),
        id=courier_id
    )

    # Get recent deliveries
    recent_deliveries = DeliveryRecord.objects.filter(
        courier=courier
    ).select_related('order').order_by('-assigned_at')[:20]

    # Get delivery statistics
    total_deliveries = DeliveryRecord.objects.filter(courier=courier).count()
    completed_deliveries = DeliveryRecord.objects.filter(courier=courier, status='delivered').count()
    failed_deliveries = DeliveryRecord.objects.filter(courier=courier, status='failed').count()

    success_rate = (completed_deliveries / total_deliveries * 100) if total_deliveries > 0 else 0

    return render(request, 'delivery/courier_detail.html', {
        'courier': courier,
        'recent_deliveries': recent_deliveries,
        'total_deliveries': total_deliveries,
        'completed_deliveries': completed_deliveries,
        'failed_deliveries': failed_deliveries,
        'success_rate': success_rate,
    })


@login_required
def edit_courier(request, courier_id):
    """Edit courier details"""
    courier = get_object_or_404(Courier, id=courier_id)

    if request.method == 'POST':
        # Update courier details
        courier.phone_number = request.POST.get('phone_number', courier.phone_number)
        courier.status = request.POST.get('status', courier.status)
        courier.availability = request.POST.get('availability', courier.availability)
        courier.vehicle_type = request.POST.get('vehicle_type', courier.vehicle_type)
        courier.license_number = request.POST.get('license_number', courier.license_number)

        company_id = request.POST.get('delivery_company')
        if company_id:
            try:
                courier.delivery_company = DeliveryCompany.objects.get(id=company_id)
            except DeliveryCompany.DoesNotExist:
                pass

        courier.save()
        messages.success(request, f'Courier {courier.user.get_full_name()} updated successfully')
        return redirect('delivery:courier_detail', courier_id=courier.id)

    companies = DeliveryCompany.objects.filter(is_active=True)

    return render(request, 'delivery/edit_courier.html', {
        'courier': courier,
        'companies': companies,
    })


@login_required
def courier_performance(request, courier_id):
    """View courier performance metrics"""
    courier = get_object_or_404(Courier.objects.select_related('user'), id=courier_id)

    # Date range
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)

    # Get deliveries in date range
    deliveries = DeliveryRecord.objects.filter(
        courier=courier,
        assigned_at__gte=start_date
    )

    # Performance metrics
    total_deliveries = deliveries.count()
    completed = deliveries.filter(status='delivered').count()
    failed = deliveries.filter(status='failed').count()
    pending = deliveries.filter(status__in=['assigned', 'picked_up', 'out_for_delivery']).count()

    success_rate = (completed / total_deliveries * 100) if total_deliveries > 0 else 0

    # Average delivery time
    completed_deliveries = deliveries.filter(
        status='delivered',
        delivered_at__isnull=False,
        assigned_at__isnull=False
    )

    avg_delivery_time = None
    if completed_deliveries.exists():
        total_time = sum(
            (d.delivered_at - d.assigned_at).total_seconds()
            for d in completed_deliveries
            if d.delivered_at and d.assigned_at
        )
        if completed_deliveries.count() > 0:
            avg_delivery_time = total_time / completed_deliveries.count() / 3600  # Convert to hours

    # Daily breakdown
    from django.db.models.functions import TruncDate
    daily_stats = deliveries.annotate(
        date=TruncDate('assigned_at')
    ).values('date').annotate(
        count=Count('id'),
        delivered=Count('id', filter=Q(status='delivered'))
    ).order_by('-date')[:30]

    return render(request, 'delivery/courier_performance.html', {
        'courier': courier,
        'days': days,
        'total_deliveries': total_deliveries,
        'completed': completed,
        'failed': failed,
        'pending': pending,
        'success_rate': success_rate,
        'avg_delivery_time': avg_delivery_time,
        'daily_stats': daily_stats,
    })
