#!/usr/bin/env python
import os
import django
from decimal import Decimal

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'test_settings')
django.setup()

from django.contrib.auth import get_user_model
from orders.models import Order, Return
from orders.return_forms import ReturnApprovalForm
from sellers.models import Product

User = get_user_model()

# Create test data
customer = User.objects.create_user(
    email='test@test.com',
    password='test',
    full_name='Test',
    phone_number='1234567890'
)

product = Product.objects.create(
    name_en='Test', name_ar='Test', code='TEST',
    selling_price=Decimal('100'), stock_quantity=10, seller=customer
)

order = Order.objects.create(
    customer=customer.email,
    order_code='ORD-TEST',
    store_link="https://example.com",
    price_per_unit=Decimal("100.00"),
    quantity=2,
    customer_phone="1234567890",
    status='delivered',
    city="Test",
    state="Test",
    shipping_address='Test'
)

return_obj = Return.objects.create(
    customer=customer,
    order=order,
    return_reason='defective',
    return_description='Test',
    refund_method='pickup',
    return_status='requested'
)

# Test the form
form_data = {
    'reject': 'on',
    'rejection_reason': 'Outside return window'
}

print("Testing reject form with data:", form_data)
form = ReturnApprovalForm(data=form_data, instance=return_obj)
print(f"Form is_valid(): {form.is_valid()}")
if not form.is_valid():
    print(f"Form errors: {form.errors}")
    print(f"Form non_field_errors: {form.non_field_errors()}")
else:
    print("Form is VALID!")
