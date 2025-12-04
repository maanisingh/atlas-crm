# Return Management System - Comprehensive Test Plan

## Document Information
- **Version:** 1.0
- **Date:** 2025-12-02
- **Status:** Ready for Testing
- **Test Environment:** Django 5.2.8 + Python 3.x

---

## 1. Test Scope Overview

This test plan covers end-to-end testing of the Return Management System implemented across:
- **Models:** Return, ReturnItem, ReturnStatusLog (orders/models.py)
- **Views:** 11 view functions (orders/return_views.py)
- **Forms:** 4 form classes (orders/return_forms.py)
- **URLs:** 14 URL patterns (orders/return_urls.py)
- **Templates:** 9 HTML templates (orders/templates/orders/returns/)
- **Admin:** 3 admin classes (orders/admin.py)

---

## 2. Test Categories

### 2.1 Unit Tests (Model Layer)
### 2.2 Integration Tests (View Layer)
### 2.3 Form Validation Tests
### 2.4 URL Routing Tests
### 2.5 Template Rendering Tests
### 2.6 Permission & Security Tests
### 2.7 Workflow Tests (End-to-End)
### 2.8 Admin Interface Tests
### 2.9 API Endpoint Tests
### 2.10 Edge Case & Error Handling Tests

---

## 3. Detailed Test Cases

## 3.1 UNIT TESTS - Return Model

### Test Case 1.1: Return Model Creation
**ID:** UT-RET-001
**Priority:** Critical
**Objective:** Verify Return model can be created with all required fields

**Test Data:**
```python
{
    'customer': <User object>,
    'order': <Order object>,
    'reason': 'defective',
    'description': 'Product arrived damaged',
    'return_method': 'pickup'
}
```

**Expected Results:**
- ✅ Return object created successfully
- ✅ return_code auto-generated (format: RET-YYYYMMDD-XXXX)
- ✅ status defaults to 'pending'
- ✅ request_date auto-set to current timestamp
- ✅ All fields saved correctly

---

### Test Case 1.2: Return Code Generation
**ID:** UT-RET-002
**Priority:** Critical
**Objective:** Verify unique return_code generation

**Test Steps:**
1. Create 5 returns on same day
2. Verify each has unique return_code
3. Check format: RET-YYYYMMDD-0001, RET-YYYYMMDD-0002, etc.

**Expected Results:**
- ✅ All return codes are unique
- ✅ Format follows pattern: RET-YYYYMMDD-XXXX
- ✅ Sequential numbering works correctly

---

### Test Case 1.3: Return Status Transitions
**ID:** UT-RET-003
**Priority:** High
**Objective:** Verify status can transition through workflow

**Valid Transitions:**
- pending → approved
- pending → rejected
- approved → in_transit
- in_transit → received
- received → inspected
- inspected → refund_approved
- inspected → refund_rejected
- refund_approved → refunded
- refund_approved → exchanged

**Expected Results:**
- ✅ All valid transitions work
- ✅ Invalid transitions prevented (if validation implemented)

---

### Test Case 1.4: Return Refund Amount Validation
**ID:** UT-RET-004
**Priority:** High
**Objective:** Verify refund_amount cannot exceed original order total

**Test Steps:**
1. Create order with total = 1000.00
2. Create return with refund_amount = 1200.00
3. Attempt to save

**Expected Results:**
- ✅ Validation error raised (if implemented)
- ❌ OR: Save succeeds but requires admin override

---

### Test Case 1.5: ReturnStatusLog Creation
**ID:** UT-RET-005
**Priority:** Medium
**Objective:** Verify status change logging

**Test Steps:**
1. Create return (status: pending)
2. Change status to approved
3. Change status to in_transit
4. Query ReturnStatusLog for this return

**Expected Results:**
- ✅ 3 log entries created
- ✅ Each has correct: status, changed_at, changed_by
- ✅ Chronological order maintained

---

## 3.2 INTEGRATION TESTS - Customer Views

