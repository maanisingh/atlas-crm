from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from django.db.models import Count, Sum, Avg, Q
from django.http import JsonResponse
from django.core.paginator import Paginator, PageNotAnInteger, EmptyPage
from django.views.decorators.http import require_POST
from .models import (
    CallLog, AgentPerformance, AgentSession, CustomerInteraction,
    OrderStatusHistory, OrderAssignment, ManagerNote, TeamPerformance
)
from .services import OrderDistributionService, AutoOrderDistributionService
from orders.models import Order, StatusLog
from users.models import User
from inventory.models import Stock
from datetime import datetime, timedelta
import json

@login_required
@require_POST
def distribute_orders(request):
    """Distribute orders to agents."""
    try:
        # Auto distribute orders
        service = AutoOrderDistributionService()
        result = service.distribute_orders()
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully distributed {result["distributed_count"]} orders',
            'distributed_count': result['distributed_count']
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error distributing orders: {str(e)}'
        }, status=500)

def is_call_center_agent(user):
    """Check if user is a call center agent."""
    return user.has_role('Call Center Agent') or user.is_superuser

def is_call_center_manager(user):
    """Check if user is a call center manager."""
    return user.has_role('Call Center Manager') or user.is_superuser

def has_callcenter_role(user):
    
    return (
        user.is_superuser or
        user.has_role('Super Admin') or
        user.has_role('Admin') or
        user.has_role('Call Center Manager') or
        user.has_role('Call Center Agent')
    )

# Agent Panel Views

@login_required
def agent_dashboard(request):
    """Call center agent dashboard."""
    if not has_callcenter_role(request.user):
        messages.error(request, "ليس لديك صلاحية للدخول لهذه الصفحة.")
        return redirect('dashboard:index')
    today = timezone.now().date()
    
    # Get or create agent session
    session, created = AgentSession.objects.get_or_create(
        agent=request.user,
        defaults={'status': 'available'}
    )
    
    # Update session status if needed
    if request.POST.get('status'):
        session.status = request.POST.get('status')
        session.save()
    
    # Get today's performance
    performance, created = AgentPerformance.objects.get_or_create(
        agent=request.user, 
        date=today,
        defaults={
            'total_calls_made': 0,
            'successful_calls': 0,
            'orders_confirmed': 0,
            'orders_cancelled': 0,
            'orders_postponed': 0,
            'total_orders_handled': 0,
        }
    )
    
    # Get assigned orders using a more reliable approach
    # First get all assignment order IDs
    assignment_order_ids = list(OrderAssignment.objects.filter(
        agent=request.user
    ).values_list('order_id', flat=True))
    
    # Then get all direct agent order IDs
    direct_order_ids = list(Order.objects.filter(
        agent=request.user
    ).values_list('id', flat=True))
    
    # Combine the IDs and remove duplicates
    all_order_ids = list(set(assignment_order_ids + direct_order_ids))
    
    # Get the actual orders using the IDs
    assigned_orders = Order.objects.filter(
        id__in=all_order_ids
    ).exclude(
        status__in=['confirmed', 'packaged', 'shipped', 'delivered']
    ).exclude(
        escalated_to_manager=True
    ).select_related(
        'product', 'seller', 'agent'
    ).prefetch_related(
        'assignments', 'items', 'items__product'
    )
    
    print(f"=== AGENT DASHBOARD DEBUG ===")
    print(f"User: {request.user}")
    print(f"User ID: {request.user.id}")
    print(f"Total assigned orders: {assigned_orders.count()}")
    print(f"Assigned orders: {list(assigned_orders.values_list('id', flat=True))}")
    print(f"Assignment order IDs: {assignment_order_ids}")
    print(f"Direct order IDs: {direct_order_ids}")
    print(f"All order IDs: {all_order_ids}")
    print("==============================")
    
    # Auto-assign orders if agent has capacity (less than 15 orders)
    if assigned_orders.count() < 15:
        print(f"Agent has {assigned_orders.count()} orders, attempting auto-assignment...")
        # Get unassigned orders that match agent's capabilities
        unassigned_orders = Order.objects.filter(
            status__in=['pending', 'processing', 'pending_confirmation'],
            assignments__isnull=True,
            agent__isnull=True  # Also check that Order.agent is not set
        ).order_by('date')[:10]  # Take up to 10 orders
        
        print(f"Found {unassigned_orders.count()} unassigned orders")
        
        for order in unassigned_orders:
            # Check if order is already assigned (both ways)
            if not (OrderAssignment.objects.filter(order=order).exists() or order.agent):
                # Auto-assign order to this agent
                OrderAssignment.objects.create(
                    order=order,
                    manager=request.user,  # Self-assignment
                    agent=request.user,
                    priority_level='medium',
                    manager_notes='تم التعيين تلقائياً بواسطة النظام',
                    assignment_reason='تعيين تلقائي بناءً على قدرة الموظف'
                )
                
                # Also update Order.agent field
                order.agent = request.user
                order.assigned_at = timezone.now()
                order.save()
                
                print(f"Auto-assigned order {order.order_code} to {request.user.username}")
        
        # Re-fetch assigned orders after auto-assignment
        assignment_order_ids = list(OrderAssignment.objects.filter(agent=request.user).values_list('order_id', flat=True))
        direct_order_ids = list(Order.objects.filter(agent=request.user).values_list('id', flat=True))
        all_order_ids = list(set(assignment_order_ids + direct_order_ids))
        
        assigned_orders = Order.objects.filter(
            id__in=all_order_ids
        ).exclude(
            status__in=['confirmed', 'packaged', 'shipped', 'delivered']
        ).exclude(
            escalated_to_manager=True
        ).select_related(
            'product', 'seller', 'agent'
        ).prefetch_related(
            'assignments', 'items', 'items__product'
        )
        
        print(f"Updated assigned orders count: {assigned_orders.count()}")
    
    # Get recent calls
    recent_calls = CallLog.objects.filter(
        agent=request.user,
        call_time__date=today
    ).order_by('-call_time')[:10]
    
    # Get pending orders that need follow-up
    pending_orders = Order.objects.filter(
        status__in=['pending', 'pending_confirmation'],
        assignments__agent=request.user
    ).distinct()[:5]
    
    # Calculate metrics from actual orders, not call logs
    total_calls_today = CallLog.objects.filter(
        agent=request.user,
        call_time__date=today
    ).count()
    
    # Get orders assigned to this agent today
    today_orders = Order.objects.filter(
        assignments__agent=request.user,
        assignments__assignment_date__date=today
    ).distinct()
    
    confirmed_orders = today_orders.filter(status='confirmed').count()
    postponed_orders = today_orders.filter(status='pending').count()  # pending orders are considered postponed
    cancelled_orders = today_orders.filter(status='cancelled').count()
    
    failed_calls = CallLog.objects.filter(
        agent=request.user,
        call_time__date=today,
        status__in=['no_answer', 'busy', 'wrong_number']
    ).count()
    
    # Calculate average call duration
    call_durations = CallLog.objects.filter(
        agent=request.user,
        call_time__date=today
    ).aggregate(avg_duration=Avg('duration'))['avg_duration'] or 0
    
    avg_duration_minutes = round(call_durations / 60, 1) if call_durations > 0 else 0
    
    # Debug: Print calculated values
    print(f"=== CALCULATED VALUES DEBUG ===")
    print(f"Confirmed orders count: {confirmed_orders}")
    print(f"Postponed orders count: {postponed_orders}")
    print(f"Cancelled orders count: {cancelled_orders}")
    print(f"Total calls today: {total_calls_today}")
    print("==============================")
    
    # Alerts & Notifications - Only show relevant alerts for agents
    # 1. High Priority: Orders pending >2 hours (only for agent's assigned orders)
    two_hours_ago = timezone.now() - timedelta(hours=2)
    high_priority_count = Order.objects.filter(
        status__in=['pending', 'pending_confirmation'],
        assignments__agent=request.user,
        date__lt=two_hours_ago
    ).count()

    # 2. Agent Overload: Only show if this agent is overloaded
    agent_overload = None
    if assigned_orders.count() > 25:  # If agent has more than 25 orders
        agent_overload = {
            'name': request.user.get_full_name(),
            'order_count': assigned_orders.count()
        }

    # 3. Low Stock Alert: Only for products in agent's assigned orders
    low_stock_alert = None
    agent_product_ids = assigned_orders.values_list('product_id', flat=True)
    if agent_product_ids:
        low_stock = (
            Stock.objects.filter(product_id__in=agent_product_ids)
            .annotate(total=Sum('product__inventoryrecord__quantity'))
            .filter(total__lt=5)
            .order_by('total')
            .first()
        )
        if low_stock:
            low_stock_alert = {
                'product': low_stock.product.name_en,
                'units': low_stock.total or 0
            }

    context = {
        'session': session,
        'performance': performance,
        'assigned_orders': assigned_orders,
        'recent_calls': recent_calls,
        'pending_orders': pending_orders,
        'total_calls_today': total_calls_today,
        'confirmed_orders': confirmed_orders,
        'postponed_orders': postponed_orders,
        'cancelled_orders': cancelled_orders,
        'failed_calls': failed_calls,
        'avg_duration_minutes': avg_duration_minutes,
        'today': today,
        'high_priority_count': high_priority_count,
        'agent_overload': agent_overload,
        'low_stock_alert': low_stock_alert,
    }
    
    return render(request, 'callcenter/agent/dashboard.html', context)

@login_required
def agent_order_list(request):
    """Agent's assigned orders list - DEBUG VERSION."""
    if not has_callcenter_role(request.user):
        messages.error(request, "ليس لديك صلاحية للدخول لهذه الصفحة.")
        return redirect('dashboard:index')
    
    # فحص إجمالي الطلبات في النظام
    total_orders = Order.objects.count()
    
    # فحص الطلبات غير المعينة
    unassigned_orders = Order.objects.filter(
        status__in=['pending', 'processing', 'pending_confirmation'],
        agent__isnull=True,
        assignments__isnull=True
    )
    
    # STEP 1: Get all orders assigned to this agent through OrderAssignment
    assignment_orders = OrderAssignment.objects.filter(agent=request.user)
    assignment_order_list = list(assignment_orders.values_list('order_id', flat=True))
    
    # STEP 2: Get all orders where this user is the direct agent
    direct_orders = Order.objects.filter(agent=request.user)
    direct_order_list = list(direct_orders.values_list('id', flat=True))
    
    # STEP 3: Combine both lists and remove duplicates
    all_order_ids = list(set(assignment_order_list + direct_order_list))
    
    # STEP 4: Auto-assign orders if agent has capacity (less than 15 orders)
    if len(all_order_ids) < 15:
        # Get unassigned orders
        unassigned_orders = Order.objects.filter(
            status__in=['pending', 'processing', 'pending_confirmation'],
            agent__isnull=True,
            assignments__isnull=True
        ).order_by('date')[:10]  # Take up to 10 orders
        
        for order in unassigned_orders:
            # Create OrderAssignment
            OrderAssignment.objects.create(
                order=order,
                manager=request.user,  # Self-assignment
                agent=request.user,
                priority_level='medium',
                manager_notes='تم التعيين تلقائياً بواسطة النظام',
                assignment_reason='تعيين تلقائي للطلبات غير المعينة'
            )
            
            # Update Order.agent
            order.agent = request.user
            order.assigned_at = timezone.now()
            order.save()
            
            all_order_ids.append(order.id)
            print(f"Auto-assigned order {order.order_code}")
        
        # Re-fetch the updated order IDs
        assignment_order_list = list(OrderAssignment.objects.filter(agent=request.user).values_list('order_id', flat=True))
        direct_order_list = list(Order.objects.filter(agent=request.user).values_list('id', flat=True))
        all_order_ids = list(set(assignment_order_list + direct_order_list))
    # STEP 5: Get the actual Order objects
    if all_order_ids:
        orders_queryset = Order.objects.filter(id__in=all_order_ids).exclude(
            status__in=['confirmed', 'packaged', 'shipped', 'delivered']
        ).exclude(
            escalated_to_manager=True
        ).order_by('-date')
    else:
        orders_queryset = Order.objects.none()
    
    # STEP 5: Apply filters
    status_filter = request.GET.get('status', '')
    priority_filter = request.GET.get('priority', '')
    search_filter = request.GET.get('search', '')
    
    filtered_orders = orders_queryset
    
    if status_filter:
        filtered_orders = filtered_orders.filter(status=status_filter)
        print(f"After status filter '{status_filter}': {filtered_orders.count()}")
    
    if priority_filter:
        # For priority, we need to check the assignments
        priority_order_ids = list(OrderAssignment.objects.filter(
            agent=request.user,
            priority_level=priority_filter
        ).values_list('order_id', flat=True))
        filtered_orders = filtered_orders.filter(id__in=priority_order_ids)
        print(f"After priority filter '{priority_filter}': {filtered_orders.count()}")
    
    if search_filter:
        filtered_orders = filtered_orders.filter(
            Q(order_code__icontains=search_filter) |
            Q(customer__icontains=search_filter) |
            Q(customer_phone__icontains=search_filter)
        )
        print(f"After search filter '{search_filter}': {filtered_orders.count()}")
    
    # STEP 6: Pagination
    paginator = Paginator(filtered_orders, 15)
    page_number = request.GET.get('page', 1)
    
    try:
        page_obj = paginator.get_page(page_number)
    except (PageNotAnInteger, EmptyPage):
        page_obj = paginator.get_page(1)
    
    print(f"Pagination - Page {page_number}, Items: {len(page_obj)}, Total: {paginator.count}")
    
    # STEP 7: Calculate statistics
    total_assigned = orders_queryset.count()
    pending_orders = orders_queryset.filter(status__in=['pending', 'pending_confirmation']).count()
    confirmed_orders = orders_queryset.filter(status='confirmed').count()
    cancelled_orders = orders_queryset.filter(status='cancelled').count()
    
    # STEP 8: Get order assignments for display
    order_assignments = {}
    for order in page_obj:
        assignment = OrderAssignment.objects.filter(order=order, agent=request.user).first()
        if assignment:
            order_assignments[order.id] = assignment
    
    # STEP 9: Debug information
    debug_info = {
        'total_orders_in_db': Order.objects.count(),
        'assignment_order_ids': assignment_order_list,
        'direct_order_ids': direct_order_list,
        'combined_order_ids': all_order_ids,
        'total_assigned_orders': total_assigned,
        'filtered_orders_count': filtered_orders.count(),
        'page_obj_count': len(page_obj),
        'user_id': request.user.id,
        'user_roles': list(request.user.user_roles.values_list('role__name', flat=True)),
    }
    
    
    context = {
        'page_obj': page_obj,
        'order_assignments': order_assignments,
        'status_filter': status_filter,
        'priority_filter': priority_filter,
        'search_query': search_filter,
        'total_assigned': total_assigned,
        'pending_orders': pending_orders,
        'confirmed_orders': confirmed_orders,
        'cancelled_orders': cancelled_orders,
        'debug_info': debug_info,
    }
    
    return render(request, 'callcenter/agent/order_list.html', context)

