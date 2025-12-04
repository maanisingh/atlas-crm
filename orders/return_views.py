from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.db.models import Q, Count, Sum
from django.http import JsonResponse, HttpResponseForbidden
from django.views.decorators.http import require_http_methods

from .models import Return, ReturnItem, ReturnStatusLog, Order, OrderItem
from .return_forms import (
    ReturnRequestForm, ReturnItemSelectionForm, ReturnApprovalForm,
    ReturnShippingForm, ReturnInspectionForm, RefundProcessingForm,
    ReturnCustomerContactForm, ReturnFilterForm
)
from utils.decorators import role_required, any_role_required


# ============================================
# Customer-Facing Views
# ============================================

@login_required
def customer_returns_list(request):
    """List all returns for the current customer"""
    returns = Return.objects.filter(customer=request.user).select_related(
        'order', 'approved_by', 'inspector', 'refund_processed_by'
    ).order_by('-created_at')

    # Apply filters if any
    filter_form = ReturnFilterForm(request.GET)
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('return_status'):
            returns = returns.filter(return_status__in=filter_form.cleaned_data['return_status'])
        if filter_form.cleaned_data.get('refund_status'):
            returns = returns.filter(refund_status__in=filter_form.cleaned_data['refund_status'])
        if filter_form.cleaned_data.get('return_reason'):
            returns = returns.filter(return_reason__in=filter_form.cleaned_data['return_reason'])
        if filter_form.cleaned_data.get('date_from'):
            returns = returns.filter(created_at__gte=filter_form.cleaned_data['date_from'])
        if filter_form.cleaned_data.get('date_to'):
            returns = returns.filter(created_at__lte=filter_form.cleaned_data['date_to'])
        if filter_form.cleaned_data.get('search'):
            search_term = filter_form.cleaned_data['search']
            returns = returns.filter(
                Q(return_code__icontains=search_term) |
                Q(order__order_code__icontains=search_term)
            )

    # Calculate statistics
    stats = {
        'total_returns': returns.count(),
        'pending_returns': returns.filter(return_status='requested').count(),
        'approved_returns': returns.filter(return_status='approved').count(),
        'completed_returns': returns.filter(return_status='completed').count(),
        'total_refunded': returns.filter(refund_status='completed').aggregate(
            total=Sum('refund_amount')
        )['total'] or 0
    }

    context = {
        'returns': returns,
        'filter_form': filter_form,
        'stats': stats,
        'page_title': _('My Returns')
    }

    return render(request, 'orders/returns/customer_list.html', context)


@login_required
def customer_return_detail(request, return_code):
    """View detailed information about a specific return"""
    return_obj = get_object_or_404(
        Return.objects.select_related(
            'order', 'customer', 'approved_by', 'inspector',
            'refund_processed_by', 'received_by', 'restocked_by'
        ).prefetch_related('items', 'status_logs'),
        return_code=return_code
    )

    # Ensure customer can only view their own returns
    if return_obj.customer != request.user:
        return HttpResponseForbidden(_('You do not have permission to view this return.'))

    # Get status timeline
    status_logs = return_obj.status_logs.all().order_by('timestamp')

    context = {
        'return': return_obj,
        'status_logs': status_logs,
        'page_title': f"{_('Return')} {return_code}"
    }

    return render(request, 'orders/returns/customer_detail.html', context)


