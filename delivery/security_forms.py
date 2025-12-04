# delivery/security_forms.py
"""
Security Forms for Delivery System
Forms for OTP verification, PIN management, geofencing, and fraud detection
"""
from django import forms
from django.contrib.auth import get_user_model
from django.utils.translation import gettext_lazy as _
from .security_models import (
    DeliveryOTP,
    DeliveryPIN,
    GeofenceZone,
    DeliverySecurityEvent,
    FraudDetection,
    DeliverySecuritySettings
)
from .models import DeliveryRecord, Courier

User = get_user_model()


class OTPVerificationForm(forms.Form):
    """Form for verifying OTP during delivery"""

    otp_code = forms.CharField(
        max_length=6,
        min_length=6,
        required=True,
        label=_('OTP Code'),
        widget=forms.TextInput(attrs={
            'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-green-500 focus:border-green-500 text-center text-2xl tracking-widest',
            'placeholder': '000000',
            'pattern': '[0-9]{6}',
            'inputmode': 'numeric',
            'autocomplete': 'off'
        })
    )

    delivery_latitude = forms.DecimalField(
        required=False,
        widget=forms.HiddenInput()
    )

    delivery_longitude = forms.DecimalField(
        required=False,
        widget=forms.HiddenInput()
    )

    device_info = forms.CharField(
        required=False,
        widget=forms.HiddenInput()
    )

    def clean_otp_code(self):
        """Validate OTP format"""
        otp = self.cleaned_data.get('otp_code')
        if otp and not otp.isdigit():
            raise forms.ValidationError(_('OTP must contain only digits'))
        return otp


class PINVerificationForm(forms.Form):
    """Form for verifying delivery PIN"""

    pin_code = forms.CharField(
        max_length=4,
        min_length=4,
        required=True,
        label=_('Delivery PIN'),
        widget=forms.TextInput(attrs={
            'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-center text-2xl tracking-widest',
            'placeholder': '0000',
            'pattern': '[0-9]{4}',
            'inputmode': 'numeric',
            'autocomplete': 'off'
        })
    )

    def clean_pin_code(self):
        """Validate PIN format"""
        pin = self.cleaned_data.get('pin_code')
        if pin and not pin.isdigit():
            raise forms.ValidationError(_('PIN must contain only digits'))
        return pin


class GenerateOTPForm(forms.Form):
    """Form for generating OTP for a delivery"""

    delivery_id = forms.IntegerField(
        widget=forms.HiddenInput()
    )

    customer_phone = forms.CharField(
        max_length=20,
        required=True,
        label=_('Customer Phone'),
        widget=forms.TextInput(attrs={
            'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
            'placeholder': '+971 50 XXX XXXX'
        })
    )

    customer_email = forms.EmailField(
        required=False,
        label=_('Customer Email (Optional)'),
        widget=forms.EmailInput(attrs={
            'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
            'placeholder': 'customer@example.com'
        })
    )

    send_via = forms.MultipleChoiceField(
        choices=[
            ('sms', _('SMS')),
            ('email', _('Email'))
        ],
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'mr-2'
        }),
        required=True,
        label=_('Send OTP via')
    )


class GeofenceZoneForm(forms.ModelForm):
    """Form for creating/editing geofence zones"""

    class Meta:
        model = GeofenceZone
        fields = [
            'delivery', 'center_latitude', 'center_longitude',
            'radius_meters', 'strict_mode'
        ]
        widgets = {
            'delivery': forms.Select(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-orange-500 focus:border-orange-500'
            }),
            'center_latitude': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                'step': '0.00000001',
                'placeholder': '25.276987'
            }),
            'center_longitude': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                'step': '0.00000001',
                'placeholder': '55.296249'
            }),
            'radius_meters': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                'min': '10',
                'max': '1000',
                'placeholder': '100'
            }),
            'strict_mode': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-orange-500 focus:ring-orange-500 border-gray-300 rounded'
            })
        }


class SecurityEventForm(forms.ModelForm):
    """Form for creating security events"""

    class Meta:
        model = DeliverySecurityEvent
        fields = [
            'delivery', 'event_type', 'severity', 'description',
            'event_latitude', 'event_longitude', 'device_info', 'ip_address'
        ]
        widgets = {
            'delivery': forms.Select(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-red-500 focus:border-red-500'
            }),
            'event_type': forms.Select(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-red-500 focus:border-red-500'
            }),
            'severity': forms.Select(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-red-500 focus:border-red-500'
            }),
            'description': forms.Textarea(attrs={
                'rows': 4,
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-red-500 focus:border-red-500 resize-none',
                'placeholder': 'Describe the security event...'
            }),
            'event_latitude': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-red-500 focus:border-red-500',
                'step': '0.00000001'
            }),
            'event_longitude': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-red-500 focus:border-red-500',
                'step': '0.00000001'
            }),
            'device_info': forms.Textarea(attrs={
                'rows': 2,
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-red-500 focus:border-red-500 resize-none'
            }),
            'ip_address': forms.TextInput(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-red-500 focus:border-red-500'
            })
        }