@login_required
def agent_order_detail(request, order_id):
    """Agent's order detail view."""
    if not has_callcenter_role(request.user):
        messages.error(request, "ليس لديك صلاحية للدخول لهذه الصفحة.")
        return redirect('dashboard:index')
    order = get_object_or_404(Order, id=order_id)
    
    # Check if user has access to this order
    if not (order.assignments.filter(agent=request.user).exists() or order.agent == request.user):
        messages.error(request, "You don't have permission to view this order.")
        return redirect('callcenter:agent_order_list')
    
    # Get call logs for this order
    call_logs = CallLog.objects.filter(order=order, agent=request.user).order_by('-call_time')
    
    # Get manager notes
    manager_notes = ManagerNote.objects.filter(order=order, agent=request.user).order_by('-created_at')
    
    # Get status history
    status_history = OrderStatusHistory.objects.filter(order=order).order_by('-change_timestamp')
    
    context = {
        'order': order,
        'call_logs': call_logs,
        'manager_notes': manager_notes,
        'status_history': status_history,
    }
    
    return render(request, 'callcenter/agent/order_detail.html', context)

@login_required
def agent_log_call(request, order_id):
    """Log a call for an order."""
    if not has_callcenter_role(request.user):
        messages.error(request, "ليس لديك صلاحية للدخول لهذه الصفحة.")
        return redirect('dashboard:index')
    
    order = get_object_or_404(Order, id=order_id)
    
    # Check if user has access to this order
    if not (order.assignments.filter(agent=request.user).exists() or order.agent == request.user):
        messages.error(request, "You don't have permission to view this order.")
        return redirect('callcenter:agent_order_list')
    
    if request.method == 'POST':
        duration = request.POST.get('duration', 0)
        status = request.POST.get('status', 'completed')
        notes = request.POST.get('notes', '')
        customer_satisfaction = request.POST.get('customer_satisfaction')
        
        call_log = CallLog.objects.create(
            order=order,
            agent=request.user,
            duration=duration,
            status=status,
            notes=notes,
            customer_satisfaction=customer_satisfaction if customer_satisfaction else None
        )
        
        messages.success(request, 'Call logged successfully.')
        return redirect('callcenter:agent_order_detail', order_id=order_id)
    
    return render(request, 'callcenter/agent/log_call.html', {'order': order})


# Manager Panel Views

@login_required
def manager_dashboard(request):
    """Call center manager dashboard with comprehensive analytics."""
    if not has_callcenter_role(request.user):
        messages.error(request, "ليس لديك صلاحية للدخول لهذه الصفحة.")
        return redirect('dashboard:index')
    
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    # Enhanced overall statistics
    total_orders = Order.objects.count()
    orders_today = Order.objects.filter(date__date=today).count()
    orders_confirmed = Order.objects.filter(status='confirmed').count()
    orders_cancelled = Order.objects.filter(status='cancelled').count()
    orders_pending = Order.objects.filter(status__in=['pending', 'pending_confirmation']).count()
    orders_processed = Order.objects.filter(date__date=today).count()
    
    # NEW: Orders awaiting Call Center approval
    orders_awaiting_approval = Order.objects.filter(
        workflow_status='callcenter_review'
    ).order_by('date')[:10]
    
    # NEW: Recently approved orders (today)
    recently_approved = Order.objects.filter(
        workflow_status='callcenter_approved',
        updated_at__date=today
    ).order_by('-updated_at')[:10]
    
    # NEW: Pending approval count
    pending_approval = Order.objects.filter(workflow_status='callcenter_review').count()
    
    # NEW: Approved today count
    approved_today = Order.objects.filter(
        workflow_status='callcenter_approved',
        updated_at__date=today
    ).count()
    
    # Calculate rates
    confirmation_rate = (orders_confirmed / total_orders * 100) if total_orders > 0 else 0
    cancellation_rate = (orders_cancelled / total_orders * 100) if total_orders > 0 else 0
    
    # NEW: Approval rate calculation
    approval_rate = (approved_today / (pending_approval + approved_today) * 100) if (pending_approval + approved_today) > 0 else 0
    
    # Get active agents and their status
    active_agents = AgentSession.objects.filter(status='available').count()
    total_agents = User.objects.filter(user_roles__role__name__in=['Call Center Agent']).count()
    
    # Get today's performance metrics
    today_performance = AgentPerformance.objects.filter(date=today)
    total_calls_handled = today_performance.aggregate(total=Sum('total_calls_made'))['total'] or 0
    avg_satisfaction = float(today_performance.aggregate(avg=Avg('customer_satisfaction_avg'))['avg'] or 0)
    avg_response_time = float(today_performance.aggregate(avg=Avg('average_call_duration'))['avg'] or 0)
    
    # Get recent assignments
    recent_assignments = OrderAssignment.objects.select_related('order', 'agent').order_by('-assignment_date')[:10]
    
    # Get pending orders that need attention
    pending_orders = Order.objects.filter(
        status__in=['pending', 'pending_confirmation']
    ).order_by('date')[:10]
    
    # Get high priority unassigned orders
    high_priority_unassigned = Order.objects.filter(
        status__in=['pending', 'pending_confirmation'],
        assignments__isnull=True
    ).order_by('-date')[:5]
    
    # Get all orders with assigned agents for the orders list
    orders_with_agents = Order.objects.select_related('agent', 'seller', 'product').filter(
        agent__isnull=False
    ).order_by('-date')[:20]
    
    # Get unassigned orders for distribution
    unassigned_orders = Order.objects.filter(
        agent__isnull=True,
        status__in=['pending', 'processing', 'confirmed']
    ).order_by('date')[:10]
    
    # NEW: Assigned orders (for the new template)
    assigned_orders = Order.objects.select_related('agent', 'seller', 'product').filter(
        agent__isnull=False
    ).order_by('-date')[:10]
    
    # No demo data - show only real orders
    
    # Get available agents for assignment
    available_agents = User.objects.filter(
        user_roles__role__name='Call Center Agent',
        agent_sessions__status='available'
    ).distinct()
    
    # Get team performance data
    team_performance, created = TeamPerformance.objects.get_or_create(
        team='Main Team',
        date=today,
        defaults={
            'total_agents': total_agents,
            'orders_handled': orders_today,
            'orders_confirmed': orders_confirmed,
            'orders_cancelled': orders_cancelled,
        }
    )
    
    # Calculate team metrics
    team_avg_confirmation_rate = (orders_confirmed / total_orders * 100) if total_orders > 0 else 0
    team_avg_response_time = avg_response_time
    team_avg_satisfaction = avg_satisfaction
    team_efficiency_score = ((float(confirmation_rate) + (100 - float(cancellation_rate)) + (float(avg_satisfaction) * 20)) / 3)
    
    # Get top performing agents
    top_agents = AgentPerformance.objects.filter(
        date=today
    ).select_related('agent').order_by('-orders_confirmed')[:5]
    
    # Generate weekly trend data for charts
    weekly_trends = []
    for i in range(5):  # Last 5 days
        date = today - timedelta(days=i)
        day_performance = AgentPerformance.objects.filter(date=date)
        
        # Calculate confirmation rate for this day
        day_orders = Order.objects.filter(date__date=date)
        day_confirmed = day_orders.filter(status='confirmed').count()
        day_confirmation_rate = (day_confirmed / day_orders.count() * 100) if day_orders.count() > 0 else 0
        
        # Calculate average response time for this day
        day_avg_response = day_performance.aggregate(avg=Avg('average_call_duration'))['avg'] or 0
        
        weekly_trends.append({
            'date': date,
            'confirmation_rate': round(day_confirmation_rate, 1),
            'response_time': round(float(day_avg_response), 1),
        })
    
    # Reverse to show oldest to newest
    weekly_trends.reverse()
    
    # Prepare team performance comparison data
    team_performance_data = []
    for agent in User.objects.filter(user_roles__role__name='Call Center Agent')[:5]:
        performance = AgentPerformance.objects.filter(agent=agent, date=today).first()
        if performance:
            team_performance_data.append({
                'id': agent.id,
                'name': agent.get_full_name(),
                'orders_handled': performance.total_orders_handled,
                'orders_confirmed': performance.orders_confirmed,
                'confirmation_rate': (performance.orders_confirmed / performance.total_orders_handled * 100) if performance.total_orders_handled > 0 else 0,
                'avg_response_time': float(performance.average_call_duration or 0),
                'satisfaction': float(performance.customer_satisfaction_avg or 0),
            })
    
    # Alerts & Notifications
    # 1. High Priority: Orders pending >2 hours
    two_hours_ago = timezone.now() - timedelta(hours=2)
    high_priority_count = Order.objects.filter(
        status__in=['pending', 'pending_confirmation'],
        date__lt=two_hours_ago
    ).count()

    # 2. Agent Overload: Agent with most assigned orders (if >30)
    overload_agent = (
        User.objects.filter(user_roles__role__name='Call Center Agent')
        .annotate(order_count=Count('assigned_orders'))
        .order_by('-order_count')
        .first()
    )
    agent_overload = None
    if overload_agent and overload_agent.order_count > 30:
        agent_overload = {
            'name': overload_agent.get_full_name(),
            'order_count': overload_agent.order_count
        }

    # 3. Low Stock Alert: Product with lowest stock (<5 units)
    low_stock = (
        Stock.objects.filter(product__isnull=False)
        .annotate(total=Sum('product__inventoryrecord__quantity'))
        .filter(total__lt=5)
        .order_by('total')
        .first()
    )
    low_stock_alert = None
    if low_stock:
        low_stock_alert = {
            'product': low_stock.product.name_en,
            'units': low_stock.total or 0
        }

    # Get escalated orders for manager review
    escalated_orders = Order.objects.filter(
        escalated_to_manager=True
    ).select_related('agent', 'seller', 'escalated_by').order_by('-escalated_at')[:10]
    
    escalated_count = Order.objects.filter(escalated_to_manager=True).count()

    context = {
        'total_orders': total_orders,
        'orders_today': orders_today,
        'orders_confirmed': orders_confirmed,
        'orders_cancelled': orders_cancelled,
        'orders_pending': orders_pending,
        'orders_processed': orders_processed,
        'confirmation_rate': round(confirmation_rate, 1),
        'cancellation_rate': round(cancellation_rate, 1),
        'active_agents': active_agents,
        'total_calls_handled': total_calls_handled,
        'avg_satisfaction': round(avg_satisfaction, 1),
        'avg_response_time': round(avg_response_time, 1),
        'recent_assignments': recent_assignments,
        'pending_orders': pending_orders,
        'high_priority_unassigned': high_priority_unassigned,
        'available_agents': available_agents,
        'team_performance': team_performance,
        'team_performance_data': team_performance_data,
        'team_avg_confirmation_rate': round(team_avg_confirmation_rate, 1),
        'team_avg_response_time': round(team_avg_response_time, 1),
        'team_avg_satisfaction': round(team_avg_satisfaction, 1),
        'team_efficiency_score': round(team_efficiency_score, 1),
        'top_agents': top_agents,
        'weekly_trends': weekly_trends,
        'today': today,
        'week_start': week_ago,
        'week_end': today,
        'high_priority_count': high_priority_count,
        'agent_overload': agent_overload,
        'low_stock_alert': low_stock_alert,
        'orders_with_agents': orders_with_agents,
        'unassigned_orders': unassigned_orders,
        # NEW: Additional context for the redesigned template
        'orders_awaiting_approval': orders_awaiting_approval,
        'recently_approved': recently_approved,
        'pending_approval': pending_approval,
        'approved_today': approved_today,
        'approval_rate': round(approval_rate, 1),
        'assigned_orders': assigned_orders,
        'total_calls': total_calls_handled,
        'customer_satisfaction': round(avg_satisfaction, 1),
        # Escalated orders
        'escalated_orders': escalated_orders,
        'escalated_count': escalated_count,
    }
    
    return render(request, 'callcenter/manager/dashboard.html', context)

@login_required
def manager_order_list(request):
    """Manager's comprehensive order management view."""
    if not has_callcenter_role(request.user):
        messages.error(request, "ليس لديك صلاحية للدخول لهذه الصفحة.")
        return redirect('dashboard:index')
    
    # Get filter parameters
    status = request.GET.get('status', '')
    agent = request.GET.get('agent', '')
    priority = request.GET.get('priority', '')
    search = request.GET.get('search', '')
    date_filter = request.GET.get('date', 'all')
    
    # Base queryset - filter orders based on user role
    if request.user.has_role('Call Center Manager'):
        # Call Center Managers see all orders
        orders = Order.objects.all()
    elif request.user.has_role('Admin') or request.user.is_superuser:
        # Admins see all orders
        orders = Order.objects.all()
    else:
        # Other roles see only orders from their department or assigned to them
        orders = Order.objects.filter(
            Q(assignments__agent=request.user) |  # Orders assigned to this user
            Q(status__in=['pending', 'pending_confirmation'])  # Pending orders
        ).distinct()
    
    # Apply date filter
    today = timezone.now().date()
    if date_filter == 'all':
        # Show all orders - no date filtering
        pass
    elif date_filter == 'today':
        orders = orders.filter(date__date=today)
    elif date_filter == 'yesterday':
        yesterday = today - timedelta(days=1)
        orders = orders.filter(date__date=yesterday)
    elif date_filter == 'week':
        week_ago = today - timedelta(days=7)
        orders = orders.filter(date__date__gte=week_ago)
    elif date_filter == 'month':
        month_ago = today - timedelta(days=30)
        orders = orders.filter(date__date__gte=month_ago)
    
    # Apply filters
    if status:
        orders = orders.filter(status=status)
    
    if agent:
        orders = orders.filter(assignments__agent_id=agent)
    
    if priority:
        orders = orders.filter(assignments__priority_level=priority)
    
    if search:
        orders = orders.filter(
            Q(id__icontains=search) |
            Q(customer__icontains=search) |
            Q(customer_phone__icontains=search) |
            Q(product__name_en__icontains=search) |
            Q(product__code__icontains=search)
        )
    
    # Get summary statistics based on user role
    if request.user.has_role('Call Center Manager') or request.user.has_role('Admin') or request.user.is_superuser:
        # Managers and Admins see all statistics
        total_orders = Order.objects.count()
        assigned_orders = Order.objects.filter(assignments__isnull=False).distinct().count()
        unassigned_orders = Order.objects.filter(assignments__isnull=True).count()
        confirmed_orders = Order.objects.filter(status='confirmed').count()
        pending_orders = Order.objects.filter(status__in=['pending', 'pending_confirmation']).count()
    else:
        # Other roles see only their relevant statistics
        user_orders = Order.objects.filter(assignments__agent=request.user)
        total_orders = user_orders.count()
        assigned_orders = user_orders.filter(assignments__isnull=False).distinct().count()
        unassigned_orders = 0  # Users don't see unassigned orders
        confirmed_orders = user_orders.filter(status='confirmed').count()
        pending_orders = user_orders.filter(status__in=['pending', 'pending_confirmation']).count()
    
    # Get high priority unassigned orders based on user role
    if request.user.has_role('Call Center Manager') or request.user.has_role('Admin') or request.user.is_superuser:
        # Managers and Admins see all high priority unassigned orders
        high_priority_unassigned = Order.objects.filter(
            status__in=['pending', 'pending_confirmation'],
            assignments__isnull=True
        ).order_by('-date')[:5]
    else:
        # Other roles see only their assigned high priority orders
        high_priority_unassigned = Order.objects.filter(
            status__in=['pending', 'pending_confirmation'],
            assignments__agent=request.user
        ).order_by('-date')[:5]
    
    # Get available agents based on user role
    if request.user.has_role('Call Center Manager'):
        # Call Center Managers see all call center agents
        available_agents = User.objects.filter(
            user_roles__role__name='Call Center Agent',
            user_roles__is_active=True
        ).distinct()
        all_agents = available_agents
    elif request.user.has_role('Admin') or request.user.is_superuser:
        # Admins see all call center agents
        available_agents = User.objects.filter(
            user_roles__role__name='Call Center Agent',
            user_roles__is_active=True
        ).distinct()
        all_agents = available_agents
    else:
        # Other roles see only active agents from their department
        available_agents = User.objects.filter(
            user_roles__role__name='Call Center Agent',
            user_roles__is_active=True,
            user_roles__role__name__in=['Call Center Agent', 'Call Center Manager']
        ).distinct()
        all_agents = available_agents
    
    # Pagination
    paginator = Paginator(orders, 25)  # Show 25 orders per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    context = {
        'orders': page_obj,
        'total_orders': total_orders,
        'assigned_orders': assigned_orders,
        'unassigned_orders': unassigned_orders,
        'confirmed_orders': confirmed_orders,
        'pending_orders': pending_orders,
        'high_priority_unassigned': high_priority_unassigned,
        'available_agents': available_agents,
        'agents': all_agents,
        'status_filter': status,
        'agent_filter': agent,
        'priority_filter': priority,
        'search_filter': search,
        'date_filter': date_filter,
    }
    
    return render(request, 'callcenter/manager/order_list.html', context)