@login_required
def create_return_request(request, order_id):
    """Create a new return request for an order"""
    order = get_object_or_404(Order, id=order_id)

    # Ensure customer can only create returns for their own orders
    if order.customer != request.user.email:
        return HttpResponseForbidden(_('You can only create returns for your own orders.'))

    # Check if order is eligible for return
    if order.status not in ['delivered', 'completed']:
        messages.error(request, _('This order is not eligible for return. Only delivered orders can be returned.'))
        return redirect('orders:detail', order_id=order_id)

    # Check if order already has a pending/active return
    existing_return = Return.objects.filter(
        order=order,
        return_status__in=['requested', 'pending_approval', 'approved', 'pickup_scheduled', 'in_transit', 'received', 'inspecting']
    ).first()

    if existing_return:
        messages.warning(request, _('A return request already exists for this order.'))
        return redirect('orders:customer_return_detail', return_code=existing_return.return_code)

    if request.method == 'POST':
        form = ReturnRequestForm(request.POST, request.FILES, order=order, customer=request.user)

        if form.is_valid():
            return_obj = form.save()

            # Create initial status log
            ReturnStatusLog.objects.create(
                return_request=return_obj,
                old_status='',
                new_status='requested',
                changed_by=request.user,
                notes='Return request submitted by customer'
            )

            messages.success(
                request,
                _(f'Return request {return_obj.return_code} has been submitted successfully. We will review it within 24-48 hours.')
            )
            return redirect('orders:customer_return_detail', return_code=return_obj.return_code)
    else:
        form = ReturnRequestForm(order=order, customer=request.user)

    context = {
        'form': form,
        'order': order,
        'page_title': f"{_('Return Request for Order')} {order.order_code}"
    }

    return render(request, 'orders/returns/create_request.html', context)


# ============================================
# Admin/Staff Views
# ============================================

@login_required
@any_role_required(['Admin', 'Manager', 'Stock Keeper'])
def returns_dashboard(request):
    """Dashboard for managing all return requests"""
    # Get filter parameters
    filter_form = ReturnFilterForm(request.GET)

    # Base queryset
    returns = Return.objects.select_related(
        'order', 'customer', 'approved_by', 'inspector', 'refund_processed_by'
    ).order_by('-created_at')

    # Apply filters
    if filter_form.is_valid():
        if filter_form.cleaned_data.get('return_status'):
            returns = returns.filter(return_status__in=filter_form.cleaned_data['return_status'])
        if filter_form.cleaned_data.get('refund_status'):
            returns = returns.filter(refund_status__in=filter_form.cleaned_data['refund_status'])
        if filter_form.cleaned_data.get('return_reason'):
            returns = returns.filter(return_reason__in=filter_form.cleaned_data['return_reason'])
        if filter_form.cleaned_data.get('date_from'):
            returns = returns.filter(created_at__gte=filter_form.cleaned_data['date_from'])
        if filter_form.cleaned_data.get('date_to'):
            returns = returns.filter(created_at__lte=filter_form.cleaned_data['date_to'])
        if filter_form.cleaned_data.get('search'):
            search_term = filter_form.cleaned_data['search']
            returns = returns.filter(
                Q(return_code__icontains=search_term) |
                Q(order__order_code__icontains=search_term) |
                Q(customer__first_name__icontains=search_term) |
                Q(customer__last_name__icontains=search_term) |
                Q(customer__email__icontains=search_term)
            )

    # Calculate comprehensive statistics
    all_returns = Return.objects.all()
    stats = {
        # Status breakdown
        'total_returns': all_returns.count(),
        'requested': all_returns.filter(return_status='requested').count(),
        'pending_approval': all_returns.filter(return_status='pending_approval').count(),
        'approved': all_returns.filter(return_status='approved').count(),
        'in_transit': all_returns.filter(return_status='in_transit').count(),
        'received': all_returns.filter(return_status='received').count(),
        'inspecting': all_returns.filter(return_status='inspecting').count(),
        'completed': all_returns.filter(return_status='completed').count(),
        'rejected': all_returns.filter(return_status='rejected').count(),

        # Refund breakdown
        'refund_pending': all_returns.filter(refund_status='pending').count(),
        'refund_approved': all_returns.filter(refund_status='approved').count(),
        'refund_processing': all_returns.filter(refund_status='processing').count(),
        'refund_completed': all_returns.filter(refund_status='completed').count(),

        # Financial metrics
        'total_refund_amount': all_returns.filter(refund_status='completed').aggregate(
            total=Sum('refund_amount')
        )['total'] or 0,
        'total_deductions': all_returns.filter(refund_status='completed').aggregate(
            total=Sum('restocking_fee') + Sum('damage_deduction') + Sum('shipping_cost_deduction')
        )['total'] or 0,

        # Priority items
        'requires_manager_approval': all_returns.filter(requires_manager_approval=True, return_status='pending_approval').count(),
        'high_priority': all_returns.filter(priority__gte=5).count(),
    }

    context = {
        'returns': returns,
        'filter_form': filter_form,
        'stats': stats,
        'page_title': _('Returns Management Dashboard')
    }

    return render(request, 'orders/returns/dashboard.html', context)