class FraudReportForm(forms.ModelForm):
    """Form for reporting potential fraud"""

    class Meta:
        model = FraudDetection
        fields = [
            'delivery', 'fraud_type', 'risk_level', 'confidence_score',
            'description', 'evidence'
        ]
        widgets = {
            'delivery': forms.Select(attrs={
                'class': 'w-full border border-red-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-red-500 focus:border-red-500'
            }),
            'fraud_type': forms.Select(attrs={
                'class': 'w-full border border-red-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-red-500 focus:border-red-500'
            }),
            'risk_level': forms.Select(attrs={
                'class': 'w-full border border-red-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-red-500 focus:border-red-500'
            }),
            'confidence_score': forms.NumberInput(attrs={
                'class': 'w-full border border-red-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-red-500 focus:border-red-500',
                'min': '0',
                'max': '100',
                'step': '0.01'
            }),
            'description': forms.Textarea(attrs={
                'rows': 5,
                'class': 'w-full border border-red-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-red-500 focus:border-red-500 resize-none',
                'placeholder': 'Describe the suspected fraud...'
            }),
            'evidence': forms.Textarea(attrs={
                'rows': 3,
                'class': 'w-full border border-red-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-red-500 focus:border-red-500 resize-none font-mono text-sm',
                'placeholder': '{"key": "value"}'
            })
        }


class FraudInvestigationForm(forms.Form):
    """Form for investigating fraud reports"""

    fraud_id = forms.IntegerField(widget=forms.HiddenInput())

    investigation_notes = forms.CharField(
        required=True,
        label=_('Investigation Notes'),
        widget=forms.Textarea(attrs={
            'rows': 5,
            'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none',
            'placeholder': 'Document your investigation findings...'
        })
    )

    is_confirmed_fraud = forms.BooleanField(
        required=False,
        label=_('Confirmed as Fraud'),
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-red-500 focus:ring-red-500 border-gray-300 rounded'
        })
    )

    is_false_positive = forms.BooleanField(
        required=False,
        label=_('False Positive'),
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-green-500 focus:ring-green-500 border-gray-300 rounded'
        })
    )

    action_taken = forms.CharField(
        required=True,
        label=_('Action Taken'),
        widget=forms.Textarea(attrs={
            'rows': 3,
            'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 resize-none',
            'placeholder': 'Describe actions taken...'
        })
    )

    report_to_authorities = forms.BooleanField(
        required=False,
        label=_('Report to Authorities'),
        widget=forms.CheckboxInput(attrs={
            'class': 'h-4 w-4 text-red-500 focus:ring-red-500 border-gray-300 rounded'
        })
    )

    report_reference = forms.CharField(
        required=False,
        label=_('Report Reference Number'),
        widget=forms.TextInput(attrs={
            'class': 'w-full border border-gray-300 rounded-lg px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
            'placeholder': 'POL-2024-XXXXX'
        })
    )


class SecuritySettingsForm(forms.ModelForm):
    """Form for configuring security settings"""

    class Meta:
        model = DeliverySecuritySettings
        fields = [
            # OTP Settings
            'otp_enabled', 'otp_length', 'otp_expiry_minutes', 'otp_max_attempts',
            # PIN Settings
            'pin_enabled', 'pin_length', 'pin_validity_days',
            # Geofencing Settings
            'geofencing_enabled', 'default_geofence_radius', 'strict_geofencing',
            # Photo Verification
            'photo_verification_required', 'photo_max_size_mb',
            # Fraud Detection
            'fraud_detection_enabled', 'fraud_alert_threshold', 'auto_block_high_risk',
            # Notifications
            'notify_security_team', 'security_team_email',
            # Audit
            'log_all_events', 'retention_days'
        ]
        widgets = {
            # OTP Settings
            'otp_enabled': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-orange-500 focus:ring-orange-500 border-gray-300 rounded'
            }),
            'otp_length': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                'min': '4', 'max': '8'
            }),
            'otp_expiry_minutes': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                'min': '5', 'max': '60'
            }),
            'otp_max_attempts': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-orange-500 focus:border-orange-500',
                'min': '1', 'max': '10'
            }),
            # PIN Settings
            'pin_enabled': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-blue-500 focus:ring-blue-500 border-gray-300 rounded'
            }),
            'pin_length': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'min': '4', 'max': '6'
            }),
            'pin_validity_days': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-blue-500 focus:border-blue-500',
                'min': '1', 'max': '30'
            }),
            # Geofencing Settings
            'geofencing_enabled': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-green-500 focus:ring-green-500 border-gray-300 rounded'
            }),
            'default_geofence_radius': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-green-500 focus:border-green-500',
                'min': '10', 'max': '1000'
            }),
            'strict_geofencing': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-green-500 focus:ring-green-500 border-gray-300 rounded'
            }),
            # Photo Verification
            'photo_verification_required': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-purple-500 focus:ring-purple-500 border-gray-300 rounded'
            }),
            'photo_max_size_mb': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-purple-500 focus:border-purple-500',
                'min': '1', 'max': '50'
            }),
            # Fraud Detection
            'fraud_detection_enabled': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-red-500 focus:ring-red-500 border-gray-300 rounded'
            }),
            'fraud_alert_threshold': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-red-500 focus:border-red-500',
                'min': '0', 'max': '100', 'step': '0.01'
            }),
            'auto_block_high_risk': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-red-500 focus:ring-red-500 border-gray-300 rounded'
            }),
            # Notifications
            'notify_security_team': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-indigo-500 focus:ring-indigo-500 border-gray-300 rounded'
            }),
            'security_team_email': forms.EmailInput(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500',
                'placeholder': 'security@example.com'
            }),
            # Audit
            'log_all_events': forms.CheckboxInput(attrs={
                'class': 'h-4 w-4 text-gray-500 focus:ring-gray-500 border-gray-300 rounded'
            }),
            'retention_days': forms.NumberInput(attrs={
                'class': 'w-full border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-gray-500 focus:border-gray-500',
                'min': '30', 'max': '365'
            })
        }