@login_required
def manager_assign_order(request, order_id):
    """Assign order to agent."""
    if not has_callcenter_role(request.user):
        messages.error(request, "ليس لديك صلاحية للدخول لهذه الصفحة.")
        return redirect('dashboard:index')
    if request.method == 'POST':
        order = get_object_or_404(Order, id=order_id)
        agent_id = request.POST.get('agent')
        priority = request.POST.get('priority', 'medium')
        notes = request.POST.get('notes', '')
        
        if agent_id:
            agent = get_object_or_404(User, id=agent_id)
            
            # Create assignment
            OrderAssignment.objects.create(
                order=order,
                manager=request.user,
                agent=agent,
                priority_level=priority,
                manager_notes=notes,
            )
            
            messages.success(request, f'Order {order.id} assigned to {agent.get_full_name() or agent.username}')
        else:
            messages.error(request, 'Please select an agent.')
        
        return redirect('callcenter:manager_order_list')
    
    order = get_object_or_404(Order, id=order_id)
    agents = User.objects.filter(groups__name='Call Center Agents')
    
    return render(request, 'callcenter/manager/assign_order.html', {
        'order': order,
        'agents': agents
    })

@login_required
def manager_agent_reports(request):
    """Manager's comprehensive agent performance reports view."""
    if not has_callcenter_role(request.user):
        messages.error(request, "ليس لديك صلاحية للدخول لهذه الصفحة.")
        return redirect('dashboard:index')
    
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    # Get all call center agents
    agents = User.objects.filter(user_roles__role__name='Call Center Agent').distinct()
    
    # Get team performance data for the week using real order data
    team_performance = []
    total_orders_processed = 0
    total_confirmation_rate = 0
    total_response_time = 0
    total_satisfaction = 0
    agent_count = 0
    
    for agent in agents:
        # Get agent's real order performance for the week (both OrderAssignment and direct Order.agent)
        agent_orders = Order.objects.filter(
            Q(assignments__agent=agent, assignments__assignment_date__date__gte=week_ago) |
            Q(agent=agent, assigned_at__date__gte=week_ago)
        ).distinct()
        
        total_orders = agent_orders.count()
        confirmed_orders = agent_orders.filter(status='confirmed').count()
        cancelled_orders = agent_orders.filter(status='cancelled').count()
        pending_orders = agent_orders.filter(status__in=['pending', 'pending_confirmation']).count()
        
        # Get agent's performance data from AgentPerformance model
        performance = AgentPerformance.objects.filter(
            agent=agent,
            date__gte=week_ago,
            date__lte=today
        ).aggregate(
            avg_response_time=Avg('average_call_duration'),
            avg_satisfaction=Avg('customer_satisfaction_avg'),
            total_calls=Sum('total_calls_made')
        )
        
        if total_orders > 0:
            confirmation_rate = (confirmed_orders / total_orders * 100)
            team_performance.append({
                'id': agent.id,
                'name': agent.get_full_name() or agent.username,
                'email': agent.email,
                'orders_handled': total_orders,
                'orders_confirmed': confirmed_orders,
                'orders_cancelled': cancelled_orders,
                'orders_pending': pending_orders,
                'confirmation_rate': round(confirmation_rate, 1),
                'avg_response_time': round(performance['avg_response_time'] or 0, 1),
                'satisfaction': round(performance['avg_satisfaction'] or 0, 1),
                'total_calls': performance['total_calls'] or 0,
            })
            
            total_orders_processed += total_orders
            total_confirmation_rate += confirmation_rate
            total_response_time += performance['avg_response_time'] or 0
            total_satisfaction += performance['avg_satisfaction'] or 0
            agent_count += 1
        else:
            # Include agents with no orders to show complete team picture
            team_performance.append({
                'id': agent.id,
                'name': agent.get_full_name() or agent.username,
                'email': agent.email,
                'orders_handled': 0,
                'orders_confirmed': 0,
                'orders_cancelled': 0,
                'orders_pending': 0,
                'confirmation_rate': 0,
                'avg_response_time': round(performance['avg_response_time'] or 0, 1),
                'satisfaction': round(performance['avg_satisfaction'] or 0, 1),
                'total_calls': performance['total_calls'] or 0,
            })
    
    # Sort by confirmation rate (top performers first)
    team_performance.sort(key=lambda x: x['confirmation_rate'], reverse=True)
    
    # Calculate team averages
    team_avg_confirmation_rate = total_confirmation_rate / agent_count if agent_count > 0 else 0
    team_avg_response_time = total_response_time / agent_count if agent_count > 0 else 0
    team_avg_satisfaction = total_satisfaction / agent_count if agent_count > 0 else 0
    team_efficiency_score = ((float(team_avg_confirmation_rate) + (100 - (float(total_orders_processed) * 0.1)) + (float(team_avg_satisfaction) * 20)) / 3)
    
    # Get individual agent performance for today
    today_performance = {}
    for agent in agents:
        perf = AgentPerformance.objects.filter(agent=agent, date=today).first()
        if perf:
            today_performance[agent.id] = {
                'orders_handled': perf.total_orders_handled,
                'orders_confirmed': perf.orders_confirmed,
                'confirmation_rate': (perf.orders_confirmed / perf.total_orders_handled * 100) if perf.total_orders_handled > 0 else 0,
                'avg_response_time': float(perf.average_call_duration or 0),
                'satisfaction': float(perf.customer_satisfaction_avg or 0),
            }
    
    # Calculate summary statistics for the template
    total_agents = agents.count()
    total_calls = sum(perf['total_calls'] for perf in team_performance)
    avg_satisfaction = team_avg_satisfaction
    resolution_rate = team_avg_confirmation_rate  # Using confirmation rate as resolution rate
    
    context = {
        'agents': agents,
        'team_performance': team_performance,
        'today_performance': today_performance,
        'total_orders_processed': total_orders_processed,
        'team_avg_confirmation_rate': round(team_avg_confirmation_rate, 1),
        'team_avg_response_time': round(team_avg_response_time, 1),
        'team_avg_satisfaction': round(team_avg_satisfaction, 1),
        'team_efficiency_score': round(team_efficiency_score, 1),
        'week_start': week_ago,
        'week_end': today,
        'today': today,
        'total_agents': total_agents,
        'total_calls': total_calls,
        'avg_satisfaction': round(avg_satisfaction, 1),
        'resolution_rate': round(resolution_rate, 1),
    }
    
    return render(request, 'callcenter/manager/agent_reports.html', context)

# Enhanced Manager Views

@login_required
def manager_order_detail(request, order_id):
    """Manager's detailed order view."""
    if not has_callcenter_role(request.user):
        messages.error(request, "ليس لديك صلاحية للدخول لهذه الصفحة.")
        return redirect('dashboard:index')
    
    order = get_object_or_404(Order, id=order_id)
    assignments = order.assignments.all().select_related('agent')
    call_logs = CallLog.objects.filter(order=order).order_by('-call_time')
    
    context = {
        'order': order,
        'assignments': assignments,
        'call_logs': call_logs,
    }
    
    return render(request, 'callcenter/manager/order_detail.html', context)

