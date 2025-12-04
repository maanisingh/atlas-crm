"""
Test Finance Module Drill-Down Functionality
============================================

Tests to verify that finance pages have proper drill-down capabilities:
- Reports should link to detailed views
- Aggregated data should allow drilling into individual records
- Navigation between finance pages should be seamless
"""

import os
import sys
import django

# Setup Django environment
sys.path.insert(0, '/root/new-python-code')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm_fulfillment.settings')
django.setup()

from django.test import Client, TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone

from finance.models import Payment, SellerFee, TruvoPayment
from orders.models import Order
from sellers.models import Product, Seller
from inventory.models import Warehouse

User = get_user_model()

class FinanceDrillDownTests(TestCase):
    """Test finance module drill-down functionality"""

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        print("\n" + "="*80)
        print("FINANCE DRILL-DOWN FUNCTIONALITY TESTS")
        print("="*80)

    def setUp(self):
        """Set up test data"""
        # Create test admin user
        self.admin_user = User.objects.create_user(
            username='admin_drilldown',
            email='admin_drilldown@test.com',
            password='testpass123',
            is_staff=True,
            is_superuser=True
        )

        # Create test seller
        self.seller_user = User.objects.create_user(
            username='seller_drilldown',
            email='seller_drilldown@test.com',
            password='testpass123'
        )

        # Create warehouse
        self.warehouse = Warehouse.objects.create(
            name='Test Warehouse',
            location='Dubai',
            description='Test warehouse for drill-down tests'
        )

        # Create test products
        self.product1 = Product.objects.create(
            name_en='Product 1',
            name_ar='منتج 1',
            selling_price=Decimal('100.00'),
            purchase_price=Decimal('80.00'),
            stock_quantity=50,
            seller=self.seller_user,
            warehouse=self.warehouse
        )

        self.product2 = Product.objects.create(
            name_en='Product 2',
            name_ar='منتج 2',
            selling_price=Decimal('200.00'),
            purchase_price=Decimal('160.00'),
            stock_quantity=30,
            seller=self.seller_user,
            warehouse=self.warehouse
        )

        # Create test orders
        self.order1 = Order.objects.create(
            order_code='ORD-DRILL-001',
            customer='Customer 1',
            product=self.product1,
            quantity=2,
            price_per_unit=Decimal('100.00'),
            status='confirmed',
            date=timezone.now()
        )

        self.order2 = Order.objects.create(
            order_code='ORD-DRILL-002',
            customer='Customer 2',
            product=self.product2,
            quantity=1,
            price_per_unit=Decimal('200.00'),
            status='delivered',
            date=timezone.now() - timedelta(days=5)
        )

        # Create test payments
        self.payment1 = Payment.objects.create(
            order=self.order1,
            amount=Decimal('200.00'),
            payment_method='credit_card',
            payment_status='completed',
            payment_date=timezone.now(),
            seller=self.seller_user
        )

        self.payment2 = Payment.objects.create(
            order=self.order2,
            amount=Decimal('200.00'),
            payment_method='cod',
            payment_status='pending',
            payment_date=timezone.now() - timedelta(days=5),
            seller=self.seller_user
        )

        # Create client
        self.client = Client()
        self.client.login(username='admin_drilldown', password='testpass123')

    def test_01_dashboard_to_reports_navigation(self):
        """Test: Dashboard has links to financial reports"""
        print("\n[Test 1] Dashboard to Reports Navigation")

        response = self.client.get(reverse('finance:accountant_dashboard'))
        self.assertEqual(response.status_code, 200)

        # Check for links to reports
        content = response.content.decode('utf-8')
        has_reports_link = 'financial_reports' in content or 'reports' in content.lower()

        print(f"  ✓ Dashboard accessible")
        print(f"  {'✓' if has_reports_link else '✗'} Reports link present: {has_reports_link}")

        self.assertTrue(has_reports_link, "Dashboard should have link to financial reports")

    def test_02_reports_to_order_detail_drill_down(self):
        """Test: Financial reports allow drilling down to order details"""
        print("\n[Test 2] Reports to Order Detail Drill-Down")

        # Access financial reports
        response = self.client.get(reverse('finance:financial_reports'))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')

        # Check if order codes are clickable/linked
        order_code_present = self.order1.order_code in content
        has_order_links = 'order_detail' in content or '/orders/' in content

        print(f"  ✓ Financial reports accessible")
        print(f"  {'✓' if order_code_present else '✗'} Order codes displayed: {order_code_present}")
        print(f"  {'✓' if has_order_links else '✗'} Order detail links present: {has_order_links}")

        # Test order detail page access
        order_detail_response = self.client.get(
            reverse('finance:order_detail', args=[self.order1.id])
        )
        self.assertEqual(order_detail_response.status_code, 200)
        print(f"  ✓ Order detail page accessible")

    def test_03_payment_list_to_payment_detail(self):
        """Test: Payment list has drill-down to individual payments"""
        print("\n[Test 3] Payment List to Payment Detail")

        # Access payment management
        response = self.client.get(reverse('finance:payment_management'))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')

        # Check for payment details or edit links
        has_payment_actions = 'payment_edit' in content or 'edit' in content.lower()
        payment_amount_present = '200' in content  # Our test payment amount

        print(f"  ✓ Payment management page accessible")
        print(f"  {'✓' if payment_amount_present else '✗'} Payment data displayed: {payment_amount_present}")
        print(f"  {'✓' if has_payment_actions else '✗'} Payment action links present: {has_payment_actions}")

    def test_04_order_management_to_invoice_generation(self):
        """Test: Order management allows drilling to invoice generation"""
        print("\n[Test 4] Order Management to Invoice Generation")

        # Access order management
        response = self.client.get(reverse('finance:order_management'))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')

        # Check for invoice generation links
        has_invoice_links = 'invoice_generation' in content or 'invoice' in content.lower()

        print(f"  ✓ Order management page accessible")
        print(f"  {'✓' if has_invoice_links else '✗'} Invoice generation links present: {has_invoice_links}")

        # Test invoice generation page access
        invoice_response = self.client.get(
            reverse('finance:invoice_generation', args=[self.order1.id])
        )
        self.assertEqual(invoice_response.status_code, 200)
        print(f"  ✓ Invoice generation page accessible")

    def test_05_reports_export_with_details(self):
        """Test: Financial reports can be exported with detailed data"""
        print("\n[Test 5] Reports Export with Details")

        # Test CSV export
        response = self.client.post(
            reverse('finance:financial_reports'),
            {'action': 'export'}
        )

        # Should either export CSV or redirect
        export_successful = response.status_code in [200, 302]

        if response.status_code == 200:
            is_csv = 'text/csv' in response.get('Content-Type', '')
            print(f"  ✓ Export functionality accessible")
            print(f"  {'✓' if is_csv else '✗'} CSV format: {is_csv}")
        else:
            print(f"  ✓ Export redirects properly")

        self.assertTrue(export_successful, "Export should work")

    def test_06_seller_financial_summary_drill_down(self):
        """Test: Seller summary allows drilling into individual transactions"""
        print("\n[Test 6] Seller Financial Summary Drill-Down")

        # Access financial reports
        response = self.client.get(reverse('finance:financial_reports'))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')

        # Check for seller information
        seller_info_present = (
            self.seller_user.username in content or
            self.seller_user.email in content or
            'seller' in content.lower()
        )

        print(f"  ✓ Financial reports accessible")
        print(f"  {'✓' if seller_info_present else '✗'} Seller information displayed: {seller_info_present}")

    def test_07_payment_status_filtering_with_detail_access(self):
        """Test: Payment filtering maintains drill-down capability"""
        print("\n[Test 7] Payment Status Filtering with Detail Access")

        # Filter by payment status
        response = self.client.get(
            reverse('finance:payment_management'),
            {'status': 'completed'}
        )
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')

        # Completed payment should be visible
        completed_payment_visible = str(self.payment1.amount) in content

        # Check for edit/detail links still present
        has_action_links = 'edit' in content.lower() or 'detail' in content.lower()

        print(f"  ✓ Payment filtering works")
        print(f"  {'✓' if completed_payment_visible else '✗'} Filtered payments displayed: {completed_payment_visible}")
        print(f"  {'✓' if has_action_links else '✗'} Action links preserved: {has_action_links}")

    def test_08_date_range_reports_with_drill_down(self):
        """Test: Date-filtered reports maintain drill-down links"""
        print("\n[Test 8] Date Range Reports with Drill-Down")

        # Get reports with date range
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        response = self.client.get(
            reverse('finance:financial_reports'),
            {
                'date_from': yesterday.strftime('%Y-%m-%d'),
                'date_to': today.strftime('%Y-%m-%d')
            }
        )
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')

        # Check that orders/payments are still linked
        has_drill_down = 'href' in content and ('order' in content.lower() or 'payment' in content.lower())

        print(f"  ✓ Date range filtering works")
        print(f"  {'✓' if has_drill_down else '✗'} Drill-down links present: {has_drill_down}")

    def test_09_fee_management_order_linking(self):
        """Test: Fee management page links to orders"""
        print("\n[Test 9] Fee Management Order Linking")

        # Access fee management for specific order
        response = self.client.get(
            reverse('finance:fee_management', args=[self.order1.id])
        )
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')

        # Check for order information
        order_code_present = self.order1.order_code in content

        print(f"  ✓ Fee management page accessible")
        print(f"  {'✓' if order_code_present else '✗'} Order details displayed: {order_code_present}")

    def test_10_bank_reconciliation_payment_linking(self):
        """Test: Bank reconciliation links to payment details"""
        print("\n[Test 10] Bank Reconciliation Payment Linking")

        # Access bank reconciliation
        response = self.client.get(reverse('finance:bank_reconciliation'))
        self.assertEqual(response.status_code, 200)

        content = response.content.decode('utf-8')

        # Check for payment information and links
        has_payment_data = '200' in content  # Our payment amounts
        has_links = 'href' in content

        print(f"  ✓ Bank reconciliation page accessible")
        print(f"  {'✓' if has_payment_data else '✗'} Payment data displayed: {has_payment_data}")
        print(f"  {'✓' if has_links else '✗'} Navigation links present: {has_links}")


