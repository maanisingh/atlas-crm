from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Return, ReturnItem, Order, OrderItem


class ReturnRequestForm(forms.ModelForm):
    """Form for customers to submit a return request"""

    class Meta:
        model = Return
        fields = [
            'return_reason',
            'return_description',
            'return_photo_1',
            'return_photo_2',
            'return_photo_3',
            'return_video'
        ]
        widgets = {
            'return_reason': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'required': True
            }),
            'return_description': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'rows': 4,
                'placeholder': _('Please provide detailed information about why you are returning this order...'),
                'required': True
            }),
            'return_photo_1': forms.FileInput(attrs={
                'class': 'mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100',
                'accept': 'image/*'
            }),
            'return_photo_2': forms.FileInput(attrs={
                'class': 'mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100',
                'accept': 'image/*'
            }),
            'return_photo_3': forms.FileInput(attrs={
                'class': 'mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100',
                'accept': 'image/*'
            }),
            'return_video': forms.FileInput(attrs={
                'class': 'mt-1 block w-full text-sm text-gray-500 file:mr-4 file:py-2 file:px-4 file:rounded-full file:border-0 file:text-sm file:font-semibold file:bg-blue-50 file:text-blue-700 hover:file:bg-blue-100',
                'accept': 'video/*'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.order = kwargs.pop('order', None)
        self.customer = kwargs.pop('customer', None)
        super().__init__(*args, **kwargs)

        # Make photos optional but at least one should be uploaded
        self.fields['return_photo_1'].required = False
        self.fields['return_photo_2'].required = False
        self.fields['return_photo_3'].required = False
        self.fields['return_video'].required = False

    def clean(self):
        cleaned_data = super().clean()

        # Check if at least one photo or video is uploaded
        photo_1 = cleaned_data.get('return_photo_1')
        photo_2 = cleaned_data.get('return_photo_2')
        photo_3 = cleaned_data.get('return_photo_3')
        video = cleaned_data.get('return_video')

        if not any([photo_1, photo_2, photo_3, video]):
            raise forms.ValidationError(
                _('Please upload at least one photo or video as evidence for your return request.')
            )

        return cleaned_data

    def save(self, commit=True):
        instance = super().save(commit=False)
        if self.order:
            instance.order = self.order
        if self.customer:
            instance.customer = self.customer
        instance.return_status = 'requested'
        instance.refund_status = 'pending'

        if commit:
            instance.save()
            self.save_m2m()

        return instance


class ReturnItemSelectionForm(forms.Form):
    """Form for selecting items to return in multi-item orders"""

    def __init__(self, *args, **kwargs):
        order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)

        if order:
            # Create a field for each order item
            for order_item in order.items.all():
                field_name = f'item_{order_item.id}'
                self.fields[field_name] = forms.BooleanField(
                    required=False,
                    label=f"{order_item.product.name_en} (Qty: {order_item.quantity})",
                    widget=forms.CheckboxInput(attrs={
                        'class': 'rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50'
                    })
                )

                # Add quantity field for partial returns
                qty_field_name = f'quantity_{order_item.id}'
                self.fields[qty_field_name] = forms.IntegerField(
                    required=False,
                    min_value=1,
                    max_value=order_item.quantity,
                    initial=order_item.quantity,
                    label=_('Quantity to Return'),
                    widget=forms.NumberInput(attrs={
                        'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                        'min': 1,
                        'max': order_item.quantity
                    })
                )

                # Add reason field for each item
                reason_field_name = f'reason_{order_item.id}'
                self.fields[reason_field_name] = forms.ChoiceField(
                    required=False,
                    choices=Return.RETURN_REASON_CHOICES,
                    widget=forms.Select(attrs={
                        'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500'
                    })
                )

    def clean(self):
        cleaned_data = super().clean()

        # Check if at least one item is selected
        selected_items = [key for key in cleaned_data.keys() if key.startswith('item_') and cleaned_data[key]]

        if not selected_items:
            raise forms.ValidationError(
                _('Please select at least one item to return.')
            )

        return cleaned_data


class ReturnApprovalForm(forms.ModelForm):
    """Form for admins to approve/reject return requests"""

    approve = forms.BooleanField(required=False, label=_('Approve Return'))
    reject = forms.BooleanField(required=False, label=_('Reject Return'))

    class Meta:
        model = Return
        fields = ['rejection_reason', 'refund_amount']
        widgets = {
            'rejection_reason': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'rows': 3,
                'placeholder': _('Provide reason for rejection...')
            }),
            'refund_amount': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'step': '0.01'
            })
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['rejection_reason'].required = False

        # Pre-fill refund amount with order total if not set
        if self.instance and self.instance.order and not self.instance.refund_amount:
            self.fields['refund_amount'].initial = self.instance.order.total_price

    def clean(self):
        cleaned_data = super().clean()
        approve = cleaned_data.get('approve')
        reject = cleaned_data.get('reject')
        rejection_reason = cleaned_data.get('rejection_reason')

        if approve and reject:
            raise forms.ValidationError(
                _('You cannot both approve and reject a return. Please select only one action.')
            )

        if not approve and not reject:
            raise forms.ValidationError(
                _('Please select whether to approve or reject this return request.')
            )

        if reject and not rejection_reason:
            raise forms.ValidationError(
                _('Please provide a reason for rejecting this return request.')
            )

        return cleaned_data


