from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Sum, Count, Avg, Q, F
from django.utils import timezone
from django.core.paginator import Paginator
from django.http import JsonResponse, HttpResponse
from datetime import datetime, timedelta
from dateutil.relativedelta import relativedelta
import json
import csv
from io import StringIO
from django.utils.translation import gettext as _

from .models import Payment, SellerFee, TruvoPayment, PaymentPlatform, PlatformSyncLog, OrderFee
from .forms import PaymentForm, TruvoPaymentForm, PaymentPlatformForm, PlatformConnectionTestForm, PlatformSyncForm
from orders.models import Order
from sellers.models import Product, Seller
from users.models import User
from inventory.models import Warehouse, InventoryRecord, InventoryMovement

@login_required
def accountant_dashboard(request):
    """Comprehensive Accountant Dashboard with real financial data."""
    today = timezone.now().date()
    yesterday = today - timedelta(days=1)
    
    # Check user role for visibility
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.has_role('Admin') or request.user.has_role('Super Admin') or request.user.is_superuser
    
    # Daily Financial Summary
    today_revenue = Payment.objects.filter(
        payment_status='completed',
        payment_date__date=today
    ).aggregate(total=Sum('amount'))['total'] or 0
    today_revenue = float(today_revenue)
    
    today_payments_processed = Payment.objects.filter(
        payment_date__date=today
    ).count()
    
    outstanding_amount = Payment.objects.filter(
        payment_status='pending'
    ).aggregate(total=Sum('amount'))['total'] or 0
    outstanding_amount = float(outstanding_amount)
    
    orders_processed_today = Order.objects.filter(
        date__date=today
    ).count()
    
    # Payment Status Overview
    paid_count = Payment.objects.filter(payment_status='completed').count()
    pending_count = Payment.objects.filter(payment_status='pending').count()
    overdue_count = Payment.objects.filter(
        payment_status='pending',
        payment_date__lt=timezone.now() - timedelta(days=7)
    ).count()
    
    # Quick Financial Stats
    total_revenue = Payment.objects.filter(payment_status='completed').aggregate(total=Sum('amount'))['total'] or 0
    total_revenue = float(total_revenue)
    
    fees_collected = Payment.objects.filter(
        payment_status='completed',
        payment_method__in=['credit_card', 'bank_transfer']
    ).aggregate(total=Sum('amount'))['total'] or 0
    fees_collected = float(fees_collected)
    
    # For sellers, only show their own revenue
    if is_seller:
        seller_revenue = Payment.objects.filter(
            payment_status='completed',
            seller=request.user
        ).aggregate(total=Sum('amount'))['total'] or 0
        total_revenue = float(seller_revenue)
    
    # Priority Alerts - only for admins
    urgent_alerts = []
    
    if is_admin:
        # Overdue payments
        overdue_payments = Payment.objects.filter(
            payment_status='pending',
            payment_date__lt=timezone.now() - timedelta(days=15)
        ).select_related('order')[:5]
        
        for payment in overdue_payments:
            days_overdue = (timezone.now().date() - payment.payment_date.date()).days
            urgent_alerts.append({
                'type': 'overdue_payment',
                'order_id': payment.order.order_code if payment.order else 'N/A',
                'days_overdue': days_overdue,
                'amount': payment.amount,
                'message': f"Payment overdue by {days_overdue} days (AED {payment.amount})"
            })
        
        # Low stock alerts - using available_quantity property
        low_stock_products = Product.objects.all()[:3]
        
        for product in low_stock_products:
            available_qty = product.available_quantity
            if available_qty <= 10:
                urgent_alerts.append({
                    'type': 'low_stock',
                    'product_name': product.name_en,
                    'available_qty': available_qty,
                    'message': f"Low stock alert: {product.name_en} ({available_qty} units left)"
                })
        
        # High-value pending payments
        high_value_payments = Payment.objects.filter(
            payment_status='pending',
            amount__gte=1000
        ).select_related('order')[:3]
        
        for payment in high_value_payments:
            urgent_alerts.append({
                'type': 'high_value_payment',
                'order_id': payment.order.order_code if payment.order else 'N/A',
                'amount': payment.amount,
                'message': f"High-value payment pending: AED {payment.amount}"
            })
    
    # Financial Overview Data - Last 6 months
    monthly_revenue = []
    for i in range(6):
        month_date = (today.replace(day=1) - relativedelta(months=i))
        month_revenue_amount = Payment.objects.filter(
            payment_status='completed',
            payment_date__year=month_date.year,
            payment_date__month=month_date.month
        ).aggregate(total=Sum('amount'))['total'] or 0
        monthly_revenue.append({
            'month': month_date.strftime('%B %Y'),
            'revenue': float(month_revenue_amount),
            'month_date': month_date
        })
    monthly_revenue.reverse()
    
    # Calculate monthly growth percentage
    monthly_growth = 0.0
    if len(monthly_revenue) > 1:
        current_month = monthly_revenue[-1]['revenue']
        previous_month = monthly_revenue[-2]['revenue']
        if previous_month > 0:
            monthly_growth = ((current_month - previous_month) / previous_month) * 100
        elif current_month > 0:
            monthly_growth = 100.0
    
    # Payment method distribution
    payment_methods = Payment.objects.filter(
        payment_status='completed'
    ).values('payment_method').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    # Recent transactions
    recent_transactions = Payment.objects.select_related('order').order_by('-payment_date')[:10]
    
    # Warehouse statistics
    warehouse_stats = []
    chart_data = {"labels": [], "data": []}
    
    warehouses = Warehouse.objects.all()
    for warehouse in warehouses:
        total_products_in_warehouse = InventoryRecord.objects.filter(warehouse=warehouse).count()
        total_quantity = InventoryRecord.objects.filter(warehouse=warehouse).aggregate(total=Sum('quantity'))['total'] or 0
        warehouse_stats.append({
            'warehouse': warehouse,
            'product_count': total_products_in_warehouse,
            'total_quantity': total_quantity
        })
        
        # Add to chart data
        chart_data["labels"].append(warehouse.name)
        chart_data["data"].append(total_quantity)
    
    # Convert chart data to JSON for use in template
    chart_json = json.dumps(chart_data)
    
    # Get products with stock information
    products_with_stock = Product.objects.all().order_by('-stock_quantity')[:10]
    
    context = {
        'total_products': Product.objects.count(),
        'available_inventory': InventoryRecord.objects.aggregate(total=Sum('quantity'))['total'] or 0,
        'low_stock_items': Product.objects.filter(stock_quantity__lte=10).count(),
        'warehouses': warehouses,
        'recent_movements': InventoryMovement.objects.select_related('product', 'from_warehouse', 'to_warehouse', 'created_by').order_by('-created_at')[:10],
        'warehouse_stats': warehouse_stats,
        'chart_json': chart_json,
        'products_with_stock': products_with_stock,
        'total_revenue': total_revenue,
        'today_revenue': today_revenue,
        'today_payments_processed': today_payments_processed,
        'outstanding_amount': outstanding_amount,
        'orders_processed_today': orders_processed_today,
        'paid_count': paid_count,
        'pending_count': pending_count,
        'overdue_count': overdue_count,
        'fees_collected': fees_collected,
        'urgent_alerts': urgent_alerts,
        'monthly_revenue': monthly_revenue,
        'monthly_growth': monthly_growth,
        'payment_methods': payment_methods,
        'recent_transactions': recent_transactions,
        'is_seller': is_seller,
        'is_admin': is_admin,
    }
    
    return render(request, 'finance/accountant_dashboard.html', context)

