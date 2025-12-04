"""
Integration tests for Return Management System views
Tests: Customer and admin views, permissions, workflows
"""

from django.test import TestCase, Client
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

User = get_user_model()

from orders.models import (
    Order, OrderItem, Return, ReturnItem, ReturnStatusLog
)
from sellers.models import Product
from roles.models import Role, UserRole


class CustomerReturnViewTests(TestCase):
    """Test suite for customer-facing return views"""

    def create_roles(self):
        """Helper to create necessary roles"""
        self.admin_role, _ = Role.objects.get_or_create(
            name='Admin',
            defaults={'role_type': 'admin'}
        )
        self.stock_keeper_role, _ = Role.objects.get_or_create(
            name='Stock Keeper',
            defaults={'role_type': 'custom'}
        )
        self.customer_role, _ = Role.objects.get_or_create(
            name='Customer',
            defaults={'role_type': 'custom'}
        )
        self.finance_role, _ = Role.objects.get_or_create(
            name='Finance',
            defaults={'role_type': 'custom'}
        )

    def setUp(self):
        """Set up test data for each test method"""
        # Create roles first
        self.create_roles()

        # Create customer user
        self.customer = User.objects.create_user(
            email='customer@test.com',
            password='testpass123',
            full_name='Test Customer',
            phone_number='1234567890',
            is_active=True,
            approval_status='approved'
        )

        # Create another customer for permission testing
        self.customer2 = User.objects.create_user(
            email='customer2@test.com',
            password='testpass123',
            full_name='Test Customer 2',
            phone_number='0987654321',
            is_active=True,
            approval_status='approved'
        )

        # Create product
        self.product = Product.objects.create(
            name_en='Test Product',
            name_ar='Test Product',
            code='TEST-001',
            selling_price=Decimal('100.00'),
            stock_quantity=50,
            seller=self.customer,
        )

        # Create delivered order for customer
        self.order = Order.objects.create(
            customer=self.customer.email,
            order_code='ORD-20250101-0001',
            store_link="https://example.com/product",
            price_per_unit=Decimal("100.00"),
            quantity=2,
            customer_phone="1234567890",
            status='delivered',
            city="Test City",
            state="Test State",
            shipping_address='123 Test St'
        )

        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=2,
            price=Decimal('100.00')
        )

        # Create returns for customer
        self.return1 = Return.objects.create(
            customer=self.customer,
            order=self.order,
            return_reason='defective',
            return_description='Test return 1',
            refund_method='pickup',
            return_status='requested'
        )

        # Create return for customer2 (for permission testing)
        order2 = Order.objects.create(
            customer=self.customer2.email,
            order_code='ORD-20250101-0002',
                        store_link="https://example.com/product",
            price_per_unit=Decimal("100.00"),
            quantity=2,
            customer_phone="1234567890",
            status='delivered',
            city="Test City",
            state="Test State",
            shipping_address='456 Test Ave'
        )

        self.return2 = Return.objects.create(
            customer=self.customer2,
            order=order2,
            return_reason='wrong_item',
            return_description='Test return 2',
            refund_method='drop_off',
            return_status='approved'
        )

        # Assign roles to users
        UserRole.objects.create(user=self.customer, role=self.customer_role)
        UserRole.objects.create(user=self.customer2, role=self.customer_role)

        self.client = Client()

    def test_customer_returns_list_requires_login(self):
        """
        Test Case 6.1: Anonymous User Blocked
        Verify login required for customer returns list
        """
        url = reverse('orders:customer_returns_list')
        response = self.client.get(url)

        # Should redirect to login
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_customer_returns_list_authenticated(self):
        """
        Test Case 2.1: Customer Returns List View
        Customer can view their own returns
        """
        from django.conf import settings
        print(f"\n=== DEBUG test_customer_returns_list_authenticated ===")
        print(f"AUTHENTICATION_BACKENDS: {settings.AUTHENTICATION_BACKENDS}")
        print(f"Customer username: {self.customer.username}")
        print(f"Customer is_active: {self.customer.is_active}")
        print(f"Customer approval_status: {self.customer.approval_status}")
        print(f"Customer has_usable_password: {self.customer.has_usable_password()}")
        print(f"Customer check_password: {self.customer.check_password('testpass123')}")

        self.client.force_login(self.customer)
        print(f"Customer user: {self.customer}")
        print(f"Customer is_authenticated: {self.customer.is_authenticated}")
        print(f"Customer roles: {list(self.customer.user_roles.all())}")

        url = reverse('orders:customer_returns_list')
        print(f"URL: {url}")
        response = self.client.get(url)
        print(f"Response status: {response.status_code}")
        if response.status_code == 302:
            print(f"Redirect URL: {response.url if hasattr(response, 'url') else 'N/A'}")

        # Should succeed
        self.assertEqual(response.status_code, 200)

        # Should show customer's return
        self.assertContains(response, self.return1.return_code)

        # Should NOT show other customer's return
        self.assertNotContains(response, self.return2.return_code)

    def test_customer_return_detail_requires_login(self):
        """Verify login required for return detail"""
        url = reverse('orders:customer_return_detail', kwargs={'return_code': self.return1.return_code})
        response = self.client.get(url)

        # Should redirect to login
        self.assertEqual(response.status_code, 302)

    def test_customer_return_detail_authenticated(self):
        """
        Test Case 2.2: Customer Return Detail View
        Customer can view their return details
        """
        self.client.force_login(self.customer)
        url = reverse('orders:customer_return_detail', kwargs={'return_code': self.return1.return_code})
        response = self.client.get(url)

        # Should succeed
        self.assertEqual(response.status_code, 200)

        # Should display return details
        self.assertContains(response, self.return1.return_code)
        self.assertContains(response, self.return1.return_description)
        self.assertContains(response, self.return1.return_status)

    def test_customer_cannot_view_other_customer_return(self):
        """
        Test Case 2.3: Customer Cannot View Other's Returns
        Security test: prevent unauthorized access
        """
        self.client.force_login(self.customer)
        url = reverse('orders:customer_return_detail', kwargs={'return_code': self.return2.return_code})
        response = self.client.get(url)

        # Should deny access
        self.assertEqual(response.status_code, 403)

    def test_create_return_request_get_requires_login(self):
        """Verify login required to access create return form"""
        url = reverse('orders:create_return_request', kwargs={'order_id': self.order.id})
        response = self.client.get(url)

        # Should redirect to login
        self.assertEqual(response.status_code, 302)

    def test_create_return_request_get_form_display(self):
        """
        Test Case 2.4: Create Return Request - GET
        Customer can access return request form
        """
        # Create a new order without an existing return
        new_order = Order.objects.create(
            customer=self.customer.email,
            order_code='ORD-GET-TEST',
            store_link="https://example.com/product",
            price_per_unit=Decimal("100.00"),
            quantity=2,
            customer_phone="1234567890",
            status='delivered',
            city="Test City",
            state="Test State",
            shipping_address='123 Test St'
        )
        OrderItem.objects.create(
            order=new_order,
            product=self.product,
            quantity=2,
            price=Decimal('100.00')
        )

        self.client.force_login(self.customer)
        url = reverse('orders:create_return_request', kwargs={'order_id': new_order.id})
        response = self.client.get(url)

        # Should succeed
        self.assertEqual(response.status_code, 200)

        # Should contain form fields (check actual field names from ReturnRequestForm)
        self.assertContains(response, 'return_reason')
        self.assertContains(response, 'return_description')
        # return_method is not in ReturnRequestForm - it's in RefundProcessingForm
        # Instead check for photo/video upload fields
        self.assertContains(response, 'return_photo')
        self.assertContains(response, 'return_video')

    def test_create_return_request_post_success(self):
        """
        Test Case 2.5: Create Return Request - POST Success
        Customer can submit valid return request
        """
        # Create new order for this test (order doesn't have return yet)
        new_order = Order.objects.create(
            customer=self.customer.email,
            order_code='ORD-TEST-NEW',
                        store_link="https://example.com/product",
            price_per_unit=Decimal("100.00"),
            quantity=2,
            customer_phone="1234567890",
            status='delivered',
            city="Test City",
            state="Test State",
            shipping_address='789 New St'
        )

        new_order_item = OrderItem.objects.create(
            order=new_order,
            product=self.product,
            quantity=3,
            price=Decimal('100.00')
        )

        self.client.force_login(self.customer)
        url = reverse('orders:create_return_request', kwargs={'order_id': new_order.id})

        # Create a valid image file for photo upload
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        import io

        # Create a 1x1 pixel image
        image = Image.new('RGB', (1, 1), color='red')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        mock_photo = SimpleUploadedFile("test_photo.jpg", image_io.read(), content_type="image/jpeg")

        form_data = {
            'return_reason': 'defective',
            'return_description': 'Product does not work properly',
            'return_photo_1': mock_photo,
        }

        response = self.client.post(url, data=form_data)

        # Debug: print response status and errors
        if response.status_code != 302:
            print(f"\n=== Debug: Expected 302, got {response.status_code} ===")
            if hasattr(response, 'context') and response.context and 'form' in response.context:
                print("Form errors:", response.context['form'].errors)
            else:
                print("No form in context. Response content (first 500 chars):")
                print(response.content.decode('utf-8')[:500])

        # Should redirect after success
        self.assertEqual(response.status_code, 302)

        # Verify return created
        return_obj = Return.objects.filter(order=new_order).first()
        self.assertIsNotNone(return_obj)
        self.assertEqual(return_obj.customer, self.customer)
        self.assertEqual(return_obj.return_reason, 'defective')
        self.assertEqual(return_obj.return_status, 'requested')

    def test_create_return_request_for_non_delivered_order(self):
        """
        Test Case 2.6: Create Return Request - Invalid Order
        Prevent returns for ineligible orders
        """
        # Create pending order (not delivered)
        pending_order = Order.objects.create(
            customer=self.customer.email,
            order_code='ORD-PENDING',
                        store_link="https://example.com/product",
            price_per_unit=Decimal("100.00"),
            quantity=2,
            customer_phone="1234567890",
            status='pending',
            city="Test City",
            state="Test State",
            shipping_address='321 Pending St'
        )

        self.client.force_login(self.customer)
        url = reverse('orders:create_return_request', kwargs={'order_id': pending_order.id})
        response = self.client.get(url)

        # Should deny access or show error
        # Assuming view redirects with error message
        self.assertIn(response.status_code, [302, 403])

    def test_create_return_request_customer_cannot_create_for_other_order(self):
        """Security: Customer cannot create return for another customer's order"""
        # Create order for customer2
        other_order = Order.objects.create(
            customer=self.customer2.email,
            order_code='ORD-OTHER',
                        store_link="https://example.com/product",
            price_per_unit=Decimal("100.00"),
            quantity=2,
            customer_phone="1234567890",
            status='delivered',
            city="Test City",
            state="Test State",
            shipping_address='999 Other St'
        )

        # Login as customer1
        print(f"\n=== DEBUG test_create_return_request_customer_cannot_create_for_other_order ===")
        print(f"Customer email: {self.customer.email}")
        print(f"Customer is_active: {self.customer.is_active}")
        print(f"Customer approval_status: {self.customer.approval_status}")
        print(f"Customer has_usable_password: {self.customer.has_usable_password()}")
        print(f"Customer check_password: {self.customer.check_password('testpass123')}")

        login_success = self.client.force_login(self.customer)
        print(f"Login success: {login_success}")
        print(f"Customer2: {self.customer2}")
        print(f"Other order customer: {other_order.customer}")

        url = reverse('orders:create_return_request', kwargs={'order_id': other_order.id})
        response = self.client.get(url)
        print(f"Response status: {response.status_code}")
        if response.status_code == 302:
            print(f"Redirect location: {response.url if hasattr(response, 'url') else 'N/A'}")

        # Should deny access
        self.assertEqual(response.status_code, 403)


