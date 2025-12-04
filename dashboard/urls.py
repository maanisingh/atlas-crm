from django.urls import path
from . import views

app_name = 'dashboard'

urlpatterns = [
    # Main Dashboard
    path('', views.index, name='index'),

    # Audit Log
    path('audit-log/', views.audit_log, name='audit_log'),
    path('audit-log/export/', views.export_audit_log, name='export_audit_log'),

    # Help Center
    path('help/', views.help, name='help'),

    # System Status
    path('system-status/', views.system_status, name='system_status'),

    # Alerts - with drilldown
    path('alerts/', views.alerts, name='alerts'),
    path('alerts/<str:alert_type>/', views.alerts_by_type, name='alerts_by_type'),

    # Inventory Drilldowns
    path('inventory/alerts/', views.inventory_alerts, name='inventory_alerts'),
    path('inventory/alerts/<int:alert_id>/', views.inventory_alert_detail, name='inventory_alert_detail'),
    path('inventory/alerts/<int:alert_id>/resolve/', views.resolve_inventory_alert, name='resolve_inventory_alert'),
    path('inventory/reservations/', views.stock_reservations, name='stock_reservations'),
    path('inventory/reservations/<int:reservation_id>/', views.stock_reservation_detail, name='stock_reservation_detail'),

    # Sales Drilldowns
    path('sales/overview/', views.sales_overview, name='sales_overview'),
    path('sales/by-period/<str:period>/', views.sales_by_period, name='sales_by_period'),

    # User Activity Drilldowns
    path('users/activity/', views.user_activity, name='user_activity'),
    path('users/activity/<int:user_id>/', views.user_activity_detail, name='user_activity_detail'),

    # JSON API Endpoints
    path('json/executive-summary/', views.json_executive_summary, name='json_executive_summary'),
    path('json/orders/', views.json_orders, name='json_orders'),
    path('json/inventory/', views.json_inventory, name='json_inventory'),
    path('json/finance/', views.json_finance, name='json_finance'),
]