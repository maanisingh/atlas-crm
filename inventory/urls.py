from django.urls import path
from . import views

app_name = 'inventory'

urlpatterns = [
    # Inventory Dashboard
    path('', views.inventory_dashboard, name='dashboard'),
    
    # Products
    path('products/', views.inventory_products, name='products'),
    path('products/add/', views.add_product, name='add_product'),
    path('products/<int:product_id>/', views.product_detail, name='product_detail'),
    path('products/<int:product_id>/edit/', views.edit_product, name='product_edit'),
    path('products/<int:product_id>/edit-product/', views.edit_product, name='edit_product'),
    
    # Warehouses
    path('warehouses/', views.warehouse_list, name='warehouses'),
    path('warehouses/<int:warehouse_id>/', views.view_warehouse, name='warehouse_detail'),
    path('warehouses/add/', views.add_warehouse, name='add_warehouse'),
    path('warehouses/<int:warehouse_id>/edit/', views.edit_warehouse, name='edit_warehouse'),
    path('warehouses/<int:warehouse_id>/delete/', views.delete_warehouse, name='delete_warehouse'),
    
    # Movements
    path('movements/', views.movements, name='movements'),
    
    # Product Approval
    path('product-approval/', views.product_approval, name='product_approval'),
    
    # Reports
    path('reports/', views.inventory_movements, name='reports'),

    # Stock Alerts
    path('alerts/', views.stock_alerts, name='alerts'),
    path('alerts/<int:alert_id>/acknowledge/', views.acknowledge_alert, name='acknowledge_alert'),
    path('alerts/settings/', views.alert_settings, name='alert_settings'),

    # Stock Reservations
    path('reservations/', views.stock_reservations, name='reservations'),
    path('reservations/create/', views.create_reservation, name='create_reservation'),
    path('reservations/<int:reservation_id>/release/', views.release_reservation, name='release_reservation'),
]