class AdminReturnViewTests(TestCase):
    """Test suite for admin/staff return views"""

    def create_roles(self):
        """Helper to create necessary roles"""
        self.admin_role, _ = Role.objects.get_or_create(
            name='Admin',
            defaults={'role_type': 'admin'}
        )
        self.stock_keeper_role, _ = Role.objects.get_or_create(
            name='Stock Keeper',
            defaults={'role_type': 'custom'}
        )
        self.customer_role, _ = Role.objects.get_or_create(
            name='Customer',
            defaults={'role_type': 'custom'}
        )
        self.finance_role, _ = Role.objects.get_or_create(
            name='Finance',
            defaults={'role_type': 'custom'}
        )
        # Create Manager role for this test class
        self.manager_role, _ = Role.objects.get_or_create(
            name='Manager',
            defaults={'role_type': 'custom'}
        )

    def setUp(self):
        """Set up test data"""
        # Create roles first
        self.create_roles()

        # Create admin user
        self.admin = User.objects.create_user(
            email='admin@test.com',
            password='testpass123',
            full_name='Admin',
            phone_number='1234569335',
            is_staff=True,
            is_active=True,
            approval_status='approved'
        )
        UserRole.objects.create(user=self.admin, role=self.admin_role)

        # Create manager user
        self.manager = User.objects.create_user(
            email='manager@test.com',
            password='testpass123',
            full_name='Manager',
            phone_number='1234566728',
            is_active=True,
            approval_status='approved'
        )
        UserRole.objects.create(user=self.manager, role=self.manager_role)

        # Create stock keeper user
        self.stock_keeper = User.objects.create_user(
            email='stockkeeper@test.com',
            password='testpass123',
            full_name='Stockkeeper',
            phone_number='1234563260',
            is_active=True,
            approval_status='approved'
        )
        UserRole.objects.create(user=self.stock_keeper, role=self.stock_keeper_role)

        # Create finance user
        self.finance = User.objects.create_user(
            email='finance@test.com',
            password='testpass123',
            full_name='Finance',
            phone_number='1234560106',
            is_active=True,
            approval_status='approved'
        )
        UserRole.objects.create(user=self.finance, role=self.finance_role)

        # Create customer user
        self.customer = User.objects.create_user(
            email='customer@test.com',
            password='testpass123',
            full_name='Customer',
            phone_number='1234560898',
            is_active=True,
            approval_status='approved'
        )
        UserRole.objects.create(user=self.customer, role=self.customer_role)

        # Create product
        self.product = Product.objects.create(
            name_en='Test Product',
            name_ar='Test Product',
            code='TEST-001',
            selling_price=Decimal('100.00'),
            stock_quantity=50,
            seller=self.customer,
        )

        # Create order
        self.order = Order.objects.create(
            customer=self.customer.email,
            order_code='ORD-20250101-0001',
            store_link="https://example.com/product",
            price_per_unit=Decimal("100.00"),
            quantity=2,
            customer_phone="1234567890",
            status='delivered',
            city="Test City",
            state="Test State",
            shipping_address='123 Test St'
        )

        # Create returns in various statuses
        self.pending_return = Return.objects.create(
            customer=self.customer,
            order=self.order,
            return_reason='defective',
            return_description='Pending return',
            refund_method='pickup',
            return_status='requested'
        )

        self.approved_return = Return.objects.create(
            customer=self.customer,
            order=self.order,
            return_reason='wrong_item',
            return_description='Approved return',
            refund_method='drop_off',
            return_status='approved',
            refund_amount=Decimal('150.00')
        )

        self.client = Client()

    def test_returns_dashboard_admin_access(self):
        """
        Test Case 3.1: Returns Dashboard - Admin Access
        Admin can access returns dashboard
        """
        self.client.force_login(self.admin)
        url = reverse('orders:returns_dashboard')
        response = self.client.get(url)

        # Should succeed
        self.assertEqual(response.status_code, 200)

        # Should show all returns
        self.assertContains(response, self.pending_return.return_code)
        self.assertContains(response, self.approved_return.return_code)

    def test_returns_dashboard_stock_keeper_access(self):
        """
        Test Case 3.2: Returns Dashboard - Stock Keeper Access
        Stock Keeper can access returns dashboard
        """
        self.client.force_login(self.stock_keeper)
        url = reverse('orders:returns_dashboard')
        response = self.client.get(url)

        # Should succeed
        self.assertEqual(response.status_code, 200)

    def test_returns_dashboard_customer_denied(self):
        """
        Test Case 3.3: Returns Dashboard - Customer Denied
        Regular customers cannot access admin dashboard
        """
        self.client.force_login(self.customer)
        url = reverse('orders:returns_dashboard')
        response = self.client.get(url)

        # Should deny access
        self.assertEqual(response.status_code, 403)

    def test_admin_return_detail_view(self):
        """
        Test Case 3.4: Admin Return Detail View
        Admin can view complete return details
        """
        self.client.force_login(self.admin)
        url = reverse('orders:return_detail_admin', kwargs={'return_code': self.pending_return.return_code})
        response = self.client.get(url)

        # Should succeed
        self.assertEqual(response.status_code, 200)

        # Should show return details
        self.assertContains(response, self.pending_return.return_code)
        self.assertContains(response, self.pending_return.return_description)

    def test_approve_return_get_form(self):
        """
        Test Case 3.5: Approve Return - GET Form
        Manager can access approve form
        """
        self.client.force_login(self.manager)
        url = reverse('orders:approve_return', kwargs={'return_code': self.pending_return.return_code})
        response = self.client.get(url)

        # Should succeed
        self.assertEqual(response.status_code, 200)

        # Should contain form fields
        self.assertContains(response, 'action')
        self.assertContains(response, 'refund_amount')

    def test_approve_return_post_approve(self):
        """
        Test Case 3.6: Approve Return - POST Approve
        Manager can approve return
        """
        self.client.force_login(self.manager)
        url = reverse('orders:approve_return', kwargs={'return_code': self.pending_return.return_code})

        form_data = {
            'approve': 'on',  # Checkbox value
            'refund_amount': '180.00'
        }

        response = self.client.post(url, data=form_data)

        # Should redirect after success
        self.assertEqual(response.status_code, 302)

        # Verify return updated
        self.pending_return.refresh_from_db()
        self.assertEqual(self.pending_return.return_status, 'approved')
        self.assertEqual(self.pending_return.refund_amount, Decimal('180.00'))
        self.assertEqual(self.pending_return.approved_by, self.manager)

    def test_approve_return_post_reject(self):
        """
        Test Case 3.7: Approve Return - POST Reject
        Manager can reject return
        """
        self.client.force_login(self.manager)
        url = reverse('orders:approve_return', kwargs={'return_code': self.pending_return.return_code})

        form_data = {
            'reject': 'on',  # Checkbox value
            'rejection_reason': 'Outside return window'
        }

        response = self.client.post(url, data=form_data)

        # Should redirect after success
        self.assertEqual(response.status_code, 302)

        # Verify return updated
        self.pending_return.refresh_from_db()
        self.assertEqual(self.pending_return.return_status, 'rejected')

    def test_mark_return_received(self):
        """
        Test Case 3.8: Mark Return Received
        Stock keeper can mark return as received
        """
        # Change return to in_transit status first
        self.approved_return.return_status = 'in_transit'
        self.approved_return.save()

        self.client.force_login(self.stock_keeper)
        url = reverse('orders:mark_return_received', kwargs={'return_code': self.approved_return.return_code})

        form_data = {
            'received_notes': 'Package intact, all items received'
        }

        response = self.client.post(url, data=form_data)

        # Should redirect after success
        self.assertEqual(response.status_code, 302)

        # Verify return updated
        self.approved_return.refresh_from_db()
        self.assertEqual(self.approved_return.return_status, 'received')
        self.assertEqual(self.approved_return.received_by, self.stock_keeper)

    def test_inspect_return_approve_for_refund(self):
        """
        Test Case 3.9: Inspect Return - Approve for Refund
        Stock keeper can inspect and approve items for refund
        """
        # Change return to received status first
        self.approved_return.return_status = 'received'
        self.approved_return.save()

        self.client.force_login(self.stock_keeper)
        url = reverse('orders:inspect_return', kwargs={'return_code': self.approved_return.return_code})

        form_data = {
            'approve_for_refund': 'on',  # Checkbox value
            'item_condition': 'excellent',  # Valid choice from ITEM_CONDITION_CHOICES
            'inspection_notes': 'Items in original condition',
            'can_restock': 'on',  # Checkbox value
            'restocking_fee': '0.00',
            'damage_deduction': '0.00',
            'shipping_cost_deduction': '0.00'
        }

        response = self.client.post(url, data=form_data)

        # Should redirect after success
        self.assertEqual(response.status_code, 302)

        # Verify return updated
        self.approved_return.refresh_from_db()
        self.assertEqual(self.approved_return.return_status, 'approved_for_refund')
        self.assertEqual(self.approved_return.inspector, self.stock_keeper)

    def test_inspect_return_reject_for_refund(self):
        """
        Test Case 3.10: Inspect Return - Reject for Refund
        Stock keeper can reject items during inspection
        """
        # Change return to received status first
        self.approved_return.return_status = 'received'
        self.approved_return.save()

        self.client.force_login(self.stock_keeper)
        url = reverse('orders:inspect_return', kwargs={'return_code': self.approved_return.return_code})

        form_data = {
            'reject_for_refund': 'on',  # Checkbox value
            'item_condition': 'damaged',  # Valid choice
            'inspection_notes': 'Items show signs of heavy use',
            # can_restock omitted = False
            'restocking_fee': '0.00',
            'damage_deduction': '50.00',
            'shipping_cost_deduction': '0.00'
        }

        response = self.client.post(url, data=form_data)

        # Should redirect after success
        self.assertEqual(response.status_code, 302)

        # Verify return updated
        self.approved_return.refresh_from_db()
        self.assertEqual(self.approved_return.return_status, 'inspected')
        self.assertEqual(self.approved_return.refund_status, 'cancelled')

    def test_process_refund(self):
        """
        Test Case 3.11: Process Refund
        Finance user can process refund
        """
        # Change return to approved_for_refund status and refund approved
        self.approved_return.return_status = 'approved_for_refund'
        self.approved_return.refund_status = 'approved'
        self.approved_return.save()

        self.client.force_login(self.finance)
        url = reverse('orders:process_refund', kwargs={'return_code': self.approved_return.return_code})

        form_data = {
            'refund_method': 'bank_transfer',
            'refund_reference': 'TXN-123456789',
            'refund_notes': 'Refund processed successfully'
        }

        response = self.client.post(url, data=form_data)

        # Should redirect after success
        self.assertEqual(response.status_code, 302)

        # Verify return updated
        self.approved_return.refresh_from_db()
        self.assertEqual(self.approved_return.return_status, 'refund_completed')
        self.assertEqual(self.approved_return.refund_processed_by, self.finance)
        self.assertEqual(self.approved_return.refund_method, 'bank_transfer')

    def test_stock_keeper_cannot_approve_return(self):
        """
        Test Case 6.3: Stock Keeper Cannot Approve
        Stock Keeper cannot approve/reject returns
        """
        self.client.force_login(self.stock_keeper)
        url = reverse('orders:approve_return', kwargs={'return_code': self.pending_return.return_code})
        response = self.client.get(url)

        # Should deny access
        self.assertEqual(response.status_code, 403)

    def test_finance_can_process_refunds(self):
        """
        Test Case 6.4: Finance Can Process Refunds
        Finance role can process refunds
        """
        # Set return to refund_approved with approved refund status
        self.approved_return.return_status = 'approved_for_refund'
        self.approved_return.refund_status = 'approved'
        self.approved_return.save()

        self.client.force_login(self.finance)
        url = reverse('orders:process_refund', kwargs={'return_code': self.approved_return.return_code})
        response = self.client.get(url)

        # Should succeed
        self.assertEqual(response.status_code, 200)