@login_required
@any_role_required(['Admin', 'Manager', 'Stock Keeper'])
def return_detail_admin(request, return_code):
    """Detailed view of return for admin/staff"""
    return_obj = get_object_or_404(
        Return.objects.select_related(
            'order', 'customer', 'approved_by', 'inspector',
            'refund_processed_by', 'received_by', 'restocked_by'
        ).prefetch_related('items__order_item__product', 'status_logs__changed_by'),
        return_code=return_code
    )

    # Get status timeline
    status_logs = return_obj.status_logs.all().order_by('timestamp')

    context = {
        'return': return_obj,
        'status_logs': status_logs,
        'page_title': f"{_('Return')} {return_code}",
        'can_approve': request.user.has_perm('orders.change_return'),
        'can_inspect': request.user.has_perm('orders.change_return'),
        'can_process_refund': request.user.has_perm('orders.change_return'),
    }

    return render(request, 'orders/returns/admin_detail.html', context)


@login_required
@any_role_required(['Admin', 'Manager'])
def approve_return(request, return_code):
    """Approve or reject a return request"""
    return_obj = get_object_or_404(Return, return_code=return_code)

    if return_obj.return_status not in ['requested', 'pending_approval']:
        messages.error(request, _('This return cannot be approved/rejected at its current status.'))
        return redirect('orders:return_detail_admin', return_code=return_code)

    if request.method == 'POST':
        form = ReturnApprovalForm(request.POST, instance=return_obj)

        if form.is_valid():
            if form.cleaned_data.get('approve'):
                return_obj.return_status = 'approved'
                return_obj.approved_by = request.user
                return_obj.approved_at = timezone.now()
                return_obj.refund_amount = form.cleaned_data['refund_amount']
                return_obj.save()

                # Create status log
                ReturnStatusLog.objects.create(
                    return_request=return_obj,
                    old_status='pending_approval',
                    new_status='approved',
                    changed_by=request.user,
                    notes='Return approved by manager'
                )

                messages.success(request, _(f'Return {return_code} has been approved.'))

            elif form.cleaned_data.get('reject'):
                return_obj.return_status = 'rejected'
                return_obj.approved_by = request.user
                return_obj.approved_at = timezone.now()
                return_obj.rejection_reason = form.cleaned_data['rejection_reason']
                return_obj.refund_status = 'cancelled'
                return_obj.save()

                # Create status log
                ReturnStatusLog.objects.create(
                    return_request=return_obj,
                    old_status='pending_approval',
                    new_status='rejected',
                    changed_by=request.user,
                    notes=f'Return rejected: {form.cleaned_data["rejection_reason"]}'
                )

                messages.warning(request, _(f'Return {return_code} has been rejected.'))

            return redirect('orders:return_detail_admin', return_code=return_code)
    else:
        form = ReturnApprovalForm(instance=return_obj)

    context = {
        'form': form,
        'return': return_obj,
        'page_title': f"{_('Approve/Reject Return')} {return_code}"
    }

    return render(request, 'orders/returns/approve_return.html', context)


