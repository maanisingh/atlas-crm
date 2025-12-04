"""
Analytics services for calculating KPIs and metrics.
"""
from datetime import datetime, timedelta
from decimal import Decimal
from django.db.models import Sum, Count, Avg, F, Q, Case, When, Value, IntegerField
from django.db.models.functions import TruncDate, TruncMonth, TruncWeek
from django.utils import timezone
from django.core.cache import cache


class OrderAnalytics:
    """Order-related analytics and KPIs."""

    CACHE_TIMEOUT = 300  # 5 minutes

    @classmethod
    def get_order_summary(cls, days=30):
        """Get order summary for the specified period."""
        cache_key = f'order_summary_{days}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        from orders.models import Order

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        orders = Order.objects.filter(created_at__gte=start_date)

        # Calculate metrics
        total_orders = orders.count()
        total_revenue = sum(order.total_price for order in orders)

        # Status breakdown
        status_breakdown = orders.values('status').annotate(
            count=Count('id')
        ).order_by('-count')

        # Daily trend - calculate revenue from OrderItems
        from orders.models import OrderItem
        daily_trend_data = []
        for date_obj in orders.dates('created_at', 'day'):
            day_orders = orders.filter(created_at__date=date_obj)
            day_revenue = sum(order.total_price for order in day_orders)
            daily_trend_data.append({
                'order_date': date_obj,
                'count': day_orders.count(),
                'revenue': float(day_revenue)
            })

        result = {
            'total_orders': total_orders,
            'total_revenue': float(total_revenue),
            'average_order_value': float(total_revenue / total_orders) if total_orders > 0 else 0,
            'status_breakdown': list(status_breakdown),
            'daily_trend': daily_trend_data,
            'period_days': days
        }

        cache.set(cache_key, result, cls.CACHE_TIMEOUT)
        return result

    @classmethod
    def get_order_fulfillment_rate(cls, days=30):
        """Calculate order fulfillment rate."""
        from orders.models import Order

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        orders = Order.objects.filter(created_at__gte=start_date)

        total_orders = orders.count()
        delivered_orders = orders.filter(status='delivered').count()

        return {
            'total_orders': total_orders,
            'delivered_orders': delivered_orders,
            'fulfillment_rate': (delivered_orders / total_orders * 100) if total_orders > 0 else 0
        }

    @classmethod
    def get_conversion_metrics(cls, days=30):
        """Calculate conversion metrics from pending to confirmed orders."""
        from orders.models import Order

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        orders = Order.objects.filter(created_at__gte=start_date)

        total = orders.count()
        confirmed = orders.filter(status__in=['confirmed', 'dispatched', 'delivered']).count()
        cancelled = orders.filter(status__in=['cancelled', 'returned']).count()
        pending = orders.filter(status__in=['pending', 'pending_confirmation']).count()

        return {
            'total_orders': total,
            'confirmed_orders': confirmed,
            'cancelled_orders': cancelled,
            'pending_orders': pending,
            'conversion_rate': (confirmed / total * 100) if total > 0 else 0,
            'cancellation_rate': (cancelled / total * 100) if total > 0 else 0
        }


class InventoryAnalytics:
    """Inventory-related analytics and KPIs."""

    @classmethod
    def get_stock_summary(cls):
        """Get inventory stock summary."""
        from products.models import Product

        products = Product.objects.all()

        total_products = products.count()
        in_stock = products.filter(stock__gt=0).count()
        out_of_stock = products.filter(stock=0).count()
        # min_stock field doesn't exist, using threshold of 10
        low_stock = products.filter(stock__gt=0, stock__lte=10).count()

        total_value = sum(
            (p.stock or 0) * float(p.price or 0)
            for p in products
        )

        return {
            'total_products': total_products,
            'in_stock': in_stock,
            'out_of_stock': out_of_stock,
            'low_stock': low_stock,
            'total_stock_value': total_value,
            'stock_health': {
                'in_stock_rate': (in_stock / total_products * 100) if total_products > 0 else 0,
                'out_of_stock_rate': (out_of_stock / total_products * 100) if total_products > 0 else 0,
                'low_stock_rate': (low_stock / total_products * 100) if total_products > 0 else 0
            }
        }

    @classmethod
    def get_top_selling_products(cls, limit=10, days=30):
        """Get top selling products."""
        from orders.models import OrderItem
        from products.models import Product

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        top_products = OrderItem.objects.filter(
            order__created_at__gte=start_date,
            order__status__in=['confirmed', 'dispatched', 'delivered']
        ).values(
            'product__id', 'product__name_en'
        ).annotate(
            total_quantity=Sum('quantity'),
            total_revenue=Sum(F('quantity') * F('price'))
        ).order_by('-total_quantity')[:limit]

        return list(top_products)

    @classmethod
    def get_slow_moving_products(cls, days=90, limit=10):
        """Get slow moving products (not sold in specified days)."""
        from products.models import Product
        from orders.models import OrderItem

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Products that have been ordered
        sold_product_ids = OrderItem.objects.filter(
            order__created_at__gte=start_date
        ).values_list('product_id', flat=True).distinct()

        # Products with stock that haven't been sold
        slow_moving = Product.objects.filter(
            stock__gt=0
        ).exclude(
            id__in=sold_product_ids
        ).values('id', 'name', 'stock', 'price')[:limit]

        return list(slow_moving)


