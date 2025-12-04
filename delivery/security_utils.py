# delivery/security_utils.py
"""
Security Utility Functions
Helper functions for OTP/PIN generation, verification, and fraud detection
"""
import random
import hashlib
import string
from datetime import timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from .security_models import (
    DeliveryOTP,
    DeliveryPIN,
    GeofenceZone,
    DeliverySecurityEvent,
    FraudDetection,
    DeliverySecuritySettings
)


def generate_otp_code(length=6):
    """
    Generate a random OTP code

    Args:
        length (int): Length of OTP (default: 6)

    Returns:
        str: Generated OTP code
    """
    return ''.join(random.choices(string.digits, k=length))


def hash_otp(otp_code):
    """
    Hash OTP code using SHA-256

    Args:
        otp_code (str): OTP code to hash

    Returns:
        str: Hashed OTP
    """
    return hashlib.sha256(otp_code.encode()).hexdigest()


def create_delivery_otp(delivery, customer_phone, customer_email='', settings_obj=None):
    """
    Create a new OTP for delivery verification

    Args:
        delivery: DeliveryRecord instance
        customer_phone (str): Customer phone number
        customer_email (str): Customer email address
        settings_obj: DeliverySecuritySettings instance

    Returns:
        tuple: (DeliveryOTP instance, plain OTP code)
    """
    # Get security settings
    if not settings_obj:
        settings_obj = DeliverySecuritySettings.get_settings()

    # Generate OTP
    otp_code = generate_otp_code(settings_obj.otp_length)
    otp_hash = hash_otp(otp_code)

    # Calculate expiry time
    expires_at = timezone.now() + timedelta(minutes=settings_obj.otp_expiry_minutes)

    # Cancel any existing pending OTPs for this delivery
    DeliveryOTP.objects.filter(
        delivery=delivery,
        status='pending'
    ).update(status='cancelled')

    # Create new OTP
    otp = DeliveryOTP.objects.create(
        delivery=delivery,
        otp_code=otp_code,
        otp_hash=otp_hash,
        customer_phone=customer_phone,
        customer_email=customer_email,
        expires_at=expires_at,
        max_attempts=settings_obj.otp_max_attempts
    )

    # Log security event
    log_security_event(
        delivery=delivery,
        event_type='otp_generated',
        severity='info',
        description=f'OTP generated for delivery {delivery.tracking_number}',
        event_data={
            'otp_id': otp.id,
            'customer_phone': customer_phone,
            'expires_at': expires_at.isoformat()
        }
    )

    return otp, otp_code


def generate_pin_code(length=4):
    """
    Generate a random PIN code

    Args:
        length (int): Length of PIN (default: 4)

    Returns:
        str: Generated PIN code
    """
    return ''.join(random.choices(string.digits, k=length))


def hash_pin(pin_code):
    """
    Hash PIN code using SHA-256

    Args:
        pin_code (str): PIN code to hash

    Returns:
        str: Hashed PIN
    """
    return hashlib.sha256(pin_code.encode()).hexdigest()


def create_delivery_pin(delivery, settings_obj=None):
    """
    Create a new PIN for delivery verification

    Args:
        delivery: DeliveryRecord instance
        settings_obj: DeliverySecuritySettings instance

    Returns:
        tuple: (DeliveryPIN instance, plain PIN code)
    """
    # Get security settings
    if not settings_obj:
        settings_obj = DeliverySecuritySettings.get_settings()

    # Generate PIN
    pin_code = generate_pin_code(settings_obj.pin_length)
    pin_hash = hash_pin(pin_code)

    # Calculate validity period
    valid_until = timezone.now() + timedelta(days=settings_obj.pin_validity_days)

    # Create PIN
    pin = DeliveryPIN.objects.create(
        delivery=delivery,
        pin_code=pin_code,
        pin_hash=pin_hash,
        valid_until=valid_until,
        max_attempts=5  # PINs typically allow more attempts
    )

    # Log security event
    log_security_event(
        delivery=delivery,
        event_type='pin_verified',
        severity='info',
        description=f'PIN generated for delivery {delivery.tracking_number}',
        event_data={
            'pin_id': pin.id,
            'valid_until': valid_until.isoformat()
        }
    )

    return pin, pin_code


def send_otp_sms(phone_number, otp_code, delivery_tracking):
    """
    Send OTP via SMS

    Args:
        phone_number (str): Customer phone number
        otp_code (str): OTP code
        delivery_tracking (str): Delivery tracking number

    Returns:
        bool: True if sent successfully
    """
    # TODO: Integrate with SMS gateway (Twilio, SNS, etc.)
    # For now, just log it
    message = f"Your delivery verification code is: {otp_code}\nTracking: {delivery_tracking}\nValid for 15 minutes."

    # In production, use actual SMS service:
    # from twilio.rest import Client
    # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    # message = client.messages.create(
    #     body=message,
    #     from_=settings.TWILIO_PHONE_NUMBER,
    #     to=phone_number
    # )

    print(f"[SMS] To: {phone_number}, Message: {message}")
    return True