class ReturnShippingForm(forms.ModelForm):
    """Form for managing return shipping information"""

    class Meta:
        model = Return
        fields = [
            'return_tracking_number',
            'return_carrier',
            'pickup_scheduled_date',
            'pickup_address'
        ]
        widgets = {
            'return_tracking_number': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'placeholder': _('Enter tracking number')
            }),
            'return_carrier': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'placeholder': _('e.g., DHL, FedEx, Aramex')
            }),
            'pickup_scheduled_date': forms.DateTimeInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'type': 'datetime-local'
            }),
            'pickup_address': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'rows': 3,
                'placeholder': _('Enter pickup address')
            })
        }


class ReturnInspectionForm(forms.ModelForm):
    """Form for warehouse staff to inspect returned items"""

    approve_for_refund = forms.BooleanField(required=False, label=_('Approve for Refund'))
    reject_for_refund = forms.BooleanField(required=False, label=_('Reject for Refund'))

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make deduction fields optional (they have default=0 in model)
        self.fields['restocking_fee'].required = False
        self.fields['damage_deduction'].required = False
        self.fields['shipping_cost_deduction'].required = False

    class Meta:
        model = Return
        fields = [
            'item_condition',
            'inspection_notes',
            'can_restock',
            'restocking_fee',
            'damage_deduction',
            'shipping_cost_deduction'
        ]
        widgets = {
            'item_condition': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'required': True
            }),
            'inspection_notes': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'rows': 4,
                'placeholder': _('Document inspection findings, defects, damages, etc.'),
                'required': True
            }),
            'can_restock': forms.CheckboxInput(attrs={
                'class': 'rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50'
            }),
            'restocking_fee': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'step': '0.01',
                'min': '0'
            }),
            'damage_deduction': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'step': '0.01',
                'min': '0'
            }),
            'shipping_cost_deduction': forms.NumberInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'step': '0.01',
                'min': '0'
            })
        }

    def clean(self):
        cleaned_data = super().clean()
        approve_for_refund = cleaned_data.get('approve_for_refund')
        reject_for_refund = cleaned_data.get('reject_for_refund')
        item_condition = cleaned_data.get('item_condition')
        inspection_notes = cleaned_data.get('inspection_notes')

        if approve_for_refund and reject_for_refund:
            raise forms.ValidationError(
                _('You cannot both approve and reject for refund. Please select only one action.')
            )

        if not approve_for_refund and not reject_for_refund:
            raise forms.ValidationError(
                _('Please select whether to approve or reject this return for refund.')
            )

        if not item_condition:
            raise forms.ValidationError(
                _('Please select the condition of the returned item.')
            )

        if not inspection_notes:
            raise forms.ValidationError(
                _('Please provide detailed inspection notes.')
            )

        return cleaned_data


class RefundProcessingForm(forms.ModelForm):
    """Form for processing refunds"""

    class Meta:
        model = Return
        fields = [
            'refund_method',
            'refund_reference',
            'refund_notes'
        ]
        widgets = {
            'refund_method': forms.Select(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'required': True
            }),
            'refund_reference': forms.TextInput(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'placeholder': _('e.g., Transaction ID, Bank Reference Number')
            }),
            'refund_notes': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'rows': 3,
                'placeholder': _('Additional notes about the refund processing...')
            })
        }

    def clean(self):
        cleaned_data = super().clean()
        refund_method = cleaned_data.get('refund_method')

        if not refund_method:
            raise forms.ValidationError(
                _('Please select a refund method.')
            )

        return cleaned_data


class ReturnCustomerContactForm(forms.ModelForm):
    """Form for documenting customer contact"""

    class Meta:
        model = Return
        fields = ['customer_contacted', 'customer_contact_notes']
        widgets = {
            'customer_contacted': forms.CheckboxInput(attrs={
                'class': 'rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50'
            }),
            'customer_contact_notes': forms.Textarea(attrs={
                'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
                'rows': 3,
                'placeholder': _('Document customer communication, agreements, concerns, etc.')
            })
        }


class ReturnFilterForm(forms.Form):
    """Form for filtering return requests"""

    return_status = forms.MultipleChoiceField(
        required=False,
        choices=Return.RETURN_STATUS_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50'
        })
    )

    refund_status = forms.MultipleChoiceField(
        required=False,
        choices=Return.REFUND_STATUS_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50'
        })
    )

    return_reason = forms.MultipleChoiceField(
        required=False,
        choices=Return.RETURN_REASON_CHOICES,
        widget=forms.CheckboxSelectMultiple(attrs={
            'class': 'rounded border-gray-300 text-blue-600 shadow-sm focus:border-blue-300 focus:ring focus:ring-blue-200 focus:ring-opacity-50'
        })
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
            'type': 'date'
        })
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
            'type': 'date'
        })
    )

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'mt-1 block w-full rounded-md border-gray-300 shadow-sm focus:border-blue-500 focus:ring-blue-500',
            'placeholder': _('Search by return code, order code, customer name...')
        })
    )