@login_required
def agent_performance_report(request, agent_id):
    """Individual agent performance report."""
    if not has_callcenter_role(request.user):
        messages.error(request, "ليس لديك صلاحية للدخول لهذه الصفحة.")
        return redirect('dashboard:index')
    
    agent = get_object_or_404(User, id=agent_id)
    period = request.GET.get('period', 'daily')
    start_date = request.GET.get('start_date')
    end_date = request.GET.get('end_date')
    
    # Get performance data based on period
    if period == 'daily':
        performance_data = AgentPerformance.objects.filter(
            agent=agent,
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')
    elif period == 'weekly':
        # Weekly aggregation logic
        performance_data = []
    else:  # monthly
        # Monthly aggregation logic
        performance_data = []
    
    context = {
        'agent': agent,
        'performance_data': performance_data,
        'period': period,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return JsonResponse(context)

@login_required
@user_passes_test(lambda u: u.has_role('Call Center Manager') or u.has_role('Admin') or u.has_role('Super Admin'))
def bulk_assign_orders(request):
    """Bulk assign orders to agents."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            order_ids = data.get('order_ids', [])
            agent_id = data.get('agent_id')
            
            if not order_ids:
                return JsonResponse({
                    'success': False,
                    'message': 'No orders selected'
                })
            
            if not agent_id:
                return JsonResponse({
                    'success': False,
                    'message': 'Agent ID is required'
                })
            
            # Get the agent
            try:
                agent = User.objects.get(id=agent_id)
            except User.DoesNotExist:
                return JsonResponse({
                    'success': False,
                    'message': 'Agent not found'
                })
            
            # Assign orders
            assigned_count = 0
            for order_id in order_ids:
                try:
                    order = Order.objects.get(id=order_id)
                    
                    # Check if order is already assigned
                    existing_assignment = OrderAssignment.objects.filter(order=order).first()
                    
                    if existing_assignment:
                        # Update existing assignment
                        existing_assignment.agent = agent
                        existing_assignment.manager = request.user
                        existing_assignment.assignment_reason = f'Bulk reassigned by {request.user.get_full_name() or request.user.username}'
                        existing_assignment.save()
                    else:
                        # Create new assignment
                        OrderAssignment.objects.create(
                            order=order,
                            manager=request.user,
                            agent=agent,
                            priority_level='medium',
                            manager_notes='Bulk assigned by manager',
                            assignment_reason=f'Bulk assigned by {request.user.get_full_name() or request.user.username}'
                        )
                    
                    assigned_count += 1
                    
                except Order.DoesNotExist:
                    continue
            
            return JsonResponse({
                'success': True,
                'message': f'Successfully assigned {assigned_count} orders to {agent.get_full_name() or agent.username}',
                'assigned_count': assigned_count
            })
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
def export_performance_report(request):
    """Export agent performance report as CSV - RESTRICTED TO SUPER ADMIN ONLY."""
    from users.models import AuditLog

    # SECURITY: Restrict data export to Super Admin only (P0 CRITICAL requirement)
    if not request.user.is_superuser:
        from utils.views import permission_denied_authenticated
        AuditLog.objects.create(
            user=request.user,
            action='unauthorized_export_attempt',
            entity_type='performance_report',
            description=f"Unauthorized attempt to export performance report by {request.user.email}",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        return permission_denied_authenticated(
            request,
            message="Data export is restricted to Super Admin only for security compliance."
        )
    
    import csv
    from django.http import HttpResponse
    from datetime import datetime
    
    # Get the same data as the reports view
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    # Check if specific agent export is requested
    agent_id = request.GET.get('agent_id')
    
    # Get call center agents
    if agent_id:
        agents = User.objects.filter(
            id=agent_id,
            user_roles__role__name='Call Center Agent'
        ).distinct()
        filename = f"agent_{agent_id}_performance_report_{today}.csv"
    else:
        agents = User.objects.filter(user_roles__role__name='Call Center Agent').distinct()
        filename = f"agent_performance_report_{today}.csv"
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    
    # Write header
    writer.writerow([
        'Agent Name', 'Email', 'Orders Handled', 'Orders Confirmed', 
        'Orders Cancelled', 'Orders Pending', 'Confirmation Rate (%)',
        'Avg Response Time (min)', 'Satisfaction Rating', 'Total Calls'
    ])
    
    # Write data for each agent
    for agent in agents:
        # Get agent's real order performance for the week
        agent_orders = Order.objects.filter(
            Q(assignments__agent=agent, assignments__assignment_date__date__gte=week_ago) |
            Q(agent=agent, assigned_at__date__gte=week_ago)
        ).distinct()
        
        total_orders = agent_orders.count()
        confirmed_orders = agent_orders.filter(status='confirmed').count()
        cancelled_orders = agent_orders.filter(status='cancelled').count()
        pending_orders = agent_orders.filter(status__in=['pending', 'pending_confirmation']).count()
        
        # Get agent's performance data
        performance = AgentPerformance.objects.filter(
            agent=agent,
            date__gte=week_ago,
            date__lte=today
        ).aggregate(
            avg_response_time=Avg('average_call_duration'),
            avg_satisfaction=Avg('customer_satisfaction_avg'),
            total_calls=Sum('total_calls_made')
        )
        
        confirmation_rate = (confirmed_orders / total_orders * 100) if total_orders > 0 else 0
        
        writer.writerow([
            agent.get_full_name() or agent.username,
            agent.email,
            total_orders,
            confirmed_orders,
            cancelled_orders,
            pending_orders,
            round(confirmation_rate, 1),
            round(performance['avg_response_time'] or 0, 1),
            round(performance['avg_satisfaction'] or 0, 1),
            performance['total_calls'] or 0,
        ])

    # Audit log for successful export (P0 CRITICAL security requirement)
    AuditLog.objects.create(
        user=request.user,
        action='data_export',
        entity_type='performance_report',
        description=f"Exported performance report for {len(agents)} agent(s) to CSV",
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )

    return response

# API Views

@login_required
def assign_order_api(request, order_id):
    """API endpoint for assigning orders."""
    if not has_callcenter_role(request.user):
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            order = Order.objects.get(id=order_id)
            agent = User.objects.get(id=data['agent_id'])
            
            # Parse expected completion date/time
            expected_completion = None
            if data.get('expected_completion'):
                try:
                    expected_completion = timezone.datetime.strptime(
                        data['expected_completion'], 
                        '%Y-%m-%d %H:%M'
                    )
                    expected_completion = timezone.make_aware(expected_completion)
                except ValueError:
                    pass
            
            # Create or update assignment
            assignment, created = OrderAssignment.objects.get_or_create(
                order=order,
                defaults={
                    'manager': request.user,
                    'agent': agent,
                    'priority_level': data.get('priority_level', 'medium'),
                    'manager_notes': data.get('manager_notes', ''),
                    'expected_completion': expected_completion,
                    'assignment_reason': data.get('assignment_reason', ''),
                    'assignment_date': timezone.now()
                }
            )
            
            if not created:
                assignment.manager = request.user
                assignment.agent = agent
                assignment.priority_level = data.get('priority_level', 'medium')
                assignment.manager_notes = data.get('manager_notes', '')
                assignment.expected_completion = expected_completion
                assignment.assignment_reason = data.get('assignment_reason', '')
                assignment.save()
            
            return JsonResponse({
                'success': True,
                'message': 'Order assigned successfully',
                'assignment_id': assignment.id
            })
            
        except (Order.DoesNotExist, User.DoesNotExist, KeyError) as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
        except json.JSONDecodeError as e:
            return JsonResponse({
                'success': False,
                'error': 'Invalid JSON data'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Unexpected error: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def get_agent_performance(request, agent_id):
    """API endpoint for getting agent performance data."""
    if not has_callcenter_role(request.user):
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    try:
        agent = User.objects.get(id=agent_id)
        period = request.GET.get('period', 'daily')
        start_date = request.GET.get('start_date')
        end_date = request.GET.get('end_date')
        
        # Get performance data
        performance = AgentPerformance.objects.filter(
            agent=agent,
            date__gte=start_date,
            date__lte=end_date
        ).aggregate(
            total_orders=Sum('total_orders_handled'),
            total_confirmed=Sum('orders_confirmed'),
            avg_response_time=Avg('average_call_duration'),
            avg_satisfaction=Avg('customer_satisfaction_avg')
        )
        
        if performance['total_orders'] and performance['total_orders'] > 0:
            confirmation_rate = (performance['total_confirmed'] / performance['total_orders'] * 100)
        else:
            confirmation_rate = 0
        
        return JsonResponse({
            'success': True,
            'agent_name': agent.get_full_name(),
            'period': period,
            'orders_handled': performance['total_orders'] or 0,
            'orders_confirmed': performance['total_confirmed'] or 0,
            'confirmation_rate': round(confirmation_rate, 1),
            'avg_response_time': round(performance['avg_response_time'] or 0, 1),
            'satisfaction': round(performance['avg_satisfaction'] or 0, 1),
        })
        
    except User.DoesNotExist:
        return JsonResponse({'success': False, 'error': 'Agent not found'})

@login_required
def export_orders_api(request):
    """API endpoint for exporting orders."""
    if not has_callcenter_role(request.user):
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    # Implementation for exporting orders
    # This would generate a CSV file
    return JsonResponse({'success': True, 'message': 'Export functionality coming soon'})

# Missing view functions

@login_required
def update_agent_status(request):
    """Update agent status via AJAX."""
    if not has_callcenter_role(request.user):
        return JsonResponse({'success': False, 'error': 'Unauthorized'})
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            status = data.get('status')
            
            session, created = AgentSession.objects.get_or_create(
                agent=request.user,
                defaults={'status': status}
            )
            
            if not created:
                session.status = status
                session.save()
            
            return JsonResponse({
                'success': True,
                'status': status,
                'message': 'Status updated successfully'
            })
            
        except (KeyError, json.JSONDecodeError) as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })
    
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def get_order_details(request, order_id):
    """Get order details for AJAX requests."""
    if not has_callcenter_role(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        order = Order.objects.get(id=order_id)
        data = {
            'id': order.id,
            'order_code': order.order_code,
            'customer': order.customer,
            'product': order.product.name_en if order.product else 'N/A',
            'status': order.get_status_display(),
            'date': order.date.strftime('%Y-%m-%d %H:%M'),
            'price': str(order.total_price_aed),
            'phone': order.customer_phone or 'N/A',
            'notes': order.notes or '',
        }
        return JsonResponse(data)
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)

@login_required
def add_note_api(request, order_id):
    """Add a note to an order via AJAX."""
    if not has_callcenter_role(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method != 'POST':
        return JsonResponse({'error': 'Method not allowed'}, status=405)
    
    try:
        order = Order.objects.get(id=order_id)
        data = json.loads(request.body)
        
        # Create the note
        note = ManagerNote.objects.create(
            order=order,
            manager=request.user,
            agent=request.user,  # For now, set to current user. You might want to get the assigned agent
            note_text=data.get('note_text', ''),
            note_type=data.get('note_type', 'instruction'),
            is_urgent=data.get('is_urgent', False)
        )
        
        return JsonResponse({
            'success': True,
            'message': 'Note added successfully',
            'note_id': note.id
        })
        
    except Order.DoesNotExist:
        return JsonResponse({'error': 'Order not found'}, status=404)
    except json.JSONDecodeError:
        return JsonResponse({'error': 'Invalid JSON data'}, status=400)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def manager_settings(request):
    """Manager settings page."""
    if not has_callcenter_role(request.user):
        messages.error(request, "ليس لديك صلاحية للدخول لهذه الصفحة.")
        return redirect('dashboard:index')
    
    # Get current settings (you can store these in database or cache)
    settings = {
        'auto_assign': True,
        'load_balancing': True,
        'priority_queue': False,
        'max_orders': 25,
        'response_threshold': 5,
        'auto_logout': 30,
        'high_priority_alerts': True,
        'performance_reports': True,
        'system_updates': False,
    }
    
    return render(request, 'callcenter/manager/settings.html', {'settings': settings})

@login_required
def save_settings(request):
    """Save manager settings via AJAX."""
    if not has_callcenter_role(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            
            # Here you would save the settings to database or cache
            # For now, we'll just return success
            settings = {
                'auto_assign': data.get('auto_assign', True),
                'load_balancing': data.get('load_balancing', True),
                'priority_queue': data.get('priority_queue', False),
                'max_orders': int(data.get('max_orders', 25)),
                'response_threshold': int(data.get('response_threshold', 5)),
                'auto_logout': int(data.get('auto_logout', 30)),
                'high_priority_alerts': data.get('high_priority_alerts', True),
                'performance_reports': data.get('performance_reports', True),
                'system_updates': data.get('system_updates', False),
            }
            
            # You can save these settings to a model or cache here
            # For example: CallCenterSettings.objects.update_or_create(user=request.user, defaults=settings)
            
            return JsonResponse({'success': True, 'message': 'Settings saved successfully'})
        except json.JSONDecodeError:
            return JsonResponse({'error': 'Invalid JSON data'}, status=400)
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    return JsonResponse({'error': 'Method not allowed'}, status=405)

# Legacy views for backward compatibility

@login_required
def dashboard(request):
    """Legacy dashboard view - redirects to appropriate dashboard."""
    if has_callcenter_role(request.user):
        if request.user.has_role('Call Center Manager') or request.user.has_role('Admin') or request.user.has_role('Super Admin') or request.user.is_superuser:
            return redirect('callcenter:manager_dashboard')
        elif request.user.has_role('Call Center Agent'):
            return redirect('callcenter:agent_dashboard')
    
    return redirect('dashboard:index')

@login_required
def order_list(request):
    """Legacy order list view - redirects to appropriate order list."""
    if has_callcenter_role(request.user):
        if request.user.has_role('Call Center Manager') or request.user.has_role('Admin') or request.user.has_role('Super Admin') or request.user.is_superuser:
            return redirect('callcenter:manager_order_list')
        elif request.user.has_role('Call Center Agent'):
            return redirect('callcenter:agent_order_list')
    
    return redirect('dashboard:index')

@login_required
def order_detail(request, order_id):
    """Order detail view for call center staff."""
    if not has_callcenter_role(request.user):
        messages.error(request, "ليس لديك صلاحية للدخول لهذه الصفحة.")
        return redirect('dashboard:index')
    
    try:
        order = Order.objects.select_related('product', 'seller', 'agent').prefetch_related('items__product').get(id=order_id)
        
        if request.user.has_role('Call Center Agent') and not order.assignments.filter(agent=request.user).exists():
            messages.error(request, "You are not assigned to this order.")
            return redirect('callcenter:agent_order_list')
        
        # Get call logs for this order
        call_logs = CallLog.objects.filter(order=order).order_by('-call_time')
        
        # Get status history
        status_history = OrderStatusHistory.objects.filter(order=order).order_by('-change_timestamp')
        
        # Get manager notes if applicable
        if request.user.has_role('Call Center Agent'):
            manager_notes = ManagerNote.objects.filter(order=order, agent=request.user).order_by('-created_at')
        else:
            manager_notes = ManagerNote.objects.filter(order=order).order_by('-created_at')
        
        context = {
            'order': order,
            'call_logs': call_logs,
            'manager_notes': manager_notes,
            'status_history': status_history,
        }
        
        return render(request, 'callcenter/order_detail.html', context)
        
    except Order.DoesNotExist:
        messages.error(request, "Order not found.")
        if request.user.has_role('Call Center Manager'):
            return redirect('callcenter:manager_order_list')
        elif request.user.has_role('Call Center Agent'):
            return redirect('callcenter:agent_order_list')
        else:
            return redirect('dashboard:index')

# Order Distribution Views

@login_required
@user_passes_test(lambda u: u.has_role('Call Center Manager') or u.has_role('Admin') or u.has_role('Super Admin'))
def auto_distribute_orders(request):
    """Automatically distribute all unassigned orders equally among agents"""
    if request.method == 'POST':
        try:
            # Use the auto distribution service
            result = AutoOrderDistributionService.distribute_orders_equally()
            
            if result['success']:
                messages.success(request, result['message'])
            else:
                messages.error(request, result['message'])
                
        except Exception as e:
            messages.error(request, f'Error during auto distribution: {str(e)}')
    
    return redirect('callcenter:manager_order_list')

@login_required
@user_passes_test(lambda u: u.has_role('Call Center Manager') or u.has_role('Admin') or u.has_role('Super Admin'))
def balance_agent_workloads(request):
    """Balance workloads between agents"""
    if request.method == 'POST':
        try:
            result = AutoOrderDistributionService.balance_workloads()
            messages.success(request, result)
        except Exception as e:
            messages.error(request, f'Error balancing workloads: {str(e)}')
    
    return redirect('callcenter:manager_order_list')

@login_required
@user_passes_test(lambda u: u.has_role('Call Center Manager') or u.has_role('Admin') or u.has_role('Super Admin'))
def reassign_order(request, order_id):
    """Reassign an order to a different agent."""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        new_agent_id = request.POST.get('new_agent')
        reason = request.POST.get('reason', '')
        
        if new_agent_id:
            result = OrderDistributionService.reassign_order(
                order_id=order_id,
                new_agent_id=new_agent_id,
                manager_id=request.user.id,
                reason=reason
            )
            
            if result['success']:
                messages.success(request, result['message'])
            else:
                messages.error(request, result['message'])
        else:
            messages.error(request, 'Please select a new agent.')
        
        return redirect('callcenter:manager_order_list')
    
    # Get current assignment
    current_assignment = OrderAssignment.objects.filter(order=order).first()
    
    # Get available agents
    available_agents = OrderDistributionService.get_available_agents()
    
    context = {
        'order': order,
        'current_assignment': current_assignment,
        'available_agents': available_agents
    }
    
    return render(request, 'callcenter/manager/reassign_order.html', context)

@login_required
def distribute_orders(request):
    """Distribute unassigned orders to available agents using round-robin method."""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    try:
        # Get unassigned orders (excluding cancelled, completed, delivered)
        unassigned_orders = Order.objects.filter(
            agent__isnull=True,
            status__in=['pending', 'processing', 'confirmed']
        ).order_by('date')
        
        if not unassigned_orders.exists():
            return JsonResponse({
                'success': False, 
                'message': 'No unassigned orders available for distribution'
            })
        
        # Get available agents (Call Center Agent or Agent role)
        from roles.models import UserRole, Role
        agent_role = Role.objects.filter(name__in=['Call Center Agent', 'Agent']).first()
        
        if not agent_role:
            return JsonResponse({
                'success': False, 
                'message': 'No agent roles found in the system'
            })
        
        available_agents = User.objects.filter(
            user_roles__role=agent_role,
            user_roles__is_active=True,
            is_active=True
        ).distinct()
        
        if not available_agents.exists():
            return JsonResponse({
                'success': False, 
                'message': 'No available agents in the system'
            })
        
        # Convert to list for round-robin distribution
        agents_list = list(available_agents)
        agent_index = 0
        distributed_count = 0
        
        for order in unassigned_orders:
            # Assign agent using round-robin
            assigned_agent = agents_list[agent_index % len(agents_list)]
            order.agent = assigned_agent
            order.assigned_at = timezone.now()
            order.save()
            
            # Create audit log
            from users.models import AuditLog
            AuditLog.objects.create(
                user=request.user,
                action='assign_agent',
                entity_type='Order',
                entity_id=str(order.id),
                description=f"Auto-assigned order {order.order_code} to agent {assigned_agent.get_full_name() or assigned_agent.username}"
            )
            
            distributed_count += 1
            agent_index += 1
        
        message = f'Successfully distributed {distributed_count} orders to {len(agents_list)} agents'
        
        return JsonResponse({
            'success': True,
            'message': message,
            'distributed_count': distributed_count,
            'agents_count': len(agents_list)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error distributing orders: {str(e)}'
        })

@login_required
def force_assign_orders(request):
    """إجبار تعيين الطلبات للموظف الحالي - DEBUG VERSION"""
    if not has_callcenter_role(request.user):
        return JsonResponse({'success': False, 'message': 'ليس لديك صلاحية للوصول لهذه الصفحة'})
    
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    try:
        print(f"\n=== FORCE ASSIGN ORDERS DEBUG ===")
        print(f"User: {request.user} (ID: {request.user.id})")
        
        # فحص إجمالي الطلبات
        total_orders = Order.objects.count()
        print(f"Total orders in system: {total_orders}")
        
        # الحصول على الطلبات غير المعينة
        unassigned_orders = Order.objects.filter(
            status__in=['pending', 'processing', 'pending_confirmation'],
            agent__isnull=True,
            assignments__isnull=True
        ).order_by('date')[:20]  # أخذ حتى 20 طلب
        
        print(f"Found {unassigned_orders.count()} unassigned orders")
        
        if not unassigned_orders.exists():
            return JsonResponse({
                'success': True, 
                'message': 'لا توجد طلبات غير معينة في النظام',
                'assigned_count': 0
            })
        
        assigned_count = 0
        
        for order in unassigned_orders:
            print(f"Processing order: {order.order_code} (ID: {order.id})")
            
            # إنشاء OrderAssignment
            assignment = OrderAssignment.objects.create(
                order=order,
                manager=request.user,
                agent=request.user,
                priority_level='medium',
                manager_notes='تم التعيين بواسطة الموظف',
                assignment_reason='تعيين إجباري للطلبات غير المعينة'
            )
            print(f"Created OrderAssignment: {assignment.id}")
            
            # تحديث Order.agent
            order.agent = request.user
            order.assigned_at = timezone.now()
            order.save()
            print(f"Updated Order.agent to: {order.agent}")
            
            assigned_count += 1
        
        print(f"Successfully assigned {assigned_count} orders")
        print("=== END FORCE ASSIGN DEBUG ===\n")
        
        return JsonResponse({
            'success': True,
            'message': f'تم تعيين {assigned_count} طلب بنجاح',
            'assigned_count': assigned_count
        })
        
    except Exception as e:
        print(f"Error in force_assign_orders: {e}")
        return JsonResponse({
            'success': False,
            'message': f'خطأ في تعيين الطلبات: {str(e)}'
        })

@login_required
@user_passes_test(lambda u: u.has_role('Call Center Manager') or u.has_role('Admin') or u.has_role('Super Admin'))
def create_test_orders(request):
    """إنشاء طلبات تجريبية للاختبار"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    try:
        from sellers.models import Product
        
        # البحث عن منتج موجود
        product = Product.objects.first()
        if not product:
            return JsonResponse({
                'success': False, 
                'message': 'لا توجد منتجات في النظام لإنشاء طلبات تجريبية'
            })
        
        # إنشاء 5 طلبات تجريبية
        created_count = 0
        for i in range(5):
            order = Order.objects.create(
                customer=f'عميل تجريبي {i+1}',
                customer_phone=f'050123456{i}',
                product=product,
                quantity=1,
                price_per_unit=100,
                status='pending',
                notes=f'طلب تجريبي رقم {i+1}'
            )
            created_count += 1
            print(f"Created test order: {order.order_code}")
        
        return JsonResponse({
            'success': True,
            'message': f'تم إنشاء {created_count} طلب تجريبي بنجاح',
            'created_count': created_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'خطأ في إنشاء الطلبات التجريبية: {str(e)}'
        })

@login_required
@user_passes_test(lambda u: u.has_role('Call Center Manager') or u.has_role('Admin') or u.has_role('Super Admin'))
def fix_all_unassigned_orders(request):
    """إصلاح جميع الطلبات غير المعينة في النظام"""
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Invalid request method'})
    
    try:
        # الحصول على الموظفين المتاحين
        from roles.models import UserRole, Role
        agent_role = Role.objects.filter(name__in=['Call Center Agent', 'Agent']).first()
        
        if not agent_role:
            return JsonResponse({
                'success': False, 
                'message': 'لا توجد أدوار للوكلاء في النظام'
            })
        
        agents = User.objects.filter(
            user_roles__role=agent_role,
            user_roles__is_active=True,
            is_active=True
        ).distinct()
        
        if not agents.exists():
            return JsonResponse({
                'success': False, 
                'message': 'لا توجد وكلاء متاحين في النظام'
            })
        
        # الحصول على الطلبات غير المعينة
        unassigned_orders = Order.objects.filter(
            status__in=['pending', 'processing', 'pending_confirmation'],
            agent__isnull=True,
            assignments__isnull=True
        ).order_by('date')
        
        if not unassigned_orders.exists():
            return JsonResponse({
                'success': True, 
                'message': 'لا توجد طلبات غير معينة في النظام',
                'fixed_count': 0
            })
        
        # تعيين الطلبات للموظفين
        agents_list = list(agents)
        agent_index = 0
        fixed_count = 0
        
        for order in unassigned_orders:
            assigned_agent = agents_list[agent_index % len(agents_list)]
            
            # إنشاء OrderAssignment
            OrderAssignment.objects.create(
                order=order,
                manager=request.user,
                agent=assigned_agent,
                priority_level='medium',
                manager_notes='تم التعيين بواسطة المدير',
                assignment_reason='إصلاح الطلبات غير المعينة'
            )
            
            # تحديث Order.agent
            order.agent = assigned_agent
            order.assigned_at = timezone.now()
            order.save()
            
            fixed_count += 1
            agent_index += 1
        
        return JsonResponse({
            'success': True,
            'message': f'تم إصلاح {fixed_count} طلب بنجاح',
            'fixed_count': fixed_count,
            'agents_count': len(agents_list)
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'خطأ في إصلاح الطلبات: {str(e)}'
        })

@login_required
@user_passes_test(lambda u: u.has_role('Call Center Manager') or u.has_role('Admin') or u.has_role('Super Admin'))
def distribution_dashboard(request):
    """Dashboard showing order distribution among agents."""
    summary = OrderDistributionService.get_agent_distribution_summary()
    
    # Get recent assignments
    recent_assignments = OrderAssignment.objects.filter(
        assignment_date__date=timezone.now().date()
    ).order_by('-assignment_date')[:10]
    
    # Get unassigned orders
    unassigned_orders = Order.objects.filter(
        status__in=['pending', 'processing'],
        assignments__isnull=True
    ).order_by('date')[:20]
    
    # Calculate average orders per agent
    avg_orders_per_agent = 0
    if summary['total_agents'] > 0:
        avg_orders_per_agent = (summary['total_assigned'] + summary['unassigned_count']) / summary['total_agents']
    
    context = {
        'summary': summary,
        'agents': summary['agents'],
        'recent_assignments': recent_assignments,
        'unassigned_orders': unassigned_orders,
        'total_assigned': summary['total_assigned'],
        'unassigned_count': summary['unassigned_count'],
        'avg_orders_per_agent': avg_orders_per_agent
    }
    
    return render(request, 'callcenter/manager/distribution_dashboard.html', context)

@login_required
@user_passes_test(lambda u: u.has_role('Call Center Manager') or u.has_role('Admin') or u.has_role('Super Admin'))
def api_auto_distribute(request):
    """API endpoint for automatic order distribution."""
    if request.method == 'POST':
        result = OrderDistributionService.distribute_orders_automatically()
        return JsonResponse(result)
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
@user_passes_test(lambda u: u.has_role('Call Center Manager') or u.has_role('Admin') or u.has_role('Super Admin'))
def api_reassign_order(request, order_id):
    """API endpoint for reassigning orders."""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)
            new_agent_id = data.get('new_agent_id')
            reason = data.get('reason', '')
            
            if not new_agent_id:
                return JsonResponse({
                    'success': False,
                    'message': 'New agent ID is required'
                })
            
            result = OrderDistributionService.reassign_order(
                order_id=order_id,
                new_agent_id=new_agent_id,
                manager_id=request.user.id,
                reason=reason
            )
            
            return JsonResponse(result)
            
        except json.JSONDecodeError:
            return JsonResponse({
                'success': False,
                'message': 'Invalid JSON data'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'message': f'Error: {str(e)}'
            })
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
@user_passes_test(lambda u: u.has_role('Call Center Manager') or u.has_role('Admin') or u.has_role('Super Admin'))
def api_distribution_summary(request):
    """API endpoint for getting distribution summary."""
    summary = OrderDistributionService.get_agent_distribution_summary()
    return JsonResponse(summary)

@login_required
@user_passes_test(has_callcenter_role)
def agent_accept_order(request, order_id):
    """Agent accepts an assigned order."""
    if request.method == 'POST':
        try:
            # Get the order and verify it's assigned to this agent
            order = get_object_or_404(Order, id=order_id)
            
            # Check if order is assigned to this agent (either way)
            if not (order.assignments.filter(agent=request.user).exists() or order.agent == request.user):
                return JsonResponse({
                    'success': False,
                    'error': 'Order not found or not assigned to you'
                })
            
            # Check if order is in pending status
            if order.status != 'pending':
                return JsonResponse({
                    'success': False,
                    'error': 'Order is not in pending status'
                })
            
            # Update order status to confirmed
            order.status = 'confirmed'
            order.save()
            
            # Update workflow status if it exists
            if hasattr(order, 'workflow_status'):
                order.workflow_status = 'callcenter_approved'
                order.save()
            
            # Create status history entry
            OrderStatusHistory.objects.create(
                order=order,
                agent=request.user,
                changed_by=request.user,
                previous_status='pending',
                new_status='confirmed',
                status_change_reason='Order accepted by call center agent',
                change_timestamp=timezone.now()
            )
            
            # Log the action
            messages.success(request, f'Order {order.order_code} has been accepted successfully.')
            
            return JsonResponse({
                'success': True,
                'message': 'Order accepted successfully',
                'new_status': 'confirmed'
            })
            
        except Order.DoesNotExist:
            return JsonResponse({
                'success': False,
                'error': 'Order not found or not assigned to you'
            })
        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': f'Error accepting order: {str(e)}'
            })
    
    return JsonResponse({
        'success': False,
        'error': 'Invalid request method'
    })