class ReturnAPIEndpointTests(TestCase):
    """Test suite for Return API endpoints"""

    def create_roles(self):
        """Helper to create necessary roles"""
        self.admin_role, _ = Role.objects.get_or_create(
            name='Admin',
            defaults={'role_type': 'admin'}
        )
        self.stock_keeper_role, _ = Role.objects.get_or_create(
            name='Stock Keeper',
            defaults={'role_type': 'custom'}
        )
        self.customer_role, _ = Role.objects.get_or_create(
            name='Customer',
            defaults={'role_type': 'custom'}
        )
        self.finance_role, _ = Role.objects.get_or_create(
            name='Finance',
            defaults={'role_type': 'custom'}
        )

    def setUp(self):
        """Set up test data"""
        # Create roles first
        self.create_roles()

        # Create customer user
        self.customer = User.objects.create_user(
            email='customer@test.com',
            password='testpass123',
            full_name='Customer',
            phone_number='1234560898',
            is_active=True,
            approval_status='approved'
        )
        UserRole.objects.create(user=self.customer, role=self.customer_role)

        # Create order
        self.order = Order.objects.create(
            customer=self.customer.email,
            order_code='ORD-20250101-0001',
            store_link="https://example.com/product",
            price_per_unit=Decimal("100.00"),
            quantity=2,
            customer_phone="1234567890",
            status='delivered',
            city="Test City",
            state="Test State",
            shipping_address='123 Test St'
        )

        # Create return
        self.return_obj = Return.objects.create(
            customer=self.customer,
            order=self.order,
            return_reason='defective',
            return_description='Test return',
            refund_method='pickup',
            return_status='approved',
            refund_amount=Decimal('180.00')
        )

        # Create status logs
        ReturnStatusLog.objects.create(
            return_request=self.return_obj,
            old_status='',
            new_status='requested',
            changed_by=self.customer,
            notes='Return requested'
        )
        ReturnStatusLog.objects.create(
            return_request=self.return_obj,
            old_status='requested',
            new_status='approved',
            changed_by=self.customer,
            notes='Return approved'
        )

        self.client = Client()

    def test_get_return_status_api(self):
        """
        Test Case 9.1: Get Return Status API
        Status API returns correct JSON
        """
        self.client.force_login(self.customer)
        url = reverse('orders:get_return_status', kwargs={'return_code': self.return_obj.return_code})
        response = self.client.get(url)

        # Should succeed
        self.assertEqual(response.status_code, 200)

        # Should return JSON
        self.assertEqual(response['Content-Type'], 'application/json')

        # Parse JSON
        import json
        data = json.loads(response.content)

        # Verify data
        self.assertTrue(data['success'])
        self.assertEqual(data['return_code'], self.return_obj.return_code)
        self.assertEqual(data['return_status'], 'approved')

    def test_get_return_timeline_api(self):
        """
        Test Case 9.2: Get Return Timeline API
        Timeline API returns status history
        """
        self.client.force_login(self.customer)
        url = reverse('orders:get_return_timeline', kwargs={'return_code': self.return_obj.return_code})
        response = self.client.get(url)

        # Should succeed
        self.assertEqual(response.status_code, 200)

        # Should return JSON
        self.assertEqual(response['Content-Type'], 'application/json')

        # Parse JSON
        import json
        data = json.loads(response.content)

        # Verify data
        self.assertTrue(data['success'])
        self.assertIn('timeline', data)
        self.assertEqual(len(data['timeline']), 2)  # 2 status logs created

    def test_api_requires_authentication(self):
        """Verify API endpoints require authentication"""
        url = reverse('orders:get_return_status', kwargs={'return_code': self.return_obj.return_code})
        response = self.client.get(url)

        # Should redirect to login or return 401/403
        self.assertIn(response.status_code, [302, 401, 403])


