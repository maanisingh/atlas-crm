"""
URL configuration for analytics app.
"""
from django.urls import path
from . import views

app_name = 'analytics'

urlpatterns = [
    # REST API endpoints
    path('api/executive-summary/', views.ExecutiveSummaryView.as_view(), name='api_executive_summary'),
    path('api/orders/', views.OrderAnalyticsView.as_view(), name='api_orders'),
    path('api/inventory/', views.InventoryAnalyticsView.as_view(), name='api_inventory'),
    path('api/finance/', views.FinanceAnalyticsView.as_view(), name='api_finance'),
    path('api/delivery/', views.DeliveryAnalyticsView.as_view(), name='api_delivery'),
    path('api/callcenter/', views.CallCenterAnalyticsView.as_view(), name='api_callcenter'),
    path('api/users/', views.UserAnalyticsView.as_view(), name='api_users'),
    path('api/operations/', views.OperationsKPIsView.as_view(), name='api_operations'),
    path('api/sales/', views.SalesKPIsView.as_view(), name='api_sales'),

    # JSON endpoints for templates
    path('json/executive-summary/', views.executive_summary_json, name='json_executive_summary'),
    path('json/orders/', views.order_analytics_json, name='json_orders'),
    path('json/inventory/', views.inventory_analytics_json, name='json_inventory'),
    path('json/finance/', views.finance_analytics_json, name='json_finance'),
    path('json/delivery/', views.delivery_analytics_json, name='json_delivery'),
    path('json/callcenter/', views.callcenter_analytics_json, name='json_callcenter'),
]
