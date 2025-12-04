from django.urls import path
from django.views.generic.base import RedirectView
from . import views

app_name = 'packaging'

urlpatterns = [
    # Redirect root packaging URL to agent
    path('', RedirectView.as_view(pattern_name='packaging:dashboard', permanent=False)),
    
    # Packaging Dashboard
    path('agent/', views.dashboard, name='dashboard'),
    
    # Orders
    path('agent/orders/', views.order_list, name='orders'),
    path('agent/orders/<int:order_id>/', views.order_detail, name='order_detail'),
    path('agent/orders/<int:order_id>/start/', views.start_packaging, name='start_packaging'),
    path('agent/orders/<int:order_id>/complete/', views.complete_packaging, name='complete_packaging'),
    path('agent/orders/<int:order_id>/print-label/', views.print_label, name='print_label'),
    
    # Materials Inventory
    path('agent/materials/', views.materials_inventory, name='materials_inventory'),
    path('agent/materials/management/', views.materials_management, name='materials_management'),
    path('agent/materials/export/', views.export_materials, name='export_materials'),
    path('agent/materials/add/', views.add_material, name='add_material'),
    path('agent/materials/<int:material_id>/', views.get_material, name='get_material'),
    path('agent/materials/<int:material_id>/edit/', views.edit_material, name='edit_material'),
    path('agent/materials/<int:material_id>/delete/', views.delete_material, name='delete_material'),
    path('agent/materials/<int:material_id>/stock/', views.add_material_stock, name='add_material_stock'),
    
    
    # Reports
    path('agent/reports/', views.packaging_report, name='reports'),
    path('agent/packaging-report/', views.packaging_report, name='packaging_report'),
    path('agent/export/', views.export_report, name='export_report'),
    
    # Order Status Management
    path('agent/update-pending-orders/', views.update_pending_orders_status, name='update_pending_orders'),
]