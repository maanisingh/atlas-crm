# delivery/security_urls.py
"""
URL Configuration for Delivery Security Features
"""
from django.urls import path
from . import security_views

app_name = 'security'

urlpatterns = [
    # OTP Management
    path('otp/generate/<int:delivery_id>/', security_views.generate_otp_view, name='generate_otp'),
    path('otp/verify/<int:delivery_id>/', security_views.verify_otp_view, name='verify_otp'),

    # PIN Management
    path('pin/generate/<int:delivery_id>/', security_views.generate_pin_view, name='generate_pin'),
    path('pin/verify/<int:delivery_id>/', security_views.verify_pin_view, name='verify_pin'),

    # Geofence Management
    path('geofence/create/<int:delivery_id>/', security_views.create_geofence_view, name='create_geofence'),
    path('geofence/list/', security_views.geofence_list_view, name='geofence_list'),

    # Security Events
    path('events/', security_views.security_events_list_view, name='security_events_list'),
    path('events/<int:event_id>/', security_views.security_event_detail_view, name='security_event_detail'),

    # Fraud Detection
    path('fraud/', security_views.fraud_detection_list_view, name='fraud_detection_list'),
    path('fraud/investigate/<int:fraud_id>/', security_views.fraud_investigation_view, name='fraud_investigation'),
    path('fraud/report/<int:delivery_id>/', security_views.report_fraud_view, name='report_fraud'),

    # Security Settings
    path('settings/', security_views.security_settings_view, name='security_settings'),

    # API Endpoints (JSON responses)
    path('api/otp/generate/', security_views.api_generate_otp, name='api_generate_otp'),
    path('api/otp/verify/', security_views.api_verify_otp, name='api_verify_otp'),
    path('api/pin/verify/', security_views.api_verify_pin, name='api_verify_pin'),
    path('api/geofence/check/', security_views.api_check_geofence, name='api_check_geofence'),
    path('api/fraud/detect/', security_views.api_detect_fraud, name='api_detect_fraud'),
    path('api/security-events/', security_views.api_security_events, name='api_security_events'),
]