@login_required
@user_passes_test(has_callcenter_role)
def update_order_status(request, order_id):
    """Update order status for call center agents with delivery area confirmation."""
    if request.method == 'POST':
        try:
            order = get_object_or_404(Order, id=order_id)
            new_status = request.POST.get('status')
            delivery_area = request.POST.get('delivery_area', '')
            notes = request.POST.get('notes', '')
            
            # Validate status
            valid_statuses = ['pending', 'confirmed', 'processing', 'shipped', 'cancelled']
            if new_status not in valid_statuses:
                return JsonResponse({'success': False, 'message': 'Invalid status'})
            
            # Store old status for history
            old_status = order.status
            old_workflow_status = getattr(order, 'workflow_status', None)
            
            # Update order status
            order.status = new_status
            
            # Handle workflow status based on new status
            if new_status == 'confirmed':
                # Require delivery area confirmation
                if not delivery_area:
                    return JsonResponse({'success': False, 'message': 'Delivery area confirmation is required'})
                
                # Update delivery area
                order.delivery_area = delivery_area
                order.workflow_status = 'callcenter_approved'
                
                # Auto-advance to pick and pack if from admin
                if request.user.is_superuser or request.user.has_role('Admin') or request.user.has_role('Super Admin'):
                    order.workflow_status = 'pick_and_pack'
                    order.status = 'processing'
                
            elif new_status == 'processing':
                order.workflow_status = 'pick_and_pack'
            elif new_status == 'shipped':
                order.workflow_status = 'ready_for_delivery'
            elif new_status == 'cancelled':
                order.workflow_status = 'cancelled'
            
            order.updated_at = timezone.now()
            order.save()
            
            # Create status history entry
            OrderStatusHistory.objects.create(
                order=order,
                agent=request.user,
                changed_by=request.user,
                previous_status=old_status,
                new_status=new_status,
                status_change_reason=f'Status updated by call center agent. Delivery area: {delivery_area}. Notes: {notes}',
                change_timestamp=timezone.now()
            )
            
            # Create call log if this is a confirmation
            if new_status == 'confirmed' and delivery_area:
                CallLog.objects.create(
                    order=order,
                    agent=request.user,
                    status='completed',
                    notes=f'Order confirmed with delivery area: {delivery_area}. {notes}',
                    resolution_status='resolved',
                    duration=0  # Will be updated by frontend
                )
            
            return JsonResponse({
                'success': True, 
                'message': f'Order status updated to {new_status.title()}',
                'new_status': new_status,
                'workflow_status': order.workflow_status
            })
            
        except Exception as e:
            return JsonResponse({'success': False, 'message': str(e)})
    
    return JsonResponse({'success': False, 'message': 'Invalid request method'})

@login_required
@require_POST
def agent_approve_order(request, order_id):
    """Approve order by call center agent - FIXED VERSION."""
    try:
        order = get_object_or_404(Order, id=order_id)
        
        # Check if user has permission to approve this order
        if not request.user.has_role('Call Center Agent') and not request.user.is_superuser:
            messages.error(request, "You don't have permission to approve orders.")
            return redirect('callcenter:agent_order_detail', order_id=order_id)
        
        # Check if order can be approved
        if order.status != 'pending' or order.workflow_status != 'seller_submitted':
            messages.error(request, f'Order {order.order_code} cannot be approved. Current status: {order.status}, Workflow: {order.workflow_status}')
            return redirect('callcenter:agent_order_detail', order_id=order_id)
        
        # Store old status for logging
        old_workflow_status = order.workflow_status
        
        # Update order status
        order.workflow_status = 'callcenter_approved'
        order.status = 'confirmed'
        order.save()
        
        # Create workflow log with correct parameters
        from orders.models import OrderWorkflowLog
        OrderWorkflowLog.objects.create(
            order=order,
            from_status=old_workflow_status,
            to_status='callcenter_approved',
            user=request.user,
            notes='Order approved by call center agent'
        )
        
        # Create status history entry
        OrderStatusHistory.objects.create(
            order=order,
            agent=request.user,
            changed_by=request.user,
            previous_status='pending',
            new_status='confirmed',
            status_change_reason='Order approved by call center agent',
            change_timestamp=timezone.now()
        )
        
        messages.success(request, f'Order {order.order_code} has been approved successfully and is now ready for packaging.')
        
    except Exception as e:
        messages.error(request, f'Error approving order: {str(e)}')
    
    return redirect('callcenter:agent_order_detail', order_id=order_id)

