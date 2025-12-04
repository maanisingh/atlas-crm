from django.urls import path
from . import views

app_name = 'callcenter'

urlpatterns = [
    # Call Center Dashboard
    path('', views.dashboard, name='dashboard'),
    
    # Agent Dashboard
    path('agent/', views.agent_dashboard, name='agent_dashboard'),
    path('agent/orders/', views.agent_order_list, name='agent_order_list'),
    
    # Manager Dashboard
    path('manager/', views.manager_dashboard, name='manager_dashboard'),
    path('manager/orders/', views.manager_order_list, name='manager_order_list'),
    path('manager/reports/', views.manager_agent_reports, name='manager_agent_reports'),
    
    # Order Management
    path('orders/', views.order_list, name='orders'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('agent/orders/<int:order_id>/', views.agent_order_detail, name='agent_order_detail'),
    path('agent/orders/<int:order_id>/approve/', views.agent_approve_order, name='agent_approve_order'),
    path('agent/orders/<int:order_id>/update-status/', views.agent_update_order_status, name='agent_update_order_status'),
    path('agent/orders/<int:order_id>/escalate/', views.escalate_to_manager, name='escalate_to_manager'),
    path('manager/orders/<int:order_id>/deescalate/', views.deescalate_order, name='deescalate_order'),
    path('agent/orders/<int:order_id>/edit/', views.agent_edit_order, name='agent_edit_order'),
    path('manager/orders/<int:order_id>/update-status/', views.agent_update_order_status, name='manager_update_order_status'),
    path('manager/orders/<int:order_id>/edit/', views.agent_edit_order, name='manager_edit_order'),
    path('manager/orders/<int:order_id>/assign/', views.manager_assign_order, name='manager_assign_order'),
    path('manager/orders/<int:order_id>/reassign/', views.manager_reassign_order, name='manager_reassign_order'),
    path('manager/orders/<int:order_id>/log-call/', views.manager_log_call, name='manager_log_call'),
    path('agent/orders/<int:order_id>/log-call/', views.agent_log_call, name='agent_log_call'),
    path('manager/orders/<int:order_id>/accept/', views.accept_order, name='manager_accept_order'),
    path('manager/orders/<int:order_id>/resolve/', views.resolve_order, name='manager_resolve_order'),
    path('orders/<int:order_id>/status-log/', views.order_status_log, name='order_status_log'),
    path('distribute-orders/', views.distribute_orders, name='distribute_orders'),
    path('fix-unassigned-orders/', views.fix_all_unassigned_orders, name='fix_unassigned_orders'),
    path('force-assign-orders/', views.force_assign_orders, name='force_assign_orders'),
    path('create-test-orders/', views.create_test_orders, name='create_test_orders'),

    # Phase 4: Enhanced Dashboard & Bulk Operations
    path('enhanced-dashboard/', views.enhanced_dashboard, name='enhanced_dashboard'),
    path('api/real-time-metrics/', views.real_time_metrics, name='real_time_metrics'),
    path('bulk/operations/', views.bulk_operations_panel, name='bulk_operations'),
    path('bulk/assign-orders/', views.bulk_assign_orders, name='bulk_assign_orders'),
    path('bulk/update-status/', views.bulk_update_order_status, name='bulk_update_status'),
    path('bulk/create-followups/', views.bulk_create_followups, name='bulk_create_followups'),
    path('export/orders-csv/', views.export_orders_csv, name='export_orders_csv'),
]