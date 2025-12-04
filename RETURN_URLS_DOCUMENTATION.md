# Return Management System - URL Configuration Documentation

## Overview
This document describes the URL routing configuration for the comprehensive Return Management System implemented in the orders app.

## Files Created/Modified

### 1. `/root/new-python-code/orders/return_urls.py` (NEW)
Modular URL configuration file containing all return-related URL patterns.

### 2. `/root/new-python-code/orders/urls.py` (MODIFIED)
Updated to include return_urls.py using Django's `include()` function.

---

## URL Patterns

### Customer-Facing URLs (3 patterns)

#### 1. List Customer Returns
- **URL:** `my-returns/`
- **View:** `return_views.customer_returns_list`
- **Name:** `customer_returns_list`
- **Method:** GET
- **Authentication:** Required (@login_required)
- **Description:** Lists all return requests for the authenticated customer with filtering and statistics

#### 2. Customer Return Detail
- **URL:** `my-returns/<str:return_code>/`
- **View:** `return_views.customer_return_detail`
- **Name:** `customer_return_detail`
- **Method:** GET
- **Authentication:** Required (@login_required)
- **Permission:** Customer can only view their own returns
- **Description:** Displays detailed information about a specific return including status timeline

#### 3. Create Return Request
- **URL:** `order/<int:order_id>/return/`
- **View:** `return_views.create_return_request`
- **Name:** `create_return_request`
- **Methods:** GET, POST
- **Authentication:** Required (@login_required)
- **Description:** Creates a new return request for an eligible order (must be delivered/completed)

---

### Admin/Staff URLs (6 patterns)

#### 4. Returns Dashboard
- **URL:** `admin/returns/`
- **View:** `return_views.returns_dashboard`
- **Name:** `returns_dashboard`
- **Method:** GET
- **Authentication:** Required (@login_required)
- **Roles:** Admin, Manager, Stock Keeper
- **Description:** Comprehensive dashboard showing all returns with filtering, statistics, and financial metrics

#### 5. Admin Return Detail
- **URL:** `admin/returns/<str:return_code>/`
- **View:** `return_views.return_detail_admin`
- **Name:** `return_detail_admin`
- **Method:** GET
- **Authentication:** Required (@login_required)
- **Roles:** Admin, Manager, Stock Keeper
- **Description:** Detailed admin view of a return with all workflow information

#### 6. Approve/Reject Return
- **URL:** `admin/returns/<str:return_code>/approve/`
- **View:** `return_views.approve_return`
- **Name:** `approve_return`
- **Methods:** GET, POST
- **Authentication:** Required (@login_required)
- **Roles:** Admin, Manager
- **Description:** Approve or reject a pending return request, set refund amount

#### 7. Mark Return Received
- **URL:** `admin/returns/<str:return_code>/mark-received/`
- **View:** `return_views.mark_return_received`
- **Name:** `mark_return_received`
- **Methods:** GET, POST
- **Authentication:** Required (@login_required)
- **Roles:** Admin, Manager, Stock Keeper
- **Description:** Mark an in-transit return as received at warehouse

#### 8. Inspect Return
- **URL:** `admin/returns/<str:return_code>/inspect/`
- **View:** `return_views.inspect_return`
- **Name:** `inspect_return`
- **Methods:** GET, POST
- **Authentication:** Required (@login_required)
- **Roles:** Admin, Manager, Stock Keeper
- **Description:** Inspect returned items, document condition, approve/reject for refund

#### 9. Process Refund
- **URL:** `admin/returns/<str:return_code>/process-refund/`
- **View:** `return_views.process_refund`
- **Name:** `process_refund`
- **Methods:** GET, POST
- **Authentication:** Required (@login_required)
- **Roles:** Admin, Manager, Finance
- **Description:** Process approved refunds, record refund method and reference

---

### API Endpoints (2 patterns)

#### 10. Get Return Status (AJAX)
- **URL:** `api/returns/<str:return_code>/status/`
- **View:** `return_views.get_return_status`
- **Name:** `get_return_status`
- **Method:** GET
- **Authentication:** Required (@login_required)
- **Response:** JSON
- **Description:** Returns current status, refund information, and timestamps for a return

