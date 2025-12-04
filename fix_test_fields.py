#!/usr/bin/env python3
"""
Script to fix Order model field mismatches in test files
"""
import re

def fix_test_file(filepath):
    """Fix Order field references in test file"""

    with open(filepath, 'r') as f:
        content = f.read()

    # Track changes
    changes = []

    # Fix 1: Remove total_amount parameter and add required fields
    # Pattern: Order.objects.create(...) blocks
    def replace_order_create(match):
        full_match = match.group(0)

        # Remove total_amount line
        result = re.sub(r'\s*total_amount=Decimal\([^)]+\),?\n', '', full_match)

        # Replace customer_address with shipping_address
        result = re.sub(r'customer_address=', 'shipping_address=', result)

        # Check if required fields are present, if not add defaults
        if 'store_link=' not in result:
            # Add store_link before the closing parenthesis
            result = re.sub(
                r'(\s+)(status=)',
                r'\1store_link="https://example.com/product",\n\1\2',
                result
            )

        if 'price_per_unit=' not in result:
            result = re.sub(
                r'(\s+)(status=)',
                r'\1price_per_unit=Decimal("100.00"),\n\1\2',
                result
            )

        if 'quantity=' not in result:
            result = re.sub(
                r'(\s+)(status=)',
                r'\1quantity=1,\n\1\2',
                result
            )

        if 'customer_phone=' not in result:
            result = re.sub(
                r'(\s+)(status=)',
                r'\1customer_phone="1234567890",\n\1\2',
                result
            )

        return result

    # Fix Order.objects.create blocks
    # Match Order.objects.create( ... ) including multiline
    pattern = r'Order\.objects\.create\([^)]*(?:\([^)]*\)[^)]*)*\)'
    content = re.sub(pattern, replace_order_create, content, flags=re.MULTILINE | re.DOTALL)

    # Fix 2: Replace references to order.total_amount with calculated value
    # For assertions like: self.order.total_amount
    # Replace with sum of order items or default calculation
    content = re.sub(
        r'(\w+)\.total_amount',
        r'(\1.price_per_unit * \1.quantity)',
        content
    )

    # Fix 3: Replace customer_address references outside of create
    content = re.sub(r'customer_address=', 'shipping_address=', content)

    # Write back
    with open(filepath, 'w') as f:
        f.write(content)

    print(f"Fixed {filepath}")

if __name__ == '__main__':
    fix_test_file('orders/tests/test_return_models.py')
    fix_test_file('orders/tests/test_return_views.py')
    print("All test files fixed!")