class SecurityEventFilterForm(forms.Form):
    """Form for filtering security events"""

    delivery = forms.ModelChoiceField(
        queryset=DeliveryRecord.objects.all(),
        required=False,
        empty_label='All Deliveries',
        widget=forms.Select(attrs={
            'class': 'border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-orange-500 focus:border-orange-500'
        })
    )

    event_type = forms.ChoiceField(
        choices=[('', 'All Event Types')] + list(DeliverySecurityEvent.EVENT_TYPE_CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-orange-500 focus:border-orange-500'
        })
    )

    severity = forms.ChoiceField(
        choices=[('', 'All Severities')] + list(DeliverySecurityEvent.SEVERITY_CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-orange-500 focus:border-orange-500'
        })
    )

    courier = forms.ModelChoiceField(
        queryset=Courier.objects.all(),
        required=False,
        empty_label='All Couriers',
        widget=forms.Select(attrs={
            'class': 'border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-orange-500 focus:border-orange-500'
        })
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-orange-500 focus:border-orange-500'
        })
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'type': 'date',
            'class': 'border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-orange-500 focus:border-orange-500'
        })
    )

    is_resolved = forms.NullBooleanField(
        required=False,
        widget=forms.Select(
            choices=[
                ('', 'All'),
                ('true', 'Resolved'),
                ('false', 'Unresolved')
            ],
            attrs={
                'class': 'border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-orange-500 focus:border-orange-500'
            }
        )
    )


class FraudFilterForm(forms.Form):
    """Form for filtering fraud detections"""

    delivery = forms.ModelChoiceField(
        queryset=DeliveryRecord.objects.all(),
        required=False,
        empty_label='All Deliveries',
        widget=forms.Select(attrs={
            'class': 'border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-red-500 focus:border-red-500'
        })
    )

    fraud_type = forms.ChoiceField(
        choices=[('', 'All Fraud Types')] + list(FraudDetection.FRAUD_TYPE_CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-red-500 focus:border-red-500'
        })
    )

    risk_level = forms.ChoiceField(
        choices=[('', 'All Risk Levels')] + list(FraudDetection.RISK_LEVEL_CHOICES),
        required=False,
        widget=forms.Select(attrs={
            'class': 'border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-red-500 focus:border-red-500'
        })
    )

    min_confidence = forms.DecimalField(
        required=False,
        min_value=0,
        max_value=100,
        decimal_places=2,
        label='Min Confidence %',
        widget=forms.NumberInput(attrs={
            'class': 'border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-red-500 focus:border-red-500',
            'placeholder': '70.00'
        })
    )

    is_investigated = forms.NullBooleanField(
        required=False,
        widget=forms.Select(
            choices=[
                ('', 'All'),
                ('true', 'Investigated'),
                ('false', 'Not Investigated')
            ],
            attrs={
                'class': 'border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-red-500 focus:border-red-500'
            }
        )
    )

    is_confirmed_fraud = forms.NullBooleanField(
        required=False,
        widget=forms.Select(
            choices=[
                ('', 'All'),
                ('true', 'Confirmed Fraud'),
                ('false', 'Not Confirmed')
            ],
            attrs={
                'class': 'border border-gray-300 rounded-lg px-4 py-2 focus:ring-2 focus:ring-red-500 focus:border-red-500'
            }
        )
    )