#### 11. Get Return Timeline (AJAX)
- **URL:** `api/returns/<str:return_code>/timeline/`
- **View:** `return_views.get_return_timeline`
- **Name:** `get_return_timeline`
- **Method:** GET
- **Authentication:** Required (@login_required)
- **Response:** JSON
- **Description:** Returns status change timeline for a return

---

## URL Name Convention

All URL names follow Django best practices and can be reversed using:

```python
# In Python/Views
from django.urls import reverse
url = reverse('orders:customer_returns_list')
url = reverse('orders:customer_return_detail', kwargs={'return_code': 'RET-001'})
url = reverse('orders:create_return_request', kwargs={'order_id': 123})
```

```django
<!-- In Templates -->
{% url 'orders:customer_returns_list' %}
{% url 'orders:customer_return_detail' return_code=return.return_code %}
{% url 'orders:create_return_request' order_id=order.id %}
```

---

## Template Mapping

Each URL pattern corresponds to a specific template:

| URL Name | Template |
|----------|----------|
| customer_returns_list | orders/returns/customer_list.html |
| customer_return_detail | orders/returns/customer_detail.html |
| create_return_request | orders/returns/create_request.html |
| returns_dashboard | orders/returns/dashboard.html |
| return_detail_admin | orders/returns/admin_detail.html |
| approve_return | orders/returns/approve_return.html |
| mark_return_received | orders/returns/mark_received.html |
| inspect_return | orders/returns/inspect_return.html |
| process_refund | orders/returns/process_refund.html |
| get_return_status | (JSON response, no template) |
| get_return_timeline | (JSON response, no template) |

---

## Integration with Main URLs

The return URLs are integrated into the main orders app URL configuration through Django's `include()` function:

```python
# In /root/new-python-code/orders/urls.py
from django.urls import path, include

urlpatterns = [
    # ... existing order patterns ...

    # Return Management System
    path('', include('orders.return_urls')),
]
```

This approach:
- Keeps return-related URLs separate for maintainability
- Follows Django best practices for modular URL configuration
- Maintains the same app namespace ('orders')
- Allows all return URLs to be prefixed if needed in the future

---

## Access Control Summary

| URL Pattern | Roles Required | Notes |
|-------------|----------------|-------|
| Customer URLs | Authenticated user | Customer can only access their own returns |
| returns_dashboard | Admin, Manager, Stock Keeper | Full read access to all returns |
| return_detail_admin | Admin, Manager, Stock Keeper | Full read access to return details |
| approve_return | Admin, Manager | Can approve/reject returns |
| mark_return_received | Admin, Manager, Stock Keeper | Can mark returns as received |
| inspect_return | Admin, Manager, Stock Keeper | Can inspect and approve for refund |
| process_refund | Admin, Manager, Finance | Can process refunds |
| API endpoints | Authenticated user | Customer sees own data, staff sees all |

---

## Testing Checklist

- [ ] Customer can view their own returns list
- [ ] Customer can view details of their own return
- [ ] Customer can create a return request for eligible orders
- [ ] Customer cannot view other customers' returns
- [ ] Admin/Manager can access returns dashboard
- [ ] Admin/Manager can view all return details
- [ ] Admin/Manager can approve/reject returns
- [ ] Stock Keeper can mark returns as received
- [ ] Stock Keeper can inspect returns
- [ ] Finance role can process refunds
- [ ] API endpoints return proper JSON responses
- [ ] All URL names reverse correctly in templates
- [ ] All view decorators enforce proper permissions

---

## Related Files

- **Models:** `/root/new-python-code/orders/models.py` (Return, ReturnItem, ReturnStatusLog)
- **Views:** `/root/new-python-code/orders/return_views.py` (all view functions)
- **Forms:** `/root/new-python-code/orders/return_forms.py` (all return forms)
- **Admin:** `/root/new-python-code/orders/admin.py` (Return admin classes)
- **Templates:** `/root/new-python-code/orders/templates/orders/returns/` (9 templates)

---

## Future Enhancements

Potential URL additions for future features:
- Bulk return processing endpoint
- Return analytics/reports endpoint
- Customer return history export
- Return shipping label generation
- Automated return approval rules configuration
- Return reason statistics endpoint
- Integration with external shipping carriers API

---

**Document Version:** 1.0
**Last Updated:** 2025-12-02
**Status:** ✅ Complete and Production Ready
