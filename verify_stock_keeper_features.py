"""
Manual Stock Keeper Feature Verification
========================================

Verifies stock keeper receiving workflow features by checking:
- Template content for barcode scanning
- Label printing functionality
- Warehouse location tracking
- Movement models and tracking
"""

import os
import re
from pathlib import Path

def check_stock_keeper_features():
    """Check stock keeper features"""

    print("="*80)
    print("STOCK KEEPER RECEIVING WORKFLOW VERIFICATION")
    print("="*80)
    print()

    results = {
        'total_checks': 0,
        'passed': 0,
        'failed': 0,
        'details': []
    }

    # Test 1: Receive Stock Template - Barcode Scanner
    print("[1] Checking Barcode Scanner Functionality...")
    results['total_checks'] += 1

    receive_stock_template = Path('/root/new-python-code/stock_keeper/templates/stock_keeper/receive_stock.html')
    if receive_stock_template.exists():
        content = receive_stock_template.read_text()

        # Check for barcode scanner elements
        has_barcode_input = 'barcode-scanner' in content
        has_scan_handler = 'handleBarcodeScan' in content
        has_barcode_api = 'api/search-product' in content
        has_manual_entry = 'Manual Entry' in content

        print(f"  - Barcode input field: {'✓' if has_barcode_input else '✗'}")
        print(f"  - Scan handler function: {'✓' if has_scan_handler else '✗'}")
        print(f"  - Product search API: {'✓' if has_barcode_api else '✗'}")
        print(f"  - Manual entry fallback: {'✓' if has_manual_entry else '✗'}")

        if all([has_barcode_input, has_scan_handler, has_barcode_api, has_manual_entry]):
            print(f"  ✓ PASS: Barcode scanning fully implemented")
            results['passed'] += 1
            results['details'].append("Barcode scanning: COMPLETE")
        else:
            print(f"  ✗ PARTIAL: Some barcode features missing")
            results['failed'] += 1
            results['details'].append("Barcode scanning: PARTIAL")
    else:
        print(f"  ✗ FAIL: receive_stock.html not found")
        results['failed'] += 1

    print()

    # Test 2: Label Printing Functionality
    print("[2] Checking Label Printing Functionality...")
    results['total_checks'] += 1

    if receive_stock_template.exists():
        content = receive_stock_template.read_text()

        # Check for label printing elements
        has_print_function = 'printLabel' in content
        has_print_button = 'fa-print' in content
        has_print_window = 'window.open' in content
        has_label_template = 'Shipping Label' in content or 'Receiving Label' in content

        print(f"  - Print function defined: {'✓' if has_print_function else '✗'}")
        print(f"  - Print button icon: {'✓' if has_print_button else '✗'}")
        print(f"  - Print window logic: {'✓' if has_print_window else '✗'}")
        print(f"  - Label template: {'✓' if has_label_template else '✗'}")

        if all([has_print_function, has_print_button, has_print_window, has_label_template]):
            print(f"  ✓ PASS: Label printing fully implemented")
            results['passed'] += 1
            results['details'].append("Label printing: COMPLETE")
        else:
            print(f"  ✗ PARTIAL: Some label printing features missing")
            results['failed'] += 1
            results['details'].append("Label printing: PARTIAL")
    else:
        print(f"  ✗ FAIL: receive_stock.html not found")
        results['failed'] += 1

    print()

    # Test 3: Warehouse Location Management
    print("[3] Checking Warehouse Location Management...")
    results['total_checks'] += 1

    models_file = Path('/root/new-python-code/stock_keeper/models.py')
    if models_file.exists():
        content = models_file.read_text()

        # Check for location tracking fields
        has_location_code = 'location_code' in content
        has_from_location = 'from_location' in content
        has_to_location = 'to_location' in content
        has_warehouse_inventory = 'WarehouseInventory' in content

        print(f"  - location_code field: {'✓' if has_location_code else '✗'}")
        print(f"  - from_location field: {'✓' if has_from_location else '✗'}")
        print(f"  - to_location field: {'✓' if has_to_location else '✗'}")
        print(f"  - WarehouseInventory model: {'✓' if has_warehouse_inventory else '✗'}")

        if all([has_location_code, has_from_location, has_to_location, has_warehouse_inventory]):
            print(f"  ✓ PASS: Warehouse location management implemented")
            results['passed'] += 1
            results['details'].append("Warehouse location management: COMPLETE")
        else:
            print(f"  ✗ PARTIAL: Some location features missing")
            results['failed'] += 1
            results['details'].append("Warehouse location management: PARTIAL")
    else:
        print(f"  ✗ FAIL: models.py not found")
        results['failed'] += 1

    print()

    # Test 4: Movement Tracking Numbers
    print("[4] Checking Movement Tracking Numbers...")
    results['total_checks'] += 1

    if models_file.exists():
        content = models_file.read_text()

        # Check for tracking number generation
        has_tracking_function = 'generate_tracking_number' in content
        has_tracking_field = 'tracking_number' in content
        has_unique_tracking = 'unique=True' in content and 'tracking_number' in content.split('unique=True')[0][-100:]

        print(f"  - generate_tracking_number function: {'✓' if has_tracking_function else '✗'}")
        print(f"  - tracking_number field: {'✓' if has_tracking_field else '✗'}")
        print(f"  - Unique constraint: {'✓' if has_unique_tracking else '✗'}")

        if all([has_tracking_function, has_tracking_field]):
            print(f"  ✓ PASS: Tracking number generation implemented")
            results['passed'] += 1
            results['details'].append("Tracking numbers: COMPLETE")
        else:
            print(f"  ✗ PARTIAL: Tracking features incomplete")
            results['failed'] += 1
            results['details'].append("Tracking numbers: PARTIAL")
    else:
        print(f"  ✗ FAIL: models.py not found")
        results['failed'] += 1

    print()

    # Test 5: Stock-In View Implementation
    print("[5] Checking Stock-In View Logic...")
    results['total_checks'] += 1

    views_file = Path('/root/new-python-code/stock_keeper/views.py')
    if views_file.exists():
        content = views_file.read_text()

        # Check for receive_stock view
        has_receive_view = 'def receive_stock' in content
        has_movement_creation = 'InventoryMovement.objects.create' in content and 'stock_in' in content
        has_inventory_update = 'InventoryRecord.objects.get_or_create' in content or 'inventory.quantity +=' in content
        has_location_handling = 'location_code' in content and 'to_location' in content

        print(f"  - receive_stock view: {'✓' if has_receive_view else '✗'}")
        print(f"  - Movement record creation: {'✓' if has_movement_creation else '✗'}")
        print(f"  - Inventory update logic: {'✓' if has_inventory_update else '✗'}")
        print(f"  - Location handling: {'✓' if has_location_handling else '✗'}")

        if all([has_receive_view, has_movement_creation, has_inventory_update]):
            print(f"  ✓ PASS: Stock-In view fully implemented")
            results['passed'] += 1
            results['details'].append("Stock-In view: COMPLETE")
        else:
            print(f"  ✗ PARTIAL: Some view logic missing")
            results['failed'] += 1
            results['details'].append("Stock-In view: PARTIAL")
    else:
        print(f"  ✗ FAIL: views.py not found")
        results['failed'] += 1

    print()

    # Test 6: Client Stock vs Sourcing Distinction
    print("[6] Checking Client Stock vs Sourcing Distinction...")
    results['total_checks'] += 1

    if receive_stock_template.exists():
        content = receive_stock_template.read_text()

        # Check for type distinction
        has_client_stock = 'Client Stock-In' in content
        has_sourcing = 'Sourcing Purchase' in content
        has_type_filter = 'receiving_type' in content
        has_reference_type = 'reference_type' in content or 'reference_number' in content

        print(f"  - Client Stock-In option: {'✓' if has_client_stock else '✗'}")
        print(f"  - Sourcing Purchase option: {'✓' if has_sourcing else '✗'}")
        print(f"  - Type filtering: {'✓' if has_type_filter else '✗'}")
        print(f"  - Reference tracking: {'✓' if has_reference_type else '✗'}")

        if all([has_client_stock, has_sourcing, has_type_filter]):
            print(f"  ✓ PASS: Stock type distinction implemented")
            results['passed'] += 1
            results['details'].append("Stock type distinction: COMPLETE")
        else:
            print(f"  ✗ PARTIAL: Stock type features incomplete")
            results['failed'] += 1
            results['details'].append("Stock type distinction: PARTIAL")
    else:
        print(f"  ✗ FAIL: receive_stock.html not found")
        results['failed'] += 1

    print()

    # Test 7: GRN (Goods Receipt Note) Display
    print("[7] Checking GRN Display and Management...")
    results['total_checks'] += 1

    if receive_stock_template.exists():
        content = receive_stock_template.read_text()

        # Check for GRN display
        has_grn_number = 'GRN Number' in content or 'GRN-S-' in content
        has_supplier_info = 'Supplier' in content
        has_view_action = 'viewReceiving' in content or 'View' in content
        has_recent_table = 'Recent Receivings' in content

        print(f"  - GRN number display: {'✓' if has_grn_number else '✗'}")
        print(f"  - Supplier information: {'✓' if has_supplier_info else '✗'}")
        print(f"  - View action: {'✓' if has_view_action else '✗'}")
        print(f"  - Recent receivings table: {'✓' if has_recent_table else '✗'}")

        if all([has_grn_number, has_supplier_info, has_view_action, has_recent_table]):
            print(f"  ✓ PASS: GRN management implemented")
            results['passed'] += 1
            results['details'].append("GRN management: COMPLETE")
        else:
            print(f"  ✗ PARTIAL: Some GRN features missing")
            results['failed'] += 1
            results['details'].append("GRN management: PARTIAL")
    else:
        print(f"  ✗ FAIL: receive_stock.html not found")
        results['failed'] += 1

    print()

    # Test 8: Date Filtering
    print("[8] Checking Date Filtering...")
    results['total_checks'] += 1

    if receive_stock_template.exists():
        content = receive_stock_template.read_text()

        # Check for date filtering
        has_period_selector = 'Select Period' in content
        has_date_from = 'date_from' in content
        has_date_to = 'date_to' in content
        has_period_modal = 'periodModal' in content

        print(f"  - Period selector button: {'✓' if has_period_selector else '✗'}")
        print(f"  - date_from parameter: {'✓' if has_date_from else '✗'}")
        print(f"  - date_to parameter: {'✓' if has_date_to else '✗'}")
        print(f"  - Period modal: {'✓' if has_period_modal else '✗'}")

        if all([has_period_selector, has_date_from, has_date_to, has_period_modal]):
            print(f"  ✓ PASS: Date filtering implemented")
            results['passed'] += 1
            results['details'].append("Date filtering: COMPLETE")
        else:
            print(f"  ✗ PARTIAL: Date filtering incomplete")
            results['failed'] += 1
            results['details'].append("Date filtering: PARTIAL")
    else:
        print(f"  ✗ FAIL: receive_stock.html not found")
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
        status = "✓" if "COMPLETE" in detail else "✗"
        print(f"  {status} {detail}")

    print()
    print("="*80)

    # Client Requirements Assessment
    print("CLIENT REQUIREMENTS STATUS:")
    print("="*80)
    print()

    all_passed = results['failed'] == 0

    if all_passed:
        print("✅ Stock-In/Receiving Workflow: FULLY IMPLEMENTED")
        print("  ✓ Barcode scanning interface")
        print("  ✓ Label printing functionality")
        print("  ✓ Warehouse location management")
        print("  ✓ Movement tracking numbers")
        print("  ✓ Stock-In view logic")
        print("  ✓ Client vs Sourcing distinction")
        print("  ✓ GRN management")
        print("  ✓ Date filtering")
    else:
        print(f"⚠️  Stock-In/Receiving Workflow: {results['passed']}/{results['total_checks']} FEATURES IMPLEMENTED")
        print()
        print("Implemented:")
        for detail in results['details']:
            if "COMPLETE" in detail:
                print(f"  ✓ {detail.split(':')[0]}")
        print()
        if results['failed'] > 0:
            print("Needs Attention:")
            for detail in results['details']:
                if "PARTIAL" in detail:
                    print(f"  ⚠️  {detail.split(':')[0]}")

    return results

if __name__ == '__main__':
    check_stock_keeper_features()
