#!/usr/bin/env python
"""
Complete fix for all analytics services issues.
"""

def fix_analytics_services():
    """Fix all remaining issues in analytics services."""

    file_path = '/root/new-python-code/analytics/services.py'

    with open(file_path, 'r') as f:
        content = f.read()

    print("Applying comprehensive fixes to analytics services...")

    # Fix 1: Remove min_stock filter (field doesn't exist in Product model)
    old_low_stock = "low_stock = products.filter(stock__gt=0, stock__lte=F('min_stock')).count()"
    new_low_stock = "# min_stock field doesn't exist, using threshold of 10\n        low_stock = products.filter(stock__gt=0, stock__lte=10).count()"
    content = content.replace(old_low_stock, new_low_stock)
    print("✓ Fixed: Product min_stock field")

    # Fix 2: Payment model uses 'payment_status' not 'status', and 'payment_date' not 'created_at'
    old_payment_filter = '''        # From payments
        payments = Payment.objects.filter(
            created_at__gte=start_date,
            status='completed'
        )'''

    new_payment_filter = '''        # From payments
        payments = Payment.objects.filter(
            payment_date__gte=start_date,
            payment_status='completed'
        )'''

    content = content.replace(old_payment_filter, new_payment_filter)
    print("✓ Fixed: Payment status and date fields")

    # Fix 3: Payment methods breakdown - same issue
    old_payment_methods = '''        breakdown = Payment.objects.filter(
            created_at__gte=start_date,
            status='completed'
        ).values('payment_method').annotate('''

    new_payment_methods = '''        breakdown = Payment.objects.filter(
            payment_date__gte=start_date,
            payment_status='completed'
        ).values('payment_method').annotate('''

    content = content.replace(old_payment_methods, new_payment_methods)
    print("✓ Fixed: Payment methods breakdown fields")

    # Fix 4: Outstanding payments - same issue
    old_outstanding = '''        pending = Payment.objects.filter(
            status='pending'
        ).aggregate('''

    new_outstanding = '''        pending = Payment.objects.filter(
            payment_status='pending'
        ).aggregate('''

    content = content.replace(old_outstanding, new_outstanding)
    print("✓ Fixed: Outstanding payments field")

    # Fix 5: Daily revenue trend - use payment_date
    old_daily_revenue = '''        # Daily revenue trend
        daily_revenue = payments.annotate(
            date=TruncDate('created_at')'''

    new_daily_revenue = '''        # Daily revenue trend
        daily_revenue = payments.annotate(
            date=TruncDate('payment_date')'''

    content = content.replace(old_daily_revenue, new_daily_revenue)
    print("✓ Fixed: Daily revenue trend date field")

    # Write the fixed content
    with open(file_path, 'w') as f:
        f.write(content)

    print(f"\nFile updated: {file_path}")
    return True

if __name__ == '__main__':
    import sys
    try:
        success = fix_analytics_services()
        if success:
            print("\n✓ All analytics fixes applied successfully!")
            print("\nChanges made:")
            print("1. Product min_stock → hardcoded threshold of 10")
            print("2. Payment 'status' → 'payment_status'")
            print("3. Payment 'created_at' → 'payment_date'")
            print("\nRestart Django server to apply changes.")
            sys.exit(0)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
