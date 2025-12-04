from django.urls import path, include
from . import views

app_name = 'orders'

urlpatterns = [
    # Orders
    path('', views.order_list, name='list'),
    path('create/', views.create_order, name='create'),
    path('<int:order_id>/', views.order_detail, name='detail'),
    path('<int:order_id>/edit/', views.update_order, name='edit'),
    path('<int:order_id>/update/', views.update_order, name='update'),
    path('<int:order_id>/delete/', views.delete_order, name='delete'),

    # Import/Export
    path('import/', views.import_orders, name='import'),
    path('export/', views.download_template, name='export'),

    # Call Center approval
    path('<int:order_id>/callcenter-approve/', views.callcenter_approve_order, name='callcenter_approve'),

    # Seller management
    path('<int:order_id>/change-seller/', views.change_order_seller, name='change_seller'),

    # Invoice and public view
    path('<int:order_id>/invoice/', views.order_invoice, name='invoice'),
    path('public/<str:order_code>/', views.public_order_view, name='public_view'),

    # API endpoints
    path('api/available-agents-count/', views.available_agents_count, name='available_agents_count'),
    path('api/get-states-for-city/', views.get_states_for_city_api, name='get_states_for_city'),

    # Return Management System
    path('', include('orders.return_urls')),
]