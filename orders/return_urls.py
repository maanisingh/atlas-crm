from django.urls import path
from . import return_views

# Note: app_name should NOT be set here since this URLconf is included
# into orders/urls.py which already has app_name = 'orders'

urlpatterns = [
    # ========================================
    # Customer-Facing Return URLs
    # ========================================

    # List all returns for the current customer
    path('my-returns/', return_views.customer_returns_list, name='customer_returns_list'),

    # View detailed information about a specific return
    path('my-returns/<str:return_code>/', return_views.customer_return_detail, name='customer_return_detail'),

    # Create a new return request for an order
    path('order/<int:order_id>/return/', return_views.create_return_request, name='create_return_request'),


    # ========================================
    # Admin/Staff Return Management URLs
    # ========================================

    # Returns management dashboard (for Admin, Manager, Stock Keeper)
    path('admin/returns/', return_views.returns_dashboard, name='returns_dashboard'),
    path('admin/returns/', return_views.returns_dashboard, name='admin_returns_dashboard'),  # Alias for template compatibility

    # View detailed return information (admin view)
    path('admin/returns/<str:return_code>/', return_views.return_detail_admin, name='return_detail_admin'),
    path('admin/returns/<str:return_code>/', return_views.return_detail_admin, name='admin_return_detail'),  # Alias for template compatibility

    # Approve or reject a return request (Admin, Manager only)
    path('admin/returns/<str:return_code>/approve/', return_views.approve_return, name='approve_return'),

    # Mark a return as received at warehouse
    path('admin/returns/<str:return_code>/mark-received/', return_views.mark_return_received, name='mark_return_received'),
    path('admin/returns/<str:return_code>/mark-received/', return_views.mark_return_received, name='mark_received'),  # Alias for template compatibility

    # Inspect a returned item (Admin, Manager, Stock Keeper)
    path('admin/returns/<str:return_code>/inspect/', return_views.inspect_return, name='inspect_return'),

    # Process refund for an approved return (Admin, Manager, Finance)
    path('admin/returns/<str:return_code>/process-refund/', return_views.process_refund, name='process_refund'),


    # ========================================
    # AJAX/API Return Endpoints
    # ========================================

    # Get current status of a return (AJAX endpoint)
    path('api/returns/<str:return_code>/status/', return_views.get_return_status, name='get_return_status'),

    # Get status timeline for a return (AJAX endpoint)
    path('api/returns/<str:return_code>/timeline/', return_views.get_return_timeline, name='get_return_timeline'),


    # ========================================
    # Future Features (Placeholders)
    # ========================================

    # Print return shipping label (TODO: Implement)
    path('admin/returns/<str:return_code>/print-label/', return_views.print_return_label, name='print_return_label'),

    # Export return details as PDF (TODO: Implement)
    path('admin/returns/<str:return_code>/export-pdf/', return_views.export_return_pdf, name='export_return_pdf'),

    # Bulk return actions (TODO: Implement)
    path('admin/returns/bulk-action/', return_views.bulk_return_action, name='bulk_return_action'),
]