@login_required
@require_POST
def agent_update_order_status(request, order_id):
    """Update order status based on call center agent action."""
    try:
        order = get_object_or_404(Order, id=order_id)
        
        if request.content_type == 'application/json':
            import json
            data = json.loads(request.body)
            status_code = data.get('status')
            edit_reason = data.get('reason', '')
            call_time_str = data.get('call_time', '')
            escalation_reason = data.get('escalation_reason', '')
            postponed_datetime = data.get('postponed_datetime', '')
            call_back_time = data.get('call_back_time', '')
            no_answer_time = data.get('no_answer_time', '')
        else:
            status_code = request.POST.get('status')
            edit_reason = request.POST.get('reason', '')
            call_time_str = request.POST.get('call_time', '')
            escalation_reason = request.POST.get('escalation_reason', '')
            postponed_datetime = request.POST.get('postponed_datetime', '')
            call_back_time = request.POST.get('call_back_time', '')
            no_answer_time = request.POST.get('no_answer_time', '')
        
        # Check if user has permission to update this order
        if not (request.user.has_role('Call Center Agent') or request.user.has_role('Call Center Manager') or request.user.is_superuser):
            if request.content_type == 'application/json':
                return JsonResponse({'success': False, 'error': 'You don\'t have permission to update order status.'})
            messages.error(request, "You don't have permission to update order status.")
            return redirect('callcenter:agent_order_detail', order_id=order_id)
        
        # Check if order is escalated to manager and user is only an agent
        if order.escalated_to_manager and request.user.has_role('Call Center Agent') and not request.user.has_role('Call Center Manager'):
            if request.content_type == 'application/json':
                return JsonResponse({'success': False, 'error': 'This order has been escalated to manager. Only managers can modify it now.'})
            messages.error(request, "This order has been escalated to manager. Only managers can modify it now.")
            return redirect('callcenter:agent_order_detail', order_id=order_id)
        
        if not status_code:
            if request.content_type == 'application/json':
                return JsonResponse({'success': False, 'error': 'Please select a status.'})
            messages.error(request, 'Please select a status.')
            return redirect('callcenter:agent_order_detail', order_id=order_id)
        
        # Map status codes to actions (including short codes from template)
        status_mapping = {
            # Short codes from template dropdown
            'CFM': {
                'workflow_status': 'callcenter_approved',
                'status': 'confirmed',
                'message': 'Order confirmed by customer',
                'notes': 'العميل أكد الطلب كما هو.'
            },
            'NA1': {
                'workflow_status': 'callcenter_review',
                'status': 'no_answer_1st',
                'message': 'No answer - 1st attempt',
                'notes': 'أول اتصال ولم يرد.'
            },
            'NA2': {
                'workflow_status': 'callcenter_review',
                'status': 'no_answer_2nd',
                'message': 'No answer - 2nd attempt',
                'notes': 'ثاني اتصال بدون رد.'
            },
            'NA3': {
                'workflow_status': 'callcenter_review',
                'status': 'no_answer_final',
                'message': 'No answer - Final attempt',
                'notes': 'بعد 3 محاولات بدون رد ← يعتبر غير مؤكد.'
            },
            'CXL': {
                'workflow_status': 'cancelled',
                'status': 'cancelled',
                'message': 'Cancelled by customer',
                'notes': 'العميل طلب إلغاء الطلب نهائيًا.'
            },
            'HLD': {
                'workflow_status': 'callcenter_review',
                'status': 'postponed',
                'message': 'Postponed by customer',
                'notes': 'العميل طلب تأجيل الشحن / التسليم.'
            },
            'INV': {
                'workflow_status': 'callcenter_review',
                'status': 'invalid_number',
                'message': 'Invalid phone number',
                'notes': 'الرقم غير صحيح / خارج الخدمة.'
            },
            'CBK': {
                'workflow_status': 'callcenter_review',
                'status': 'call_back_later',
                'message': 'Call back requested',
                'notes': 'العميل طلب الاتصال في وقت آخر.'
            },
            'ESC': {
                'workflow_status': 'callcenter_review',
                'status': 'escalate_manager',
                'message': 'Escalated to manager',
                'notes': 'مشكلة أو استفسار يحتاج تدخل الإدارة.',
                'escalate': True
            },
            # Full status names (for modal and other uses)
            'confirmed': {
                'workflow_status': 'callcenter_approved',
                'status': 'confirmed',
                'message': 'Order confirmed by customer',
                'notes': 'العميل أكد الطلب كما هو.'
            },
            'no_answer_1st': {
                'workflow_status': 'callcenter_review',
                'status': 'no_answer_1st',
                'message': 'No answer - 1st attempt',
                'notes': 'أول اتصال ولم يرد.'
            },
            'no_answer_2nd': {
                'workflow_status': 'callcenter_review',
                'status': 'no_answer_2nd',
                'message': 'No answer - 2nd attempt',
                'notes': 'ثاني اتصال بدون رد.'
            },
            'no_answer_final': {
                'workflow_status': 'callcenter_review',
                'status': 'no_answer_final',
                'message': 'No answer - Final attempt',
                'notes': 'بعد 3 محاولات بدون رد ← يعتبر غير مؤكد.'
            },
            'cancelled': {
                'workflow_status': 'cancelled',
                'status': 'cancelled',
                'message': 'Cancelled by customer',
                'notes': 'العميل طلب إلغاء الطلب نهائيًا.'
            },
            'postponed': {
                'workflow_status': 'callcenter_review',
                'status': 'postponed',
                'message': 'Postponed by customer',
                'notes': 'العميل طلب تأجيل الشحن / التسليم.'
            },
            'invalid_number': {
                'workflow_status': 'callcenter_review',
                'status': 'invalid_number',
                'message': 'Invalid phone number',
                'notes': 'الرقم غير صحيح / خارج الخدمة.'
            },
            'call_back_later': {
                'workflow_status': 'callcenter_review',
                'status': 'call_back_later',
                'message': 'Call back requested',
                'notes': 'العميل طلب الاتصال في وقت آخر.'
            },
            'escalate_manager': {
                'workflow_status': 'callcenter_review',
                'status': 'escalate_manager',
                'message': 'Escalated to manager',
                'notes': 'مشكلة أو استفسار يحتاج تدخل الإدارة.',
                'escalate': True
            },
            'processing': {
                'workflow_status': 'pick_and_pack',
                'status': 'processing',
                'message': 'Order processing started',
                'notes': 'تم بدء معالجة الطلب.'
            },
            'packaged': {
                'workflow_status': 'packaging_completed',
                'status': 'packaged',
                'message': 'Order packaged',
                'notes': 'تم تعبئة الطلب.'
            },
            'shipped': {
                'workflow_status': 'ready_for_delivery',
                'status': 'shipped',
                'message': 'Order shipped',
                'notes': 'تم شحن الطلب.'
            },
            'delivered': {
                'workflow_status': 'delivered',
                'status': 'delivered',
                'message': 'Order delivered',
                'notes': 'تم تسليم الطلب.'
            }
        }
        
        if status_code not in status_mapping:
            # Log the invalid status code for debugging
            print(f"Invalid status code received: '{status_code}'")
            print(f"Available status codes: {list(status_mapping.keys())}")
            
            if request.content_type == 'application/json':
                return JsonResponse({
                    'success': False, 
                    'error': f'Invalid status code: {status_code}. Available codes: {", ".join(status_mapping.keys())}'
                })
            messages.error(request, f'Invalid status code: {status_code}')
            return redirect('callcenter:agent_order_detail', order_id=order_id)
        
        status_info = status_mapping[status_code]
        old_workflow_status = order.workflow_status
        old_status = order.status
        
        # Update order status
        # For call center specific statuses, keep workflow_status as is and only update status
        if status_info['status'] in ['postponed', 'call_back_later', 'invalid_number', 'no_answer_1st', 'no_answer_2nd', 'no_answer_final', 'escalate_manager']:
            order.status = status_info['status']
            # Keep workflow_status unchanged for these statuses
        else:
            order.workflow_status = status_info['workflow_status']
            order.status = status_info['status']
        
        if status_info.get('escalate', False):
            if not escalation_reason.strip():
                if request.content_type == 'application/json':
                    return JsonResponse({'success': False, 'error': 'Escalation reason is required when escalating to manager.'})
                messages.error(request, "Escalation reason is required when escalating to manager.")
                return redirect('callcenter:agent_order_detail', order_id=order_id)
            
            order.escalated_to_manager = True
            order.escalated_at = timezone.now()
            order.escalated_by = request.user
            order.escalation_reason = escalation_reason
        
        # Add edit reason to internal notes if provided
        if edit_reason:
            current_notes = order.internal_notes or ''
            timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
            new_note = f"\n[{timestamp}] Status changed to {status_info['status']}: {edit_reason}"
            order.internal_notes = current_notes + new_note
        
        # Handle postponed datetime if provided
        if status_code in ['postponed', 'HLD'] and postponed_datetime:
            try:
                from datetime import datetime
                # Parse the datetime string and save to order
                postponed_dt = datetime.fromisoformat(postponed_datetime.replace('Z', '+00:00'))
                order.postponed_until = postponed_dt
                # Add to internal notes
                current_notes = order.internal_notes or ''
                timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
                new_note = f"\n[{timestamp}] Postponed until: {postponed_dt.strftime('%Y-%m-%d %H:%M')}"
                order.internal_notes = current_notes + new_note
            except ValueError as e:
                if request.content_type == 'application/json':
                    return JsonResponse({'success': False, 'error': f'Invalid postponed datetime format: {str(e)}'})
                messages.error(request, f'Invalid postponed datetime format: {str(e)}')
                return redirect('callcenter:agent_order_detail', order_id=order_id)
        
        # Handle call back time only for call_back_later
        if status_info['status'] == 'call_back_later':
            if not call_back_time:
                if request.content_type == 'application/json':
                    return JsonResponse({'success': False, 'error': 'Call back time is required for call back later status.'})
                messages.error(request, 'Call back time is required for call back later status.')
                return redirect('callcenter:agent_order_detail', order_id=order_id)
            
            try:
                from datetime import datetime
                call_back_dt = datetime.fromisoformat(call_back_time.replace('Z', '+00:00'))
                order.call_back_time = call_back_dt
                current_notes = order.internal_notes or ''
                timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
                new_note = f"\n[{timestamp}] Call back time set to: {call_back_dt.strftime('%Y-%m-%d %H:%M')}"
                order.internal_notes = current_notes + new_note
            except ValueError as e:
                if request.content_type == 'application/json':
                    return JsonResponse({'success': False, 'error': f'Invalid call back time format: {str(e)}'})
                messages.error(request, f'Invalid call back time format: {str(e)}')
                return redirect('callcenter:agent_order_detail', order_id=order_id)
        
        # Handle no answer time for no_answer statuses
        if status_info['status'] in ['no_answer_1st', 'no_answer_2nd', 'no_answer_final']:
            if not no_answer_time:
                if request.content_type == 'application/json':
                    return JsonResponse({'success': False, 'error': 'No answer time is required for this status.'})
                messages.error(request, 'No answer time is required for this status.')
                return redirect('callcenter:agent_order_detail', order_id=order_id)
            
            try:
                from datetime import datetime
                no_answer_dt = datetime.fromisoformat(no_answer_time.replace('Z', '+00:00'))
                order.no_answer_time = no_answer_dt
                current_notes = order.internal_notes or ''
                timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
                new_note = f"\n[{timestamp}] No answer time set to: {no_answer_dt.strftime('%Y-%m-%d %H:%M')}"
                order.internal_notes = current_notes + new_note
            except ValueError as e:
                if request.content_type == 'application/json':
                    return JsonResponse({'success': False, 'error': f'Invalid no answer time format: {str(e)}'})
                messages.error(request, f'Invalid no answer time format: {str(e)}')
                return redirect('callcenter:agent_order_detail', order_id=order_id)
        
        order.save()
        
        # Create StatusLog entry
        is_manager_change = request.user.has_role('Call Center Manager')
        StatusLog.objects.create(
            order=order,
            old_status=old_status,
            new_status=status_info['status'],
            changed_by=request.user,
            change_reason=edit_reason or status_info['notes'],
            is_manager_change=is_manager_change
        )
        
        # Create workflow log
        from orders.models import OrderWorkflowLog
        OrderWorkflowLog.objects.create(
            order=order,
            from_status=old_workflow_status,
            to_status=status_info['workflow_status'],
            user=request.user,
            notes=f"{status_info['message']}: {status_info['notes']}"
        )
        
        OrderStatusHistory.objects.create(
            order=order,
            agent=request.user,
            changed_by=request.user,
            previous_status=old_status,
            new_status=status_info['status'],
            status_change_reason=f"{status_info['message']}: {status_info['notes']}",
            change_timestamp=timezone.now()
        )
        
        from datetime import datetime
        call_status_mapping = {
            'confirmed': 'completed',
            'no_answer_1st': 'no_answer',
            'no_answer_2nd': 'no_answer',
            'no_answer_final': 'no_answer',
            'cancelled': 'completed',
            'postponed': 'call_back',
            'invalid_number': 'wrong_number',
            'call_back_later': 'call_back',
            'escalate_manager': 'escalated',
        }
        
        call_time = timezone.now()
        if call_time_str:
            try:
                call_time = datetime.fromisoformat(call_time_str.replace('Z', '+00:00'))
                if timezone.is_naive(call_time):
                    call_time = timezone.make_aware(call_time)
            except:
                call_time = timezone.now()
        
        call_status = call_status_mapping.get(status_info['status'], 'completed')
        
        CallLog.objects.create(
            order=order,
            agent=request.user,
            call_time=call_time,
            status=call_status,
            notes=status_info['notes'],
            resolution_status='resolved' if status_info['status'] == 'confirmed' else 'pending'
        )
        
        if request.content_type == 'application/json':
            return JsonResponse({
                'success': True, 
                'message': f'Order {order.order_code} status updated: {status_info["message"]}',
                'new_status': status_info['status'],
                'workflow_status': status_info['workflow_status']
            })
        
        messages.success(request, f'Order {order.order_code} status updated: {status_info["message"]}')
        return redirect('callcenter:agent_order_detail', order_id=order_id)
        
    except Exception as e:
        if request.content_type == 'application/json':
            return JsonResponse({'success': False, 'error': f'Error updating order status: {str(e)}'})
        messages.error(request, f'Error updating order status: {str(e)}')
        return redirect('callcenter:agent_order_detail', order_id=order_id)


@login_required
def order_status_log(request, order_id):
    """Display status change log for an order."""
    order = get_object_or_404(Order, id=order_id)
    
    # Check permissions
    if not (request.user.has_role('Call Center Agent') or 
            request.user.has_role('Call Center Manager') or 
            request.user.is_superuser):
        messages.error(request, "You don't have permission to view this page.")
        return redirect('callcenter:dashboard')
    
    # Get status logs for this order
    status_logs = StatusLog.objects.filter(order=order).order_by('-timestamp')
    
    # Get manager change count
    manager_changes = status_logs.filter(is_manager_change=True).count()
    
    context = {
        'order': order,
        'status_logs': status_logs,
        'manager_changes': manager_changes,
    }
    
    return render(request, 'callcenter/order_status_log.html', context)


@login_required
def agent_edit_order(request, order_id):
    """Edit order details after confirmation."""
    order = get_object_or_404(Order, id=order_id)
    
    # Check if user has permission to edit this order
    if not (request.user.has_role('Call Center Agent') or request.user.has_role('Call Center Manager') or request.user.is_superuser):
        if request.content_type == 'application/json':
            return JsonResponse({'success': False, 'error': 'You don\'t have permission to edit this order.'})
        messages.error(request, 'You don\'t have permission to edit this order.')
        return redirect('callcenter:agent_order_detail', order_id=order_id)
    
    # Handle GET request - redirect to order detail
    if request.method == 'GET':
        if request.user.has_role('Call Center Manager'):
            return redirect('callcenter:order_detail', order_id=order_id)
        return redirect('callcenter:agent_order_detail', order_id=order_id)
    
    # Handle POST request
    try:
        # Handle JSON data
        if request.content_type == 'application/json':
            import json
            data = json.loads(request.body)
        else:
            data = request.POST
        
        # Update order fields
        order.customer = data.get('customer', order.customer)
        order.customer_phone = data.get('customer_phone', order.customer_phone)
        order.quantity = int(data.get('quantity', order.quantity))
        order.price_per_unit = float(data.get('price_per_unit', order.price_per_unit))
        order.shipping_address = data.get('shipping_address', order.shipping_address)
        order.city = data.get('city', order.city)
        order.state = data.get('state', order.state)
        order.zip_code = data.get('zip_code', order.zip_code)
        order.emirate = data.get('emirate', order.emirate)
        order.region = data.get('region', order.region)
        
        # Add additional phone to notes if provided
        additional_phone = data.get('additional_phone', '')
        if additional_phone:
            current_notes = order.notes or ''
            timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
            new_note = f"\n[{timestamp}] Additional contact: {additional_phone}"
            order.notes = current_notes + new_note
        
        # Add edit log to internal notes
        current_internal_notes = order.internal_notes or ''
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
        edit_log = f"\n[{timestamp}] Order edited by {request.user.get_full_name() or request.user.username}"
        order.internal_notes = current_internal_notes + edit_log
        
        order.save()
        
        if request.content_type == 'application/json':
            return JsonResponse({
                'success': True, 
                'message': f'Order {order.order_code} updated successfully'
            })
        
        messages.success(request, f'Order {order.order_code} updated successfully')
        if request.user.has_role('Call Center Manager'):
            return redirect('callcenter:order_detail', order_id=order_id)
        return redirect('callcenter:agent_order_detail', order_id=order_id)
        
    except Exception as e:
        if request.content_type == 'application/json':
            return JsonResponse({'success': False, 'error': f'Error updating order: {str(e)}'})
        messages.error(request, f'Error updating order: {str(e)}')
        if request.user.has_role('Call Center Manager'):
            return redirect('callcenter:order_detail', order_id=order_id)
        return redirect('callcenter:agent_order_detail', order_id=order_id)

@login_required
def agent_log_call(request, order_id):
    """Log call for order by call center agent."""
    try:
        order = get_object_or_404(Order, id=order_id)
        
        # Check if user has permission to log calls for this order
        if not request.user.has_role('Call Center Agent') and not request.user.is_superuser:
            messages.error(request, "You don't have permission to log calls.")
            return redirect('callcenter:agent_order_detail', order_id=order_id)
        
        if request.method == 'POST':
            # Handle call logging form submission
            call_type = request.POST.get('call_type')
            call_status = request.POST.get('call_status')
            resolution_status = request.POST.get('resolution_status')
            satisfaction = request.POST.get('satisfaction')
            notes = request.POST.get('notes')
            duration = request.POST.get('duration', 0)
            
            try:
                duration = int(duration) if duration else 0
            except (ValueError, TypeError):
                duration = 0
            
            # Create call log
            CallLog.objects.create(
                order=order,
                agent=request.user,
                status=call_status,
                resolution_status=resolution_status,
                customer_satisfaction=satisfaction,
                notes=notes,
                duration=duration
            )
            
            messages.success(request, 'Call logged successfully.')
            return redirect('callcenter:agent_order_detail', order_id=order_id)
        
        # Render call logging form
        context = {
            'order': order,
        }
        return render(request, 'callcenter/agent/log_call.html', context)
        
    except Exception as e:
        messages.error(request, f'Error logging call: {str(e)}')
        return redirect('callcenter:agent_order_detail', order_id=order_id)

