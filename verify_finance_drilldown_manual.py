"""
Manual Finance Drill-Down Verification
======================================

This script manually checks the finance module templates and views
to verify drill-down functionality exists.
"""

import os
import re
from pathlib import Path

def check_drill_down_features():
    """Check for drill-down features in finance templates"""

    print("="*80)
    print("FINANCE DRILL-DOWN VERIFICATION - MANUAL CHECK")
    print("="*80)
    print()

    results = {
        'total_checks': 0,
        'passed': 0,
        'failed': 0,
        'details': []
    }

    finance_templates_dir = Path('/root/new-python-code/finance/templates/finance')

    # Test 1: Check if financial_reports.html has clickable elements
    print("[1] Checking financial_reports.html for drill-down links...")
    results['total_checks'] += 1

    reports_file = finance_templates_dir / 'financial_reports.html'
    if reports_file.exists():
        content = reports_file.read_text()

        # Look for href links
        href_count = len(re.findall(r'href\s*=', content))
        # Look for order or payment links
        order_links = len(re.findall(r'order[_-]?detail|order[_-]?management', content, re.I))
        payment_links = len(re.findall(r'payment[_-]?detail|payment[_-]?management', content, re.I))

        print(f"  - Total href links found: {href_count}")
        print(f"  - Order-related links: {order_links}")
        print(f"  - Payment-related links: {payment_links}")

        if href_count > 10 and (order_links > 0 or payment_links > 0):
            print(f"  ✓ PASS: Financial reports has drill-down capability")
            results['passed'] += 1
            results['details'].append("Financial reports has drill-down links")
        else:
            print(f"  ✗ FAIL: Limited drill-down in financial reports")
            results['failed'] += 1
            results['details'].append("Financial reports needs more drill-down links")
    else:
        print(f"  ✗ FAIL: financial_reports.html not found")
        results['failed'] += 1

    print()

    # Test 2: Check order_detail.html for comprehensive information
    print("[2] Checking order_detail.html for comprehensive data...")
    results['total_checks'] += 1

    order_detail_file = finance_templates_dir / 'order_detail.html'
    if order_detail_file.exists():
        content = order_detail_file.read_text()

        # Check for key elements
        has_customer_info = 'customer' in content.lower()
        has_payment_info = 'payment' in content.lower()
        has_product_info = 'product' in content.lower()
        has_invoice_link = 'invoice' in content.lower()

        print(f"  - Customer information: {'✓' if has_customer_info else '✗'}")
        print(f"  - Payment information: {'✓' if has_payment_info else '✗'}")
        print(f"  - Product information: {'✓' if has_product_info else '✗'}")
        print(f"  - Invoice generation link: {'✓' if has_invoice_link else '✗'}")

        if all([has_customer_info, has_payment_info, has_product_info, has_invoice_link]):
            print(f"  ✓ PASS: Order detail has comprehensive drill-down")
            results['passed'] += 1
            results['details'].append("Order detail page is comprehensive")
        else:
            print(f"  ✗ FAIL: Order detail missing some information")
            results['failed'] += 1
            results['details'].append("Order detail needs enhancement")
    else:
        print(f"  ✗ FAIL: order_detail.html not found")
        results['failed'] += 1

    print()

    # Test 3: Check invoice_detail.html
    print("[3] Checking invoice_detail.html for drill-down...")
    results['total_checks'] += 1

    invoice_detail_file = finance_templates_dir / 'invoice_detail.html'
    if invoice_detail_file.exists():
        content = invoice_detail_file.read_text()

        # Check for back links and related information
        has_back_link = 'back' in content.lower()
        has_order_info = 'order' in content.lower()
        has_edit_link = 'edit' in content.lower()

        print(f"  - Back navigation: {'✓' if has_back_link else '✗'}")
        print(f"  - Order information: {'✓' if has_order_info else '✗'}")
        print(f"  - Edit functionality: {'✓' if has_edit_link else '✗'}")

        if all([has_back_link, has_order_info]):
            print(f"  ✓ PASS: Invoice detail has navigation")
            results['passed'] += 1
            results['details'].append("Invoice detail has proper navigation")
        else:
            print(f"  ✗ FAIL: Invoice detail navigation incomplete")
            results['failed'] += 1
            results['details'].append("Invoice detail needs navigation improvements")
    else:
        print(f"  ✗ FAIL: invoice_detail.html not found")
        results['failed'] += 1

    print()

    # Test 4: Check payment_management.html
    print("[4] Checking payment_management.html for drill-down...")
    results['total_checks'] += 1

    payment_mgmt_file = finance_templates_dir / 'payment_management.html'
    if payment_mgmt_file.exists():
        content = payment_mgmt_file.read_text()

        # Look for payment action links
        edit_links = len(re.findall(r'payment[_-]?edit|edit[_-]?payment', content, re.I))
        detail_links = len(re.findall(r'payment[_-]?detail|detail[_-]?payment', content, re.I))
        order_links = len(re.findall(r'order', content, re.I))

        print(f"  - Edit payment links: {edit_links}")
        print(f"  - Detail links: {detail_links}")
        print(f"  - Order references: {order_links}")

        if edit_links > 0 or detail_links > 0 or order_links > 5:
            print(f"  ✓ PASS: Payment management has drill-down capability")
            results['passed'] += 1
            results['details'].append("Payment management has drill-down")
        else:
            print(f"  ✗ FAIL: Payment management needs drill-down links")
            results['failed'] += 1
            results['details'].append("Payment management needs more drill-down")
    else:
        print(f"  ✗ FAIL: payment_management.html not found")
        results['failed'] += 1

    print()

    # Test 5: Check accountant_dashboard.html for report links
    print("[5] Checking accountant_dashboard.html for report access...")
    results['total_checks'] += 1

    dashboard_file = finance_templates_dir / 'accountant_dashboard.html'
    if dashboard_file.exists():
        content = dashboard_file.read_text()

        # Look for links to various reports and details
        report_links = len(re.findall(r'report|financial', content, re.I))
        order_links = len(re.findall(r'order', content, re.I))
        payment_links = len(re.findall(r'payment', content, re.I))
        invoice_links = len(re.findall(r'invoice', content, re.I))

        print(f"  - Report/financial links: {report_links}")
        print(f"  - Order references: {order_links}")
        print(f"  - Payment references: {payment_links}")
        print(f"  - Invoice references: {invoice_links}")

        if report_links > 5 and order_links > 5:
            print(f"  ✓ PASS: Dashboard has comprehensive navigation")
            results['passed'] += 1
            results['details'].append("Dashboard has good navigation structure")
        else:
            print(f"  ✗ FAIL: Dashboard needs more navigation links")
            results['failed'] += 1
            results['details'].append("Dashboard navigation could be enhanced")
    else:
        print(f"  ✗ FAIL: accountant_dashboard.html not found")
        results['failed'] += 1

    print()

    # Summary
    print("="*80)
    print("VERIFICATION SUMMARY")
    print("="*80)
    print(f"Total Checks: {results['total_checks']}")
    print(f"Passed: {results['passed']}")
    print(f"Failed: {results['failed']}")
    print(f"Success Rate: {(results['passed']/results['total_checks']*100):.1f}%")
    print()

    print("Details:")
    for detail in results['details']:
        print(f"  - {detail}")

    print()
    print("="*80)

    # Recommendations
    print("RECOMMENDATIONS FOR ENHANCEMENT:")
    print("="*80)
    print()

    if results['failed'] > 0:
        print("To improve drill-down functionality:")
        print("1. Add clickable order codes in all financial reports")
        print("2. Link payment amounts to payment detail pages")
        print("3. Add breadcrumb navigation across finance pages")
        print("4. Implement 'view details' buttons in summary tables")
        print("5. Add quick actions (view/edit/invoice) in data tables")
    else:
        print("✓ All drill-down checks passed!")
        print("  Finance module has good drill-down capability")

    return results

if __name__ == '__main__':
    check_drill_down_features()