@login_required
@any_role_required(['Admin', 'Manager', 'Stock Keeper'])
def mark_return_received(request, return_code):
    """Mark a return as received at warehouse"""
    return_obj = get_object_or_404(Return, return_code=return_code)

    if return_obj.return_status != 'in_transit':
        messages.error(request, _('This return is not currently in transit.'))
        return redirect('orders:return_detail_admin', return_code=return_code)

    if request.method == 'POST':
        return_obj.return_status = 'received'
        return_obj.received_by = request.user
        return_obj.received_at_warehouse = timezone.now()
        return_obj.save()

        # Create status log
        ReturnStatusLog.objects.create(
            return_request=return_obj,
            old_status='in_transit',
            new_status='received',
            changed_by=request.user,
            notes='Return received at warehouse'
        )

        messages.success(request, _(f'Return {return_code} has been marked as received.'))
        return redirect('orders:return_detail_admin', return_code=return_code)

    context = {
        'return': return_obj,
        'page_title': f"{_('Mark as Received')} {return_code}"
    }

    return render(request, 'orders/returns/mark_received.html', context)


@login_required
@any_role_required(['Admin', 'Manager', 'Stock Keeper'])
def inspect_return(request, return_code):
    """Inspect a returned item"""
    return_obj = get_object_or_404(Return, return_code=return_code)

    if return_obj.return_status not in ['received', 'inspecting']:
        messages.error(request, _('This return is not ready for inspection.'))
        return redirect('orders:return_detail_admin', return_code=return_code)

    if request.method == 'POST':
        form = ReturnInspectionForm(request.POST, instance=return_obj)

        if form.is_valid():
            # Update inspection started time if not set
            if not return_obj.inspection_started_at:
                return_obj.inspection_started_at = timezone.now()
                return_obj.return_status = 'inspecting'

            return_obj.inspector = request.user
            return_obj.inspection_completed_at = timezone.now()

            if form.cleaned_data.get('approve_for_refund'):
                return_obj.return_status = 'approved_for_refund'
                return_obj.refund_status = 'approved'

                # Create status log
                ReturnStatusLog.objects.create(
                    return_request=return_obj,
                    old_status='inspecting',
                    new_status='approved_for_refund',
                    changed_by=request.user,
                    notes='Inspection completed - approved for refund'
                )

                messages.success(request, _(f'Return {return_code} has been approved for refund.'))

            elif form.cleaned_data.get('reject_for_refund'):
                return_obj.return_status = 'inspected'
                return_obj.refund_status = 'cancelled'

                # Create status log
                ReturnStatusLog.objects.create(
                    return_request=return_obj,
                    old_status='inspecting',
                    new_status='inspected',
                    changed_by=request.user,
                    notes='Inspection completed - rejected for refund'
                )

                messages.warning(request, _(f'Return {return_code} has been rejected for refund after inspection.'))

            form.save()
            return redirect('orders:return_detail_admin', return_code=return_code)
    else:
        form = ReturnInspectionForm(instance=return_obj)

    context = {
        'form': form,
        'return': return_obj,
        'page_title': f"{_('Inspect Return')} {return_code}"
    }

    return render(request, 'orders/returns/inspect_return.html', context)


@login_required
@any_role_required(['Admin', 'Manager', 'Finance'])
def process_refund(request, return_code):
    """Process refund for an approved return"""
    return_obj = get_object_or_404(Return, return_code=return_code)

    if return_obj.refund_status != 'approved':
        messages.error(request, _('This return is not approved for refund yet.'))
        return redirect('orders:return_detail_admin', return_code=return_code)

    if request.method == 'POST':
        form = RefundProcessingForm(request.POST, instance=return_obj)

        if form.is_valid():
            return_obj.refund_status = 'completed'
            return_obj.refund_processed_by = request.user
            return_obj.refund_processed_at = timezone.now()
            return_obj.return_status = 'refund_completed'
            form.save()

            # Create status log
            ReturnStatusLog.objects.create(
                return_request=return_obj,
                old_status='approved_for_refund',
                new_status='refund_completed',
                changed_by=request.user,
                notes=f'Refund processed via {return_obj.refund_method}'
            )

            messages.success(
                request,
                _(f'Refund of AED {return_obj.net_refund_amount:.2f} has been processed for return {return_code}.')
            )
            return redirect('orders:return_detail_admin', return_code=return_code)
    else:
        form = RefundProcessingForm(instance=return_obj)

    context = {
        'form': form,
        'return': return_obj,
        'page_title': f"{_('Process Refund')} {return_code}"
    }

    return render(request, 'orders/returns/process_refund.html', context)