class FinanceAnalytics:
    """Finance-related analytics and KPIs."""

    @classmethod
    def get_revenue_summary(cls, days=30):
        """Get revenue summary."""
        from finance.models import Payment
        from orders.models import Order

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # From payments
        payments = Payment.objects.filter(
            payment_date__gte=start_date,
            payment_status='completed'
        )

        total_payments = payments.aggregate(total=Sum('amount'))['total'] or 0

        # From orders
        orders = Order.objects.filter(
            created_at__gte=start_date,
            status__in=['confirmed', 'dispatched', 'delivered']
        )

        order_revenue = sum(order.total_price for order in orders)

        # Daily revenue trend
        daily_revenue = payments.annotate(
            date=TruncDate('payment_date')
        ).values('date').annotate(
            total=Sum('amount')
        ).order_by('date')

        return {
            'total_revenue': float(total_payments),
            'order_revenue': float(order_revenue),
            'daily_trend': list(daily_revenue),
            'period_days': days
        }

    @classmethod
    def get_payment_methods_breakdown(cls, days=30):
        """Get payment methods breakdown."""
        from finance.models import Payment

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        breakdown = Payment.objects.filter(
            payment_date__gte=start_date,
            payment_status='completed'
        ).values('payment_method').annotate(
            count=Count('id'),
            total=Sum('amount')
        ).order_by('-total')

        return list(breakdown)

    @classmethod
    def get_outstanding_payments(cls):
        """Get outstanding payments summary."""
        from finance.models import Payment

        pending = Payment.objects.filter(
            payment_status='pending'
        ).aggregate(
            count=Count('id'),
            total=Sum('amount')
        )

        return {
            'pending_count': pending['count'] or 0,
            'pending_amount': float(pending['total'] or 0)
        }


class DeliveryAnalytics:
    """Delivery-related analytics and KPIs."""

    @classmethod
    def get_delivery_summary(cls, days=30):
        """Get delivery summary."""
        from delivery.models import DeliveryRecord

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        deliveries = DeliveryRecord.objects.filter(created_at__gte=start_date)

        total = deliveries.count()
        completed = deliveries.filter(status='delivered').count()
        pending = deliveries.filter(status='pending').count()
        in_progress = deliveries.filter(status='in_transit').count()
        failed = deliveries.filter(status__in=['failed', 'returned']).count()

        return {
            'total_deliveries': total,
            'completed': completed,
            'pending': pending,
            'in_progress': in_progress,
            'failed': failed,
            'success_rate': (completed / total * 100) if total > 0 else 0,
            'failure_rate': (failed / total * 100) if total > 0 else 0
        }

    @classmethod
    def get_delivery_performance(cls, days=30):
        """Get delivery performance metrics."""
        from delivery.models import DeliveryRecord

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        completed_deliveries = DeliveryRecord.objects.filter(
            created_at__gte=start_date,
            status='delivered',
            delivered_at__isnull=False
        )

        # Calculate average delivery time
        delivery_times = []
        for d in completed_deliveries:
            if d.delivered_at and d.created_at:
                diff = d.delivered_at - d.created_at
                delivery_times.append(diff.total_seconds() / 3600)  # in hours

        avg_delivery_time = sum(delivery_times) / len(delivery_times) if delivery_times else 0

        # On-time delivery rate (assuming 48 hours is on-time)
        on_time = sum(1 for t in delivery_times if t <= 48)
        on_time_rate = (on_time / len(delivery_times) * 100) if delivery_times else 0

        return {
            'average_delivery_time_hours': round(avg_delivery_time, 2),
            'on_time_deliveries': on_time,
            'on_time_rate': round(on_time_rate, 2),
            'total_completed': len(delivery_times)
        }


