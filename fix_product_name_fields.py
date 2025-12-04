#!/usr/bin/env python
"""
Fix script for product name field mismatches in analytics.

Issue: OrderItem.product points to sellers.Product which has name_en/name_ar,
not a simple 'name' field.
"""

def fix_product_name_fields():
    """Fix the product name field references."""

    file_path = '/root/new-python-code/analytics/services.py'

    with open(file_path, 'r') as f:
        content = f.read()

    print("Fixing product name field references...")

    # Fix: Change 'product__name' to 'product__name_en' in get_top_selling_products
    # This is for OrderItem which has FK to sellers.Product (name_en field)
    old_values = "        ).values(\n            'product__id', 'product__name'\n        ).annotate("
    new_values = "        ).values(\n            'product__id', 'product__name_en'\n        ).annotate("

    content = content.replace(old_values, new_values)
    print("✓ Fixed: product__name → product__name_en in get_top_selling_products")

    # Write the fixed content
    with open(file_path, 'w') as f:
        f.write(content)

    print(f"\nFile updated: {file_path}")
    return True

if __name__ == '__main__':
    import sys
    try:
        success = fix_product_name_fields()
        if success:
            print("\n✓ Product name field fix applied successfully!")
            print("\nChanges made:")
            print("1. OrderItem query: 'product__name' → 'product__name_en'")
            print("   (sellers.Product has name_en/name_ar, not name)")
            print("\nRestart Django server to apply changes.")
            sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
