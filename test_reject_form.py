#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')
django.setup()

from orders.return_forms import ReturnApprovalForm

# Simulate the reject form submission
form_data = {
    'reject': 'on',
    'rejection_reason': 'Outside return window'
}

print("Testing reject form with data:", form_data)
form = ReturnApprovalForm(data=form_data)
print(f"Form is_valid(): {form.is_valid()}")
if not form.is_valid():
    print(f"Form errors: {form.errors}")
    print(f"Form non_field_errors: {form.non_field_errors()}")
