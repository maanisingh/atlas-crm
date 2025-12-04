# delivery/security_views.py
"""
Security Views and API Endpoints
Handles OTP/PIN verification, geofencing, fraud detection, and security event management
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import csrf_exempt
from django.utils import timezone
from django.db.models import Q, Count
from django.core.paginator import Paginator
from datetime import timedelta
import json

from .models import DeliveryRecord, Courier
from .security_models import (
    DeliveryOTP,
    DeliveryPIN,
    GeofenceZone,
    DeliverySecurityEvent,
    FraudDetection,
    DeliverySecuritySettings
)
from .security_forms import (
    OTPVerificationForm,
    PINVerificationForm,
    GenerateOTPForm,
    GeofenceZoneForm,
    SecurityEventForm,
    FraudReportForm,
    FraudInvestigationForm,
    SecuritySettingsForm,
    SecurityEventFilterForm,
    FraudFilterForm
)
from .security_utils import (
    create_delivery_otp,
    create_delivery_pin,
    send_otp_sms,
    send_otp_email,
    send_pin_sms,
    send_pin_email,
    verify_geofence,
    log_security_event,
    detect_fraud_patterns,
    get_client_info
)


# ============================================================================
# OTP Management Views
# ============================================================================

@login_required
@permission_required('delivery.add_deliveryotp', raise_exception=True)
def generate_otp_view(request, delivery_id):
    """
    Generate OTP for delivery verification
    """
    delivery = get_object_or_404(DeliveryRecord, id=delivery_id)

    if request.method == 'POST':
        form = GenerateOTPForm(request.POST)
        if form.is_valid():
            customer_phone = form.cleaned_data['customer_phone']
            customer_email = form.cleaned_data.get('customer_email', '')
            send_via = form.cleaned_data['send_via']

            # Create OTP
            otp_obj, otp_code = create_delivery_otp(
                delivery=delivery,
                customer_phone=customer_phone,
                customer_email=customer_email
            )

            # Send OTP
            sent_successfully = []
            if 'sms' in send_via:
                if send_otp_sms(customer_phone, otp_code, delivery.tracking_number):
                    sent_successfully.append('SMS')

            if 'email' in send_via and customer_email:
                if send_otp_email(customer_email, otp_code, delivery.tracking_number):
                    sent_successfully.append('Email')

            if sent_successfully:
                messages.success(
                    request,
                    f'OTP generated and sent via {", ".join(sent_successfully)} successfully.'
                )
            else:
                messages.warning(request, 'OTP generated but sending failed.')

            return redirect('delivery:delivery_detail', pk=delivery_id)
    else:
        form = GenerateOTPForm(initial={'delivery_id': delivery_id})

    context = {
        'form': form,
        'delivery': delivery,
        'page_title': f'Generate OTP - {delivery.tracking_number}'
    }
    return render(request, 'delivery/security/generate_otp.html', context)


@login_required
@permission_required('delivery.change_deliveryotp', raise_exception=True)
def verify_otp_view(request, delivery_id):
    """
    Verify OTP for delivery
    """
    delivery = get_object_or_404(DeliveryRecord, id=delivery_id)

    # Get active OTP
    try:
        otp_obj = DeliveryOTP.objects.get(
            delivery=delivery,
            status='pending',
            expires_at__gt=timezone.now()
        )
    except DeliveryOTP.DoesNotExist:
        messages.error(request, 'No active OTP found for this delivery.')
        return redirect('delivery:delivery_detail', pk=delivery_id)

    if request.method == 'POST':
        form = OTPVerificationForm(request.POST)
        if form.is_valid():
            otp_code = form.cleaned_data['otp_code']
            latitude = form.cleaned_data.get('delivery_latitude')
            longitude = form.cleaned_data.get('delivery_longitude')
            device_info = form.cleaned_data.get('device_info', '')

            # Get client info
            client_info = get_client_info(request)

            # Verify OTP
            is_valid, error_message = otp_obj.verify_otp(otp_code)

            if is_valid:
                # Check geofence if coordinates provided
                if latitude and longitude:
                    is_within, distance, geofence = verify_geofence(
                        delivery, float(latitude), float(longitude)
                    )

                    if not is_within:
                        messages.warning(
                            request,
                            f'OTP verified but delivery location is {distance:.0f}m outside geofence.'
                        )

                # Update delivery status
                delivery.status = 'delivered'
                delivery.delivered_at = timezone.now()
                delivery.save()

                messages.success(request, 'OTP verified successfully! Delivery marked as completed.')
                return redirect('delivery:delivery_detail', pk=delivery_id)
            else:
                messages.error(request, error_message)

                # Check for fraud patterns after failed attempt
                fraud_detections = detect_fraud_patterns(delivery)
                if fraud_detections:
                    messages.warning(request, 'Suspicious activity detected. Security team notified.')
    else:
        form = OTPVerificationForm()

    context = {
        'form': form,
        'delivery': delivery,
        'otp': otp_obj,
        'page_title': f'Verify OTP - {delivery.tracking_number}'
    }
    return render(request, 'delivery/security/verify_otp.html', context)


# ============================================================================
# PIN Management Views
# ============================================================================

@login_required
@permission_required('delivery.add_deliverypin', raise_exception=True)
def generate_pin_view(request, delivery_id):
    """
    Generate PIN for delivery verification
    """
    delivery = get_object_or_404(DeliveryRecord, id=delivery_id)

    # Check if PIN already exists
    existing_pin = DeliveryPIN.objects.filter(
        delivery=delivery,
        status='active',
        valid_until__gt=timezone.now()
    ).first()

    if existing_pin:
        messages.info(request, 'Active PIN already exists for this delivery.')
        return redirect('delivery:delivery_detail', pk=delivery_id)

    if request.method == 'POST':
        # Create PIN
        pin_obj, pin_code = create_delivery_pin(delivery)

        # Send PIN to customer
        customer_phone = delivery.customer_phone if hasattr(delivery, 'customer_phone') else ''
        customer_email = delivery.customer_email if hasattr(delivery, 'customer_email') else ''

        sent_successfully = []
        if customer_phone:
            if send_pin_sms(customer_phone, pin_code, delivery.tracking_number):
                sent_successfully.append('SMS')

        if customer_email:
            if send_pin_email(customer_email, pin_code, delivery.tracking_number):
                sent_successfully.append('Email')

        if sent_successfully:
            messages.success(
                request,
                f'PIN generated and sent via {", ".join(sent_successfully)} successfully.'
            )
        else:
            messages.warning(request, 'PIN generated but sending failed.')

        return redirect('delivery:delivery_detail', pk=delivery_id)

    context = {
        'delivery': delivery,
        'page_title': f'Generate PIN - {delivery.tracking_number}'
    }
    return render(request, 'delivery/security/generate_pin.html', context)


@login_required
@permission_required('delivery.change_deliverypin', raise_exception=True)
def verify_pin_view(request, delivery_id):
    """
    Verify PIN for delivery
    """
    delivery = get_object_or_404(DeliveryRecord, id=delivery_id)

    # Get active PIN
    try:
        pin_obj = DeliveryPIN.objects.get(
            delivery=delivery,
            status='active',
            valid_until__gt=timezone.now()
        )
    except DeliveryPIN.DoesNotExist:
        messages.error(request, 'No active PIN found for this delivery.')
        return redirect('delivery:delivery_detail', pk=delivery_id)

    if request.method == 'POST':
        form = PINVerificationForm(request.POST)
        if form.is_valid():
            pin_code = form.cleaned_data['pin_code']

            # Verify PIN
            is_valid, error_message = pin_obj.verify_pin(pin_code)

            if is_valid:
                # Update delivery status
                delivery.status = 'delivered'
                delivery.delivered_at = timezone.now()
                delivery.save()

                messages.success(request, 'PIN verified successfully! Delivery marked as completed.')
                return redirect('delivery:delivery_detail', pk=delivery_id)
            else:
                messages.error(request, error_message)
    else:
        form = PINVerificationForm()

    context = {
        'form': form,
        'delivery': delivery,
        'pin': pin_obj,
        'page_title': f'Verify PIN - {delivery.tracking_number}'
    }
    return render(request, 'delivery/security/verify_pin.html', context)


# ============================================================================
# Geofence Management Views
# ============================================================================

@login_required
@permission_required('delivery.add_geofencezone', raise_exception=True)
def create_geofence_view(request, delivery_id):
    """
    Create geofence zone for delivery
    """
    delivery = get_object_or_404(DeliveryRecord, id=delivery_id)

    if request.method == 'POST':
        form = GeofenceZoneForm(request.POST)
        if form.is_valid():
            geofence = form.save(commit=False)
            geofence.delivery = delivery
            geofence.created_by = request.user
            geofence.save()

            messages.success(request, 'Geofence zone created successfully.')
            return redirect('delivery:delivery_detail', pk=delivery_id)
    else:
        # Pre-fill with delivery destination coordinates if available
        initial_data = {}
        if hasattr(delivery, 'destination_latitude') and delivery.destination_latitude:
            initial_data['center_latitude'] = delivery.destination_latitude
            initial_data['center_longitude'] = delivery.destination_longitude

        form = GeofenceZoneForm(initial=initial_data)

    context = {
        'form': form,
        'delivery': delivery,
        'page_title': f'Create Geofence - {delivery.tracking_number}'
    }
    return render(request, 'delivery/security/create_geofence.html', context)


@login_required
@permission_required('delivery.view_geofencezone', raise_exception=True)
def geofence_list_view(request):
    """
    List all geofence zones
    """
    geofences = GeofenceZone.objects.select_related('delivery', 'created_by').all()

    # Filter by status
    status = request.GET.get('status')
    if status:
        geofences = geofences.filter(status=status)

    # Pagination
    paginator = Paginator(geofences, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    context = {
        'page_obj': page_obj,
        'page_title': 'Geofence Zones'
    }
    return render(request, 'delivery/security/geofence_list.html', context)


# ============================================================================
# Security Event Views
# ============================================================================

@login_required
@permission_required('delivery.view_deliverysecurityevent', raise_exception=True)
def security_events_list_view(request):
    """
    List security events with filtering
    """
    events = DeliverySecurityEvent.objects.select_related(
        'delivery', 'courier', 'triggered_by'
    ).all()

    # Apply filters
    form = SecurityEventFilterForm(request.GET or None)
    if form.is_valid():
        event_type = form.cleaned_data.get('event_type')
        severity = form.cleaned_data.get('severity')
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')

        if event_type:
            events = events.filter(event_type=event_type)
        if severity:
            events = events.filter(severity=severity)
        if date_from:
            events = events.filter(timestamp__gte=date_from)
        if date_to:
            events = events.filter(timestamp__lte=date_to)

    # Pagination
    paginator = Paginator(events, 50)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistics
    stats = {
        'total': events.count(),
        'critical': events.filter(severity='critical').count(),
        'warning': events.filter(severity='warning').count(),
        'info': events.filter(severity='info').count(),
    }

    context = {
        'form': form,
        'page_obj': page_obj,
        'stats': stats,
        'page_title': 'Security Events'
    }
    return render(request, 'delivery/security/security_events_list.html', context)


@login_required
@permission_required('delivery.view_deliverysecurityevent', raise_exception=True)
def security_event_detail_view(request, event_id):
    """
    View security event details
    """
    event = get_object_or_404(
        DeliverySecurityEvent.objects.select_related('delivery', 'courier', 'triggered_by'),
        id=event_id
    )

    context = {
        'event': event,
        'page_title': f'Security Event - {event.get_event_type_display()}'
    }
    return render(request, 'delivery/security/security_event_detail.html', context)


# ============================================================================
# Fraud Detection Views
# ============================================================================

@login_required
@permission_required('delivery.view_frauddetection', raise_exception=True)
def fraud_detection_list_view(request):
    """
    List fraud detections with filtering
    """
    fraud_cases = FraudDetection.objects.select_related(
        'delivery', 'investigated_by', 'resolved_by'
    ).all()

    # Apply filters
    form = FraudFilterForm(request.GET or None)
    if form.is_valid():
        fraud_type = form.cleaned_data.get('fraud_type')
        risk_level = form.cleaned_data.get('risk_level')
        status = form.cleaned_data.get('status')
        date_from = form.cleaned_data.get('date_from')
        date_to = form.cleaned_data.get('date_to')

        if fraud_type:
            fraud_cases = fraud_cases.filter(fraud_type=fraud_type)
        if risk_level:
            fraud_cases = fraud_cases.filter(risk_level=risk_level)
        if status:
            fraud_cases = fraud_cases.filter(status=status)
        if date_from:
            fraud_cases = fraud_cases.filter(detected_at__gte=date_from)
        if date_to:
            fraud_cases = fraud_cases.filter(detected_at__lte=date_to)

    # Pagination
    paginator = Paginator(fraud_cases, 25)
    page_number = request.GET.get('page')
    page_obj = paginator.get_page(page_number)

    # Statistics
    stats = {
        'total': fraud_cases.count(),
        'high_risk': fraud_cases.filter(risk_level='high').count(),
        'under_investigation': fraud_cases.filter(status='under_investigation').count(),
        'confirmed': fraud_cases.filter(status='confirmed').count(),
    }

    context = {
        'form': form,
        'page_obj': page_obj,
        'stats': stats,
        'page_title': 'Fraud Detection'
    }
    return render(request, 'delivery/security/fraud_detection_list.html', context)


@login_required
@permission_required('delivery.change_frauddetection', raise_exception=True)
def fraud_investigation_view(request, fraud_id):
    """
    Investigate fraud case
    """
    fraud = get_object_or_404(FraudDetection, id=fraud_id)

    if request.method == 'POST':
        form = FraudInvestigationForm(request.POST, instance=fraud)
        if form.is_valid():
            fraud_case = form.save(commit=False)

            if fraud_case.status == 'under_investigation' and not fraud_case.investigated_by:
                fraud_case.investigated_by = request.user
                fraud_case.investigation_started_at = timezone.now()

            if fraud_case.status in ['confirmed', 'false_positive']:
                fraud_case.resolved_by = request.user
                fraud_case.resolved_at = timezone.now()

            fraud_case.save()

            messages.success(request, 'Fraud investigation updated successfully.')
            return redirect('delivery:fraud_detection_list')
    else:
        form = FraudInvestigationForm(instance=fraud)

    context = {
        'form': form,
        'fraud': fraud,
        'page_title': f'Investigate Fraud - {fraud.get_fraud_type_display()}'
    }
    return render(request, 'delivery/security/fraud_investigation.html', context)


@login_required
@permission_required('delivery.add_frauddetection', raise_exception=True)
def report_fraud_view(request, delivery_id):
    """
    Report fraud for a delivery
    """
    delivery = get_object_or_404(DeliveryRecord, id=delivery_id)

    if request.method == 'POST':
        form = FraudReportForm(request.POST, request.FILES)
        if form.is_valid():
            fraud = form.save(commit=False)
            fraud.delivery = delivery
            fraud.save()

            # Log security event
            log_security_event(
                delivery=delivery,
                event_type='fraud_reported',
                severity='critical',
                description=f'Fraud reported: {fraud.get_fraud_type_display()}',
                triggered_by=request.user,
                event_data={
                    'fraud_id': fraud.id,
                    'fraud_type': fraud.fraud_type,
                    'risk_level': fraud.risk_level
                }
            )

            messages.success(request, 'Fraud report submitted successfully.')
            return redirect('delivery:delivery_detail', pk=delivery_id)
    else:
        form = FraudReportForm()

    context = {
        'form': form,
        'delivery': delivery,
        'page_title': f'Report Fraud - {delivery.tracking_number}'
    }
    return render(request, 'delivery/security/report_fraud.html', context)


# ============================================================================
# Security Settings Views
# ============================================================================

@login_required
@permission_required('delivery.change_deliverysecuritysettings', raise_exception=True)
def security_settings_view(request):
    """
    Configure security settings
    """
    settings_obj = DeliverySecuritySettings.get_settings()

    if request.method == 'POST':
        form = SecuritySettingsForm(request.POST, instance=settings_obj)
        if form.is_valid():
            form.save()
            messages.success(request, 'Security settings updated successfully.')
            return redirect('delivery:security_settings')
    else:
        form = SecuritySettingsForm(instance=settings_obj)

    context = {
        'form': form,
        'settings': settings_obj,
        'page_title': 'Security Settings'
    }
    return render(request, 'delivery/security/security_settings.html', context)


# ============================================================================
# API Endpoints (JSON responses for mobile/web apps)
# ============================================================================

@csrf_exempt
@require_http_methods(["POST"])
def api_generate_otp(request):
    """
    API: Generate OTP for delivery

    POST /api/delivery/otp/generate/
    {
        "tracking_number": "TRK123456",
        "customer_phone": "+971501234567",
        "customer_email": "customer@example.com",
        "send_via": ["sms", "email"]
    }
    """
    try:
        data = json.loads(request.body)
        tracking_number = data.get('tracking_number')
        customer_phone = data.get('customer_phone')
        customer_email = data.get('customer_email', '')
        send_via = data.get('send_via', ['sms'])

        # Get delivery
        delivery = DeliveryRecord.objects.get(tracking_number=tracking_number)

        # Create OTP
        otp_obj, otp_code = create_delivery_otp(
            delivery=delivery,
            customer_phone=customer_phone,
            customer_email=customer_email
        )

        # Send OTP
        sent_successfully = []
        if 'sms' in send_via:
            if send_otp_sms(customer_phone, otp_code, delivery.tracking_number):
                sent_successfully.append('sms')

        if 'email' in send_via and customer_email:
            if send_otp_email(customer_email, otp_code, delivery.tracking_number):
                sent_successfully.append('email')

        return JsonResponse({
            'success': True,
            'message': 'OTP generated successfully',
            'otp_id': otp_obj.id,
            'expires_at': otp_obj.expires_at.isoformat(),
            'sent_via': sent_successfully
        })

    except DeliveryRecord.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Delivery not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def api_verify_otp(request):
    """
    API: Verify OTP for delivery

    POST /api/delivery/otp/verify/
    {
        "tracking_number": "TRK123456",
        "otp_code": "123456",
        "latitude": 25.2048,
        "longitude": 55.2708,
        "device_info": "iPhone 12, iOS 15.0"
    }
    """
    try:
        data = json.loads(request.body)
        tracking_number = data.get('tracking_number')
        otp_code = data.get('otp_code')
        latitude = data.get('latitude')
        longitude = data.get('longitude')
        device_info = data.get('device_info', '')

        # Get delivery
        delivery = DeliveryRecord.objects.get(tracking_number=tracking_number)

        # Get active OTP
        otp_obj = DeliveryOTP.objects.get(
            delivery=delivery,
            status='pending',
            expires_at__gt=timezone.now()
        )

        # Verify OTP
        is_valid, error_message = otp_obj.verify_otp(otp_code)

        if not is_valid:
            return JsonResponse({
                'success': False,
                'error': error_message
            }, status=400)

        # Check geofence
        geofence_data = {}
        if latitude and longitude:
            is_within, distance, geofence = verify_geofence(
                delivery, float(latitude), float(longitude)
            )
            geofence_data = {
                'within_zone': is_within,
                'distance_meters': distance,
                'geofence_radius': geofence.radius_meters if geofence else None
            }

        # Update delivery status
        delivery.status = 'delivered'
        delivery.delivered_at = timezone.now()
        delivery.save()

        return JsonResponse({
            'success': True,
            'message': 'OTP verified successfully',
            'delivery_status': delivery.status,
            'delivered_at': delivery.delivered_at.isoformat(),
            'geofence': geofence_data
        })

    except DeliveryRecord.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Delivery not found'
        }, status=404)
    except DeliveryOTP.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'No active OTP found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def api_verify_pin(request):
    """
    API: Verify PIN for delivery

    POST /api/delivery/pin/verify/
    {
        "tracking_number": "TRK123456",
        "pin_code": "1234"
    }
    """
    try:
        data = json.loads(request.body)
        tracking_number = data.get('tracking_number')
        pin_code = data.get('pin_code')

        # Get delivery
        delivery = DeliveryRecord.objects.get(tracking_number=tracking_number)

        # Get active PIN
        pin_obj = DeliveryPIN.objects.get(
            delivery=delivery,
            status='active',
            valid_until__gt=timezone.now()
        )

        # Verify PIN
        is_valid, error_message = pin_obj.verify_pin(pin_code)

        if not is_valid:
            return JsonResponse({
                'success': False,
                'error': error_message
            }, status=400)

        # Update delivery status
        delivery.status = 'delivered'
        delivery.delivered_at = timezone.now()
        delivery.save()

        return JsonResponse({
            'success': True,
            'message': 'PIN verified successfully',
            'delivery_status': delivery.status,
            'delivered_at': delivery.delivered_at.isoformat()
        })

    except DeliveryRecord.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Delivery not found'
        }, status=404)
    except DeliveryPIN.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'No active PIN found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def api_check_geofence(request):
    """
    API: Check if location is within geofence

    POST /api/delivery/geofence/check/
    {
        "tracking_number": "TRK123456",
        "latitude": 25.2048,
        "longitude": 55.2708
    }
    """
    try:
        data = json.loads(request.body)
        tracking_number = data.get('tracking_number')
        latitude = float(data.get('latitude'))
        longitude = float(data.get('longitude'))

        # Get delivery
        delivery = DeliveryRecord.objects.get(tracking_number=tracking_number)

        # Check geofence
        is_within, distance, geofence = verify_geofence(delivery, latitude, longitude)

        return JsonResponse({
            'success': True,
            'within_zone': is_within,
            'distance_meters': distance,
            'geofence_radius': geofence.radius_meters if geofence else None,
            'message': 'Within geofence' if is_within else f'Outside geofence by {distance:.0f}m'
        })

    except DeliveryRecord.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Delivery not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@csrf_exempt
@require_http_methods(["POST"])
def api_detect_fraud(request):
    """
    API: Run fraud detection for delivery

    POST /api/delivery/fraud/detect/
    {
        "tracking_number": "TRK123456"
    }
    """
    try:
        data = json.loads(request.body)
        tracking_number = data.get('tracking_number')

        # Get delivery
        delivery = DeliveryRecord.objects.get(tracking_number=tracking_number)

        # Detect fraud patterns
        fraud_detections = detect_fraud_patterns(delivery)

        fraud_data = []
        for fraud in fraud_detections:
            fraud_data.append({
                'id': fraud.id,
                'fraud_type': fraud.get_fraud_type_display(),
                'risk_level': fraud.risk_level,
                'confidence_score': float(fraud.confidence_score),
                'description': fraud.description,
                'detected_at': fraud.detected_at.isoformat()
            })

        return JsonResponse({
            'success': True,
            'fraud_detected': len(fraud_detections) > 0,
            'fraud_count': len(fraud_detections),
            'detections': fraud_data
        })

    except DeliveryRecord.DoesNotExist:
        return JsonResponse({
            'success': False,
            'error': 'Delivery not found'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)


@require_http_methods(["GET"])
def api_security_events(request):
    """
    API: Get security events

    GET /api/delivery/security-events/?delivery_id=123&severity=critical
    """
    try:
        events = DeliverySecurityEvent.objects.all()

        # Filter by delivery
        delivery_id = request.GET.get('delivery_id')
        if delivery_id:
            events = events.filter(delivery_id=delivery_id)

        # Filter by severity
        severity = request.GET.get('severity')
        if severity:
            events = events.filter(severity=severity)

        # Filter by event type
        event_type = request.GET.get('event_type')
        if event_type:
            events = events.filter(event_type=event_type)

        # Limit results
        limit = int(request.GET.get('limit', 50))
        events = events[:limit]

        events_data = []
        for event in events:
            events_data.append({
                'id': event.id,
                'event_type': event.get_event_type_display(),
                'severity': event.get_severity_display(),
                'description': event.description,
                'timestamp': event.timestamp.isoformat(),
                'delivery_tracking': event.delivery.tracking_number,
                'latitude': float(event.event_latitude) if event.event_latitude else None,
                'longitude': float(event.event_longitude) if event.event_longitude else None
            })

        return JsonResponse({
            'success': True,
            'count': len(events_data),
            'events': events_data
        })

    except Exception as e:
        return JsonResponse({
            'success': False,
            'error': str(e)
        }, status=400)