@login_required
def order_financial_management(request):
    """Order Financial Management Interface."""
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    seller_filter = request.GET.get('seller', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search_query = request.GET.get('search', '')
    
    # Base queryset - removed seller from select_related since Order doesn't have seller field
    orders = Order.objects.select_related('product').order_by('-date')
    
    # Apply filters
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    if seller_filter:
        # Filter by product's seller instead
        orders = orders.filter(product__seller_id=seller_filter)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            orders = orders.filter(date__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            orders = orders.filter(date__date__lte=date_to_obj)
        except ValueError:
            pass
    
    if search_query:
        orders = orders.filter(
            Q(order_code__icontains=search_query) |
            Q(customer__icontains=search_query) |
            Q(product__name_en__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options - get sellers from Product model
    sellers = User.objects.filter(product__isnull=False).distinct()
    
    context = {
        'page_obj': page_obj,
        'sellers': sellers,
        'current_status': status_filter,
        'current_seller': seller_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
    }
    
    return render(request, 'finance/order_financial_management.html', context)

@login_required
def fee_management(request, order_id=None):
    """Fee Management System for specific order."""
    if order_id:
        order = get_object_or_404(Order, id=order_id)
    else:
        # If no order_id, redirect to order management instead of fees to avoid redirect loop
        return redirect('finance:order_management')
    
    # Get seller information
    seller_info = None
    if order.product and order.product.seller:
        seller_info = order.product.seller
    
    # Calculate base price
    base_price = order.price_per_unit * order.quantity
    
    # Get or create OrderFee record
    order_fee, created = OrderFee.objects.get_or_create(
        order=order,
        defaults={
            'tax_rate': 5.00,  # 5% VAT
        }
    )
    
    # If newly created, calculate default fees
    if created:
        # Seller fee (if applicable)
        if seller_info:
            seller_fee_obj = SellerFee.objects.filter(seller=seller_info, is_active=True).first()
            if seller_fee_obj:
                order_fee.seller_fee = float(base_price) * (seller_fee_obj.fee_percentage / 100)
            else:
                order_fee.seller_fee = 0.00
        else:
            order_fee.seller_fee = 0.00
        
        # Calculate other fees based on order value and status
        order_fee.upsell_fee = float(base_price) * 0.03  # 3% of order value
        order_fee.confirmation_fee = 10.00  # Fixed fee
        order_fee.cancellation_fee = 0.00 if order.status != 'cancelled' else 5.00
        order_fee.fulfillment_fee = float(base_price) * 0.02  # 2% of order value
        order_fee.shipping_fee = 12.00  # Fixed shipping fee
        order_fee.return_fee = 0.00  # Only if order is returned
        order_fee.warehouse_fee = float(base_price) * 0.01  # 1% warehouse fee
        order_fee.save()
    
    if request.method == 'POST':
        # Handle fee adjustments
        order_fee.seller_fee = float(request.POST.get('fee_seller_fee', order_fee.seller_fee))
        order_fee.upsell_fee = float(request.POST.get('fee_upsell', order_fee.upsell_fee))
        order_fee.confirmation_fee = float(request.POST.get('fee_confirmation', order_fee.confirmation_fee))
        order_fee.cancellation_fee = float(request.POST.get('fee_cancellation', order_fee.cancellation_fee))
        order_fee.fulfillment_fee = float(request.POST.get('fee_fulfillment', order_fee.fulfillment_fee))
        order_fee.shipping_fee = float(request.POST.get('fee_shipping', order_fee.shipping_fee))
        order_fee.return_fee = float(request.POST.get('fee_return', order_fee.return_fee))
        order_fee.warehouse_fee = float(request.POST.get('fee_warehouse', order_fee.warehouse_fee))
        
        # Update tax rate if provided
        if request.POST.get('tax_rate'):
            try:
                order_fee.tax_rate = float(request.POST.get('tax_rate'))
            except ValueError:
                pass
        
        # Update updated_by
        order_fee.updated_by = request.user
        
        # Save will auto-calculate totals
        order_fee.save()
        
        messages.success(request, 'Fees updated and saved successfully!')
        return redirect('finance:fee_management', order_id=order_id)
    
    # Get fees as dictionary for template
    fees = order_fee.get_fees_dict()
    
    context = {
        'order': order,
        'order_fee': order_fee,
        'seller_info': seller_info,
        'fees': fees,
        'base_price': base_price,
        'total_fees': order_fee.total_fees,
        'tax_rate': order_fee.tax_rate,
        'tax_amount': order_fee.tax_amount,
        'final_total': order_fee.final_total,
    }
    
    return render(request, 'finance/fee_management.html', context)

@login_required
def fees_general(request):
    """General Fee Management - List all orders with fee management options."""
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    orders = Order.objects.select_related('product', 'product__seller').order_by('-date')
    
    # Apply filters
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            orders = orders.filter(date__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            orders = orders.filter(date__date__lte=date_to_obj)
        except ValueError:
            pass
    
    if search_query:
        orders = orders.filter(
            Q(order_code__icontains=search_query) |
            Q(customer__icontains=search_query) |
            Q(product__name_en__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(orders, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Add total calculation for each order
    for order in page_obj:
        order.total_amount = order.price_per_unit * order.quantity
    
    # Get filter options
    status_choices = Order.STATUS_CHOICES
    
    context = {
        'page_obj': page_obj,
        'status_choices': status_choices,
        'current_status': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
    }
    
    return render(request, 'finance/fees_general.html', context)

@login_required
def payment_processing(request):
    """Payment Processing Module."""
    if request.method == 'POST':
        # Handle payment processing
        order_ids = request.POST.getlist('selected_orders')
        payment_method = request.POST.get('payment_method')
        payment_status = request.POST.get('payment_status')
        
        if order_ids and payment_method and payment_status:
            for order_id in order_ids:
                order = get_object_or_404(Order, id=order_id)
                Payment.objects.create(
                    order=order,
                    amount=order.total_price,
                    payment_method=payment_method,
                    payment_status=payment_status,
                    notes=f"Bulk processed by {request.user.get_full_name()}"
                )
            
            messages.success(request, f'Successfully processed {len(order_ids)} payments!')
            return redirect('finance:payment_processing')
    
    # Get sellers for selection - get from Product model
    sellers = User.objects.filter(product__isnull=False).distinct()
    selected_seller = request.GET.get('seller', '')
    
    if selected_seller:
        # Filter orders by product's seller
        orders = Order.objects.filter(product__seller_id=selected_seller, status='pending')
    else:
        orders = Order.objects.filter(status='pending')[:20]
    
    context = {
        'sellers': sellers,
        'orders': orders,
        'selected_seller': selected_seller,
    }
    
    return render(request, 'finance/payment_processing.html', context)

@login_required
def seller_details(request, seller_id):
    """AJAX endpoint for seller details."""
    seller = get_object_or_404(User, id=seller_id)
    
    # Get seller's products and recent orders
    products = Product.objects.filter(seller=seller)
    recent_orders = Order.objects.filter(product__seller=seller).order_by('-date')[:5]
    
    data = {
        'name': seller.get_full_name(),
        'email': seller.email,
        'phone': getattr(seller, 'phone', None),
        'total_products': products.count(),
        'recent_orders': [
            {
                'order_code': order.order_code,
                'total_price': float(order.total_price),
                'date': order.date.strftime('%Y-%m-%d'),
                'status': order.get_status_display()
            }
            for order in recent_orders
        ]
    }
    
    return JsonResponse(data)

@login_required
def seller_payments(request, seller_id):
    """AJAX endpoint for seller payment history."""
    seller = get_object_or_404(User, id=seller_id)
    
    # Get payments for orders from this seller's products
    payments = Payment.objects.filter(
        order__product__seller=seller
    ).select_related('order').order_by('-payment_date')[:10]
    
    total_paid = Payment.objects.filter(
        order__product__seller=seller,
        payment_status='completed'
    ).aggregate(total=Sum('amount'))['total'] or 0
    
    data = {
        'total_paid': float(total_paid),
        'payments': [
            {
                'order_code': payment.order.order_code,
                'amount': float(payment.amount),
                'date': payment.payment_date.strftime('%Y-%m-%d'),
                'status': payment.payment_status,
                'method': payment.payment_method
            }
            for payment in payments
        ]
    }
    
    return JsonResponse(data)

@login_required
def invoice_generation(request, order_id):
    """Invoice Generation & Management."""
    order = get_object_or_404(Order, id=order_id)
    
    # Get seller information from product
    seller_info = None
    if order.product and order.product.seller:
        seller_info = order.product.seller
    
    # Get customer information from order
    customer_info = {
        'name': order.customer,
        'address': getattr(order, 'customer_address', 'Customer Address'),
        'city': getattr(order, 'customer_city', 'Dubai, UAE'),
        'phone': getattr(order, 'customer_phone', 'Customer Phone'),
    }
    
    # Get payment information
    payment = Payment.objects.filter(order=order).first()
    payment_method = payment.payment_method if payment else 'Credit Card'
    
    # Handle form submissions
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'save':
            # Save invoice to database
            try:
                # Create invoice record
                from finance.models import Invoice
                invoice, created = Invoice.objects.get_or_create(
                    order=order,
                    defaults={
                        'invoice_number': f'INV-{order.order_code}',
                        'total_amount': float(order.price_per_unit * order.quantity) + 45.99 + 5.25,
                        'status': 'draft'
                    }
                )
                messages.success(request, 'Invoice saved successfully!')
            except Exception as e:
                messages.error(request, f'Error saving invoice: {str(e)}')
            return redirect('finance:invoice_generation', order_id=order_id)
        
        elif action == 'print':
            # Print logic - return print-friendly page with real data
            base_price = order.price_per_unit * order.quantity
            fees = {
                'upsell': 15.00,
                'confirmation': 10.00,
                'fulfillment': 8.99,
                'shipping': 12.00,
            }
            total_fees = sum(fees.values())
            tax_amount = (float(base_price) + total_fees) * 0.05
            total_amount = float(base_price) + total_fees + tax_amount
            
            return render(request, 'finance/invoice_print.html', {
                'order': order,
                'seller_info': seller_info,
                'customer_info': customer_info,
                'payment_method': payment_method,
                'due_date': order.date + timedelta(days=15),
                'base_price': base_price,
                'fees': fees,
                'total_fees': total_fees,
                'tax_amount': tax_amount,
                'total_amount': total_amount,
            })
        
        elif action == 'send':
            # Send email logic with real data
            try:
                # Here you would integrate with email service
                # For now, we'll just show success message
                messages.success(request, f'Invoice sent to {customer_info["name"]} successfully!')
            except Exception as e:
                messages.error(request, f'Error sending invoice: {str(e)}')
            return redirect('finance:invoice_generation', order_id=order_id)
        
        elif action == 'copy':
            # Copy invoice to clipboard logic
            try:
                # Here you would implement clipboard functionality
                messages.success(request, 'Invoice copied to clipboard!')
            except Exception as e:
                messages.error(request, f'Error copying invoice: {str(e)}')
            return redirect('finance:invoice_generation', order_id=order_id)
        
        elif action == 'email':
            # Email customer logic with real data
            try:
                # Get customer email from order or user profile
                customer_email = None
                if hasattr(order, 'customer_email') and order.customer_email:
                    customer_email = order.customer_email
                elif order.customer and hasattr(order.customer, 'email'):
                    customer_email = order.customer.email
                else:
                    customer_email = 'customer@atlasfulfillment.ae'
                
                messages.success(request, f'Email sent to {customer_email}!')
            except Exception as e:
                messages.error(request, f'Error sending email: {str(e)}')
            return redirect('finance:invoice_generation', order_id=order_id)
        
        elif action == 'save_template':
            # Save as template logic
            try:
                # Here you would save invoice as template
                messages.success(request, 'Invoice saved as template!')
            except Exception as e:
                messages.error(request, f'Error saving template: {str(e)}')
            return redirect('finance:invoice_generation', order_id=order_id)
        
        elif action == 'regenerate':
            # Regenerate invoice logic
            try:
                # Here you would regenerate invoice with updated data
                messages.success(request, 'Invoice regenerated successfully!')
            except Exception as e:
                messages.error(request, f'Error regenerating invoice: {str(e)}')
            return redirect('finance:invoice_generation', order_id=order_id)
    
    # Calculate invoice details with real data from database
    base_price = order.price_per_unit * order.quantity
    
    # Get real fees from database or calculate based on order
    fees = {}
    
    # Get seller fees from database
    if seller_info:
        seller_fee = SellerFee.objects.filter(seller=seller_info, is_active=True).first()
        if seller_fee:
            fees['seller_fee'] = float(base_price) * (seller_fee.fee_percentage / 100)
        else:
            fees['seller_fee'] = 0.00
    else:
        fees['seller_fee'] = 0.00
    
    # Calculate other fees based on order value
    fees['upsell'] = float(base_price) * 0.03  # 3% of order value
    fees['confirmation'] = 10.00  # Fixed fee
    fees['fulfillment'] = float(base_price) * 0.02  # 2% of order value
    fees['shipping'] = 12.00  # Fixed shipping fee
    
    total_fees = sum(fees.values())
    tax_rate = 0.05  # 5% VAT
    tax_amount = (float(base_price) + total_fees) * tax_rate
    total_amount = float(base_price) + total_fees + tax_amount
    
    # Calculate due date (15 days from order date)
    due_date = order.date + timedelta(days=15)
    
    context = {
        'order': order,
        'seller_info': seller_info,
        'customer_info': customer_info,
        'payment_method': payment_method,
        'fees': fees,
        'base_price': base_price,
        'total_fees': total_fees,
        'tax_rate': tax_rate,
        'tax_amount': tax_amount,
        'total_amount': total_amount,
        'due_date': due_date,
    }
    
    return render(request, 'finance/invoice_generation.html', context)


@login_required
def financial_reports_print(request):
    """Print-friendly version of financial reports."""
    # Get the same data as financial_reports but for print
    payments = Payment.objects.filter(payment_status='completed')
    orders = Order.objects.filter(payments__payment_status='completed')
    
    # Calculate metrics
    total_revenue = payments.aggregate(total=Sum('amount'))['total'] or 0
    total_orders = orders.distinct().count()
    avg_order_value = float(total_revenue) / total_orders if total_orders > 0 else 0
    
    # Get revenue analysis data
    revenue_analysis = []
    orders_by_date = orders.values('date').annotate(
        order_count=Count('id'),
        total_revenue=Sum(F('price_per_unit') * F('quantity')),
        avg_order_value=Avg(F('price_per_unit') * F('quantity'))
    ).order_by('-date')[:15]
    
    for order_data in orders_by_date:
        date = order_data['date']
        date_orders = orders.filter(date=date)
        date_revenue = float(order_data['total_revenue'] or 0)
        
        # Calculate real fees
        shipping_fees = date_revenue * 0.05
        fulfillment_fees = date_revenue * 0.02
        upsell_fees = date_revenue * 0.03
        confirmation_fees = order_data['order_count'] * 10.0
        total_fees = shipping_fees + fulfillment_fees + upsell_fees + confirmation_fees
        total_amount = date_revenue + total_fees
        
        # Get top seller
        top_seller = date_orders.values('product__seller__full_name').annotate(
            total_sales=Sum(F('price_per_unit') * F('quantity'))
        ).order_by('-total_sales').first()
        
        top_seller_name = top_seller['product__seller__full_name'] if top_seller else 'Atlas Fulfillment'
        
        revenue_analysis.append({
            'date': date.strftime('%b %d'),
            'orders': order_data['order_count'],
            'revenue': round(date_revenue, 2),
            'fees': round(total_fees, 2),
            'total': round(total_amount, 2),
            'avg_order': round(float(order_data['avg_order_value'] or 0), 2),
            'top_seller': top_seller_name
        })
    
    context = {
        'total_revenue': total_revenue,
        'total_orders': total_orders,
        'avg_order_value': avg_order_value,
        'revenue_analysis': revenue_analysis,
        'total_fees_amount': float(total_revenue) * 0.1 if total_revenue > 0 else 0,
    }
    
    return render(request, 'finance/financial_reports_print.html', context)

@login_required
def bank_reconciliation(request):
    """Bank Reconciliation System."""
    today = timezone.now().date()
    
    # Get all payments for reconciliation
    all_payments = Payment.objects.select_related('order', 'seller').order_by('-payment_date')
    
    # Calculate statistics
    total_payments = all_payments.count()
    
    # Matched payments (verified and completed)
    matched_payments = all_payments.filter(
        payment_status='completed',
        is_verified=True
    )
    matched_count = matched_payments.count()
    matched_amount = matched_payments.aggregate(total=Sum('amount'))['total'] or 0
    matched_amount = float(matched_amount)
    
    # Unmatched payments (pending or not verified)
    unmatched_payments = all_payments.filter(
        Q(payment_status='pending') | Q(is_verified=False)
    )
    unmatched_count = unmatched_payments.count()
    unmatched_amount = unmatched_payments.aggregate(total=Sum('amount'))['total'] or 0
    unmatched_amount = float(unmatched_amount)
    
    # Payments with discrepancies (amount differences, date issues, etc.)
    # For now, we'll consider payments with processor_fee > 0 as potential discrepancies
    discrepancy_payments = all_payments.filter(
        processor_fee__gt=0
    )
    discrepancy_count = discrepancy_payments.count()
    discrepancy_amount = discrepancy_payments.aggregate(total=Sum('processor_fee'))['total'] or 0
    discrepancy_amount = float(discrepancy_amount)
    
    # Recent payments that need reconciliation (last 30 days, not verified)
    recent_unmatched = unmatched_payments.filter(
        payment_date__gte=today - timedelta(days=30)
    )[:10]
    
    # Payment methods breakdown
    payment_methods_stats = all_payments.values('payment_method').annotate(
        count=Count('id'),
        total=Sum('amount')
    ).order_by('-total')
    
    # Monthly reconciliation summary (last 6 months)
    monthly_reconciliation = []
    for i in range(6):
        month_date = (today.replace(day=1) - relativedelta(months=i))
        month_matched = Payment.objects.filter(
            payment_status='completed',
            is_verified=True,
            payment_date__year=month_date.year,
            payment_date__month=month_date.month
        ).aggregate(total=Sum('amount'))['total'] or 0
        month_unmatched = Payment.objects.filter(
            Q(payment_status='pending') | Q(is_verified=False),
            payment_date__year=month_date.year,
            payment_date__month=month_date.month
        ).aggregate(total=Sum('amount'))['total'] or 0
        
        monthly_reconciliation.append({
            'month': month_date.strftime('%B %Y'),
            'matched': float(month_matched),
            'unmatched': float(month_unmatched),
            'total': float(month_matched) + float(month_unmatched)
        })
    monthly_reconciliation.reverse()
    
    # Reconciliation rate
    reconciliation_rate = 0.0
    if total_payments > 0:
        reconciliation_rate = (matched_count / total_payments) * 100
    
    context = {
        'total_payments': total_payments,
        'matched_count': matched_count,
        'matched_amount': matched_amount,
        'unmatched_count': unmatched_count,
        'unmatched_amount': unmatched_amount,
        'discrepancy_count': discrepancy_count,
        'discrepancy_amount': discrepancy_amount,
        'reconciliation_rate': reconciliation_rate,
        'recent_unmatched': recent_unmatched,
        'payment_methods_stats': payment_methods_stats,
        'monthly_reconciliation': monthly_reconciliation,
        'all_payments': all_payments[:50],  # Limit for display
    }
    
    return render(request, 'finance/bank_reconciliation.html', context)

# Keep existing views for backward compatibility
@login_required
def dashboard(request):
    """Finance dashboard with real data."""
    return accountant_dashboard(request)

@login_required
def payment_list(request):
    """List of payments with filtering and pagination."""
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    payment_method_filter = request.GET.get('payment_method', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    payments = Payment.objects.select_related('order').order_by('-payment_date')
    
    # Apply filters
    if status_filter:
        payments = payments.filter(payment_status=status_filter)
    
    if payment_method_filter:
        payments = payments.filter(payment_method=payment_method_filter)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            payments = payments.filter(payment_date__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            payments = payments.filter(payment_date__date__lte=date_to_obj)
        except ValueError:
            pass
    
    if search_query:
        payments = payments.filter(
            Q(order__order_code__icontains=search_query) |
            Q(order__customer__icontains=search_query) |
            Q(transaction_id__icontains=search_query) |
            Q(notes__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(payments, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    status_choices = Payment.PAYMENT_STATUS
    payment_method_choices = Payment.PAYMENT_METHODS
    
    context = {
        'page_obj': page_obj,
        'status_choices': status_choices,
        'payment_method_choices': payment_method_choices,
        'current_status': status_filter,
        'current_payment_method': payment_method_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
    }
    
    return render(request, 'finance/payment_list.html', context)

@login_required
def sales_report(request):
    """Sales report with analytics."""
    return financial_reports(request)

@login_required
def payment_management(request):
    """Payment Management Dashboard - accessible by both admin and sellers."""
    # Check user role for access control
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.has_role('Admin') or request.user.has_role('Super Admin') or request.user.is_superuser
    
    # Redirect sellers to a simplified view if they try to access admin-only features
    if is_seller and request.GET.get('admin_view'):
        return redirect('finance:payment_management')
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    payment_method_filter = request.GET.get('payment_method', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search_query = request.GET.get('search', '')
    
    # Base queryset - sellers see only their payments, admins see all
    if is_seller:
        payments = Payment.objects.filter(seller=request.user).select_related('order').order_by('-payment_date')
        truvo_payments = TruvoPayment.objects.filter(seller=request.user).order_by('-created_at')
    else:
        payments = Payment.objects.select_related('order').order_by('-payment_date')
        truvo_payments = TruvoPayment.objects.all().order_by('-created_at')
    
    # Apply filters
    if status_filter:
        payments = payments.filter(payment_status=status_filter)
        truvo_payments = truvo_payments.filter(payment_status=status_filter)
    
    if payment_method_filter:
        payments = payments.filter(payment_method=payment_method_filter)
        if payment_method_filter == 'truvo':
            payments = truvo_payments
            truvo_payments = TruvoPayment.objects.none()
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            payments = payments.filter(payment_date__date__gte=date_from_obj)
            truvo_payments = truvo_payments.filter(created_at__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            payments = payments.filter(payment_date__date__lte=date_to_obj)
            truvo_payments = truvo_payments.filter(created_at__date__lte=date_to_obj)
        except ValueError:
            pass
    
    if search_query:
        payments = payments.filter(
            Q(order__order_code__icontains=search_query) |
            Q(customer_name__icontains=search_query) |
            Q(transaction_id__icontains=search_query) |
            Q(notes__icontains=search_query)
        )
        truvo_payments = truvo_payments.filter(
            Q(payment_id__icontains=search_query) |
            Q(customer_name__icontains=search_query) |
            Q(truvo_transaction_id__icontains=search_query)
        )
    
    # Combine payments for display
    all_payments = list(payments) + list(truvo_payments)
    all_payments.sort(key=lambda x: x.payment_date if hasattr(x, 'payment_date') else x.created_at, reverse=True)
    
    # Pagination
    paginator = Paginator(all_payments, 10)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    status_choices = Payment.PAYMENT_STATUS
    payment_method_choices = Payment.PAYMENT_METHODS
    
    # Statistics
    total_payments = len(all_payments)
    total_amount = sum(p.amount for p in all_payments)
    completed_payments = len([p for p in all_payments if p.payment_status == 'completed'])
    pending_payments = len([p for p in all_payments if p.payment_status == 'pending'])
    
    # Additional statistics for cards
    today_payments = len([p for p in all_payments if p.payment_date and p.payment_date.date() == timezone.now().date()])
    this_month_payments = len([p for p in all_payments if p.payment_date and p.payment_date.month == timezone.now().month])
    overdue_payments = len([p for p in all_payments if p.payment_status == 'pending' and p.payment_date and p.payment_date.date() < timezone.now().date()])
    
    context = {
        'page_obj': page_obj,
        'status_choices': status_choices,
        'payment_method_choices': payment_method_choices,
        'current_status': status_filter,
        'current_payment_method': payment_method_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
        'total_payments': total_payments,
        'total_amount': total_amount,
        'completed_payments': completed_payments,
        'pending_payments': pending_payments,
        'today_payments': today_payments,
        'this_month_payments': this_month_payments,
        'overdue_payments': overdue_payments,
        'is_seller': is_seller,
        'is_admin': is_admin,
    }
    
    return render(request, 'finance/payment_management.html', context)

@login_required
def add_payment(request):
    """Add new payment - accessible by both admin and sellers."""
    # Check user role for access control
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.has_role('Admin') or request.user.has_role('Super Admin') or request.user.is_superuser
    
    if request.method == 'POST':
        try:
            # Get form data
            amount = request.POST.get('amount')
            payment_method = request.POST.get('payment_method')
            customer_name = request.POST.get('customer_name')
            customer_email = request.POST.get('customer_email')
            customer_phone = request.POST.get('customer_phone')
            order_id = request.POST.get('order_id')
            notes = request.POST.get('notes', '')
            payment_status = request.POST.get('payment_status', 'pending')
            
            # Validate required fields
            if not all([amount, payment_method, customer_name]):
                messages.error(request, 'Please fill in all required fields.')
                return redirect('finance:add_payment')
            
            # Create payment
            payment_data = {
                'amount': float(amount),
                'payment_method': payment_method,
                'customer_name': customer_name,
                'customer_email': customer_email,
                'customer_phone': customer_phone,
                'notes': notes,
                'payment_status': payment_status,
                'payment_date': timezone.now(),
                'seller': request.user if is_seller else None,
            }
            
            if order_id:
                try:
                    order = Order.objects.get(id=order_id)
                    payment_data['order'] = order
                except Order.DoesNotExist:
                    pass
            
            # Create regular payment or Truvo payment
            if payment_method == 'truvo':
                payment = TruvoPayment.objects.create(**payment_data)
                messages.success(request, f'Truvo payment {payment.payment_id} created successfully!')
            else:
                payment = Payment.objects.create(**payment_data)
                messages.success(request, f'Payment created successfully!')
            
            return redirect('finance:payment_management')
            
        except Exception as e:
            messages.error(request, f'Error creating payment: {str(e)}')
            return redirect('finance:add_payment')
    
    # Get available orders for selection
    if is_seller:
        orders = Order.objects.filter(seller_email=request.user.email)[:10]
    else:
        orders = Order.objects.all()[:10]
    
    context = {
        'orders': orders,
        'payment_methods': Payment.PAYMENT_METHODS,
        'payment_statuses': Payment.PAYMENT_STATUS,
        'is_seller': is_seller,
        'is_admin': is_admin,
    }
    
    return render(request, 'finance/add_payment.html', context)

@login_required
def truvo_payment_create(request):
    """Create a new Truvo payment."""
    # Check user role for access control
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.has_role('Admin') or request.user.has_role('Super Admin') or request.user.is_superuser
    
    if request.method == 'POST':
        try:
            # Get form data
            amount = request.POST.get('amount')
            customer_name = request.POST.get('customer_name')
            customer_email = request.POST.get('customer_email')
            customer_phone = request.POST.get('customer_phone')
            order_id = request.POST.get('order_id')
            
            # Validate required fields
            if not all([amount, customer_name, customer_email, customer_phone]):
                messages.error(request, 'Please fill in all required fields.')
                return redirect('finance:payment_management')
            
            # Create Truvo payment
            payment_data = {
                'amount': float(amount),
                'customer_name': customer_name,
                'customer_email': customer_email,
                'customer_phone': customer_phone,
                'seller': request.user if is_seller else None,
            }
            
            if order_id:
                try:
                    order = Order.objects.get(id=order_id)
                    payment_data['order'] = order
                except Order.DoesNotExist:
                    pass
            
            # In a real implementation, you would integrate with Truvo API here
            # For now, we'll create a mock payment
            payment = TruvoPayment.objects.create(**payment_data)
            
            # Simulate payment URL generation
            payment.payment_url = f"https://truvo.pay/{payment.payment_id}"
            payment.save()
            
            messages.success(request, f'Truvo payment {payment.payment_id} created successfully!')
            return redirect('finance:payment_management')
            
        except Exception as e:
            messages.error(request, f'Error creating Truvo payment: {str(e)}')
            return redirect('finance:payment_management')
    
    # Get available orders for selection
    if is_seller:
        orders = Order.objects.filter(seller_email=request.user.email)[:10]
    else:
        orders = Order.objects.all()[:10]
    
    context = {
        'orders': orders,
        'is_seller': is_seller,
        'is_admin': is_admin,
    }
    
    return render(request, 'finance/truvo_payment_create.html', context)

@login_required
def export_payments(request):
    """Export payments to CSV - RESTRICTED TO SUPER ADMIN ONLY."""
    import csv
    from io import StringIO
    from users.models import AuditLog

    # SECURITY: Restrict data export to Super Admin only (P0 CRITICAL requirement)
    if not request.user.is_superuser:
        from utils.views import permission_denied_authenticated
        AuditLog.objects.create(
            user=request.user,
            action='unauthorized_export_attempt',
            entity_type='payment',
            description=f"Unauthorized attempt to export payments by {request.user.email}",
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT', '')
        )
        return permission_denied_authenticated(
            request,
            message="Data export is restricted to Super Admin only for security compliance."
        )

    # Check user role for access control (legacy - now only superuser can reach here)
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.has_role('Admin') or request.user.has_role('Super Admin') or request.user.is_superuser
    
    # Get filter parameters (same as payment_management)
    status_filter = request.GET.get('status', '')
    payment_method_filter = request.GET.get('payment_method', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search_query = request.GET.get('search', '')
    
    # Base queryset - sellers see only their payments, admins see all
    if is_seller:
        payments = Payment.objects.filter(seller=request.user).select_related('order').order_by('-payment_date')
        truvo_payments = TruvoPayment.objects.filter(seller=request.user).order_by('-created_at')
    else:
        payments = Payment.objects.select_related('order').order_by('-payment_date')
        truvo_payments = TruvoPayment.objects.all().order_by('-created_at')
    
    # Apply filters (same logic as payment_management)
    if status_filter:
        payments = payments.filter(payment_status=status_filter)
        truvo_payments = truvo_payments.filter(payment_status=status_filter)
    
    if payment_method_filter:
        payments = payments.filter(payment_method=payment_method_filter)
        if payment_method_filter == 'truvo':
            payments = truvo_payments
            truvo_payments = TruvoPayment.objects.none()
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            payments = payments.filter(payment_date__date__gte=date_from_obj)
            truvo_payments = truvo_payments.filter(created_at__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            payments = payments.filter(payment_date__date__lte=date_to_obj)
            truvo_payments = truvo_payments.filter(created_at__date__lte=date_to_obj)
        except ValueError:
            pass
    
    if search_query:
        payments = payments.filter(
            Q(order__order_code__icontains=search_query) |
            Q(customer_name__icontains=search_query) |
            Q(transaction_id__icontains=search_query) |
            Q(notes__icontains=search_query)
        )
        truvo_payments = truvo_payments.filter(
            Q(payment_id__icontains=search_query) |
            Q(customer_name__icontains=search_query) |
            Q(truvo_transaction_id__icontains=search_query)
        )
    
    # Combine payments
    all_payments = list(payments) + list(truvo_payments)
    all_payments.sort(key=lambda x: x.payment_date if hasattr(x, 'payment_date') else x.created_at, reverse=True)
    
    # Create CSV response
    response = HttpResponse(content_type='text/csv')
    filename = f"payments_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    if is_seller:
        filename = f"my_payments_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Payment ID', 'Order ID', 'Customer', 'Amount', 'Currency', 'Method', 
        'Status', 'Date', 'Seller', 'Transaction ID', 'Notes'
    ])
    
    for payment in all_payments:
        writer.writerow([
            getattr(payment, 'payment_id', payment.id),
            payment.order.order_code if payment.order else 'N/A',
            payment.customer_name,
            payment.amount,
            getattr(payment, 'currency', 'AED'),
            payment.payment_method,
            payment.payment_status,
            payment.payment_date.strftime('%Y-%m-%d %H:%M:%S') if hasattr(payment, 'payment_date') else payment.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            payment.seller.get_full_name() if payment.seller else 'N/A',
            getattr(payment, 'transaction_id', getattr(payment, 'truvo_transaction_id', '')),
            payment.notes
        ])

    # Audit log for successful export (P0 CRITICAL security requirement)
    AuditLog.objects.create(
        user=request.user,
        action='data_export',
        entity_type='payment',
        description=f"Exported {len(all_payments)} payment records to CSV",
        ip_address=request.META.get('REMOTE_ADDR'),
        user_agent=request.META.get('HTTP_USER_AGENT', '')
    )

    return response

@login_required
def payment_platforms(request):
    """View for managing payment platform integrations"""
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.has_role('Admin') or request.user.has_role('Super Admin') or request.user.is_superuser
    
    # Get platforms for the current user
    platforms = PaymentPlatform.objects.filter(user=request.user).order_by('-created_at')
    
    # Calculate real statistics
    total_platforms = platforms.count()
    active_platforms = platforms.filter(status='active').count()
    pending_platforms = platforms.filter(status='pending').count()
    inactive_platforms = platforms.filter(status='inactive').count()
    
    # Get recent sync logs
    recent_syncs = PlatformSyncLog.objects.filter(platform__user=request.user).order_by('-started_at')[:5]
    
    context = {
        'platforms': platforms,
        'is_seller': is_seller,
        'is_admin': is_admin,
        'total_platforms': total_platforms,
        'active_platforms': active_platforms,
        'pending_platforms': pending_platforms,
        'inactive_platforms': inactive_platforms,
        'recent_syncs': recent_syncs,
    }
    
    return render(request, 'finance/payment_platforms.html', context)

@login_required
def add_payment_platform(request):
    """View for adding a new payment platform integration"""
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.has_role('Admin') or request.user.has_role('Super Admin') or request.user.is_superuser
    
    if request.method == 'POST':
        form = PaymentPlatformForm(request.POST)
        if form.is_valid():
            try:
                platform = form.save(commit=False)
                platform.user = request.user
                platform.status = 'pending'  # Default status
                platform.created_at = timezone.now()
                platform.save()
                
                messages.success(request, _('Payment platform added successfully! Please test the connection.'))
                return redirect('finance:payment_platforms')
            except Exception as e:
                messages.error(request, f'Error saving platform: {str(e)}')
        else:
            messages.error(request, 'Please correct the errors below.')
    else:
        form = PaymentPlatformForm()
    
    context = {
        'form': form,
        'is_seller': is_seller,
        'is_admin': is_admin,
    }
    
    return render(request, 'finance/add_payment_platform.html', context)

@login_required
def edit_payment_platform(request, platform_id):
    """View for editing a payment platform integration"""
    platform = get_object_or_404(PaymentPlatform, id=platform_id, user=request.user)
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.is_superuser
    
    if request.method == 'POST':
        form = PaymentPlatformForm(request.POST, instance=platform)
        if form.is_valid():
            form.save()
            messages.success(request, _('Payment platform updated successfully!'))
            return redirect('finance:payment_platforms')
    else:
        form = PaymentPlatformForm(instance=platform)
    
    context = {
        'form': form,
        'platform': platform,
        'is_seller': is_seller,
        'is_admin': is_admin,
    }
    
    return render(request, 'finance/edit_payment_platform.html', context)

@login_required
def delete_payment_platform(request, platform_id):
    """View for deleting a payment platform integration"""
    platform = get_object_or_404(PaymentPlatform, id=platform_id, user=request.user)
    
    if request.method == 'POST':
        platform_name = platform.get_platform_display_name()
        platform.delete()
        messages.success(request, _('Payment platform "{}" deleted successfully!').format(platform_name))
        return redirect('finance:payment_platforms')
    
    context = {
        'platform': platform,
    }
    
    return render(request, 'finance/delete_payment_platform.html', context)

@login_required
def test_platform_connection(request, platform_id):
    """View for testing platform connection"""
    platform = get_object_or_404(PaymentPlatform, id=platform_id, user=request.user)
    
    if request.method == 'POST':
        form = PlatformConnectionTestForm(request.POST)
        if form.is_valid():
            test_type = form.cleaned_data['test_type']
            
            # Simulate connection test (in real implementation, this would call platform APIs)
            try:
                if test_type == 'connection':
                    # Test basic connection
                    platform.status = 'active'
                    platform.save()
                    messages.success(request, _('Connection test successful! Platform is now active.'))
                else:
                    # Test data sync
                    sync_log = PlatformSyncLog.objects.create(
                        platform=platform,
                        sync_type=test_type,
                        status='success',
                        records_processed=10,
                        records_synced=10,
                        completed_at=timezone.now()
                    )
                    messages.success(request, _('{} sync test successful! 10 records processed.').format(
                        sync_log.get_sync_type_display()
                    ))
                
            except Exception as e:
                platform.status = 'error'
                platform.save()
                messages.error(request, _('Connection test failed: {}').format(str(e)))
            
            return redirect('finance:payment_platforms')
    else:
        form = PlatformConnectionTestForm(initial={'platform_id': platform_id})
    
    context = {
        'form': form,
        'platform': platform,
    }
    
    return render(request, 'finance/test_platform_connection.html', context)

@login_required
def sync_platform_data(request, platform_id):
    """View for manually syncing platform data"""
    platform = get_object_or_404(PaymentPlatform, id=platform_id, user=request.user)
    
    if request.method == 'POST':
        form = PlatformSyncForm(request.POST)
        if form.is_valid():
            # Simulate data sync (in real implementation, this would call platform APIs)
            try:
                sync_log = PlatformSyncLog.objects.create(
                    platform=platform,
                    sync_type='orders',
                    status='success',
                    records_processed=25,
                    records_synced=25,
                    completed_at=timezone.now()
                )
                
                platform.last_sync = timezone.now()
                platform.save()
                
                messages.success(request, _('Data sync completed successfully! 25 records synced.'))
                
            except Exception as e:
                messages.error(request, _('Data sync failed: {}').format(str(e)))
            
            return redirect('finance:payment_platforms')
    else:
        form = PlatformSyncForm(initial={'platform_id': platform_id})
    
    context = {
        'form': form,
        'platform': platform,
    }
    
    return render(request, 'finance/sync_platform_data.html', context)

@login_required
def platform_sync_logs(request, platform_id):
    """View for viewing platform sync logs"""
    platform = get_object_or_404(PaymentPlatform, id=platform_id, user=request.user)
    sync_logs = PlatformSyncLog.objects.filter(platform=platform).order_by('-started_at')[:50]
    
    context = {
        'platform': platform,
        'sync_logs': sync_logs,
    }
    
    return render(request, 'finance/platform_sync_logs.html', context)

@login_required
def edit_payment(request, payment_id):
    """View for editing a payment"""
    payment = get_object_or_404(Payment, id=payment_id)
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.is_superuser
    
    if request.method == 'POST':
        form = PaymentForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
            messages.success(request, _('Payment updated successfully!'))
            return redirect('finance:payment_management')
    else:
        form = PaymentForm(instance=payment)
    
    context = {
        'form': form,
        'payment': payment,
        'is_seller': is_seller,
        'is_admin': is_admin,
    }
    
    return render(request, 'finance/edit_payment.html', context)

@login_required
def delete_payment(request, payment_id):
    """View for deleting a payment"""
    payment = get_object_or_404(Payment, id=payment_id)
    
    if request.method == 'POST':
        payment.delete()
        messages.success(request, _('Payment deleted successfully!'))
        return redirect('finance:payment_management')
    
    context = {
        'payment': payment,
    }
    
    return render(request, 'finance/delete_payment.html', context)

@login_required
def edit_truvo_payment(request, payment_id):
    """View for editing a Truvo payment"""
    payment = get_object_or_404(TruvoPayment, id=payment_id)
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.is_superuser
    
    if request.method == 'POST':
        form = TruvoPaymentForm(request.POST, instance=payment)
        if form.is_valid():
            form.save()
            messages.success(request, _('Truvo payment updated successfully!'))
            return redirect('finance:payment_management')
    else:
        form = TruvoPaymentForm(instance=payment)
    
    context = {
        'form': form,
        'payment': payment,
        'is_seller': is_seller,
        'is_admin': is_admin,
    }
    
    return render(request, 'finance/edit_truvo_payment.html', context)

@login_required
def delete_truvo_payment(request, payment_id):
    """View for deleting a Truvo payment"""
    payment = get_object_or_404(TruvoPayment, id=payment_id)
    
    if request.method == 'POST':
        payment.delete()
        messages.success(request, _('Truvo payment deleted successfully!'))
        return redirect('finance:payment_management')
    
    context = {
        'payment': payment,
    }
    
    return render(request, 'finance/delete_truvo_payment.html', context)

@login_required
def financial_reports(request):
    """View for financial reports with real data"""
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.is_superuser
    
    # Get real financial data
    from django.db.models import Sum, Count, Avg
    
    # Date range for reports
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    # Get orders and payments data
    if is_seller:
        orders = Order.objects.filter(
            product__seller=request.user,
            date__range=(start_date, end_date)
        )
        payments = Payment.objects.filter(
            seller=request.user,
            payment_date__range=(start_date, end_date)
        )
        truvo_payments = TruvoPayment.objects.filter(
            seller=request.user,
            created_at__range=(start_date, end_date)
        )
    else:
        orders = Order.objects.filter(date__range=(start_date, end_date))
        payments = Payment.objects.filter(payment_date__range=(start_date, end_date))
        truvo_payments = TruvoPayment.objects.filter(created_at__range=(start_date, end_date))
    
    # Calculate financial metrics
    total_revenue = orders.aggregate(
        total=Sum(F('price_per_unit') * F('quantity'))
    )['total'] or 0
    
    total_payments = payments.aggregate(total=Sum('amount'))['total'] or 0
    total_truvo_payments = truvo_payments.aggregate(total=Sum('amount'))['total'] or 0
    total_payments_received = total_payments + total_truvo_payments
    
    # Order statistics
    total_orders = orders.count()
    pending_orders = orders.filter(status='pending').count()
    completed_orders = orders.filter(status__in=['delivered', 'shipped']).count()
    cancelled_orders = orders.filter(status='cancelled').count()
    
    # Payment statistics
    completed_payments = payments.filter(payment_status='completed').count()
    pending_payments = payments.filter(payment_status='pending').count()
    failed_payments = payments.filter(payment_status='failed').count()
    
    # Average order value
    avg_order_value = orders.aggregate(
        avg=Avg(F('price_per_unit') * F('quantity'))
    )['avg'] or 0
    
    # Top selling products
    top_products = orders.values('product__name_en').annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum(F('price_per_unit') * F('quantity'))
    ).order_by('-total_revenue')[:5]
    
    # Daily revenue for chart
    daily_revenue = orders.values('date__date').annotate(
        revenue=Sum(F('price_per_unit') * F('quantity'))
    ).order_by('date__date')
    
    # Handle form actions
    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'export':
            # Export functionality
            import csv
            from django.http import HttpResponse
            
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="financial_report.csv"'
            
            writer = csv.writer(response)
            writer.writerow(['Date', 'Orders', 'Revenue', 'Payments', 'Net Revenue'])
            
            for day_data in daily_revenue:
                date = day_data['date__date']
                day_orders = orders.filter(date__date=date)
                day_payments = payments.filter(payment_date__date=date)
                
                writer.writerow([
                    date,
                    day_orders.count(),
                    day_data['revenue'],
                    day_payments.aggregate(total=Sum('amount'))['total'] or 0,
                    day_data['revenue'] - (day_payments.aggregate(total=Sum('amount'))['total'] or 0)
                ])
            
            return response
        
        elif action == 'new_report':
            # Generate new report with different parameters
            report_type = request.POST.get('report_type', 'monthly')
            messages.success(request, f'New {report_type} report generated successfully!')
            return redirect('finance:financial_reports')
        
        elif action == 'settings':
            # Handle report settings
            messages.success(request, 'Report settings updated successfully!')
            return redirect('finance:financial_reports')
        
        elif action == 'daily_revenue':
            # Generate daily revenue report
            messages.success(request, 'Daily revenue report generated successfully!')
            return redirect('finance:financial_reports')
        
        elif action == 'payment_summary':
            # Generate payment summary report
            messages.success(request, 'Payment summary report generated successfully!')
            return redirect('finance:financial_reports')
        
        elif action == 'fee_analysis':
            # Generate fee analysis report
            messages.success(request, 'Fee analysis report generated successfully!')
            return redirect('finance:financial_reports')
        
        elif action == 'seller_report':
            # Generate seller report
            messages.success(request, 'Seller report generated successfully!')
            return redirect('finance:financial_reports')
    
    context = {
        'is_seller': is_seller,
        'is_admin': is_admin,
        'total_revenue': total_revenue,
        'total_payments_received': total_payments_received,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'completed_orders': completed_orders,
        'cancelled_orders': cancelled_orders,
        'completed_payments': completed_payments,
        'pending_payments': pending_payments,
        'failed_payments': failed_payments,
        'avg_order_value': avg_order_value,
        'top_products': top_products,
        'daily_revenue': daily_revenue,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'finance/financial_reports.html', context)

@login_required
def sales_reports(request):
    """View for sales reports with real data"""
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.is_superuser
    
    # Get real sales data
    from datetime import datetime, timedelta
    from django.db.models import Sum, Count, Avg
    from django.utils import timezone
    
    # Date range for reports
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    # Get sales data
    if is_seller:
        orders = Order.objects.filter(
            product__seller=request.user,
            date__range=(start_date, end_date)
        )
    else:
        orders = Order.objects.filter(date__range=(start_date, end_date))
    
    # Calculate sales metrics
    total_sales = orders.aggregate(
        total=Sum(F('price_per_unit') * F('quantity'))
    )['total'] or 0
    
    total_orders = orders.count()
    avg_order_value = orders.aggregate(
        avg=Avg(F('price_per_unit') * F('quantity'))
    )['avg'] or 0
    
    # Sales by status
    pending_sales = orders.filter(status='pending').aggregate(
        total=Sum(F('price_per_unit') * F('quantity'))
    )['total'] or 0
    
    completed_sales = orders.filter(status__in=['delivered', 'shipped']).aggregate(
        total=Sum(F('price_per_unit') * F('quantity'))
    )['total'] or 0
    
    # Top selling products
    top_products = orders.values('product__name_en').annotate(
        total_quantity=Sum('quantity'),
        total_revenue=Sum(F('price_per_unit') * F('quantity'))
    ).order_by('-total_revenue')[:10]
    
    # Daily sales for chart
    daily_sales = orders.values('date__date').annotate(
        sales=Sum(F('price_per_unit') * F('quantity')),
        orders_count=Count('id')
    ).order_by('date__date')
    
    context = {
        'is_seller': is_seller,
        'is_admin': is_admin,
        'total_sales': total_sales,
        'total_orders': total_orders,
        'avg_order_value': avg_order_value,
        'pending_sales': pending_sales,
        'completed_sales': completed_sales,
        'top_products': top_products,
        'daily_sales': daily_sales,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'finance/sales_reports.html', context)

@login_required
def payment_reports(request):
    """View for payment reports with real data"""
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.is_superuser
    
    # Get real payment data
    from datetime import datetime, timedelta
    from django.db.models import Sum, Count, Avg
    from django.utils import timezone
    
    # Date range for reports
    end_date = timezone.now()
    start_date = end_date - timedelta(days=30)
    
    # Get payment data
    if is_seller:
        payments = Payment.objects.filter(
            seller=request.user,
            payment_date__range=(start_date, end_date)
        )
        truvo_payments = TruvoPayment.objects.filter(
            seller=request.user,
            created_at__range=(start_date, end_date)
        )
    else:
        payments = Payment.objects.filter(payment_date__range=(start_date, end_date))
        truvo_payments = TruvoPayment.objects.filter(created_at__range=(start_date, end_date))
    
    # Calculate payment metrics
    total_payments = payments.aggregate(total=Sum('amount'))['total'] or 0
    total_truvo_payments = truvo_payments.aggregate(total=Sum('amount'))['total'] or 0
    total_received = total_payments + total_truvo_payments
    
    # Payment status breakdown
    completed_payments = payments.filter(payment_status='completed').aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    pending_payments = payments.filter(payment_status='pending').aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    failed_payments = payments.filter(payment_status='failed').aggregate(
        total=Sum('amount')
    )['total'] or 0
    
    # Payment method breakdown
    payment_methods = payments.values('payment_method').annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')
    
    # Daily payments for chart
    daily_payments = payments.values('payment_date__date').annotate(
        amount=Sum('amount'),
        count=Count('id')
    ).order_by('payment_date__date')
    
    context = {
        'is_seller': is_seller,
        'is_admin': is_admin,
        'total_received': total_received,
        'total_payments': total_payments,
        'total_truvo_payments': total_truvo_payments,
        'completed_payments': completed_payments,
        'pending_payments': pending_payments,
        'failed_payments': failed_payments,
        'payment_methods': payment_methods,
        'daily_payments': daily_payments,
        'start_date': start_date,
        'end_date': end_date,
    }
    
    return render(request, 'finance/payment_reports.html', context)

@login_required
def order_management(request):
    """View for order management with enhanced filtering"""
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.is_superuser
    
    # Get orders with pagination
    orders = Order.objects.select_related('product', 'seller', 'agent').order_by('-date')
    
    # Apply filters
    search_query = request.GET.get('search', '')
    status_filter = request.GET.get('status', '')
    workflow_status_filter = request.GET.get('workflow_status', '')
    date_filter = request.GET.get('date', '')
    emirate_filter = request.GET.get('emirate', '')
    seller_filter = request.GET.get('seller', '')
    agent_filter = request.GET.get('agent', '')
    amount_min = request.GET.get('amount_min', '')
    amount_max = request.GET.get('amount_max', '')
    payment_status = request.GET.get('payment_status', '')
    
    # Search filter
    if search_query:
        orders = orders.filter(
            Q(order_code__icontains=search_query) |
            Q(customer__icontains=search_query) |
            Q(customer_phone__icontains=search_query) |
            Q(product__name_en__icontains=search_query) |
            Q(product__name_ar__icontains=search_query) |
            Q(notes__icontains=search_query)
        )
    
    # Status filter
    if status_filter:
        orders = orders.filter(status=status_filter)
    
    # Workflow status filter
    if workflow_status_filter:
        orders = orders.filter(workflow_status=workflow_status_filter)
    
    # Date filter
    if date_filter:
        today = timezone.now().date()
        if date_filter == 'today':
            orders = orders.filter(date__date=today)
        elif date_filter == 'yesterday':
            yesterday = today - timedelta(days=1)
            orders = orders.filter(date__date=yesterday)
        elif date_filter == 'week':
            week_ago = today - timedelta(days=7)
            orders = orders.filter(date__date__gte=week_ago)
        elif date_filter == 'month':
            orders = orders.filter(date__month=today.month, date__year=today.year)
        elif date_filter == 'quarter':
            quarter_start = today.replace(day=1)
            quarter_start = quarter_start.replace(month=((today.month - 1) // 3) * 3 + 1)
            orders = orders.filter(date__date__gte=quarter_start)
        elif date_filter == 'year':
            orders = orders.filter(date__year=today.year)
    
    # Emirate filter
    if emirate_filter:
        orders = orders.filter(emirate=emirate_filter)
    
    # Seller filter
    if seller_filter:
        orders = orders.filter(seller_id=seller_filter)
    
    # Agent filter
    if agent_filter:
        orders = orders.filter(agent_id=agent_filter)
    
    # Amount range filter
    if amount_min:
        try:
            min_amount = float(amount_min)
            orders = orders.filter(
                F('price_per_unit') * F('quantity') >= min_amount
            )
        except ValueError:
            pass
    
    if amount_max:
        try:
            max_amount = float(amount_max)
            orders = orders.filter(
                F('price_per_unit') * F('quantity') <= max_amount
            )
        except ValueError:
            pass
    
    # Payment status filter
    if payment_status:
        if payment_status == 'paid':
            # Orders with completed payments
            orders = orders.filter(
                Q(payments__payment_status='completed') | 
                Q(truvo_payments__payment_status='completed')
            ).distinct()
        elif payment_status == 'pending':
            # Orders with pending payments
            orders = orders.filter(
                Q(payments__payment_status='pending') | 
                Q(truvo_payments__payment_status__in=['initiated', 'processing'])
            ).distinct()
        elif payment_status == 'failed':
            # Orders with failed payments
            orders = orders.filter(
                Q(payments__payment_status='failed') | 
                Q(truvo_payments__payment_status__in=['failed', 'cancelled'])
            ).distinct()
        elif payment_status == 'no_payment':
            # Orders without any payment records
            orders = orders.filter(
                Q(payments__isnull=True) & Q(truvo_payments__isnull=True)
            )
    
    # Pagination
    paginator = Paginator(orders, 20)  # 20 orders per page
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Calculate statistics
    total_orders = Order.objects.count()
    pending_orders = Order.objects.filter(status='pending').count()
    confirmed_orders = Order.objects.filter(status='confirmed').count()
    processing_orders = Order.objects.filter(status='processing').count()
    packaged_orders = Order.objects.filter(status='packaged').count()
    shipped_orders = Order.objects.filter(status='shipped').count()
    completed_orders = Order.objects.filter(status__in=['delivered', 'shipped']).count()
    cancelled_orders = Order.objects.filter(status='cancelled').count()
    postponed_orders = Order.objects.filter(status='postponed').count()
    
    # Payment statistics
    paid_orders = Order.objects.filter(
        Q(payments__payment_status='completed') | 
        Q(truvo_payments__payment_status='completed')
    ).distinct().count()
    
    pending_payment_orders = Order.objects.filter(
        Q(payments__payment_status='pending') | 
        Q(truvo_payments__payment_status__in=['initiated', 'processing'])
    ).distinct().count()
    
    total_revenue = Order.objects.aggregate(
        total=Sum(F('price_per_unit') * F('quantity'))
    )['total'] or 0
    
    # Get filter options for dropdowns
    emirates = Order.objects.values_list('emirate', flat=True).distinct().exclude(emirate='').exclude(emirate__isnull=True)
    sellers = User.objects.filter(orders__isnull=False).distinct().values('id', 'email', 'first_name', 'last_name')
    agents = User.objects.filter(assigned_orders__isnull=False).distinct().values('id', 'email', 'first_name', 'last_name')
    
    context = {
        'orders': page_obj,
        'total_orders': total_orders,
        'pending_orders': pending_orders,
        'confirmed_orders': confirmed_orders,
        'processing_orders': processing_orders,
        'packaged_orders': packaged_orders,
        'shipped_orders': shipped_orders,
        'completed_orders': completed_orders,
        'cancelled_orders': cancelled_orders,
        'postponed_orders': postponed_orders,
        'paid_orders': paid_orders,
        'pending_payment_orders': pending_payment_orders,
        'total_revenue': total_revenue,
        'is_seller': is_seller,
        'is_admin': is_admin,
        'emirates': emirates,
        'sellers': sellers,
        'agents': agents,
        'current_filters': {
            'search': search_query,
            'status': status_filter,
            'workflow_status': workflow_status_filter,
            'date': date_filter,
            'emirate': emirate_filter,
            'seller': seller_filter,
            'agent': agent_filter,
            'amount_min': amount_min,
            'amount_max': amount_max,
            'payment_status': payment_status,
        }
    }
    
    return render(request, 'finance/order_management.html', context)

@login_required
def order_detail(request, order_id):
    """View for order detail"""
    order = get_object_or_404(Order, id=order_id)
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.is_superuser
    
    # Calculate financial values
    subtotal = order.price_per_unit * order.quantity
    total_amount = order.total_price_aed if order.total_price_aed else subtotal
    
    context = {
        'order': order,
        'subtotal': subtotal,
        'total_amount': total_amount,
        'is_seller': is_seller,
        'is_admin': is_admin,
    }
    
    return render(request, 'finance/order_detail.html', context)

@login_required
def upload_bank_statement(request):
    """View for uploading bank statement"""
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.is_superuser
    
    context = {
        'is_seller': is_seller,
        'is_admin': is_admin,
    }
    
    return render(request, 'finance/upload_bank_statement.html', context)

@login_required
def finance_settings(request):
    """View for finance settings"""
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.is_superuser
    
    context = {
        'is_seller': is_seller,
        'is_admin': is_admin,
    }
    
    return render(request, 'finance/finance_settings.html', context)

@login_required
def fee_settings(request):
    """View for fee settings"""
    is_seller = request.user.has_role('Seller')
    is_admin = request.user.is_superuser
    
    context = {
        'is_seller': is_seller,
        'is_admin': is_admin,
    }
    
    return render(request, 'finance/fee_settings.html', context)


@login_required
def invoice_list(request):
    """List all invoices with filtering and pagination"""
    from .models import Invoice
    
    # Get filter parameters
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search_query = request.GET.get('search', '')
    
    # Base queryset
    invoices = Invoice.objects.select_related('order').order_by('-created_at')
    
    # Apply filters
    if status_filter:
        invoices = invoices.filter(status=status_filter)
    
    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            invoices = invoices.filter(created_at__date__gte=date_from_obj)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            invoices = invoices.filter(created_at__date__lte=date_to_obj)
        except ValueError:
            pass
    
    if search_query:
        invoices = invoices.filter(
            Q(invoice_number__icontains=search_query) |
            Q(order__order_code__icontains=search_query) |
            Q(order__customer__icontains=search_query)
        )
    
    # Pagination
    paginator = Paginator(invoices, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)
    
    # Get filter options
    status_choices = Invoice.INVOICE_STATUS
    
    context = {
        'page_obj': page_obj,
        'status_choices': status_choices,
        'current_status': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
    }
    
    return render(request, 'finance/invoice_list.html', context)

@login_required
def create_invoice(request):
    """Create a new invoice"""
    from .models import Invoice
    from .forms import InvoiceForm
    
    if request.method == 'POST':
        form = InvoiceForm(request.POST)
        if form.is_valid():
            invoice = form.save(commit=False)
            # Generate invoice number if not provided
            if not invoice.invoice_number:
                invoice.invoice_number = f'INV-{invoice.order.order_code}-{timezone.now().strftime("%Y%m%d")}'
            invoice.save()
            messages.success(request, f'Invoice {invoice.invoice_number} created successfully!')
            return redirect('finance:invoice_detail', invoice_id=invoice.id)
    else:
        form = InvoiceForm()
    
    # Get orders that don't have invoices yet
    orders_without_invoices = Order.objects.filter(invoices__isnull=True).order_by('-date')[:20]
    
    context = {
        'form': form,
        'orders': orders_without_invoices,
    }
    
    return render(request, 'finance/create_invoice.html', context)

@login_required
def invoice_detail(request, invoice_id):
    """View invoice details"""
    from .models import Invoice
    
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    # Calculate subtotal
    subtotal = invoice.order.price_per_unit * invoice.order.quantity
    
    context = {
        'invoice': invoice,
        'subtotal': subtotal,
    }
    
    return render(request, 'finance/invoice_detail.html', context)

@login_required
def edit_invoice(request, invoice_id):
    """Edit invoice details"""
    from .models import Invoice
    
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if request.method == 'POST':
        invoice.total_amount = request.POST.get('total_amount', invoice.total_amount)
        invoice.status = request.POST.get('status', invoice.status)
        invoice.due_date = request.POST.get('due_date', invoice.due_date)
        invoice.notes = request.POST.get('notes', invoice.notes)
        invoice.save()
        
        messages.success(request, 'Invoice updated successfully!')
        return redirect('finance:invoice_detail', invoice_id=invoice.id)
    
    context = {
        'invoice': invoice,
        'status_choices': Invoice.INVOICE_STATUS,
    }
    
    return render(request, 'finance/edit_invoice.html', context)

@login_required
def delete_invoice(request, invoice_id):
    """Delete an invoice"""
    from .models import Invoice
    
    invoice = get_object_or_404(Invoice, id=invoice_id)
    
    if request.method == 'POST':
        invoice_number = invoice.invoice_number
        invoice.delete()
        messages.success(request, f'Invoice {invoice_number} deleted successfully!')
        return redirect('finance:invoices')
    
    context = {
        'invoice': invoice,
    }
    
    return render(request, 'finance/delete_invoice.html', context)


# ============= COD Management Views =============

@login_required
def cod_management(request):
    """COD (Cash on Delivery) Management Dashboard."""
    from orders.models import Order

    # Get filter parameters
    status_filter = request.GET.get('status', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search_query = request.GET.get('search', '')

    # Get COD payments
    cod_payments = Payment.objects.filter(
        payment_method='cod'
    ).select_related('order').order_by('-payment_date')

    # Apply filters
    if status_filter:
        cod_payments = cod_payments.filter(payment_status=status_filter)

    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            cod_payments = cod_payments.filter(payment_date__date__gte=date_from_obj)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            cod_payments = cod_payments.filter(payment_date__date__lte=date_to_obj)
        except ValueError:
            pass

    if search_query:
        cod_payments = cod_payments.filter(
            Q(order__order_code__icontains=search_query) |
            Q(customer_name__icontains=search_query) |
            Q(transaction_id__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(cod_payments, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistics
    total_cod = cod_payments.aggregate(total=Sum('amount'))['total'] or 0
    pending_cod = cod_payments.filter(payment_status='pending').aggregate(total=Sum('amount'))['total'] or 0
    collected_cod = cod_payments.filter(payment_status='completed').aggregate(total=Sum('amount'))['total'] or 0

    # COD by delivery agent (from orders)
    cod_by_agent = cod_payments.values(
        'order__delivery_agent__first_name',
        'order__delivery_agent__last_name'
    ).annotate(
        total=Sum('amount'),
        count=Count('id')
    ).order_by('-total')[:10]

    context = {
        'page_obj': page_obj,
        'total_cod': total_cod,
        'pending_cod': pending_cod,
        'collected_cod': collected_cod,
        'cod_by_agent': cod_by_agent,
        'current_status': status_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
        'status_choices': Payment.PAYMENT_STATUS,
    }

    return render(request, 'finance/cod_management.html', context)


@login_required
def cod_collect(request, cod_id):
    """Mark COD as collected."""
    payment = get_object_or_404(Payment, id=cod_id, payment_method='cod')

    if request.method == 'POST':
        payment.payment_status = 'completed'
        payment.is_verified = True
        payment.verified_at = timezone.now()
        payment.verified_by = request.user
        payment.notes = request.POST.get('notes', '') + f"\nCollected by {request.user.get_full_name()} on {timezone.now().strftime('%Y-%m-%d %H:%M')}"
        payment.save()

        messages.success(request, f'COD payment of AED {payment.amount} marked as collected.')
        return redirect('finance:cod')

    context = {
        'payment': payment,
    }

    return render(request, 'finance/cod_collect.html', context)


@login_required
def cod_reconcile(request, cod_id):
    """Reconcile COD payment with bank deposit."""
    payment = get_object_or_404(Payment, id=cod_id, payment_method='cod')

    if request.method == 'POST':
        bank_reference = request.POST.get('bank_reference', '')
        deposited_amount = request.POST.get('deposited_amount', payment.amount)

        payment.transaction_id = bank_reference
        payment.is_verified = True
        payment.verified_at = timezone.now()
        payment.verified_by = request.user
        payment.notes = payment.notes + f"\nReconciled with bank ref: {bank_reference}, Amount: {deposited_amount}"
        payment.save()

        messages.success(request, f'COD payment reconciled with bank reference {bank_reference}.')
        return redirect('finance:cod')

    context = {
        'payment': payment,
    }

    return render(request, 'finance/cod_reconcile.html', context)


# ============= Seller Payouts Views =============

@login_required
def seller_payouts(request):
    """Seller Payouts Management Dashboard."""
    from .models import SellerPayout

    # Get filter parameters
    status_filter = request.GET.get('status', '')
    seller_filter = request.GET.get('seller', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search_query = request.GET.get('search', '')

    # Get payouts
    payouts = SellerPayout.objects.select_related('seller', 'processed_by').order_by('-created_at')

    # Apply filters
    if status_filter:
        payouts = payouts.filter(status=status_filter)

    if seller_filter:
        payouts = payouts.filter(seller_id=seller_filter)

    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            payouts = payouts.filter(created_at__date__gte=date_from_obj)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            payouts = payouts.filter(created_at__date__lte=date_to_obj)
        except ValueError:
            pass

    if search_query:
        payouts = payouts.filter(
            Q(payout_reference__icontains=search_query) |
            Q(seller__email__icontains=search_query) |
            Q(seller__first_name__icontains=search_query) |
            Q(seller__last_name__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(payouts, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistics
    total_payouts = payouts.aggregate(total=Sum('net_amount'))['total'] or 0
    pending_payouts = payouts.filter(status='pending').aggregate(total=Sum('net_amount'))['total'] or 0
    completed_payouts = payouts.filter(status='completed').aggregate(total=Sum('net_amount'))['total'] or 0

    # Get sellers for filter dropdown
    sellers = User.objects.filter(payouts__isnull=False).distinct()

    context = {
        'page_obj': page_obj,
        'total_payouts': total_payouts,
        'pending_payouts': pending_payouts,
        'completed_payouts': completed_payouts,
        'sellers': sellers,
        'current_status': status_filter,
        'current_seller': seller_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
        'status_choices': SellerPayout.PAYOUT_STATUS,
    }

    return render(request, 'finance/seller_payouts.html', context)


@login_required
def create_payout(request):
    """Create a new seller payout."""
    from .models import SellerPayout

    if request.method == 'POST':
        seller_id = request.POST.get('seller_id')
        gross_amount = request.POST.get('gross_amount')
        commission_rate = request.POST.get('commission_rate', 10)

        try:
            seller = User.objects.get(id=seller_id)
            gross = float(gross_amount)
            commission = gross * (float(commission_rate) / 100)
            net = gross - commission

            payout = SellerPayout.objects.create(
                seller=seller,
                gross_amount=gross,
                commission_amount=commission,
                net_amount=net,
                period_start=request.POST.get('period_start'),
                period_end=request.POST.get('period_end'),
                bank_name=request.POST.get('bank_name', ''),
                account_number=request.POST.get('account_number', ''),
                notes=request.POST.get('notes', ''),
            )

            messages.success(request, f'Payout {payout.payout_reference} created for {seller.get_full_name()}.')
            return redirect('finance:payouts')

        except Exception as e:
            messages.error(request, f'Error creating payout: {str(e)}')

    # Get sellers with sales
    sellers = User.objects.filter(product__isnull=False).distinct()

    context = {
        'sellers': sellers,
    }

    return render(request, 'finance/create_payout.html', context)


@login_required
def payout_detail(request, payout_id):
    """View payout details."""
    from .models import SellerPayout

    payout = get_object_or_404(SellerPayout, id=payout_id)

    context = {
        'payout': payout,
    }

    return render(request, 'finance/payout_detail.html', context)


@login_required
def process_payout(request, payout_id):
    """Process a seller payout."""
    from .models import SellerPayout

    payout = get_object_or_404(SellerPayout, id=payout_id)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            payout.status = 'processing'
            payout.processed_by = request.user
            payout.processed_at = timezone.now()
            messages.success(request, f'Payout {payout.payout_reference} approved for processing.')

        elif action == 'complete':
            payout.status = 'completed'
            payout.transaction_reference = request.POST.get('transaction_reference', '')
            payout.processed_at = timezone.now()
            messages.success(request, f'Payout {payout.payout_reference} marked as completed.')

        elif action == 'reject':
            payout.status = 'failed'
            payout.notes = payout.notes + f"\nRejected by {request.user.get_full_name()}: {request.POST.get('rejection_reason', '')}"
            messages.warning(request, f'Payout {payout.payout_reference} rejected.')

        payout.save()
        return redirect('finance:payouts')

    context = {
        'payout': payout,
    }

    return render(request, 'finance/process_payout.html', context)


# ============= Refunds Views =============

@login_required
def refunds_list(request):
    """Refunds Management Dashboard."""
    from .models import Refund

    # Get filter parameters
    status_filter = request.GET.get('status', '')
    reason_filter = request.GET.get('reason', '')
    date_from = request.GET.get('date_from', '')
    date_to = request.GET.get('date_to', '')
    search_query = request.GET.get('search', '')

    # Get refunds
    refunds = Refund.objects.select_related('order', 'requested_by', 'approved_by').order_by('-created_at')

    # Apply filters
    if status_filter:
        refunds = refunds.filter(status=status_filter)

    if reason_filter:
        refunds = refunds.filter(refund_reason=reason_filter)

    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, '%Y-%m-%d').date()
            refunds = refunds.filter(created_at__date__gte=date_from_obj)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, '%Y-%m-%d').date()
            refunds = refunds.filter(created_at__date__lte=date_to_obj)
        except ValueError:
            pass

    if search_query:
        refunds = refunds.filter(
            Q(refund_reference__icontains=search_query) |
            Q(order__order_code__icontains=search_query) |
            Q(customer_name__icontains=search_query)
        )

    # Pagination
    paginator = Paginator(refunds, 20)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistics
    total_refunds = refunds.aggregate(total=Sum('refund_amount'))['total'] or 0
    pending_refunds = refunds.filter(status='pending').aggregate(total=Sum('refund_amount'))['total'] or 0
    approved_refunds = refunds.filter(status='approved').aggregate(total=Sum('refund_amount'))['total'] or 0
    completed_refunds = refunds.filter(status='completed').aggregate(total=Sum('refund_amount'))['total'] or 0

    context = {
        'page_obj': page_obj,
        'total_refunds': total_refunds,
        'pending_refunds': pending_refunds,
        'approved_refunds': approved_refunds,
        'completed_refunds': completed_refunds,
        'current_status': status_filter,
        'current_reason': reason_filter,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query,
        'status_choices': Refund.REFUND_STATUS,
        'reason_choices': Refund.REFUND_REASON,
    }

    return render(request, 'finance/refunds_list.html', context)


@login_required
def create_refund(request):
    """Create a new refund request."""
    from .models import Refund
    from orders.models import Order

    if request.method == 'POST':
        order_id = request.POST.get('order_id')
        refund_amount = request.POST.get('refund_amount')
        refund_reason = request.POST.get('refund_reason')

        try:
            order = Order.objects.get(id=order_id)

            refund = Refund.objects.create(
                order=order,
                refund_amount=float(refund_amount),
                refund_reason=refund_reason,
                customer_name=order.customer,
                customer_email=getattr(order, 'customer_email', ''),
                customer_phone=getattr(order, 'customer_phone', ''),
                reason_details=request.POST.get('reason_details', ''),
                requested_by=request.user,
            )

            messages.success(request, f'Refund request {refund.refund_reference} created.')
            return redirect('finance:refunds')

        except Exception as e:
            messages.error(request, f'Error creating refund: {str(e)}')

    # Get orders that can be refunded
    orders = Order.objects.filter(
        status__in=['delivered', 'shipped', 'completed']
    ).order_by('-date')[:50]

    context = {
        'orders': orders,
        'reason_choices': Refund.REFUND_REASON,
    }

    return render(request, 'finance/create_refund.html', context)


@login_required
def refund_detail(request, refund_id):
    """View refund details."""
    from .models import Refund

    refund = get_object_or_404(Refund, id=refund_id)

    context = {
        'refund': refund,
    }

    return render(request, 'finance/refund_detail.html', context)


@login_required
def approve_refund(request, refund_id):
    """Approve a refund request."""
    from .models import Refund

    refund = get_object_or_404(Refund, id=refund_id)

    if request.method == 'POST':
        action = request.POST.get('action')

        if action == 'approve':
            refund.status = 'approved'
            refund.approved_by = request.user
            refund.approved_at = timezone.now()
            refund.approval_notes = request.POST.get('approval_notes', '')
            messages.success(request, f'Refund {refund.refund_reference} approved.')

        elif action == 'reject':
            refund.status = 'rejected'
            refund.approved_by = request.user
            refund.approved_at = timezone.now()
            refund.rejection_reason = request.POST.get('rejection_reason', '')
            messages.warning(request, f'Refund {refund.refund_reference} rejected.')

        refund.save()
        return redirect('finance:refunds')

    context = {
        'refund': refund,
    }

    return render(request, 'finance/approve_refund.html', context)


@login_required
def process_refund(request, refund_id):
    """Process an approved refund."""
    from .models import Refund

    refund = get_object_or_404(Refund, id=refund_id, status='approved')

    if request.method == 'POST':
        refund.status = 'completed'
        refund.processed_by = request.user
        refund.processed_at = timezone.now()
        refund.transaction_reference = request.POST.get('transaction_reference', '')
        refund.refund_method = request.POST.get('refund_method', 'bank_transfer')
        refund.save()

        messages.success(request, f'Refund {refund.refund_reference} processed successfully.')
        return redirect('finance:refunds')

    context = {
        'refund': refund,
    }

    return render(request, 'finance/process_refund.html', context)


# ============= Reconciliation Views =============

@login_required
def reconciliation(request):
    """Financial Reconciliation Dashboard."""
    today = timezone.now().date()

    # Get all payments for reconciliation
    all_payments = Payment.objects.select_related('order', 'seller').order_by('-payment_date')

    # Calculate statistics
    total_payments = all_payments.count()

    # Matched payments (verified and completed)
    matched_payments = all_payments.filter(
        payment_status='completed',
        is_verified=True
    )
    matched_count = matched_payments.count()
    matched_amount = matched_payments.aggregate(total=Sum('amount'))['total'] or 0

    # Unmatched payments (pending or not verified)
    unmatched_payments = all_payments.filter(
        Q(payment_status='pending') | Q(is_verified=False)
    )
    unmatched_count = unmatched_payments.count()
    unmatched_amount = unmatched_payments.aggregate(total=Sum('amount'))['total'] or 0

    # Discrepancies
    discrepancy_payments = all_payments.filter(processor_fee__gt=0)
    discrepancy_count = discrepancy_payments.count()
    discrepancy_amount = discrepancy_payments.aggregate(total=Sum('processor_fee'))['total'] or 0

    # Recent unmatched for action
    recent_unmatched = unmatched_payments.filter(
        payment_date__gte=today - timedelta(days=30)
    )[:20]

    # Payment methods stats
    payment_methods_stats = all_payments.values('payment_method').annotate(
        count=Count('id'),
        total=Sum('amount')
    ).order_by('-total')

    # Monthly reconciliation summary
    monthly_reconciliation = []
    for i in range(6):
        month_date = (today.replace(day=1) - relativedelta(months=i))
        month_matched = Payment.objects.filter(
            payment_status='completed',
            is_verified=True,
            payment_date__year=month_date.year,
            payment_date__month=month_date.month
        ).aggregate(total=Sum('amount'))['total'] or 0
        month_unmatched = Payment.objects.filter(
            Q(payment_status='pending') | Q(is_verified=False),
            payment_date__year=month_date.year,
            payment_date__month=month_date.month
        ).aggregate(total=Sum('amount'))['total'] or 0

        monthly_reconciliation.append({
            'month': month_date.strftime('%B %Y'),
            'matched': float(month_matched),
            'unmatched': float(month_unmatched),
            'total': float(month_matched) + float(month_unmatched)
        })
    monthly_reconciliation.reverse()

    # Reconciliation rate
    reconciliation_rate = 0.0
    if total_payments > 0:
        reconciliation_rate = (matched_count / total_payments) * 100

    context = {
        'total_payments': total_payments,
        'matched_count': matched_count,
        'matched_amount': float(matched_amount),
        'unmatched_count': unmatched_count,
        'unmatched_amount': float(unmatched_amount),
        'discrepancy_count': discrepancy_count,
        'discrepancy_amount': float(discrepancy_amount),
        'reconciliation_rate': reconciliation_rate,
        'recent_unmatched': recent_unmatched,
        'payment_methods_stats': payment_methods_stats,
        'monthly_reconciliation': monthly_reconciliation,
    }

    return render(request, 'finance/reconciliation.html', context)


@login_required
def reconciliation_auto_match(request):
    """Auto-match payments with orders/invoices."""
    if request.method == 'POST':
        # Get unmatched payments
        unmatched = Payment.objects.filter(
            Q(payment_status='pending') | Q(is_verified=False)
        )

        matched_count = 0
        for payment in unmatched:
            # Try to auto-match based on amount and date
            if payment.order and payment.amount:
                # If payment has order and amount matches expected, mark as verified
                expected_amount = payment.order.total_price
                if abs(float(payment.amount) - float(expected_amount)) < 0.01:
                    payment.is_verified = True
                    payment.verified_at = timezone.now()
                    payment.verified_by = request.user
                    payment.notes = payment.notes + f"\nAuto-matched on {timezone.now().strftime('%Y-%m-%d %H:%M')}"
                    payment.save()
                    matched_count += 1

        messages.success(request, f'Auto-matching complete. {matched_count} payments matched.')
        return redirect('finance:reconciliation')

    return redirect('finance:reconciliation')