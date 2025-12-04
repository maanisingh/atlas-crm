"""
Analytics API views for dashboards.
"""
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework.decorators import api_view, permission_classes
from django.http import JsonResponse
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_GET

from .services import (
    OrderAnalytics,
    InventoryAnalytics,
    FinanceAnalytics,
    DeliveryAnalytics,
    CallCenterAnalytics,
    UserAnalytics,
    DashboardKPIs
)


class ExecutiveSummaryView(APIView):
    """Executive summary KPIs for admin dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        data = DashboardKPIs.get_executive_summary(days)
        return Response(data)


class OrderAnalyticsView(APIView):
    """Order analytics API."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        return Response({
            'summary': OrderAnalytics.get_order_summary(days),
            'fulfillment': OrderAnalytics.get_order_fulfillment_rate(days),
            'conversion': OrderAnalytics.get_conversion_metrics(days)
        })


class InventoryAnalyticsView(APIView):
    """Inventory analytics API."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        limit = int(request.query_params.get('limit', 10))
        return Response({
            'stock_summary': InventoryAnalytics.get_stock_summary(),
            'top_selling': InventoryAnalytics.get_top_selling_products(limit, days),
            'slow_moving': InventoryAnalytics.get_slow_moving_products(90, limit)
        })


class FinanceAnalyticsView(APIView):
    """Finance analytics API."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        return Response({
            'revenue': FinanceAnalytics.get_revenue_summary(days),
            'payment_methods': FinanceAnalytics.get_payment_methods_breakdown(days),
            'outstanding': FinanceAnalytics.get_outstanding_payments()
        })


class DeliveryAnalyticsView(APIView):
    """Delivery analytics API."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        return Response({
            'summary': DeliveryAnalytics.get_delivery_summary(days),
            'performance': DeliveryAnalytics.get_delivery_performance(days)
        })


class CallCenterAnalyticsView(APIView):
    """Call center analytics API."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        limit = int(request.query_params.get('limit', 10))
        return Response({
            'summary': CallCenterAnalytics.get_call_summary(days),
            'agent_performance': CallCenterAnalytics.get_agent_performance(days, limit)
        })


class UserAnalyticsView(APIView):
    """User analytics API."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        return Response({
            'summary': UserAnalytics.get_user_summary(),
            'activity': UserAnalytics.get_user_activity(days)
        })


class OperationsKPIsView(APIView):
    """Operations KPIs for management dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        data = DashboardKPIs.get_operations_kpis(days)
        return Response(data)


class SalesKPIsView(APIView):
    """Sales KPIs for sales dashboard."""
    permission_classes = [IsAuthenticated]

    def get(self, request):
        days = int(request.query_params.get('days', 30))
        data = DashboardKPIs.get_sales_kpis(days)
        return Response(data)


# Function-based views for templates

@login_required
@require_GET
def executive_summary_json(request):
    """JSON endpoint for executive summary."""
    days = int(request.GET.get('days', 30))
    data = DashboardKPIs.get_executive_summary(days)
    return JsonResponse(data)


@login_required
@require_GET
def order_analytics_json(request):
    """JSON endpoint for order analytics."""
    days = int(request.GET.get('days', 30))
    data = {
        'summary': OrderAnalytics.get_order_summary(days),
        'fulfillment': OrderAnalytics.get_order_fulfillment_rate(days),
        'conversion': OrderAnalytics.get_conversion_metrics(days)
    }
    return JsonResponse(data)


@login_required
@require_GET
def inventory_analytics_json(request):
    """JSON endpoint for inventory analytics."""
    days = int(request.GET.get('days', 30))
    limit = int(request.GET.get('limit', 10))
    data = {
        'stock_summary': InventoryAnalytics.get_stock_summary(),
        'top_selling': InventoryAnalytics.get_top_selling_products(limit, days),
        'slow_moving': InventoryAnalytics.get_slow_moving_products(90, limit)
    }
    return JsonResponse(data)


@login_required
@require_GET
def finance_analytics_json(request):
    """JSON endpoint for finance analytics."""
    days = int(request.GET.get('days', 30))
    data = {
        'revenue': FinanceAnalytics.get_revenue_summary(days),
        'payment_methods': FinanceAnalytics.get_payment_methods_breakdown(days),
        'outstanding': FinanceAnalytics.get_outstanding_payments()
    }
    return JsonResponse(data)


@login_required
@require_GET
def delivery_analytics_json(request):
    """JSON endpoint for delivery analytics."""
    days = int(request.GET.get('days', 30))
    data = {
        'summary': DeliveryAnalytics.get_delivery_summary(days),
        'performance': DeliveryAnalytics.get_delivery_performance(days)
    }
    return JsonResponse(data)


@login_required
@require_GET
def callcenter_analytics_json(request):
    """JSON endpoint for call center analytics."""
    days = int(request.GET.get('days', 30))
    limit = int(request.GET.get('limit', 10))
    data = {
        'summary': CallCenterAnalytics.get_call_summary(days),
        'agent_performance': CallCenterAnalytics.get_agent_performance(days, limit)
    }
    return JsonResponse(data)