class CallCenterAnalytics:
    """Call center analytics and KPIs."""

    @classmethod
    def get_call_summary(cls, days=30):
        """Get call center summary."""
        from callcenter.models import CallLog

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        calls = CallLog.objects.filter(created_at__gte=start_date)

        total_calls = calls.count()
        completed = calls.filter(status='completed').count()
        no_answer = calls.filter(status='no_answer').count()

        # Calls by status
        status_breakdown = calls.values('status').annotate(
            count=Count('id')
        ).order_by('-count')

        # Calls by resolution status
        resolution_breakdown = calls.values('resolution_status').annotate(
            count=Count('id')
        ).order_by('-count')

        return {
            'total_calls': total_calls,
            'completed': completed,
            'no_answer': no_answer,
            'answer_rate': (completed / total_calls * 100) if total_calls > 0 else 0,
            'status_breakdown': list(status_breakdown),
            'resolution_breakdown': list(resolution_breakdown)
        }

    @classmethod
    def get_agent_performance(cls, days=30, limit=10):
        """Get agent performance metrics."""
        from callcenter.models import CallLog
        from django.contrib.auth import get_user_model

        User = get_user_model()

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        agent_stats = CallLog.objects.filter(
            created_at__gte=start_date
        ).values(
            'agent__id', 'agent__full_name'
        ).annotate(
            total_calls=Count('id'),
            resolved_calls=Count(Case(
                When(resolution_status='resolved', then=1),
                output_field=IntegerField()
            )),
            avg_duration=Avg('duration')
        ).order_by('-total_calls')[:limit]

        return list(agent_stats)


class UserAnalytics:
    """User-related analytics."""

    @classmethod
    def get_user_summary(cls):
        """Get user summary."""
        from django.contrib.auth import get_user_model

        User = get_user_model()

        total_users = User.objects.count()
        active_users = User.objects.filter(is_active=True).count()
        inactive_users = User.objects.filter(is_active=False).count()

        # Users by role
        role_breakdown = User.objects.values(
            'user_roles__role__name'
        ).annotate(
            count=Count('id')
        ).exclude(user_roles__role__name__isnull=True).order_by('-count')

        return {
            'total_users': total_users,
            'active_users': active_users,
            'inactive_users': inactive_users,
            'role_breakdown': list(role_breakdown)
        }

    @classmethod
    def get_user_activity(cls, days=30):
        """Get user activity trends."""
        from users.models import AuditLog

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        # Daily login activity
        daily_logins = AuditLog.objects.filter(
            action='login',
            timestamp__gte=start_date
        ).annotate(
            date=TruncDate('timestamp')
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')

        return {
            'daily_logins': list(daily_logins)
        }


class DashboardKPIs:
    """Aggregate KPIs for dashboards."""

    @classmethod
    def get_executive_summary(cls, days=30):
        """Get executive summary KPIs for admin dashboard."""
        cache_key = f'executive_summary_{days}'
        cached = cache.get(cache_key)
        if cached:
            return cached

        result = {
            'orders': OrderAnalytics.get_order_summary(days),
            'inventory': InventoryAnalytics.get_stock_summary(),
            'revenue': FinanceAnalytics.get_revenue_summary(days),
            'delivery': DeliveryAnalytics.get_delivery_summary(days),
            'users': UserAnalytics.get_user_summary(),
            'generated_at': timezone.now().isoformat()
        }

        cache.set(cache_key, result, 300)  # Cache for 5 minutes
        return result

    @classmethod
    def get_operations_kpis(cls, days=30):
        """Get operational KPIs."""
        return {
            'order_fulfillment': OrderAnalytics.get_order_fulfillment_rate(days),
            'delivery_performance': DeliveryAnalytics.get_delivery_performance(days),
            'stock_health': InventoryAnalytics.get_stock_summary()['stock_health'],
            'call_center': CallCenterAnalytics.get_call_summary(days)
        }

    @classmethod
    def get_sales_kpis(cls, days=30):
        """Get sales KPIs."""
        return {
            'conversion': OrderAnalytics.get_conversion_metrics(days),
            'top_products': InventoryAnalytics.get_top_selling_products(10, days),
            'payment_methods': FinanceAnalytics.get_payment_methods_breakdown(days)
        }