@login_required
def order_list(request):
    """General order list view."""
    if request.user.has_role('Call Center Manager'):
        return redirect('callcenter:manager_order_list')
    elif request.user.has_role('Call Center Agent'):
        return redirect('callcenter:agent_order_list')
    else:
        return redirect('callcenter:dashboard')

@login_required
@user_passes_test(is_call_center_manager)
def manager_assign_order(request, order_id):
    """Assign order to an agent."""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        agent_id = request.POST.get('agent_id')
        if agent_id:
            try:
                agent = User.objects.get(id=agent_id)
                order.agent = agent
                order.save()
                
                # Log the assignment
                OrderStatusHistory.objects.create(
                    order=order,
                    status='assigned',
                    changed_by=request.user,
                    notes=f'Order assigned to {agent.get_full_name()}'
                )
                
                messages.success(request, f'Order assigned to {agent.get_full_name()}')
                return redirect('callcenter:order_detail', order_id=order.id)
            except User.DoesNotExist:
                messages.error(request, 'Agent not found')
        else:
            messages.error(request, 'Please select an agent')
    
    # Get available agents
    agents = User.objects.filter(
        user_roles__role__name='Call Center Agent',
        user_roles__is_active=True,
        is_active=True
    ).distinct()
    
    context = {
        'order': order,
        'agents': agents,
    }
    return render(request, 'callcenter/manager/assign_order.html', context)

@login_required
@user_passes_test(is_call_center_manager)
def manager_reassign_order(request, order_id):
    """Reassign order to another agent."""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        agent_id = request.POST.get('agent_id')
        if agent_id:
            try:
                old_agent = order.agent
                agent = User.objects.get(id=agent_id)
                order.agent = agent
                order.save()
                
                # Log the reassignment
                OrderStatusHistory.objects.create(
                    order=order,
                    status='reassigned',
                    changed_by=request.user,
                    notes=f'Order reassigned from {old_agent.get_full_name() if old_agent else "Unassigned"} to {agent.get_full_name()}'
                )
                
                messages.success(request, f'Order reassigned to {agent.get_full_name()}')
                return redirect('callcenter:order_detail', order_id=order.id)
            except User.DoesNotExist:
                messages.error(request, 'Agent not found')
        else:
            messages.error(request, 'Please select an agent')
    
    # Get available agents (excluding current agent)
    agents = User.objects.filter(
        user_roles__role__name='Call Center Agent',
        user_roles__is_active=True,
        is_active=True
    ).exclude(id=order.agent.id if order.agent else None).distinct()
    
    context = {
        'order': order,
        'agents': agents,
    }
    return render(request, 'callcenter/manager/reassign_order.html', context)

@login_required
@user_passes_test(is_call_center_manager)
def manager_log_call(request, order_id):
    """Log a call for manager."""
    order = get_object_or_404(Order, id=order_id)
    
    if request.method == 'POST':
        call_type = request.POST.get('call_type')
        call_status = request.POST.get('call_status')
        outcome = request.POST.get('outcome')
        notes = request.POST.get('notes')
        duration = request.POST.get('duration', 0)
        customer_name = request.POST.get('customer_name')
        phone_number = request.POST.get('phone_number')
        
        # Action items
        follow_up = request.POST.get('follow_up') == 'on'
        send_info = request.POST.get('send_info') == 'on'
        escalate = request.POST.get('escalate') == 'on'
        
        try:
            # Create call log
            call_log = CallLog.objects.create(
                order=order,
                agent=request.user,
                call_type=call_type,
                outcome=outcome,
                notes=notes,
                duration=int(duration) if duration else 0
            )
            
            # Add action items to notes if any
            action_items = []
            if follow_up:
                action_items.append("Schedule follow-up call")
            if send_info:
                action_items.append("Send additional information")
            if escalate:
                action_items.append("Escalate to supervisor")
            
            if action_items:
                call_log.notes += f"\n\nAction Items: {', '.join(action_items)}"
                call_log.save()
            
            messages.success(request, 'Call logged successfully.')
            return redirect('callcenter:order_detail', order_id=order.id)
        except Exception as e:
            messages.error(request, f'Error logging call: {str(e)}')
    
    context = {
        'order': order,
    }
    return render(request, 'callcenter/manager/log_call.html', context)

@login_required
@require_POST
def escalate_to_manager(request, order_id):
    """Escalate order to manager with required reason."""
    if not has_callcenter_role(request.user):
        messages.error(request, "ليس لديك صلاحية للدخول لهذه الصفحة.")
        return redirect('dashboard:index')
    
    order = get_object_or_404(Order, id=order_id)
    escalation_reason = request.POST.get('escalation_reason', '').strip()
    postponed_datetime = request.POST.get('postponed_datetime', '').strip()
    
    if not escalation_reason:
        messages.error(request, "يجب كتابة سبب التصعيد للمدير.")
        return redirect('callcenter:agent_order_detail', order_id=order_id)
    
    try:
        # Update order with escalation
        order.escalated_to_manager = True
        order.escalated_at = timezone.now()
        order.escalated_by = request.user
        order.escalation_reason = escalation_reason
        order.status = 'escalate_manager'
        order.save()
        
        # Add escalation note to internal notes
        current_notes = order.internal_notes or ''
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
        escalation_note = f"\n[{timestamp}] ESCALATED TO MANAGER by {request.user.get_full_name()}: {escalation_reason}"
        
        # Handle postponed datetime if provided
        if postponed_datetime:
            try:
                from datetime import datetime
                postponed_dt = datetime.fromisoformat(postponed_datetime.replace('Z', '+00:00'))
                order.postponed_until = postponed_dt
                escalation_note += f"\n[{timestamp}] Postponed until: {postponed_dt.strftime('%Y-%m-%d %H:%M')}"
            except ValueError as e:
                messages.error(request, f'Invalid postponed datetime format: {str(e)}')
                return redirect('callcenter:agent_order_detail', order_id=order_id)
        
        order.internal_notes = current_notes + escalation_note
        order.save()
        
        # Create status log
        StatusLog.objects.create(
            order=order,
            old_status=order.status,
            new_status='escalate_manager',
            changed_by=request.user,
            change_reason=f"Escalated to manager: {escalation_reason}",
            is_manager_change=False
        )
        
        messages.success(request, f'تم تصعيد الطلب {order.order_code} للمدير بنجاح.')
        
    except Exception as e:
        messages.error(request, f'حدث خطأ أثناء تصعيد الطلب: {str(e)}')
    
    return redirect('callcenter:agent_order_detail', order_id=order_id)

@login_required
@require_POST
def deescalate_order(request, order_id):
    """De-escalate order from manager back to agent."""
    if not (request.user.has_role('Call Center Manager') or request.user.is_superuser):
        messages.error(request, "ليس لديك صلاحية لإلغاء التصعيد.")
        return redirect('callcenter:manager_dashboard')
    
    order = get_object_or_404(Order, id=order_id)
    deescalation_reason = request.POST.get('deescalation_reason', '').strip()
    
    if not deescalation_reason:
        messages.error(request, "يجب كتابة سبب إلغاء التصعيد.")
        return redirect('callcenter:manager_dashboard')
    
    try:
        # Update order to remove escalation
        order.escalated_to_manager = False
        order.escalated_at = None
        order.escalated_by = None
        order.escalation_reason = ''
        order.status = 'pending'  # Reset to pending
        order.save()
        
        # Add de-escalation note to internal notes
        current_notes = order.internal_notes or ''
        timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
        deescalation_note = f"\n[{timestamp}] DE-ESCALATED by {request.user.get_full_name()}: {deescalation_reason}"
        order.internal_notes = current_notes + deescalation_note
        order.save()
        
        # Create call log entry
        CallLog.objects.create(
            order=order,
            agent=request.user,
            call_time=timezone.now(),
            duration=0,
            status='completed',
            notes=f'Manager de-escalated order: {deescalation_reason}',
            resolution_status='pending',
            escalation_reason=''
        )
        
        # Create status log
        StatusLog.objects.create(
            order=order,
            old_status='escalate_manager',
            new_status='pending',
            changed_by=request.user,
            change_reason=f'Order de-escalated: {deescalation_reason}',
            is_manager_change=True
        )
        
        messages.success(request, f'تم إلغاء تصعيد الطلب #{order.order_code} بنجاح.')
        
    except Exception as e:
        messages.error(request, f'حدث خطأ في إلغاء التصعيد: {str(e)}')
    
    return redirect('callcenter:manager_dashboard')

@login_required
def accept_order(request, order_id):
    """Accept escalated order."""
    if not has_callcenter_role(request.user):
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية للدخول لهذه الصفحة.'})
    
    try:
        order = get_object_or_404(Order, id=order_id)
        
        if request.method == 'POST':
            import json
            data = json.loads(request.body)
            manager_note = data.get('manager_note', 'تم قبول الطلب من المدير')
            
            # Update order status
            order.status = 'confirmed'
            order.escalated_to_manager = False
            order.escalated_at = None
            order.escalated_by = None
            order.escalation_reason = ''
            
            # Add manager note to internal notes
            current_notes = order.internal_notes or ''
            timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
            new_note = f"\n[{timestamp}] MANAGER ACCEPTED by {request.user.get_full_name()}: {manager_note}"
            order.internal_notes = current_notes + new_note
            
            order.save()
            
            # Create call log entry
            CallLog.objects.create(
                order=order,
                agent=request.user,
                call_time=timezone.now(),
                duration=0,
                status='completed',
                notes=f'Manager accepted order: {manager_note}',
                resolution_status='resolved',
                escalation_reason=''
            )
            
            # Create status history entry
            StatusLog.objects.create(
                order=order,
                old_status='escalate_manager',
                new_status='confirmed',
                changed_by=request.user,
                change_reason=f'Manager accepted order: {manager_note}',
                is_manager_change=True
            )
            
            return JsonResponse({'success': True, 'message': 'تم قبول الطلب بنجاح'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'حدث خطأ: {str(e)}'})
    
    return JsonResponse({'success': False, 'error': 'طريقة طلب غير صحيحة'})

@login_required
def resolve_order(request, order_id):
    """Mark escalated order as resolved."""
    if not has_callcenter_role(request.user):
        return JsonResponse({'success': False, 'error': 'ليس لديك صلاحية للدخول لهذه الصفحة.'})
    
    try:
        order = get_object_or_404(Order, id=order_id)
        
        if request.method == 'POST':
            import json
            data = json.loads(request.body)
            resolution_note = data.get('resolution_note', '')
            
            if not resolution_note.strip():
                return JsonResponse({'success': False, 'error': 'يجب كتابة ملاحظة الحل'})
            
            # Update order status
            order.status = 'completed'
            order.escalated_to_manager = False
            order.escalated_at = None
            order.escalated_by = None
            order.escalation_reason = ''
            
            # Add resolution note to internal notes
            current_notes = order.internal_notes or ''
            timestamp = timezone.now().strftime('%Y-%m-%d %H:%M')
            new_note = f"\n[{timestamp}] MANAGER RESOLVED by {request.user.get_full_name()}: {resolution_note}"
            order.internal_notes = current_notes + new_note
            
            order.save()
            
            # Create call log entry
            CallLog.objects.create(
                order=order,
                agent=request.user,
                call_time=timezone.now(),
                duration=0,
                status='completed',
                notes=f'Manager resolved order: {resolution_note}',
                resolution_status='resolved',
                escalation_reason=''
            )
            
            # Create status history entry
            StatusLog.objects.create(
                order=order,
                old_status='escalate_manager',
                new_status='completed',
                changed_by=request.user,
                change_reason=f'Manager resolved order: {resolution_note}',
                is_manager_change=True
            )
            
            return JsonResponse({'success': True, 'message': 'تم حل الطلب بنجاح'})
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': f'حدث خطأ: {str(e)}'})
    
    return JsonResponse({'success': False, 'error': 'طريقة طلب غير صحيحة'})

# Enhanced Dashboard Views for Phase 4

@login_required
@user_passes_test(has_callcenter_role)
def enhanced_dashboard(request):
    """Enhanced call center dashboard with real-time metrics."""
    from django.db.models.functions import TruncDate, TruncHour
    
    today = timezone.now().date()
    now = timezone.now()
    start_of_day = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    
    # Real-time agent metrics
    active_agents = AgentSession.objects.filter(
        status__in=['available', 'busy'],
        last_activity__gte=now - timedelta(minutes=5)
    ).count()
    
    total_agents = AgentSession.objects.filter(
        login_time__gte=start_of_day
    ).values('agent').distinct().count()
    
    # Today's call statistics
    today_calls = CallLog.objects.filter(call_time__gte=start_of_day)
    today_stats = today_calls.aggregate(
        total_calls=Count('id'),
        completed_calls=Count('id', filter=Q(status='completed')),
        average_duration=Avg('duration'),
        average_satisfaction=Avg('customer_satisfaction', filter=Q(customer_satisfaction__isnull=False))
    )
    
    # Order statistics
    today_orders = Order.objects.filter(created_at__gte=start_of_day)
    order_stats = today_orders.aggregate(
        total_orders=Count('id'),
        confirmed_orders=Count('id', filter=Q(status='CONFIRMED')),
        cancelled_orders=Count('id', filter=Q(status='CANCELLED')),
        pending_orders=Count('id', filter=Q(status='PENDING'))
    )
    
    # Hourly performance data for charts
    hourly_calls = CallLog.objects.filter(
        call_time__gte=start_of_day
    ).annotate(
        hour=TruncHour('call_time')
    ).values('hour').annotate(
        count=Count('id')
    ).order_by('hour')
    
    # Top performers today
    top_performers = AgentPerformance.objects.filter(
        date=today
    ).select_related('agent').order_by('-orders_confirmed')[:5]
    
    # Active sessions by status
    session_stats = AgentSession.objects.filter(
        last_activity__gte=now - timedelta(minutes=10)
    ).values('status').annotate(count=Count('id'))
    
    # Pending follow-ups
    pending_followups = CustomerInteraction.objects.filter(
        follow_up_date__lte=now + timedelta(days=1),
        resolution_status='follow_up_required'
    ).count()
    
    # Escalated issues
    escalated_count = CustomerInteraction.objects.filter(
        resolution_status='escalated',
        interaction_time__gte=start_of_day
    ).count()
    
    context = {
        'active_agents': active_agents,
        'total_agents': total_agents,
        'today_stats': today_stats,
        'order_stats': order_stats,
        'hourly_calls': list(hourly_calls),
        'top_performers': top_performers,
        'session_stats': list(session_stats),
        'pending_followups': pending_followups,
        'escalated_count': escalated_count,
        'current_time': now,
    }
    
    return render(request, 'callcenter/enhanced_dashboard.html', context)