# ============================================
# AJAX/API Views
# ============================================

@login_required
@require_http_methods(["GET"])
def get_return_status(request, return_code):
    """Get current status of a return (AJAX endpoint)"""
    try:
        return_obj = Return.objects.get(return_code=return_code)

        # Ensure user can only access their own returns or has admin privileges
        if return_obj.customer != request.user and not request.user.is_staff:
            return JsonResponse({'error': 'Permission denied'}, status=403)

        data = {
            'success': True,
            'return_code': return_obj.return_code,
            'return_status': return_obj.return_status,
            'return_status_display': return_obj.get_return_status_display(),
            'refund_status': return_obj.refund_status,
            'refund_status_display': return_obj.get_refund_status_display(),
            'refund_amount': float(return_obj.refund_amount),
            'net_refund_amount': float(return_obj.net_refund_amount),
            'created_at': return_obj.created_at.isoformat(),
            'updated_at': return_obj.updated_at.isoformat(),
        }

        return JsonResponse(data)

    except Return.DoesNotExist:
        return JsonResponse({'error': 'Return not found'}, status=404)


@login_required
@require_http_methods(["GET"])
def get_return_timeline(request, return_code):
    """Get status timeline for a return (AJAX endpoint)"""
    try:
        return_obj = Return.objects.get(return_code=return_code)

        # Ensure user can only access their own returns or has admin privileges
        if return_obj.customer != request.user and not request.user.is_staff:
            return JsonResponse({'error': 'Permission denied'}, status=403)

        status_logs = return_obj.status_logs.all().order_by('timestamp')

        timeline = [{
            'old_status': log.old_status,
            'new_status': log.new_status,
            'new_status_display': return_obj.get_return_status_display() if log.new_status == return_obj.return_status else log.new_status,
            'changed_by': log.changed_by.get_full_name() if log.changed_by else 'System',
            'notes': log.notes,
            'timestamp': log.timestamp.isoformat()
        } for log in status_logs]

        return JsonResponse({'success': True, 'timeline': timeline})

    except Return.DoesNotExist:
        return JsonResponse({'error': 'Return not found'}, status=404)


# ========================================
# Future Feature Placeholders
# ========================================

@login_required
@any_role_required(['Admin', 'Manager', 'Stock Keeper'])
def print_return_label(request, return_code):
    """
    Generate and print return shipping label
    TODO: Implement return label generation with barcode and shipping details
    """
    messages.warning(request, _('Return label printing feature is coming soon.'))
    return redirect('orders:return_detail_admin', return_code=return_code)


@login_required
@any_role_required(['Admin', 'Manager', 'Stock Keeper'])
def export_return_pdf(request, return_code):
    """
    Export return details as PDF
    TODO: Implement PDF generation with return details, timeline, and documentation
    """
    messages.warning(request, _('PDF export feature is coming soon.'))
    return redirect('orders:return_detail_admin', return_code=return_code)


@login_required
@any_role_required(['Admin', 'Manager'])
def bulk_return_action(request):
    """
    Perform bulk actions on multiple returns
    TODO: Implement bulk approve, reject, mark received, etc.
    """
    messages.warning(request, _('Bulk action feature is coming soon.'))
    return redirect('orders:returns_dashboard')
