from django.urls import path
from . import views

app_name = 'users'

urlpatterns = [
    # User Management
    path('', views.user_list, name='list'),
    path('create/', views.user_create, name='create'),
    path('<int:user_id>/', views.user_detail, name='detail'),
    path('<int:user_id>/edit/', views.user_edit, name='edit'),
    
    # User Authentication
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('verify-email/<int:user_id>/', views.verify_email_view, name='verify_email'),
    path('resend-verification/<int:user_id>/', views.resend_verification_code, name='resend_verification'),
    path('registration-success/', views.registration_success_view, name='registration_success'),
    path('profile/', views.profile_view, name='profile'),
    path('change-password/', views.change_password_view, name='change_password'),
    path('force-password-change/', views.force_password_change, name='force_password_change'),
    path('edit-profile/', views.edit_profile_view, name='edit_profile'),
    
    # User Management Actions
    path('<int:user_id>/delete/', views.delete_user, name='delete_user'),
    path('<int:user_id>/toggle-status/', views.toggle_user_status, name='toggle_user_status'),

    # Roles Management
    path('roles/', views.roles_list, name='roles'),
    path('roles/create/', views.create_role, name='create_role'),
    path('roles/<int:role_id>/edit/', views.edit_role, name='edit_role'),
    path('roles/<int:role_id>/permissions/', views.manage_role_permissions, name='role_permissions'),

    # User Settings
    path('settings/', views.user_settings, name='settings'),
    path('settings/notifications/', views.notification_settings, name='notification_settings'),

    # Two-Factor Authentication
    path('2fa/', views.two_factor_settings, name='two_factor'),
    path('2fa/enable/', views.enable_two_factor, name='enable_two_factor'),
    path('2fa/disable/', views.disable_two_factor, name='disable_two_factor'),
    path('2fa/verify/', views.verify_two_factor, name='verify_two_factor'),
]