def send_otp_email(email, otp_code, delivery_tracking):
    """
    Send OTP via email

    Args:
        email (str): Customer email address
        otp_code (str): OTP code
        delivery_tracking (str): Delivery tracking number

    Returns:
        bool: True if sent successfully
    """
    subject = f"Delivery Verification Code - {delivery_tracking}"
    message = f"""
    Your delivery verification code is: {otp_code}

    Tracking Number: {delivery_tracking}

    This code is valid for 15 minutes.

    If you did not request this delivery, please contact customer support immediately.
    """

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False
        )
        return True
    except Exception as e:
        print(f"[Email Error] Failed to send OTP: {str(e)}")
        return False


def send_pin_sms(phone_number, pin_code, delivery_tracking):
    """
    Send PIN via SMS

    Args:
        phone_number (str): Customer phone number
        pin_code (str): PIN code
        delivery_tracking (str): Delivery tracking number

    Returns:
        bool: True if sent successfully
    """
    message = f"Your delivery PIN is: {pin_code}\nTracking: {delivery_tracking}\nShare this PIN with the delivery agent."

    # TODO: Integrate with SMS gateway
    print(f"[SMS] To: {phone_number}, Message: {message}")
    return True


def send_pin_email(email, pin_code, delivery_tracking):
    """
    Send PIN via email

    Args:
        email (str): Customer email address
        pin_code (str): PIN code
        delivery_tracking (str): Delivery tracking number

    Returns:
        bool: True if sent successfully
    """
    subject = f"Delivery PIN - {delivery_tracking}"
    message = f"""
    Your delivery PIN is: {pin_code}

    Tracking Number: {delivery_tracking}

    Please share this PIN with the delivery agent when they arrive.

    This PIN is valid for 7 days from your order date.
    """

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [email],
            fail_silently=False
        )
        return True
    except Exception as e:
        print(f"[Email Error] Failed to send PIN: {str(e)}")
        return False


def verify_geofence(delivery, latitude, longitude):
    """
    Verify if delivery location is within geofence

    Args:
        delivery: DeliveryRecord instance
        latitude (float): Current latitude
        longitude (float): Current longitude

    Returns:
        tuple: (is_within_zone, distance_meters, geofence_zone)
    """
    try:
        geofence = GeofenceZone.objects.get(delivery=delivery)
        is_within, distance = geofence.is_within_zone(latitude, longitude)

        # Log event
        event_type = 'geofence_success' if is_within else 'geofence_violation'
        severity = 'info' if is_within else 'warning'

        log_security_event(
            delivery=delivery,
            event_type=event_type,
            severity=severity,
            description=f'Geofence check: {"PASSED" if is_within else "FAILED"} (Distance: {distance:.2f}m)',
            event_latitude=latitude,
            event_longitude=longitude,
            event_data={
                'distance_meters': distance,
                'radius_meters': geofence.radius_meters,
                'is_within_zone': is_within
            }
        )

        return is_within, distance, geofence
    except GeofenceZone.DoesNotExist:
        return True, 0, None  # No geofence configured, allow delivery


def log_security_event(delivery, event_type, severity, description,
                       courier=None, triggered_by=None, event_latitude=None,
                       event_longitude=None, device_info='', ip_address=None,
                       user_agent='', event_data=None):
    """
    Log a security event

    Args:
        delivery: DeliveryRecord instance
        event_type (str): Type of event
        severity (str): Severity level
        description (str): Event description
        courier: Courier instance (optional)
        triggered_by: User instance (optional)
        event_latitude (float): Latitude (optional)
        event_longitude (float): Longitude (optional)
        device_info (str): Device information
        ip_address (str): IP address
        user_agent (str): User agent string
        event_data (dict): Additional event data

    Returns:
        DeliverySecurityEvent: Created event instance
    """
    settings_obj = DeliverySecuritySettings.get_settings()

    if not settings_obj.log_all_events and severity == 'info':
        return None

    event = DeliverySecurityEvent.objects.create(
        delivery=delivery,
        event_type=event_type,
        severity=severity,
        description=description,
        courier=courier,
        triggered_by=triggered_by,
        event_latitude=event_latitude,
        event_longitude=event_longitude,
        device_info=device_info,
        ip_address=ip_address,
        user_agent=user_agent,
        event_data=event_data or {}
    )

    # Send alert for critical events
    if severity == 'critical' and settings_obj.notify_security_team:
        send_security_alert(event)

    return event