@login_required
@user_passes_test(has_callcenter_role)
def real_time_metrics(request):
    """API endpoint for real-time dashboard metrics."""
    now = timezone.now()
    today = now.date()
    start_of_day = timezone.make_aware(datetime.combine(today, datetime.min.time()))
    
    # Get current metrics
    active_agents = AgentSession.objects.filter(
        status__in=['available', 'busy'],
        last_activity__gte=now - timedelta(minutes=5)
    )
    
    metrics = {
        'timestamp': now.isoformat(),
        'agents': {
            'active': active_agents.count(),
            'available': active_agents.filter(status='available').count(),
            'busy': active_agents.filter(status='busy').count(),
            'on_break': AgentSession.objects.filter(
                status='break',
                last_activity__gte=now - timedelta(minutes=30)
            ).count(),
        },
        'calls': {
            'today_total': CallLog.objects.filter(call_time__gte=start_of_day).count(),
            'last_hour': CallLog.objects.filter(
                call_time__gte=now - timedelta(hours=1)
            ).count(),
            'in_progress': AgentSession.objects.filter(
                status='busy',
                last_activity__gte=now - timedelta(minutes=5)
            ).count(),
        },
        'orders': {
            'pending': Order.objects.filter(status='PENDING').count(),
            'confirmed_today': Order.objects.filter(
                status='CONFIRMED',
                updated_at__gte=start_of_day
            ).count(),
        },
        'alerts': {
            'pending_followups': CustomerInteraction.objects.filter(
                follow_up_date__lte=now + timedelta(hours=2),
                resolution_status='follow_up_required'
            ).count(),
            'escalated': CustomerInteraction.objects.filter(
                resolution_status='escalated',
                interaction_time__gte=start_of_day
            ).count(),
        }
    }
    
    return JsonResponse(metrics)

# Bulk Operations Views

@login_required
@user_passes_test(is_call_center_manager)
@require_POST
def bulk_assign_orders(request):
    """Bulk assign orders to agents."""
    try:
        order_ids = request.POST.getlist('order_ids[]')
        agent_id = request.POST.get('agent_id')
        priority = request.POST.get('priority', 'medium')
        notes = request.POST.get('notes', '')
        
        if not order_ids or not agent_id:
            return JsonResponse({
                'success': False,
                'message': 'Order IDs and Agent ID are required'
            }, status=400)
        
        agent = get_object_or_404(User, id=agent_id)
        orders = Order.objects.filter(id__in=order_ids)
        
        assignments_created = 0
        for order in orders:
            OrderAssignment.objects.create(
                order=order,
                manager=request.user,
                agent=agent,
                priority_level=priority,
                manager_notes=notes
            )
            
            # Update order agent
            order.call_center_agent = agent
            order.save()
            
            assignments_created += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully assigned {assignments_created} orders to {agent.get_full_name()}',
            'assigned_count': assignments_created
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error assigning orders: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(is_call_center_manager)
@require_POST
def bulk_update_order_status(request):
    """Bulk update order status."""
    try:
        order_ids = request.POST.getlist('order_ids[]')
        new_status = request.POST.get('status')
        reason = request.POST.get('reason', '')
        
        if not order_ids or not new_status:
            return JsonResponse({
                'success': False,
                'message': 'Order IDs and status are required'
            }, status=400)
        
        orders = Order.objects.filter(id__in=order_ids)
        updated_count = 0
        
        for order in orders:
            old_status = order.status
            order.status = new_status
            order.save()
            
            # Create status history
            OrderStatusHistory.objects.create(
                order=order,
                agent=request.user,
                changed_by=request.user,
                previous_status=old_status,
                new_status=new_status,
                status_change_reason=reason
            )
            
            updated_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully updated {updated_count} orders',
            'updated_count': updated_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error updating orders: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(is_call_center_manager)
def bulk_operations_panel(request):
    """Bulk operations management panel."""
    from django.core.paginator import Paginator

    # Get available agents with their session status
    available_agents = User.objects.filter(
        is_active=True,
        user_roles__role__name__icontains='Call Center'
    ).select_related('agentsession_set__agent').distinct()

    # Get filter parameters
    status_filter = request.GET.get('status', '')
    date_range = request.GET.get('date_range', 'today')
    priority_filter = request.GET.get('priority', '')

    # Build query
    orders = Order.objects.select_related('customer').prefetch_related('assignments__agent')

    # Apply status filter
    if status_filter:
        orders = orders.filter(status=status_filter)

    # Apply date range filter
    today = timezone.now().date()
    if date_range == 'today':
        start_date = timezone.make_aware(datetime.combine(today, datetime.min.time()))
        orders = orders.filter(created_at__gte=start_date)
    elif date_range == 'week':
        start_date = today - timedelta(days=7)
        orders = orders.filter(created_at__gte=start_date)
    elif date_range == 'month':
        start_date = today - timedelta(days=30)
        orders = orders.filter(created_at__gte=start_date)

    # Apply priority filter (if orders have priority on assignments)
    if priority_filter:
        orders = orders.filter(assignments__priority_level=priority_filter)

    # Order by created date descending
    orders = orders.order_by('-created_at').distinct()

    # Pagination
    paginator = Paginator(orders, 50)  # 50 orders per page
    page_number = request.GET.get('page', 1)
    page_obj = paginator.get_page(page_number)

    context = {
        'available_agents': available_agents,
        'orders': page_obj,
        'page_obj': page_obj,
        'is_paginated': page_obj.has_other_pages(),
    }

    return render(request, 'callcenter/bulk_operations.html', context)


@login_required
@user_passes_test(has_callcenter_role)
@require_POST
def bulk_create_followups(request):
    """Bulk create follow-up interactions for orders."""
    try:
        order_ids = request.POST.getlist('order_ids[]')
        followup_date_str = request.POST.get('followup_date')
        notes = request.POST.get('notes', '')
        
        if not order_ids or not followup_date_str:
            return JsonResponse({
                'success': False,
                'message': 'Order IDs and follow-up date are required'
            }, status=400)
        
        followup_date = datetime.fromisoformat(followup_date_str)
        orders = Order.objects.filter(id__in=order_ids)
        
        created_count = 0
        for order in orders:
            CustomerInteraction.objects.create(
                order=order,
                agent=request.user,
                customer=order.customer,
                interaction_type='follow_up',
                resolution_status='follow_up_required',
                interaction_notes=notes,
                follow_up_date=followup_date
            )
            created_count += 1
        
        return JsonResponse({
            'success': True,
            'message': f'Successfully created {created_count} follow-ups',
            'created_count': created_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': f'Error creating follow-ups: {str(e)}'
        }, status=500)


@login_required
def export_orders_csv(request):
    """Export orders to CSV - RESTRICTED TO SUPER ADMIN ONLY."""
    import csv
    from django.http import HttpResponse
    from users.models import AuditLog

    # SECURITY: Restrict data export to Super Admin only (P0 CRITICAL requirement)
    if not request.user.is_superuser:
        from utils.views import permission_denied_authenticated
        AuditLog.objects.create(
            user=request.user,
            action='unauthorized_export_attempt',
            entity_type='order',
            description=f"Unauthorized attempt to export orders by {request.user.email}",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        return permission_denied_authenticated(
            request,
            message="Data export is restricted to Super Admin only for security compliance."
        )
    
    order_ids = request.GET.getlist('order_ids[]')
    status_filter = request.GET.get('status')
    
    # Build query
    query = Order.objects.all()
    if order_ids:
        query = query.filter(id__in=order_ids)
    if status_filter:
        query = query.filter(status=status_filter)
    
    query = query.select_related('customer', 'call_center_agent')[:1000]
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv; charset=utf-8')
    response['Content-Disposition'] = f'attachment; filename="orders_{timezone.now().strftime("%Y%m%d_%H%M%S")}.csv"'
    response.write('\ufeff')  # UTF-8 BOM for Excel
    
    writer = csv.writer(response)
    writer.writerow([
        'Order ID', 'Customer Name', 'Customer Phone', 'Status',
        'Agent', 'Created Date', 'Total Amount', 'Payment Status'
    ])
    
    for order in query:
        writer.writerow([
            order.id,
            order.customer.get_full_name() if order.customer else 'N/A',
            order.customer_phone or 'N/A',
            order.status,
            order.call_center_agent.get_full_name() if order.call_center_agent else 'Unassigned',
            order.created_at.strftime('%Y-%m-%d %H:%M'),
            order.total_amount,
            order.payment_status
        ])

    # Audit log for successful export (P0 CRITICAL security requirement)
    AuditLog.objects.create(
        user=request.user,
        action='data_export',
        entity_type='order',
        description=f"Exported {query.count()} orders to CSV",
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )

    return response


# ============================================
# Callbacks Management Views
# ============================================

@login_required
def callbacks_list(request):
    """List all scheduled callbacks"""
    from orders.models import Order

    # Get callbacks (orders marked for follow-up)
    callbacks = Order.objects.filter(
        needs_followup=True
    ).select_related('customer', 'call_center_agent').order_by('followup_date')

    # Filter by status
    status = request.GET.get('status', '')
    if status == 'pending':
        callbacks = callbacks.filter(followup_completed=False)
    elif status == 'completed':
        callbacks = callbacks.filter(followup_completed=True)
    elif status == 'overdue':
        callbacks = callbacks.filter(
            followup_completed=False,
            followup_date__lt=timezone.now()
        )

    # Filter by agent (for managers)
    agent_id = request.GET.get('agent', '')
    if agent_id:
        callbacks = callbacks.filter(call_center_agent_id=agent_id)

    # For agents, show only their callbacks
    if hasattr(request.user, 'role') and request.user.role == 'call_center_agent':
        callbacks = callbacks.filter(call_center_agent=request.user)

    # Statistics
    stats = {
        'total': callbacks.count(),
        'pending': callbacks.filter(followup_completed=False).count(),
        'completed_today': callbacks.filter(
            followup_completed=True,
            updated_at__date=timezone.now().date()
        ).count(),
        'overdue': callbacks.filter(
            followup_completed=False,
            followup_date__lt=timezone.now()
        ).count(),
    }

    # Get agents for filter dropdown
    agents = User.objects.filter(role='call_center_agent', is_active=True)

    # Pagination
    paginator = Paginator(callbacks, 20)
    page = request.GET.get('page', 1)
    callbacks_page = paginator.get_page(page)

    return render(request, 'callcenter/callbacks_list.html', {
        'callbacks': callbacks_page,
        'stats': stats,
        'agents': agents,
        'current_status': status,
        'current_agent': agent_id,
        'now': timezone.now(),
    })


@login_required
def create_callback(request):
    """Create a new callback/follow-up"""
    from orders.models import Order

    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        followup_date = request.POST.get('followup_date')
        followup_notes = request.POST.get('notes', '')

        try:
            order = Order.objects.get(id=order_id)
            order.needs_followup = True
            order.followup_date = followup_date
            order.followup_notes = followup_notes
            order.save()

            messages.success(request, f'Callback scheduled for order #{order.id}')
            return redirect('callcenter:callbacks')
        except Order.DoesNotExist:
            messages.error(request, 'Order not found')

    # Get orders that can have callbacks
    orders = Order.objects.filter(
        needs_followup=False
    ).exclude(
        status__in=['delivered', 'cancelled']
    ).select_related('customer')[:100]

    return render(request, 'callcenter/create_callback.html', {
        'orders': orders,
    })


@login_required
def complete_callback(request, callback_id):
    """Mark a callback as completed"""
    from orders.models import Order

    try:
        order = Order.objects.get(id=callback_id)

        if request.method == 'POST':
            order.followup_completed = True
            order.followup_completed_at = timezone.now()
            order.followup_completed_by = request.user

            # Add call log entry
            outcome = request.POST.get('outcome', '')
            notes = request.POST.get('notes', '')

            CallLog.objects.create(
                order=order,
                agent=request.user,
                call_type='followup',
                outcome=outcome,
                notes=notes,
                duration=int(request.POST.get('duration', 0))
            )

            order.save()
            messages.success(request, f'Callback for order #{order.id} marked as completed')
            return redirect('callcenter:callbacks')

        return render(request, 'callcenter/complete_callback.html', {
            'order': order,
        })
    except Order.DoesNotExist:
        messages.error(request, 'Callback not found')
        return redirect('callcenter:callbacks')


# ============================================
# Agents Management Views
# ============================================

@login_required
def agents_list(request):
    """List all call center agents"""
    agents = User.objects.filter(
        role='call_center_agent'
    ).annotate(
        total_orders=Count('assigned_orders'),
        completed_orders=Count('assigned_orders', filter=Q(assigned_orders__status='delivered')),
        pending_orders=Count('assigned_orders', filter=Q(assigned_orders__status__in=['pending', 'confirmed'])),
    ).order_by('-is_active', 'first_name')

    # Filter by status
    status = request.GET.get('status', '')
    if status == 'active':
        agents = agents.filter(is_active=True)
    elif status == 'inactive':
        agents = agents.filter(is_active=False)

    # Statistics
    stats = {
        'total_agents': agents.count(),
        'active_agents': agents.filter(is_active=True).count(),
        'online_agents': agents.filter(is_active=True, last_login__gte=timezone.now() - timedelta(hours=1)).count(),
    }

    return render(request, 'callcenter/agents_list.html', {
        'agents': agents,
        'stats': stats,
        'current_status': status,
    })


@login_required
def agent_performance(request, agent_id):
    """View agent performance metrics"""
    from orders.models import Order

    agent = get_object_or_404(User, id=agent_id, role='call_center_agent')

    # Date range
    days = int(request.GET.get('days', 30))
    start_date = timezone.now() - timedelta(days=days)

    # Get orders handled by this agent
    orders = Order.objects.filter(
        call_center_agent=agent,
        created_at__gte=start_date
    )

    # Performance metrics
    total_orders = orders.count()
    confirmed_orders = orders.filter(status__in=['confirmed', 'processing', 'shipped', 'delivered']).count()
    cancelled_orders = orders.filter(status='cancelled').count()

    confirmation_rate = (confirmed_orders / total_orders * 100) if total_orders > 0 else 0

    # Call logs
    call_logs = CallLog.objects.filter(
        agent=agent,
        created_at__gte=start_date
    )

    total_calls = call_logs.count()
    avg_call_duration = call_logs.aggregate(avg=Avg('duration'))['avg'] or 0

    # Daily breakdown
    from django.db.models.functions import TruncDate
    daily_stats = orders.annotate(
        date=TruncDate('created_at')
    ).values('date').annotate(
        count=Count('id')
    ).order_by('-date')[:30]

    return render(request, 'callcenter/agent_performance.html', {
        'agent': agent,
        'days': days,
        'total_orders': total_orders,
        'confirmed_orders': confirmed_orders,
        'cancelled_orders': cancelled_orders,
        'confirmation_rate': confirmation_rate,
        'total_calls': total_calls,
        'avg_call_duration': avg_call_duration,
        'daily_stats': daily_stats,
    })


@login_required
def agent_schedule(request, agent_id):
    """View and manage agent schedule"""
    agent = get_object_or_404(User, id=agent_id, role='call_center_agent')

    if request.method == 'POST':
        # Update schedule
        schedule_data = {
            'monday': request.POST.get('monday', ''),
            'tuesday': request.POST.get('tuesday', ''),
            'wednesday': request.POST.get('wednesday', ''),
            'thursday': request.POST.get('thursday', ''),
            'friday': request.POST.get('friday', ''),
            'saturday': request.POST.get('saturday', ''),
            'sunday': request.POST.get('sunday', ''),
        }

        # Store schedule in user profile or separate model
        # For now, store in session or a simple field
        agent.schedule_json = json.dumps(schedule_data)
        agent.save()

        messages.success(request, f'Schedule updated for {agent.get_full_name()}')
        return redirect('callcenter:agents')

    # Get current schedule
    schedule = {}
    if hasattr(agent, 'schedule_json') and agent.schedule_json:
        try:
            schedule = json.loads(agent.schedule_json)
        except:
            schedule = {}

    return render(request, 'callcenter/agent_schedule.html', {
        'agent': agent,
        'schedule': schedule,
    })
