from django.urls import path
from . import views

app_name = 'delivery'

urlpatterns = [
    # Delivery Dashboard (Legacy - for Delivery Agents)
    path('', views.dashboard, name='dashboard'),
    
    # Orders
    path('orders/', views.order_list, name='orders'),
    path('orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('orders/<int:order_id>/update-status/', views.update_order_status, name='update_order_status'),
    
    # Performance
    path('performance/', views.performance, name='performance'),
    
    # Companies
    path('companies/', views.companies, name='companies'),
    path('companies/<int:company_id>/', views.company_detail, name='company_detail'),
    
    # Settings
    path('settings/', views.settings, name='settings'),
    
    # Order Assignment
    path('assign-orders/', views.assign_orders, name='assign_orders'),
    path('assign-order/<int:order_id>/', views.assign_order, name='assign_order'),
    path('start-delivery/<int:order_id>/', views.start_delivery, name='start_delivery'),
    path('complete-delivery/<int:order_id>/', views.complete_delivery, name='complete_delivery'),
    
    # Returns Process
    path('returns/', views.returns_process, name='returns_process'),
    
    # ============================================
    # DELIVERY MANAGER URLs (New Implementation)
    # ============================================
    path('manager/dashboard/', views.manager_dashboard, name='manager_dashboard'),
    path('manager/all-orders/', views.manager_all_orders, name='manager_all_orders'),
    path('manager/shipping-companies/', views.manager_shipping_companies, name='manager_shipping_companies'),
    path('manager/company/<int:company_id>/orders/', views.manager_company_orders, name='manager_company_orders'),
    path('manager/assign-orders/', views.manager_assign_orders, name='manager_assign_orders'),
    path('manager/update-orders/', views.manager_update_orders, name='manager_update_orders'),
    path('manager/process-returns/', views.manager_process_returns, name='manager_process_returns'),
    path('manager/pending-confirmations/', views.manager_pending_confirmations, name='manager_pending_confirmations'),
    path('manager/confirm-delivery/<uuid:delivery_id>/', views.manager_confirm_delivery, name='manager_confirm_delivery'),
    path('manager/returned-orders/', views.manager_returned_orders, name='manager_returned_orders'),

    # Couriers Management
    path('couriers/', views.couriers_list, name='couriers'),
    path('couriers/<int:courier_id>/', views.courier_detail, name='courier_detail'),
    path('couriers/<int:courier_id>/edit/', views.edit_courier, name='edit_courier'),
    path('couriers/<int:courier_id>/performance/', views.courier_performance, name='courier_performance'),
]