def send_security_alert(event):
    """
    Send security alert to security team

    Args:
        event: DeliverySecurityEvent instance

    Returns:
        bool: True if sent successfully
    """
    settings_obj = DeliverySecuritySettings.get_settings()

    if not settings_obj.security_team_email:
        return False

    subject = f"[CRITICAL] Security Alert - {event.event_type}"
    message = f"""
    Security Event Detected

    Delivery: {event.delivery.tracking_number}
    Event Type: {event.get_event_type_display()}
    Severity: {event.get_severity_display()}

    Description:
    {event.description}

    Timestamp: {event.timestamp}

    Location: {event.event_latitude}, {event.event_longitude}
    IP Address: {event.ip_address}

    Please investigate immediately.
    """

    try:
        send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings_obj.security_team_email],
            fail_silently=False
        )
        return True
    except Exception as e:
        print(f"[Security Alert Error] {str(e)}")
        return False


def detect_fraud_patterns(delivery, courier=None):
    """
    Analyze delivery for fraud patterns

    Args:
        delivery: DeliveryRecord instance
        courier: Courier instance (optional)

    Returns:
        list: List of FraudDetection instances (if any fraud detected)
    """
    fraud_detections = []
    settings_obj = DeliverySecuritySettings.get_settings()

    if not settings_obj.fraud_detection_enabled:
        return fraud_detections

    # Check for location mismatch
    if hasattr(delivery, 'geofence_zones'):
        geofences = delivery.geofence_zones.all()
        for geofence in geofences:
            if delivery.courier and hasattr(delivery.courier, 'current_location'):
                location = delivery.courier.current_location
                is_within, distance = geofence.is_within_zone(
                    location.latitude,
                    location.longitude
                )

                if not is_within and distance > geofence.radius_meters * 2:
                    # Significantly outside geofence
                    confidence = min(100, (distance / geofence.radius_meters) * 25)
                    fraud = FraudDetection.objects.create(
                        delivery=delivery,
                        fraud_type='location_mismatch',
                        risk_level='high' if confidence > 75 else 'medium',
                        confidence_score=confidence,
                        description=f'Delivery location {distance:.0f}m outside geofence',
                        evidence={
                            'distance_meters': distance,
                            'geofence_radius': geofence.radius_meters
                        }
                    )
                    fraud_detections.append(fraud)

    # Check for multiple failed verification attempts
    failed_otps = DeliveryOTP.objects.filter(
        delivery=delivery,
        status='failed'
    ).count()

    if failed_otps >= 2:
        confidence = min(100, failed_otps * 30)
        fraud = FraudDetection.objects.create(
            delivery=delivery,
            fraud_type='multiple_failures',
            risk_level='high' if failed_otps >= 3 else 'medium',
            confidence_score=confidence,
            description=f'{failed_otps} failed OTP verification attempts',
            evidence={
                'failed_attempts': failed_otps
            }
        )
        fraud_detections.append(fraud)

    # Check for suspicious timing patterns
    security_events = DeliverySecurityEvent.objects.filter(
        delivery=delivery,
        event_type__in=['suspicious_activity', 'unauthorized_access']
    )

    if security_events.exists():
        fraud = FraudDetection.objects.create(
            delivery=delivery,
            fraud_type='suspicious_pattern',
            risk_level='high',
            confidence_score=80.0,
            description='Suspicious activity detected in security events',
            evidence={
                'event_count': security_events.count(),
                'event_types': list(security_events.values_list('event_type', flat=True))
            }
        )
        fraud_detections.append(fraud)

    # Send alerts for high-risk fraud
    for fraud in fraud_detections:
        if fraud.confidence_score >= settings_obj.fraud_alert_threshold:
            log_security_event(
                delivery=delivery,
                event_type='fraud_alert',
                severity='critical',
                description=f'Fraud detected: {fraud.get_fraud_type_display()}',
                event_data={
                    'fraud_id': fraud.id,
                    'confidence_score': float(fraud.confidence_score),
                    'risk_level': fraud.risk_level
                }
            )

    return fraud_detections


def get_client_info(request):
    """
    Extract client information from request

    Args:
        request: Django request object

    Returns:
        dict: Client information (IP, user agent, device info)
    """
    # Get IP address
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip_address = x_forwarded_for.split(',')[0]
    else:
        ip_address = request.META.get('REMOTE_ADDR')

    # Get user agent
    user_agent = request.META.get('HTTP_USER_AGENT', '')

    # Build device info
    device_info = f"IP: {ip_address}\nUser-Agent: {user_agent}"

    return {
        'ip_address': ip_address,
        'user_agent': user_agent,
        'device_info': device_info
    }