class ReturnWorkflowTests(TestCase):
    """
    End-to-end workflow tests
    Tests complete return lifecycle
    """

    def create_roles(self):
        """Helper to create necessary roles"""
        self.admin_role, _ = Role.objects.get_or_create(
            name='Admin',
            defaults={'role_type': 'admin'}
        )
        self.stock_keeper_role, _ = Role.objects.get_or_create(
            name='Stock Keeper',
            defaults={'role_type': 'custom'}
        )
        self.customer_role, _ = Role.objects.get_or_create(
            name='Customer',
            defaults={'role_type': 'custom'}
        )
        self.finance_role, _ = Role.objects.get_or_create(
            name='Finance',
            defaults={'role_type': 'custom'}
        )
        # Create Manager role for this test class
        self.manager_role, _ = Role.objects.get_or_create(
            name='Manager',
            defaults={'role_type': 'custom'}
        )

    def setUp(self):
        """Set up test data"""
        # Create roles first
        self.create_roles()

        # Create customer user
        self.customer = User.objects.create_user(
            email='customer@test.com',
            password='testpass123',
            full_name='Customer',
            phone_number='1234560898',
            is_active=True,
            approval_status='approved'
        )
        UserRole.objects.create(user=self.customer, role=self.customer_role)

        # Create manager user
        self.manager = User.objects.create_user(
            email='manager@test.com',
            password='testpass123',
            full_name='Manager',
            phone_number='1234566728',
            is_active=True,
            approval_status='approved'
        )
        UserRole.objects.create(user=self.manager, role=self.manager_role)

        # Create stock keeper user
        self.stock_keeper = User.objects.create_user(
            email='stockkeeper@test.com',
            password='testpass123',
            full_name='Stockkeeper',
            phone_number='1234563260',
            is_active=True,
            approval_status='approved'
        )
        UserRole.objects.create(user=self.stock_keeper, role=self.stock_keeper_role)

        # Create finance user
        self.finance = User.objects.create_user(
            email='finance@test.com',
            password='testpass123',
            full_name='Finance',
            phone_number='1234560106',
            is_active=True,
            approval_status='approved'
        )
        UserRole.objects.create(user=self.finance, role=self.finance_role)

        # Create product
        self.product = Product.objects.create(
            name_en='Test Product',
            name_ar='Test Product',
            code='TEST-001',
            selling_price=Decimal('100.00'),
            stock_quantity=50,
            seller=self.customer,
        )

        # Create order
        self.order = Order.objects.create(
            customer=self.customer.email,
            order_code='ORD-20250101-0001',
                        store_link="https://example.com/product",
            price_per_unit=Decimal("100.00"),
            quantity=2,
            customer_phone="1234567890",
            status='delivered',
            city="Test City",
            state="Test State",
            shipping_address='123 Test St'
        )

        self.order_item = OrderItem.objects.create(
            order=self.order,
            product=self.product,
            quantity=3,
            price=Decimal('100.00')
        )

        self.client = Client()

    def test_complete_return_workflow_success_path(self):
        """
        Test Case 7.1: Complete Return Workflow - Success Path
        Test complete return lifecycle from creation to refund
        """
        # Step 1: Customer creates return
        self.client.force_login(self.customer)
        create_url = reverse('orders:create_return_request', kwargs={'order_id': self.order.id})

        # Create a valid image file for photo upload
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        import io

        # Create a 1x1 pixel image
        image = Image.new('RGB', (1, 1), color='red')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        mock_photo = SimpleUploadedFile("test_photo.jpg", image_io.read(), content_type="image/jpeg")

        create_data = {
            'return_reason': 'defective',
            'return_description': 'Product malfunction',
            'return_photo_1': mock_photo,
        }
        response = self.client.post(create_url, data=create_data)
        self.assertEqual(response.status_code, 302)

        # Verify return created
        return_obj = Return.objects.filter(order=self.order).first()
        self.assertIsNotNone(return_obj)
        self.assertEqual(return_obj.return_status, 'requested')

        # Step 2: Manager approves
        self.client.force_login(self.manager)
        approve_url = reverse('orders:approve_return', kwargs={'return_code': return_obj.return_code})
        approve_data = {
            'approve': 'on',  # Checkbox value
            'refund_amount': '280.00'
        }
        response = self.client.post(approve_url, data=approve_data)
        self.assertEqual(response.status_code, 302)

        return_obj.refresh_from_db()
        self.assertEqual(return_obj.return_status, 'approved')

        # Step 3: Mark as in_transit (simulated)
        return_obj.return_status = 'in_transit'
        return_obj.save()

        # Step 4: Stock Keeper marks received
        self.client.force_login(self.stock_keeper)
        received_url = reverse('orders:mark_return_received', kwargs={'return_code': return_obj.return_code})
        received_data = {
            'received_notes': 'Package received'
        }
        response = self.client.post(received_url, data=received_data)
        self.assertEqual(response.status_code, 302)

        return_obj.refresh_from_db()
        self.assertEqual(return_obj.return_status, 'received')

        # Step 5: Stock Keeper inspects
        inspect_url = reverse('orders:inspect_return', kwargs={'return_code': return_obj.return_code})
        inspect_data = {
            'approve_for_refund': 'on',
            'item_condition': 'excellent',
            'inspection_notes': 'Items OK',
            'can_restock': 'on',
            'restocking_fee': '0.00',
            'damage_deduction': '0.00',
            'shipping_cost_deduction': '0.00'
        }
        response = self.client.post(inspect_url, data=inspect_data)
        self.assertEqual(response.status_code, 302)

        return_obj.refresh_from_db()
        self.assertEqual(return_obj.return_status, 'approved_for_refund')

        # Step 6: Finance processes refund
        self.client.force_login(self.finance)
        refund_url = reverse('orders:process_refund', kwargs={'return_code': return_obj.return_code})
        refund_data = {
            'refund_method': 'bank_transfer',
            'refund_reference': 'TXN-999',
            'refund_notes': 'Refund complete'
        }
        response = self.client.post(refund_url, data=refund_data)
        self.assertEqual(response.status_code, 302)

        return_obj.refresh_from_db()
        self.assertEqual(return_obj.return_status, 'refund_completed')

        # Final Verification: Check status logs
        logs = ReturnStatusLog.objects.filter(return_request=return_obj)
        # Should have logs for each status change
        self.assertGreaterEqual(logs.count(), 6)

    def test_complete_return_workflow_rejection_path(self):
        """
        Test Case 7.2: Complete Return Workflow - Rejection Path
        Test return rejection scenarios
        """
        # Step 1: Customer creates return
        self.client.force_login(self.customer)
        create_url = reverse('orders:create_return_request', kwargs={'order_id': self.order.id})

        # Create a valid image file for photo upload
        from django.core.files.uploadedfile import SimpleUploadedFile
        from PIL import Image
        import io

        # Create a 1x1 pixel image
        image = Image.new('RGB', (1, 1), color='red')
        image_io = io.BytesIO()
        image.save(image_io, format='JPEG')
        image_io.seek(0)
        mock_photo = SimpleUploadedFile("test_photo.jpg", image_io.read(), content_type="image/jpeg")

        create_data = {
            'return_reason': 'customer_regret',
            'return_description': 'No longer want the product',
            'return_photo_1': mock_photo,
        }
        response = self.client.post(create_url, data=create_data)

        return_obj = Return.objects.filter(order=self.order).first()
        self.assertEqual(return_obj.return_status, 'requested')

        # Step 2: Manager rejects
        self.client.force_login(self.manager)
        approve_url = reverse('orders:approve_return', kwargs={'return_code': return_obj.return_code})
        reject_data = {
            'reject': 'on',  # Checkbox value
            'rejection_reason': 'Change of mind not covered by policy'
        }
        response = self.client.post(approve_url, data=reject_data)

        return_obj.refresh_from_db()
        self.assertEqual(return_obj.return_status, 'rejected')

        # No further actions should be possible
        # Verify status logs
        logs = ReturnStatusLog.objects.filter(return_request=return_obj)
        self.assertGreaterEqual(logs.count(), 2)
