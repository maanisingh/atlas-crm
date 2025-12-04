#!/usr/bin/env python3
"""
Script to add required fields to Order.objects.create() calls
"""
import re

def fix_order_creates(filepath):
    """Add required fields to Order.objects.create() calls"""

    with open(filepath, 'r') as f:
        content = f.read()

    # Pattern to match Order.objects.create blocks
    # This will match from "Order.objects.create(" to the closing ")"
    pattern = r'(Order\.objects\.create\(\s*\n)((?:.*?\n)*?)(\s*\))'

    def add_required_fields(match):
        prefix = match.group(1)
        body = match.group(2)
        suffix = match.group(3)

        # Check if required fields are already present
        has_store_link = 'store_link=' in body
        has_price_per_unit = 'price_per_unit=' in body
        has_quantity = 'quantity=' in body
        has_customer_phone = 'customer_phone=' in body

        # Get the indentation from the first line in body
        indent_match = re.search(r'^(\s+)', body)
        indent = indent_match.group(1) if indent_match else '            '

        # Build list of fields to add
        fields_to_add = []
        if not has_store_link:
            fields_to_add.append(f'{indent}store_link="https://example.com/product",\n')
        if not has_price_per_unit:
            fields_to_add.append(f'{indent}price_per_unit=Decimal("100.00"),\n')
        if not has_quantity:
            fields_to_add.append(f'{indent}quantity=2,\n')
        if not has_customer_phone:
            fields_to_add.append(f'{indent}customer_phone="1234567890",\n')

        # Add fields before status= if possible, or at the start
        if 'status=' in body:
            # Insert before status
            parts = body.split('status=', 1)
            new_body = parts[0] + ''.join(fields_to_add) + 'status=' + parts[1]
        else:
            # Insert at the start
            new_body = ''.join(fields_to_add) + body

        return prefix + new_body + suffix

    # Apply the transformation
    content = re.sub(pattern, add_required_fields, content, flags=re.MULTILINE)

    # Write back
    with open(filepath, 'w') as f:
        f.write(content)

    print(f"Fixed {filepath}")

if __name__ == '__main__':
    fix_order_creates('orders/tests/test_return_views.py')
    print("All Order.objects.create() calls fixed!")
