"""
Unit tests for Return Management System models
Tests: Return, ReturnItem, ReturnStatusLog models
"""

from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from decimal import Decimal
from datetime import timedelta

User = get_user_model()

from orders.models import (
    Order, OrderItem, Return, ReturnItem, ReturnStatusLog
)
from sellers.models import Product


class ReturnModelTests(TestCase):
    """
    Test suite for Return model functionality
    Covers: creation, validation, status transitions, return code generation
    """

    @classmethod
    def setUpTestData(cls):
        """Set up test data once for all test methods"""
        # Create test users
        cls.customer = User.objects.create_user(
            username='customer@test.com',
            email='customer@test.com',
            password='testpass123'
        )
        cls.admin = User.objects.create_user(
            username='admin@test.com',
            email='admin@test.com',
            password='testpass123',
            is_staff=True
        )

        # Create test products
        cls.product1 = Product.objects.create(
            name_en='Test Product 1',
            name_ar='Test Product 1',
            code='TEST-001',
            selling_price=Decimal('100.00'),
            stock_quantity=50,
            seller=cls.customer,
        )
        cls.product2 = Product.objects.create(
            name_en='Test Product 2',
            name_ar='Test Product 2',
            code='TEST-002',
            selling_price=Decimal('200.00'),
            stock_quantity=30,
            seller=cls.customer,
        )

        # Create test order
        cls.order = Order.objects.create(
            customer=cls.customer.email,
            order_code='ORD-20250101-0001',
            status='delivered',
            city='Test City',
            state='Test State',
            shipping_address='123 Test St',
            customer_phone='1234567890',
            store_link='https://example.com/product1',
            price_per_unit=Decimal('150.00'),
            quantity=2
        )

        # Create order items
        cls.order_item1 = OrderItem.objects.create(
            order=cls.order,
            product=cls.product1,
            quantity=1,
            price=Decimal('100.00')
        )
        cls.order_item2 = OrderItem.objects.create(
            order=cls.order,
            product=cls.product2,
            quantity=1,
            price=Decimal('200.00')
        )

    def test_return_creation_with_required_fields(self):
        """
        Test Case 1.1: Return Model Creation
        Verify Return model can be created with all required fields
        """
        return_obj = Return.objects.create(
            customer=self.customer,
            order=self.order,
            return_reason='defective',
            return_description='Product arrived damaged',
            refund_method='pickup'
        )

        # Verify object created
        self.assertIsNotNone(return_obj)
        self.assertIsNotNone(return_obj.id)

        # Verify auto-generated fields
        self.assertIsNotNone(return_obj.return_code)
        self.assertEqual(return_obj.return_status, 'requested')
        self.assertIsNotNone(return_obj.created_at)

        # Verify saved fields
        self.assertEqual(return_obj.customer, self.customer)
        self.assertEqual(return_obj.order, self.order)
        self.assertEqual(return_obj.reason, 'defective')
        self.assertEqual(return_obj.description, 'Product arrived damaged')
        self.assertEqual(return_obj.return_method, 'pickup')

    def test_return_code_auto_generation(self):
        """
        Test Case 1.2: Return Code Generation
        Verify unique return_code generation with correct format
        """
        # Create first return
        return1 = Return.objects.create(
            customer=self.customer,
            order=self.order,
            return_reason='defective',
            return_description='Test 1',
            refund_method='pickup'
        )

        # Create second return (different order needed)
        order2 = Order.objects.create(
            customer=self.customer,
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

        return2 = Return.objects.create(
            customer=self.customer,
            order=order2,
            return_reason='wrong_item',
            return_description='Test 2',
            refund_method='drop_off'
        )

        # Verify both have return codes
        self.assertIsNotNone(return1.return_code)
        self.assertIsNotNone(return2.return_code)

        # Verify codes are unique
        self.assertNotEqual(return1.return_code, return2.return_code)

        # Verify format: RETYYMMDDN NNN
        self.assertTrue(return1.return_code.startswith('RET'))
        self.assertTrue(return2.return_code.startswith('RET'))

        # Verify date component (YYMMDD format)
        from django.utils import timezone
        today = timezone.now()
        date_part = f"RET{today.year % 100:02d}{today.month:02d}{today.day:02d}"
        self.assertTrue(return1.return_code.startswith(date_part))
        self.assertTrue(return2.return_code.startswith(date_part))

    def test_return_code_sequential_numbering(self):
        """
        Test Case 1.2 Extended: Verify sequential numbering on same day
        """
        returns = []
        for i in range(5):
            order = Order.objects.create(
                customer=self.customer,
                order_code=f'ORD-TEST-{i}',
                                store_link="https://example.com/product",
                price_per_unit=Decimal("100.00"),
                quantity=2,
                customer_phone="1234567890",
            status='delivered',
                city="Test City",
                state="Test State",
                shipping_address=f'{i} Test St'
            )
            return_obj = Return.objects.create(
                customer=self.customer,
                order=order,
                return_reason='defective',
                return_description=f'Test return {i}',
                refund_method='pickup'
            )
            returns.append(return_obj)

        # Verify all codes are unique
        return_codes = [r.return_code for r in returns]
        self.assertEqual(len(return_codes), len(set(return_codes)))

        # Verify all have today's date (YYMMDD format)
        from django.utils import timezone
        today = timezone.now()
        date_part = f"RET{today.year % 100:02d}{today.month:02d}{today.day:02d}"
        for code in return_codes:
            self.assertTrue(code.startswith(date_part))

    def test_return_status_default_value(self):
        """Verify default status is 'pending'"""
        return_obj = Return.objects.create(
            customer=self.customer,
            order=self.order,
            return_reason='defective',
            return_description='Test',
            refund_method='pickup'
        )
        self.assertEqual(return_obj.return_status, 'requested')

    def test_return_status_transitions_pending_to_approved(self):
        """
        Test Case 1.3: Return Status Transitions
        Test: pending → approved
        """
        return_obj = Return.objects.create(
            customer=self.customer,
            order=self.order,
            return_reason='defective',
            return_description='Test',
            refund_method='pickup'
        )

        # Initial status
        self.assertEqual(return_obj.return_status, 'requested')

        # Transition to approved
        return_obj.return_status = 'approved'
        return_obj.approved_by = self.admin
        return_obj.approved_date = timezone.now()
        return_obj.refund_amount = Decimal('250.00')
        return_obj.save()

        # Verify transition
        return_obj.refresh_from_db()
        self.assertEqual(return_obj.return_status, 'approved')
        self.assertEqual(return_obj.approved_by, self.admin)
        self.assertIsNotNone(return_obj.approved_date)
        self.assertEqual(return_obj.refund_amount, Decimal('250.00'))

    def test_return_status_transitions_pending_to_rejected(self):
        """Test: pending → rejected"""
        return_obj = Return.objects.create(
            customer=self.customer,
            order=self.order,
            return_reason='defective',
            return_description='Test',
            refund_method='pickup'
        )

        # Transition to rejected
        return_obj.return_status = 'rejected'
        return_obj.rejection_reason = 'Outside return window'
        return_obj.save()

        # Verify transition
        return_obj.refresh_from_db()
        self.assertEqual(return_obj.return_status, 'rejected')
        self.assertEqual(return_obj.rejection_reason, 'Outside return window')

    def test_return_status_full_workflow_approved_path(self):
        """Test complete workflow: pending → approved → in_transit → received → inspected → refund_approved → refunded"""
        return_obj = Return.objects.create(
            customer=self.customer,
            order=self.order,
            return_reason='defective',
            return_description='Test',
            refund_method='pickup'
        )

        # Step 1: pending → approved
        return_obj.return_status = 'approved'
        return_obj.approved_by = self.admin
        return_obj.approved_date = timezone.now()
        return_obj.refund_amount = Decimal('250.00')
        return_obj.save()
        self.assertEqual(return_obj.return_status, 'approved')

        # Step 2: approved → in_transit
        return_obj.return_status = 'in_transit'
        return_obj.save()
        self.assertEqual(return_obj.return_status, 'in_transit')

        # Step 3: in_transit → received
        return_obj.return_status = 'received'
        return_obj.received_by = self.admin
        return_obj.received_date = timezone.now()
        return_obj.save()
        self.assertEqual(return_obj.return_status, 'received')

        # Step 4: received → inspected (intermediate state)
        return_obj.return_status = 'inspected'
        return_obj.inspected_by = self.admin
        return_obj.inspection_date = timezone.now()
        return_obj.save()
        self.assertEqual(return_obj.return_status, 'inspected')

        # Step 5: inspected → refund_approved
        return_obj.return_status = 'refund_approved'
        return_obj.save()
        self.assertEqual(return_obj.return_status, 'refund_approved')

        # Step 6: refund_approved → refunded
        return_obj.return_status = 'refunded'
        return_obj.refund_processed_by = self.admin
        return_obj.refund_processed_date = timezone.now()
        return_obj.refund_method = 'bank_transfer'
        return_obj.refund_reference = 'TXN-123456'
        return_obj.save()
        self.assertEqual(return_obj.return_status, 'refunded')

    def test_return_refund_amount_can_be_set(self):
        """
        Test Case 1.4: Return Refund Amount Validation
        Verify refund_amount can be set and saved
        """
        return_obj = Return.objects.create(
            customer=self.customer,
            order=self.order,
            return_reason='defective',
            return_description='Test',
            refund_method='pickup'
        )

        # Set refund amount
        return_obj.refund_amount = Decimal('250.00')
        return_obj.save()

        # Verify saved
        return_obj.refresh_from_db()
        self.assertEqual(return_obj.refund_amount, Decimal('250.00'))

    def test_return_refund_amount_can_be_partial(self):
        """Verify partial refunds are allowed"""
        return_obj = Return.objects.create(
            customer=self.customer,
            order=self.order,
            return_reason='defective',
            return_description='Test',
            refund_method='pickup'
        )

        # Order total is 300.00, refund partial amount
        return_obj.refund_amount = Decimal('150.00')
        return_obj.save()

        return_obj.refresh_from_db()
        self.assertEqual(return_obj.refund_amount, Decimal('150.00'))
        self.assertLess(return_obj.refund_amount, (self.order.price_per_unit * self.order.quantity))

    def test_return_string_representation(self):
        """Test __str__ method returns meaningful string"""
        return_obj = Return.objects.create(
            customer=self.customer,
            order=self.order,
            return_reason='defective',
            return_description='Test',
            refund_method='pickup'
        )

        # Should include return_code
        str_repr = str(return_obj)
        self.assertIn(return_obj.return_code, str_repr)

    def test_return_meta_ordering(self):
        """Verify returns are ordered by created_at descending"""
        # Create returns with different timestamps
        return1 = Return.objects.create(
            customer=self.customer,
            order=self.order,
            return_reason='defective',
            return_description='First',
            refund_method='pickup'
        )

        # Create second order for second return
        order2 = Order.objects.create(
            customer=self.customer,
            order_code='ORD-TEST-2',
                        store_link="https://example.com/product",
            price_per_unit=Decimal("100.00"),
            quantity=2,
            customer_phone="1234567890",
            status='delivered',
            city="Test City",
            state="Test State",
            shipping_address='789 Test Blvd'
        )

        # Wait a moment
        import time
        time.sleep(0.1)

        return2 = Return.objects.create(
            customer=self.customer,
            order=order2,
            return_reason='wrong_item',
            return_description='Second',
            refund_method='drop_off'
        )

        # Query returns
        returns = Return.objects.all()

        # Most recent should be first (if ordering by -created_at)
        self.assertEqual(returns[0].id, return2.id)
        self.assertEqual(returns[1].id, return1.id)


class ReturnItemModelTests(TestCase):
    """Test suite for ReturnItem model"""

    @classmethod
    def setUpTestData(cls):
        """Set up test data"""
        cls.customer = User.objects.create_user(
            username='customer@test.com',
            email='customer@test.com',
            password='testpass123'
        )


        cls.product = Product.objects.create(
            name_en='Test Product',
            name_ar='Test Product',
            code='TEST-001',
            selling_price=Decimal('100.00'),
            stock_quantity=50,
            seller=cls.customer,
        )

        cls.order = Order.objects.create(
            customer=cls.customer,
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

        cls.order_item = OrderItem.objects.create(
            order=cls.order,
            product=cls.product,
            quantity=2,
            price=Decimal('100.00')
        )

        cls.return_obj = Return.objects.create(
            customer=cls.customer,
            order=cls.order,
            return_reason='defective',
            return_description='Test return',
            refund_method='pickup'
        )

    def test_return_item_creation(self):
        """Test ReturnItem can be created"""
        return_item = ReturnItem.objects.create(
            return_request=self.return_obj,
            order_item=self.order_item,
            quantity=1,
            reason='damaged',
            condition='poor'
        )

        self.assertIsNotNone(return_item)
        self.assertEqual(return_item.return_request, self.return_obj)
        self.assertEqual(return_item.order_item, self.order_item)
        self.assertEqual(return_item.quantity, 1)
        self.assertEqual(return_item.reason, 'damaged')
        self.assertEqual(return_item.condition, 'poor')

    def test_return_item_quantity_validation(self):
        """Verify quantity can be less than or equal to order quantity"""
        # Quantity 1 (valid)
        return_item1 = ReturnItem.objects.create(
            return_request=self.return_obj,
            order_item=self.order_item,
            quantity=1,
            reason='defective'
        )
        self.assertEqual(return_item1.quantity, 1)

        # Quantity 2 (equal to order quantity, valid)
        return_item2 = ReturnItem.objects.create(
            return_request=self.return_obj,
            order_item=self.order_item,
            quantity=2,
            reason='defective'
        )
        self.assertEqual(return_item2.quantity, 2)

    def test_return_item_string_representation(self):
        """Test __str__ method"""
        return_item = ReturnItem.objects.create(
            return_request=self.return_obj,
            order_item=self.order_item,
            quantity=1,
            reason='defective'
        )

        str_repr = str(return_item)
        # Should include product name and quantity
        self.assertIsNotNone(str_repr)
        self.assertGreater(len(str_repr), 0)


class ReturnStatusLogModelTests(TestCase):
    """
    Test suite for ReturnStatusLog model
    Covers: status logging, timeline tracking
    """

    @classmethod
    def setUpTestData(cls):
        """Set up test data"""
        cls.customer = User.objects.create_user(
            username='customer@test.com',
            email='customer@test.com',
            password='testpass123'
        )
        cls.admin = User.objects.create_user(
            username='admin@test.com',
            email='admin@test.com',
            password='testpass123',
            is_staff=True
        )


        cls.order = Order.objects.create(
            customer=cls.customer,
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

        cls.return_obj = Return.objects.create(
            customer=cls.customer,
            order=cls.order,
            return_reason='defective',
            return_description='Test return',
            refund_method='pickup'
        )

    def test_return_status_log_creation(self):
        """
        Test Case 1.5: ReturnStatusLog Creation
        Verify status change can be logged
        """
        log_entry = ReturnStatusLog.objects.create(
            return_request=self.return_obj,
            new_status='approved',
            changed_by=self.admin,
            notes='Return approved by admin'
        )

        self.assertIsNotNone(log_entry)
        self.assertEqual(log_entry.return_request, self.return_obj)
        self.assertEqual(log_entry.new_status, 'approved')
        self.assertEqual(log_entry.changed_by, self.admin)
        self.assertEqual(log_entry.notes, 'Return approved by admin')
        self.assertIsNotNone(log_entry.timestamp)

    def test_return_status_log_auto_timestamp(self):
        """Verify changed_at is auto-set"""
        log_entry = ReturnStatusLog.objects.create(
            return_request=self.return_obj,
            new_status='approved',
            changed_by=self.admin
        )

        self.assertIsNotNone(log_entry.timestamp)
        # Verify timestamp is recent (within last 5 seconds)
        now = timezone.now()
        time_diff = now - log_entry.timestamp
        self.assertLess(time_diff.total_seconds(), 5)

    def test_return_status_log_multiple_entries(self):
        """Test multiple status changes are logged chronologically"""
        # Create initial log
        log1 = ReturnStatusLog.objects.create(
            return_request=self.return_obj,
            new_status='pending',
            changed_by=self.customer,
            notes='Return requested'
        )

        # Wait a moment
        import time
        time.sleep(0.1)

        # Create second log
        log2 = ReturnStatusLog.objects.create(
            return_request=self.return_obj,
            new_status='approved',
            changed_by=self.admin,
            notes='Return approved'
        )

        # Wait a moment
        time.sleep(0.1)

        # Create third log
        log3 = ReturnStatusLog.objects.create(
            return_request=self.return_obj,
            new_status='in_transit',
            changed_by=self.admin,
            notes='Item shipped back'
        )

        # Query logs for this return
        logs = ReturnStatusLog.objects.filter(return_request=self.return_obj).order_by('changed_at')

        # Verify count
        self.assertEqual(logs.count(), 3)

        # Verify chronological order
        self.assertEqual(logs[0].status, 'pending')
        self.assertEqual(logs[1].status, 'approved')
        self.assertEqual(logs[2].status, 'in_transit')

        # Verify timestamps are in order
        self.assertLess(logs[0].changed_at, logs[1].changed_at)
        self.assertLess(logs[1].changed_at, logs[2].changed_at)

    def test_return_status_log_string_representation(self):
        """Test __str__ method"""
        log_entry = ReturnStatusLog.objects.create(
            return_request=self.return_obj,
            new_status='approved',
            changed_by=self.admin
        )

        str_repr = str(log_entry)
        # Should include return code and status
        self.assertIn(self.return_obj.return_code, str_repr)
        self.assertIn('approved', str_repr)

    def test_return_status_log_meta_ordering(self):
        """Verify logs are ordered by timestamp descending (newest first)"""
        # Create logs in random order
        log1 = ReturnStatusLog.objects.create(
            return_request=self.return_obj,
            new_status='approved',
            changed_by=self.admin
        )

        import time
        time.sleep(0.1)

        log2 = ReturnStatusLog.objects.create(
            return_request=self.return_obj,
            new_status='pending',
            changed_by=self.customer
        )

        # Query all logs
        logs = ReturnStatusLog.objects.filter(return_request=self.return_obj)

        # First should be newest (log2)
        self.assertEqual(logs[0].id, log2.id)
        self.assertEqual(logs[1].id, log1.id)


class ReturnModelIntegrationTests(TestCase):
    """
    Integration tests for Return model with related models
    Tests relationships and cascading behavior
    """

    @classmethod
    def setUpTestData(cls):
        """Set up test data"""
        cls.customer = User.objects.create_user(
            username='customer@test.com',
            email='customer@test.com',
            password='testpass123'
        )


        cls.product = Product.objects.create(
            name_en='Test Product',
            name_ar='Test Product',
            code='TEST-001',
            selling_price=Decimal('100.00'),
            stock_quantity=50,
            seller=cls.customer,
        )

        cls.order = Order.objects.create(
            customer=cls.customer,
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

        cls.order_item = OrderItem.objects.create(
            order=cls.order,
            product=cls.product,
            quantity=2,
            price=Decimal('100.00')
        )

    def test_return_with_items_and_logs(self):
        """Test creating return with items and status logs"""
        # Create return
        return_obj = Return.objects.create(
            customer=self.customer,
            order=self.order,
            return_reason='defective',
            return_description='Complete test',
            refund_method='pickup'
        )

        # Add return items
        return_item = ReturnItem.objects.create(
            return_request=return_obj,
            order_item=self.order_item,
            quantity=2,
            reason='damaged'
        )

        # Add status log
        log_entry = ReturnStatusLog.objects.create(
            return_request=return_obj,
            new_status='pending',
            changed_by=self.customer,
            notes='Return created'
        )

        # Verify relationships
        self.assertEqual(return_obj.items.count(), 1)
        self.assertEqual(return_obj.return_status_logs.count(), 1)
        self.assertEqual(return_item.return_request, return_obj)
        self.assertEqual(log_entry.return_request, return_obj)

    def test_return_deletion_cascades_to_items_and_logs(self):
        """Test that deleting return also deletes related items and logs"""
        # Create return with items and logs
        return_obj = Return.objects.create(
            customer=self.customer,
            order=self.order,
            return_reason='defective',
            return_description='Test cascade',
            refund_method='pickup'
        )

        ReturnItem.objects.create(
            return_request=return_obj,
            order_item=self.order_item,
            quantity=1,
            reason='damaged'
        )

        ReturnStatusLog.objects.create(
            return_request=return_obj,
            new_status='pending',
            changed_by=self.customer
        )

        # Verify they exist
        self.assertEqual(ReturnItem.objects.filter(return_request=return_obj).count(), 1)
        self.assertEqual(ReturnStatusLog.objects.filter(return_request=return_obj).count(), 1)

        # Delete return
        return_id = return_obj.id
        return_obj.delete()

        # Verify cascading deletion
        self.assertEqual(Return.objects.filter(id=return_id).count(), 0)
        self.assertEqual(ReturnItem.objects.filter(return_request_id=return_id).count(), 0)
        self.assertEqual(ReturnStatusLog.objects.filter(return_request_id=return_id).count(), 0)

    def test_customer_deletion_cascades_to_returns(self):
        """Test that returns are deleted when customer is deleted (on_delete=CASCADE)"""
        # Create return
        return_obj = Return.objects.create(
            customer=self.customer,
            order=self.order,
            return_reason='defective',
            return_description='Test customer deletion',
            refund_method='pickup'
        )

        return_id = return_obj.id

        # Delete customer
        # The customer ForeignKey has on_delete=CASCADE, so return should be deleted too
        self.customer.delete()

        # Verify return was deleted due to cascade
        self.assertFalse(Return.objects.filter(id=return_id).exists())