### Test Case 2.1: Customer Returns List View
**ID:** IT-CUST-001
**Priority:** Critical
**Objective:** Customer can view their own returns

**Prerequisites:**
- Customer user logged in
- 3 returns exist for this customer
- 2 returns exist for different customer

**URL:** `/my-returns/`
**View:** `customer_returns_list`

**Expected Results:**
- ✅ Status code: 200
- ✅ Shows 3 returns (customer's own)
- ❌ Does NOT show other customer's returns
- ✅ Statistics displayed (total, pending, approved, etc.)
- ✅ Filter links work (pending, approved, refunded)

---

### Test Case 2.2: Customer Return Detail View
**ID:** IT-CUST-002
**Priority:** Critical
**Objective:** Customer can view their return details

**Prerequisites:**
- Customer logged in
- Return exists with return_code = RET-20250101-0001
- Return belongs to this customer

**URL:** `/my-returns/RET-20250101-0001/`
**View:** `customer_return_detail`

**Expected Results:**
- ✅ Status code: 200
- ✅ Displays return details (code, status, reason, description)
- ✅ Shows status timeline with all changes
- ✅ Displays items to be returned
- ✅ Shows refund information (if applicable)

---

### Test Case 2.3: Customer Cannot View Other's Returns
**ID:** IT-CUST-003
**Priority:** Critical (Security)
**Objective:** Prevent unauthorized access to returns

**Prerequisites:**
- Customer A logged in
- Return RET-20250101-0001 belongs to Customer B

**URL:** `/my-returns/RET-20250101-0001/`

**Expected Results:**
- ✅ Status code: 403 Forbidden
- ❌ OR redirect to own returns list with error message

---

### Test Case 2.4: Create Return Request - GET
**ID:** IT-CUST-004
**Priority:** High
**Objective:** Customer can access return request form

**Prerequisites:**
- Customer logged in
- Order #123 exists, status='delivered', belongs to customer

**URL:** `/order/123/return/`
**Method:** GET

**Expected Results:**
- ✅ Status code: 200
- ✅ Form displayed with reason dropdown
- ✅ Form shows order items for selection
- ✅ Return method choices shown (pickup/drop-off)

---

### Test Case 2.5: Create Return Request - POST Success
**ID:** IT-CUST-005
**Priority:** Critical
**Objective:** Customer can submit valid return request

**Prerequisites:**
- Customer logged in
- Order #123 delivered

**URL:** `/order/123/return/`
**Method:** POST
**Data:**
```python
{
    'reason': 'defective',
    'description': 'Screen cracked on arrival',
    'return_method': 'pickup',
    'items': [item1_id, item2_id]
}
```

**Expected Results:**
- ✅ Return created in database
- ✅ Status = 'pending'
- ✅ return_code generated
- ✅ ReturnStatusLog entry created
- ✅ Redirect to customer_return_detail with success message
- ✅ Order status unchanged (still 'delivered')

---

### Test Case 2.6: Create Return Request - Invalid Order
**ID:** IT-CUST-006
**Priority:** High
**Objective:** Prevent returns for ineligible orders

**Prerequisites:**
- Customer logged in
- Order #123 status='pending' (not delivered)

**URL:** `/order/123/return/`

**Expected Results:**
- ✅ Status code: 403 or redirect with error
- ✅ Error message: "Order must be delivered to request return"
- ❌ No return created

---

## 3.3 INTEGRATION TESTS - Admin Views

### Test Case 3.1: Returns Dashboard - Admin Access
**ID:** IT-ADM-001
**Priority:** Critical
**Objective:** Admin can access returns dashboard

**Prerequisites:**
- Admin user logged in
- 10 returns exist in various statuses

**URL:** `/admin/returns/`
**View:** `returns_dashboard`

**Expected Results:**
- ✅ Status code: 200
- ✅ Shows all 10 returns (from all customers)
- ✅ Statistics displayed (total value, pending count, etc.)
- ✅ Filter buttons work (pending, approved, rejected, etc.)
- ✅ Search functionality present

---

### Test Case 3.2: Returns Dashboard - Stock Keeper Access
**ID:** IT-ADM-002
**Priority:** High
**Objective:** Stock Keeper can access returns dashboard

**Prerequisites:**
- Stock Keeper user logged in

**URL:** `/admin/returns/`

**Expected Results:**
- ✅ Status code: 200
- ✅ Dashboard accessible
- ✅ All returns visible

---

### Test Case 3.3: Returns Dashboard - Customer Denied
**ID:** IT-ADM-003
**Priority:** Critical (Security)
**Objective:** Regular customers cannot access admin dashboard

**Prerequisites:**
- Regular customer logged in

**URL:** `/admin/returns/`

**Expected Results:**
- ✅ Status code: 403 Forbidden
- ❌ OR redirect to login with error message

---

### Test Case 3.4: Admin Return Detail View
**ID:** IT-ADM-004
**Priority:** High
**Objective:** Admin can view complete return details

**Prerequisites:**
- Admin logged in
- Return RET-20250101-0001 exists

**URL:** `/admin/returns/RET-20250101-0001/`
**View:** `return_detail_admin`

**Expected Results:**
- ✅ Status code: 200
- ✅ Shows all return details
- ✅ Customer information displayed
- ✅ Order information displayed
- ✅ Status timeline visible
- ✅ Action buttons shown based on current status

---

### Test Case 3.5: Approve Return - GET Form
**ID:** IT-ADM-005
**Priority:** High
**Objective:** Manager can access approve form

**Prerequisites:**
- Manager logged in
- Return RET-20250101-0001 exists, status='pending'

**URL:** `/admin/returns/RET-20250101-0001/approve/`
**Method:** GET

**Expected Results:**
- ✅ Status code: 200
- ✅ Form displayed with approve/reject options
- ✅ Refund amount field present
- ✅ Return details shown for reference

---

### Test Case 3.6: Approve Return - POST Approve
**ID:** IT-ADM-006
**Priority:** Critical
**Objective:** Manager can approve return

**Prerequisites:**
- Manager logged in
- Return status='pending'

**URL:** `/admin/returns/RET-20250101-0001/approve/`
**Method:** POST
**Data:**
```python
{
    'action': 'approve',
    'refund_amount': 950.00,
    'admin_notes': 'Valid return request'
}
```

**Expected Results:**
- ✅ Return.status changed to 'approved'
- ✅ Return.approved_date set to current timestamp
- ✅ Return.approved_by set to manager
- ✅ Return.refund_amount set to 950.00
- ✅ ReturnStatusLog entry created
- ✅ Redirect with success message

---

### Test Case 3.7: Approve Return - POST Reject
**ID:** IT-ADM-007
**Priority:** Critical
**Objective:** Manager can reject return

**Prerequisites:**
- Manager logged in
- Return status='pending'

**URL:** `/admin/returns/RET-20250101-0001/approve/`
**Method:** POST
**Data:**
```python
{
    'action': 'reject',
    'admin_notes': 'Outside return window'
}
```

**Expected Results:**
- ✅ Return.status changed to 'rejected'
- ✅ Return.rejection_reason saved
- ✅ ReturnStatusLog entry created
- ✅ Redirect with notification message

---

### Test Case 3.8: Mark Return Received
**ID:** IT-ADM-008
**Priority:** High
**Objective:** Stock keeper can mark return as received

**Prerequisites:**
- Stock Keeper logged in
- Return status='in_transit'

**URL:** `/admin/returns/RET-20250101-0001/mark-received/`
**Method:** POST
**Data:**
```python
{
    'received_notes': 'Package intact, 2 items received'
}
```

**Expected Results:**
- ✅ Return.status changed to 'received'
- ✅ Return.received_date set
- ✅ Return.received_by set to stock keeper
- ✅ ReturnStatusLog entry created
- ✅ Redirect with success message

---

### Test Case 3.9: Inspect Return - Approve for Refund
**ID:** IT-ADM-009
**Priority:** Critical
**Objective:** Stock keeper can inspect and approve items for refund

**Prerequisites:**
- Stock Keeper logged in
- Return status='received'

**URL:** `/admin/returns/RET-20250101-0001/inspect/`
**Method:** POST
**Data:**
```python
{
    'inspection_result': 'approve',
    'inspection_notes': 'Items in original condition',
    'item_conditions': {
        'item1': 'good',
        'item2': 'good'
    }
}
```

**Expected Results:**
- ✅ Return.status changed to 'refund_approved'
- ✅ Return.inspection_date set
- ✅ Return.inspected_by set
- ✅ Return.inspection_notes saved
- ✅ ReturnStatusLog entry created
- ✅ Redirect with success message

---

### Test Case 3.10: Inspect Return - Reject for Refund
**ID:** IT-ADM-010
**Priority:** High
**Objective:** Stock keeper can reject items during inspection

**Prerequisites:**
- Stock Keeper logged in
- Return status='received'

**URL:** `/admin/returns/RET-20250101-0001/inspect/`
**Method:** POST
**Data:**
```python
{
    'inspection_result': 'reject',
    'inspection_notes': 'Items show signs of use',
    'item_conditions': {
        'item1': 'damaged',
        'item2': 'used'
    }
}
```

**Expected Results:**
- ✅ Return.status changed to 'refund_rejected'
- ✅ Inspection details saved
- ✅ ReturnStatusLog entry created
- ✅ Customer notified (if notification system exists)

---

### Test Case 3.11: Process Refund
**ID:** IT-ADM-011
**Priority:** Critical
**Objective:** Finance user can process refund

**Prerequisites:**
- Finance user logged in
- Return status='refund_approved'

**URL:** `/admin/returns/RET-20250101-0001/process-refund/`
**Method:** POST
**Data:**
```python
{
    'refund_method': 'bank_transfer',
    'refund_reference': 'TXN-123456789',
    'refund_notes': 'Refund processed via bank transfer'
}
```

**Expected Results:**
- ✅ Return.status changed to 'refunded'
- ✅ Return.refund_processed_date set
- ✅ Return.refund_processed_by set
- ✅ Return.refund_method saved
- ✅ Return.refund_reference saved
- ✅ ReturnStatusLog entry created
- ✅ Customer notified (if notification system exists)

---

## 3.4 FORM VALIDATION TESTS

### Test Case 4.1: CreateReturnForm - Valid Data
**ID:** FT-FORM-001
**Priority:** High
**Objective:** Form accepts valid return request data

**Form Data:**
```python
{
    'reason': 'defective',
    'description': 'Product does not work',
    'return_method': 'pickup',
    'items': [1, 2]
}
```

**Expected Results:**
- ✅ form.is_valid() returns True
- ✅ No validation errors

---

### Test Case 4.2: CreateReturnForm - Missing Required Fields
**ID:** FT-FORM-002
**Priority:** High
**Objective:** Form rejects missing required fields

**Form Data:**
```python
{
    'reason': 'defective',
    # description missing
    # return_method missing
}
```

**Expected Results:**
- ❌ form.is_valid() returns False
- ✅ Errors for 'description' field
- ✅ Errors for 'return_method' field

---

### Test Case 4.3: ApproveReturnForm - Refund Amount Validation
**ID:** FT-FORM-003
**Priority:** High
**Objective:** Form validates refund amount is positive

**Form Data:**
```python
{
    'action': 'approve',
    'refund_amount': -100.00,
    'admin_notes': 'Test'
}
```

**Expected Results:**
- ❌ form.is_valid() returns False
- ✅ Error: "Refund amount must be positive"

---

### Test Case 4.4: InspectReturnForm - Item Conditions Required
**ID:** FT-FORM-004
**Priority:** Medium
**Objective:** Form requires condition for each item

**Form Data:**
```python
{
    'inspection_result': 'approve',
    'inspection_notes': 'Items OK',
    # item_conditions missing
}
```

**Expected Results:**
- ❌ form.is_valid() returns False
- ✅ Error: "Item conditions required"

---

## 3.5 URL ROUTING TESTS

### Test Case 5.1: Customer URL - My Returns List
**ID:** UT-URL-001
**Priority:** Critical
**Objective:** Verify URL pattern resolves correctly

**URL:** `/my-returns/`
**Expected View:** `customer_returns_list`
**URL Name:** `orders:customer_returns_list`

**Test Steps:**
```python
from django.urls import reverse, resolve
url = reverse('orders:customer_returns_list')
assert url == '/my-returns/'
view = resolve('/my-returns/')
assert view.func.__name__ == 'customer_returns_list'
```

---

### Test Case 5.2: Customer URL - Return Detail
**ID:** UT-URL-002
**Priority:** Critical
**Objective:** Verify return_code parameter routing

**URL:** `/my-returns/RET-20250101-0001/`
**Expected View:** `customer_return_detail`
**URL Name:** `orders:customer_return_detail`

**Test Steps:**
```python
url = reverse('orders:customer_return_detail', kwargs={'return_code': 'RET-20250101-0001'})
assert url == '/my-returns/RET-20250101-0001/'
```

---

### Test Case 5.3: Admin URL - Returns Dashboard
**ID:** UT-URL-003
**Priority:** High
**Objective:** Verify admin dashboard URL and alias

**URL:** `/admin/returns/`
**Expected View:** `returns_dashboard`
**URL Names:** `orders:returns_dashboard`, `orders:admin_returns_dashboard`

**Test Steps:**
```python
url1 = reverse('orders:returns_dashboard')
url2 = reverse('orders:admin_returns_dashboard')
assert url1 == url2 == '/admin/returns/'
```

---

### Test Case 5.4: API URL - Return Status
**ID:** UT-URL-004
**Priority:** Medium
**Objective:** Verify API endpoint routing

**URL:** `/api/returns/RET-20250101-0001/status/`
**Expected View:** `get_return_status`
**URL Name:** `orders:get_return_status`

**Test Steps:**
```python
url = reverse('orders:get_return_status', kwargs={'return_code': 'RET-20250101-0001'})
assert url == '/api/returns/RET-20250101-0001/status/'
```

---

## 3.6 PERMISSION & SECURITY TESTS

### Test Case 6.1: Anonymous User Blocked
**ID:** ST-SEC-001
**Priority:** Critical
**Objective:** All return views require authentication

**Test Steps:**
1. Logout (or use anonymous client)
2. Attempt to access `/my-returns/`

**Expected Results:**
- ✅ Redirect to login page
- ✅ Status code: 302
- ✅ Next parameter set correctly

---

### Test Case 6.2: Customer Role Restrictions
**ID:** ST-SEC-002
**Priority:** Critical
**Objective:** Customers cannot access admin views

**Test Steps:**
1. Login as customer
2. Attempt to access `/admin/returns/`

**Expected Results:**
- ✅ Status code: 403 Forbidden
- ❌ OR redirect with "Permission denied" message

---

### Test Case 6.3: Stock Keeper Cannot Approve
**ID:** ST-SEC-003
**Priority:** High
**Objective:** Stock Keeper cannot approve/reject returns

**Test Steps:**
1. Login as Stock Keeper
2. Attempt POST to `/admin/returns/RET-001/approve/`

**Expected Results:**
- ✅ Status code: 403 Forbidden
- ✅ Return status unchanged

---

### Test Case 6.4: Finance Can Process Refunds
**ID:** ST-SEC-004
**Priority:** High
**Objective:** Finance role can process refunds

**Test Steps:**
1. Login as Finance user
2. POST to `/admin/returns/RET-001/process-refund/`

**Expected Results:**
- ✅ Status code: 200 or 302 (success redirect)
- ✅ Refund processed successfully

---

### Test Case 6.5: Customer Data Isolation
**ID:** ST-SEC-005
**Priority:** Critical
**Objective:** Customer A cannot access Customer B's data via API

**Test Steps:**
1. Login as Customer A
2. GET `/api/returns/RET-20250101-0001/status/` (belongs to Customer B)

**Expected Results:**
- ✅ Status code: 403 or 404
- ✅ No data leaked

---

## 3.7 WORKFLOW TESTS (End-to-End)

### Test Case 7.1: Complete Return Workflow - Success Path
**ID:** WT-E2E-001
**Priority:** Critical
**Objective:** Test complete return lifecycle from creation to refund

**Workflow Steps:**
1. **Customer creates return** → POST `/order/123/return/`
   - Expected: Return created, status='pending'

2. **Manager approves** → POST `/admin/returns/RET-001/approve/`
   - Expected: status='approved', refund_amount set

3. **Customer ships item** (manual step)
   - Expected: status changed to 'in_transit' (may be manual update)

4. **Stock Keeper marks received** → POST `/admin/returns/RET-001/mark-received/`
   - Expected: status='received'

5. **Stock Keeper inspects** → POST `/admin/returns/RET-001/inspect/`
   - Expected: status='refund_approved'

6. **Finance processes refund** → POST `/admin/returns/RET-001/process-refund/`
   - Expected: status='refunded'

**Final Verification:**
- ✅ 6 ReturnStatusLog entries exist
- ✅ All timestamps populated
- ✅ All actor fields (approved_by, inspected_by, etc.) populated
- ✅ Customer can see updated status

---

### Test Case 7.2: Complete Return Workflow - Rejection Path
**ID:** WT-E2E-002
**Priority:** High
**Objective:** Test return rejection scenarios

**Workflow Steps:**
1. Customer creates return → status='pending'
2. Manager rejects → status='rejected'

**Expected Results:**
- ✅ Return marked as rejected
- ✅ Rejection reason saved
- ✅ Customer notified
- ✅ No further actions allowed

---

### Test Case 7.3: Return Inspection Rejection
**ID:** WT-E2E-003
**Priority:** High
**Objective:** Test rejection during inspection

**Workflow Steps:**
1. Return approved → status='approved'
2. Items received → status='received'
3. Inspection rejects → status='refund_rejected'

**Expected Results:**
- ✅ Inspection notes saved
- ✅ Customer notified of rejection
- ✅ Items marked as damaged/not eligible

---

## 3.8 ADMIN INTERFACE TESTS

### Test Case 8.1: Return Admin List View
**ID:** AT-ADM-001
**Priority:** Medium
**Objective:** Returns visible in Django admin

**Test Steps:**
1. Login to Django admin as superuser
2. Navigate to Orders → Returns

**Expected Results:**
- ✅ Returns list displayed
- ✅ Columns: return_code, customer, order, status, request_date
- ✅ Filters: status, reason, created date
- ✅ Search by return_code, customer name

---

### Test Case 8.2: Return Admin Detail View
**ID:** AT-ADM-002
**Priority:** Medium
**Objective:** Return details editable in admin

**Test Steps:**
1. Click on a return in admin list
2. Modify status field
3. Save

**Expected Results:**
- ✅ All fields displayed
- ✅ Changes saved successfully
- ✅ Related items shown as inline

---

### Test Case 8.3: ReturnItem Inline Admin
**ID:** AT-ADM-003
**Priority:** Low
**Objective:** Return items manageable from return admin

**Test Steps:**
1. Open return in admin
2. View ReturnItem inline formset

**Expected Results:**
- ✅ All return items displayed
- ✅ Can add/remove items
- ✅ Quantity and reason editable

---

## 3.9 API ENDPOINT TESTS

### Test Case 9.1: Get Return Status API
**ID:** AT-API-001
**Priority:** High
**Objective:** Status API returns correct JSON

**Request:**
```
GET /api/returns/RET-20250101-0001/status/
Authorization: Bearer <customer_token>
```

**Expected Response:**
```json
{
  "success": true,
  "return_code": "RET-20250101-0001",
  "status": "approved",
  "refund_amount": 950.00,
  "request_date": "2025-01-01T10:30:00Z",
  "approved_date": "2025-01-02T14:20:00Z"
}
```

---

### Test Case 9.2: Get Return Timeline API
**ID:** AT-API-002
**Priority:** Medium
**Objective:** Timeline API returns status history

**Request:**
```
GET /api/returns/RET-20250101-0001/timeline/
Authorization: Bearer <customer_token>
```

**Expected Response:**
```json
{
  "success": true,
  "timeline": [
    {
      "status": "pending",
      "changed_at": "2025-01-01T10:30:00Z",
      "changed_by": "Customer Name",
      "notes": "Return requested"
    },
    {
      "status": "approved",
      "changed_at": "2025-01-02T14:20:00Z",
      "changed_by": "Manager Name",
      "notes": "Return approved"
    }
  ]
}
```

---

## 3.10 EDGE CASES & ERROR HANDLING

### Test Case 10.1: Return for Already Returned Order
**ID:** ET-EDG-001
**Priority:** High
**Objective:** Prevent duplicate returns for same order

**Test Steps:**
1. Create return for order #123
2. Attempt to create another return for order #123

**Expected Results:**
- ✅ Validation error
- ✅ Message: "Return already exists for this order"
- ❌ OR: Allow multiple returns with different items

---

### Test Case 10.2: Invalid Return Code
**ID:** ET-EDG-002
**Priority:** Medium
**Objective:** Handle non-existent return codes gracefully

**Test Steps:**
1. GET `/my-returns/INVALID-CODE/`

**Expected Results:**
- ✅ Status code: 404 Not Found
- ✅ User-friendly error message

---

### Test Case 10.3: Concurrent Status Updates
**ID:** ET-EDG-003
**Priority:** Low
**Objective:** Handle race conditions in status updates

**Test Steps:**
1. Two staff members open same return
2. Both attempt to change status simultaneously

**Expected Results:**
- ✅ Only one update succeeds
- ❌ OR: Last write wins (acceptable)
- ✅ No data corruption

---

### Test Case 10.4: Refund Amount Exceeds Order Total
**ID:** ET-EDG-004
**Priority:** High
**Objective:** Prevent refund fraud

**Test Steps:**
1. Order total = 1000.00
2. Manager approves with refund_amount = 1500.00

**Expected Results:**
- ✅ Validation error OR warning
- ✅ Admin override required (if implemented)

---

### Test Case 10.5: Return After 30 Days
**ID:** ET-EDG-005
**Priority:** Medium
**Objective:** Enforce return window policy

**Test Steps:**
1. Order delivered 35 days ago
2. Customer attempts to create return

**Expected Results:**
- ✅ Error: "Return window expired"
- ❌ OR: Allow with admin review flag

---

## 4. Test Data Requirements

### 4.1 User Accounts Needed
- **Customer A** (username: customer1@test.com)
- **Customer B** (username: customer2@test.com)
- **Admin** (username: admin@test.com)
- **Manager** (username: manager@test.com)
- **Stock Keeper** (username: stockkeeper@test.com)
- **Finance** (username: finance@test.com)

### 4.2 Sample Orders Needed
- **Order #101** - Delivered 5 days ago (eligible for return)
- **Order #102** - Delivered 35 days ago (outside return window)
- **Order #103** - Status: pending (not eligible for return)
- **Order #104** - Already has return (test duplicate prevention)

### 4.3 Sample Returns Needed
- **RET-20250101-0001** - status: pending
- **RET-20250101-0002** - status: approved
- **RET-20250101-0003** - status: in_transit
- **RET-20250101-0004** - status: received
- **RET-20250101-0005** - status: refund_approved
- **RET-20250101-0006** - status: refunded (complete)
- **RET-20250101-0007** - status: rejected

---

## 5. Test Execution Priority

### Phase 1: Critical (P0) - Must Pass Before Deployment
- All Unit Tests (1.1 - 1.5)
- Customer view access (2.1, 2.2, 2.5)
- Admin dashboard (3.1)
- Security tests (6.1, 6.2, 6.5)
- Complete workflow (7.1)

### Phase 2: High Priority (P1) - Essential Features
- Form validations (4.1, 4.2, 4.3)
- Admin actions (3.6, 3.7, 3.8, 3.9, 3.10, 3.11)
- URL routing (5.1, 5.2, 5.3)
- API endpoints (9.1, 9.2)

### Phase 3: Medium Priority (P2) - Nice to Have
- Admin interface tests (8.1, 8.2, 8.3)
- Edge cases (10.1, 10.2, 10.4, 10.5)
- Permission edge cases (6.3, 6.4)

### Phase 4: Low Priority (P3) - Future Enhancement
- Concurrent updates (10.3)
- Advanced admin features

---

## 6. Test Environment Setup

### 6.1 Database Setup
```bash
python manage.py migrate
python manage.py loaddata test_users
python manage.py loaddata test_orders
python manage.py loaddata test_returns
```

### 6.2 Test User Creation
```python
# Create test users with proper roles
from django.contrib.auth.models import User
from core.models import UserRole

# Create users as defined in section 4.1
```

### 6.3 Test Execution Commands
```bash
# Run all return management tests
python manage.py test orders.tests.test_returns

# Run specific test class
python manage.py test orders.tests.test_returns.ReturnModelTests

# Run with coverage
coverage run --source='orders' manage.py test
coverage report
```

---

## 7. Success Criteria

### 7.1 Phase 1 (Critical) Success Criteria
- ✅ 100% of P0 tests pass
- ✅ No security vulnerabilities detected
- ✅ Customer can create return successfully
- ✅ Admin can process complete workflow
- ✅ No data leakage between customers

### 7.2 Overall Success Criteria
- ✅ 95%+ of all tests pass
- ✅ All critical workflows functional
- ✅ No blocking bugs identified
- ✅ Performance acceptable (response < 2 seconds)
- ✅ Code coverage > 80%

---

## 8. Known Limitations & Future Tests

### 8.1 Not Currently Tested
- Email notifications to customers
- SMS notifications
- Return shipping label generation
- PDF export functionality
- Bulk action operations
- Real-time status updates via WebSocket

### 8.2 Future Test Requirements
- Load testing (100+ concurrent return requests)
- Mobile app integration tests
- Third-party shipping integration tests
- Automated refund processing tests

---

## 9. Bug Reporting Template

When a test fails, document as follows:

**Bug ID:** BUG-RET-XXX
**Test Case:** [Test Case ID]
**Severity:** Critical / High / Medium / Low
**Priority:** P0 / P1 / P2 / P3

**Description:** [What went wrong]
**Steps to Reproduce:**
1. Step 1
2. Step 2

**Expected Result:** [What should happen]
**Actual Result:** [What actually happened]
**Environment:** Django 5.2.8, Python 3.x
**Screenshots:** [If applicable]

---

## 10. Test Sign-Off

### 10.1 Testers
- **Unit Tests:** Developer
- **Integration Tests:** QA Team
- **Security Tests:** Security Team
- **UAT:** Product Owner + Sample Customers

### 10.2 Approval
- [ ] All P0 tests passed
- [ ] All P1 tests passed
- [ ] Security review complete
- [ ] Performance review complete
- [ ] Documentation updated

**Approved By:** _______________
**Date:** _______________

---

**Document Version:** 1.0
**Last Updated:** 2025-12-02
**Next Review:** After Phase 1 testing complete