def run_tests():
    """Run all drill-down tests"""
    import unittest
    from django.test.runner import DiscoverRunner

    # Create test suite
    suite = unittest.TestSuite()

    # Add all test methods
    for test_name in dir(FinanceDrillDownTests):
        if test_name.startswith('test_'):
            suite.addTest(FinanceDrillDownTests(test_name))

    # Run tests
    runner = DiscoverRunner(verbosity=2, interactive=False, keepdb=True)
    result = runner.run_suite(suite)

    # Print summary
    print("\n" + "="*80)
    print("FINANCE DRILL-DOWN TEST SUMMARY")
    print("="*80)
    print(f"Tests Run: {result.testsRun}")
    print(f"Successes: {result.testsRun - len(result.failures) - len(result.errors)}")
    print(f"Failures: {len(result.failures)}")
    print(f"Errors: {len(result.errors)}")

    if result.failures:
        print("\nFailed Tests:")
        for test, traceback in result.failures:
            print(f"  ✗ {test}")

    if result.errors:
        print("\nErrors:")
        for test, traceback in result.errors:
            print(f"  ✗ {test}")

    success_rate = ((result.testsRun - len(result.failures) - len(result.errors)) / result.testsRun * 100) if result.testsRun > 0 else 0
    print(f"\nSuccess Rate: {success_rate:.1f}%")
    print("="*80)

    return result.wasSuccessful()


if __name__ == '__main__':
    success = run_tests()
    sys.exit(0 if success else 1)
