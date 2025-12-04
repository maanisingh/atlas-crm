#!/usr/bin/env python
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')
django.setup()

from orders.return_forms import ReturnInspectionForm
from orders.models import Return

# Simulate the form submission
form_data = {
    'approve_for_refund': True,
    'item_condition': 'like_new',
    'inspection_notes': 'Items in original condition',
    'can_restock': True
}

print("Testing form with data:", form_data)
form = ReturnInspectionForm(data=form_data)
print(f"Form is_valid(): {form.is_valid()}")
if not form.is_valid():
    print(f"Form errors: {form.errors}")
    print(f"Form non_field_errors: {form.non_field_errors()}")
