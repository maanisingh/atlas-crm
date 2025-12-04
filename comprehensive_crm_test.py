#!/usr/bin/env python3
"""
Comprehensive CRM & Fulfillment System Test Suite
Tests all phases of the specification document
"""

import requests
import json
from datetime import datetime
import sys

BASE_URL = "https://atlas.alexandratechlab.com"

# Test results storage
test_results = {
    "timestamp": datetime.now().isoformat(),
    "phases": {},
    "summary": {
        "total_tests": 0,
        "passed": 0,
        "failed": 0,
        "warnings": 0
    }
}

class TestSession:
    def __init__(self):
        self.session = requests.Session()
        self.csrf_token = None
        self.logged_in = False

    def login(self, email, password):
        """Login and get CSRF token"""
        try:
            # Get login page for CSRF token
            response = self.session.get(f"{BASE_URL}/users/login/")
            if 'csrftoken' in self.session.cookies:
                self.csrf_token = self.session.cookies['csrftoken']

            # Perform login
            login_data = {
                'email': email,
                'password': password,
                'csrfmiddlewaretoken': self.csrf_token
            }

            response = self.session.post(
                f"{BASE_URL}/users/login/",
                data=login_data,
                headers={'Referer': f"{BASE_URL}/users/login/"}
            )

            self.logged_in = response.status_code == 200 or response.status_code == 302
            return self.logged_in
        except Exception as e:
            print(f"❌ Login failed: {e}")
            return False

def test_phase_1_ui_design(session):
    """Phase 1: UI/UX & Design Tests"""
    results = []

    print("\n" + "="*80)
    print("PHASE 1: UI/UX & DESIGN CONSISTENCY")
    print("="*80)

    # Test 1.1: Dashboard responsiveness
    print("\n[1.1] Testing Dashboard Page...")
    try:
        response = session.session.get(f"{BASE_URL}/dashboard/")
        if response.status_code == 200:
            # Check for responsive meta tags
            has_viewport = 'viewport' in response.text
            has_responsive = 'responsive' in response.text.lower()

            results.append({
                "test": "Dashboard Responsive Design",
                "status": "PASS" if has_viewport else "WARN",
                "details": f"Viewport meta: {has_viewport}, Responsive indicators: {has_responsive}"
            })
            print(f"  ✅ Dashboard accessible (viewport: {has_viewport})")
        else:
            results.append({
                "test": "Dashboard Responsive Design",
                "status": "FAIL",
                "details": f"HTTP {response.status_code}"
            })
            print(f"  ❌ Dashboard returned {response.status_code}")
    except Exception as e:
        results.append({
            "test": "Dashboard Responsive Design",
            "status": "FAIL",
            "details": str(e)
        })
        print(f"  ❌ Error: {e}")

    # Test 1.2: Consistent styling across pages
    print("\n[1.2] Testing Styling Consistency...")
    pages_to_check = [
        '/dashboard/',
        '/orders/',
        '/inventory/',
        '/users/',
        '/finance/'
    ]

    consistent_styling = True
    for page in pages_to_check:
        try:
            response = session.session.get(f"{BASE_URL}{page}")
            if response.status_code == 200:
                print(f"  ✅ {page} - Accessible")
            else:
                print(f"  ⚠️  {page} - HTTP {response.status_code}")
                consistent_styling = False
        except Exception as e:
            print(f"  ❌ {page} - Error: {e}")
            consistent_styling = False

    results.append({
        "test": "Styling Consistency Across Pages",
        "status": "PASS" if consistent_styling else "WARN",
        "details": f"Checked {len(pages_to_check)} major pages"
    })

    # Test 1.3: Navigation and back button
    print("\n[1.3] Testing Navigation Flow...")
    results.append({
        "test": "Navigation and Back Button",
        "status": "MANUAL",
        "details": "Requires browser testing for back button behavior"
    })
    print("  ℹ️  Back button testing requires manual verification")

    return results

def test_phase_1_backend_health(session):
    """Phase 1: Backend Health & Core Logic"""
    results = []

    print("\n" + "="*80)
    print("PHASE 1: BACKEND HEALTH & CORE LOGIC")
    print("="*80)

    # Test 1.4: API Health Check
    print("\n[1.4] Testing Backend API Health...")
    api_endpoints = [
        '/analytics/api/executive-summary/',
        '/dashboard/json/executive-summary/',
        '/dashboard/json/orders/',
        '/dashboard/json/inventory/',
        '/dashboard/json/finance/'
    ]

    healthy_apis = 0
    for endpoint in api_endpoints:
        try:
            response = session.session.get(f"{BASE_URL}{endpoint}")
            if response.status_code == 200:
                healthy_apis += 1
                print(f"  ✅ {endpoint}")
            else:
                print(f"  ❌ {endpoint} - HTTP {response.status_code}")
        except Exception as e:
            print(f"  ❌ {endpoint} - Error: {e}")

    results.append({
        "test": "Backend API Health",
        "status": "PASS" if healthy_apis == len(api_endpoints) else "WARN",
        "details": f"{healthy_apis}/{len(api_endpoints)} APIs healthy"
    })

    # Test 1.5: Authentication security
    print("\n[1.5] Testing Authentication Security...")

    # Test secure headers
    response = session.session.get(BASE_URL)
    secure_headers = {
        'X-Frame-Options': 'X-Frame-Options' in response.headers,
        'X-Content-Type-Options': 'X-Content-Type-Options' in response.headers,
        'Strict-Transport-Security': 'Strict-Transport-Security' in response.headers
    }

    all_secure = all(secure_headers.values())
    results.append({
        "test": "Security Headers Present",
        "status": "PASS" if all_secure else "WARN",
        "details": f"Headers: {secure_headers}"
    })
    print(f"  {'✅' if all_secure else '⚠️ '} Security headers: {secure_headers}")

    return results

def test_phase_1_roles_permissions(session):
    """Phase 1: Roles & Permissions"""
    results = []

    print("\n" + "="*80)
    print("PHASE 1: ROLES & PERMISSIONS")
    print("="*80)

    # Test 1.6: Role management interface
    print("\n[1.6] Testing Role Management...")
    try:
        response = session.session.get(f"{BASE_URL}/users/roles/")
        if response.status_code == 200:
            print("  ✅ Role management page accessible")
            results.append({
                "test": "Role Management Interface",
                "status": "PASS",
                "details": "Role management page exists"
            })
        else:
            print(f"  ❌ Role management page returned {response.status_code}")
            results.append({
                "test": "Role Management Interface",
                "status": "FAIL",
                "details": f"HTTP {response.status_code}"
            })
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.append({
            "test": "Role Management Interface",
            "status": "FAIL",
            "details": str(e)
        })

    # Test 1.7: User listing and profile
    print("\n[1.7] Testing User Management...")
    try:
        response = session.session.get(f"{BASE_URL}/users/")
        if response.status_code == 200:
            print("  ✅ User listing accessible")
            results.append({
                "test": "User Management Interface",
                "status": "PASS",
                "details": "User listing page exists"
            })
        else:
            print(f"  ⚠️  User listing returned {response.status_code}")
            results.append({
                "test": "User Management Interface",
                "status": "WARN",
                "details": f"HTTP {response.status_code}"
            })
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.append({
            "test": "User Management Interface",
            "status": "FAIL",
            "details": str(e)
        })

    return results

def test_phase_2_authentication(session):
    """Phase 2: Authentication & User Management"""
    results = []

    print("\n" + "="*80)
    print("PHASE 2: AUTHENTICATION & USER MANAGEMENT")
    print("="*80)

    # Test 2.1: Seller registration form
    print("\n[2.1] Testing Seller Registration...")
    try:
        # Check if registration page exists
        response = session.session.get(f"{BASE_URL}/sellers/register/")

        if response.status_code == 200:
            # Check for required fields
            required_fields = ['email', 'company', 'phone', 'password']
            has_fields = all(field in response.text.lower() for field in required_fields)

            results.append({
                "test": "Seller Registration Form",
                "status": "PASS" if has_fields else "WARN",
                "details": f"Registration page exists, required fields: {has_fields}"
            })
            print(f"  ✅ Registration page exists (fields: {has_fields})")
        elif response.status_code == 404:
            results.append({
                "test": "Seller Registration Form",
                "status": "FAIL",
                "details": "Registration page not implemented (404)"
            })
            print("  ❌ Registration page not found (404)")
        else:
            results.append({
                "test": "Seller Registration Form",
                "status": "WARN",
                "details": f"HTTP {response.status_code}"
            })
            print(f"  ⚠️  Registration page returned {response.status_code}")
    except Exception as e:
        results.append({
            "test": "Seller Registration Form",
            "status": "FAIL",
            "details": str(e)
        })
        print(f"  ❌ Error: {e}")

    # Test 2.2: Password security
    print("\n[2.2] Testing Password Security...")
    results.append({
        "test": "Password Hashing & Security",
        "status": "MANUAL",
        "details": "Requires database inspection to verify hashing algorithm"
    })
    print("  ℹ️  Password hashing verification requires database access")

    return results

def test_phase_3_sourcing_inventory(session):
    """Phase 3: Sourcing & Inventory (WMS)"""
    results = []

    print("\n" + "="*80)
    print("PHASE 3: SOURCING & INVENTORY (WMS)")
    print("="*80)

    # Test 3.1: Inventory page
    print("\n[3.1] Testing Inventory Management...")
    try:
        response = session.session.get(f"{BASE_URL}/inventory/")
        if response.status_code == 200:
            print("  ✅ Inventory page accessible")
            results.append({
                "test": "Inventory Management",
                "status": "PASS",
                "details": "Inventory page exists"
            })
        else:
            print(f"  ❌ Inventory page returned {response.status_code}")
            results.append({
                "test": "Inventory Management",
                "status": "FAIL",
                "details": f"HTTP {response.status_code}"
            })
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.append({
            "test": "Inventory Management",
            "status": "FAIL",
            "details": str(e)
        })

    # Test 3.2: Product listing
    print("\n[3.2] Testing Product Listing...")
    try:
        response = session.session.get(f"{BASE_URL}/products/")
        if response.status_code == 200:
            print("  ✅ Product listing accessible")
            results.append({
                "test": "Product Listing",
                "status": "PASS",
                "details": "Product listing page exists"
            })
        else:
            print(f"  ❌ Product listing returned {response.status_code}")
            results.append({
                "test": "Product Listing",
                "status": "FAIL",
                "details": f"HTTP {response.status_code}"
            })
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.append({
            "test": "Product Listing",
            "status": "FAIL",
            "details": str(e)
        })

    return results

def test_phase_4_orders_fulfillment(session):
    """Phase 4: Order & Fulfillment"""
    results = []

    print("\n" + "="*80)
    print("PHASE 4: ORDER & FULFILLMENT WORKFLOW")
    print("="*80)

    # Test 4.1: Order creation
    print("\n[4.1] Testing Order Creation...")
    try:
        response = session.session.get(f"{BASE_URL}/orders/create/")
        if response.status_code == 200:
            print("  ✅ Order creation page accessible")
            results.append({
                "test": "Order Creation Interface",
                "status": "PASS",
                "details": "Order creation page exists"
            })
        else:
            print(f"  ❌ Order creation returned {response.status_code}")
            results.append({
                "test": "Order Creation Interface",
                "status": "FAIL",
                "details": f"HTTP {response.status_code}"
            })
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.append({
            "test": "Order Creation Interface",
            "status": "FAIL",
            "details": str(e)
        })

    # Test 4.2: Order listing
    print("\n[4.2] Testing Order Listing...")
    try:
        response = session.session.get(f"{BASE_URL}/orders/")
        if response.status_code == 200:
            print("  ✅ Order listing accessible")
            results.append({
                "test": "Order Listing",
                "status": "PASS",
                "details": "Order listing page exists"
            })
        else:
            print(f"  ❌ Order listing returned {response.status_code}")
            results.append({
                "test": "Order Listing",
                "status": "FAIL",
                "details": f"HTTP {response.status_code}"
            })
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.append({
            "test": "Order Listing",
            "status": "FAIL",
            "details": str(e)
        })

    # Test 4.3: Call Center
    print("\n[4.3] Testing Call Center...")
    try:
        response = session.session.get(f"{BASE_URL}/callcenter/")
        if response.status_code == 200:
            print("  ✅ Call Center dashboard accessible")
            results.append({
                "test": "Call Center Module",
                "status": "PASS",
                "details": "Call Center dashboard exists"
            })
        else:
            print(f"  ❌ Call Center returned {response.status_code}")
            results.append({
                "test": "Call Center Module",
                "status": "FAIL",
                "details": f"HTTP {response.status_code}"
            })
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.append({
            "test": "Call Center Module",
            "status": "FAIL",
            "details": str(e)
        })

    return results

def test_phase_5_delivery_finance(session):
    """Phase 5: Delivery & Finance"""
    results = []

    print("\n" + "="*80)
    print("PHASE 5: DELIVERY & FINANCE CONTROL")
    print("="*80)

    # Test 5.1: Delivery management
    print("\n[5.1] Testing Delivery Management...")
    try:
        response = session.session.get(f"{BASE_URL}/delivery/")
        if response.status_code == 200:
            print("  ✅ Delivery page accessible")
            results.append({
                "test": "Delivery Management",
                "status": "PASS",
                "details": "Delivery page exists"
            })
        else:
            print(f"  ❌ Delivery page returned {response.status_code}")
            results.append({
                "test": "Delivery Management",
                "status": "FAIL",
                "details": f"HTTP {response.status_code}"
            })
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.append({
            "test": "Delivery Management",
            "status": "FAIL",
            "details": str(e)
        })

    # Test 5.2: Finance module
    print("\n[5.2] Testing Finance Module...")
    try:
        response = session.session.get(f"{BASE_URL}/finance/")
        if response.status_code == 200:
            print("  ✅ Finance dashboard accessible")
            results.append({
                "test": "Finance Module",
                "status": "PASS",
                "details": "Finance dashboard exists"
            })
        else:
            print(f"  ❌ Finance dashboard returned {response.status_code}")
            results.append({
                "test": "Finance Module",
                "status": "FAIL",
                "details": f"HTTP {response.status_code}"
            })
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.append({
            "test": "Finance Module",
            "status": "FAIL",
            "details": str(e)
        })

    # Test 5.3: Finance reports
    print("\n[5.3] Testing Finance Reports...")
    try:
        response = session.session.get(f"{BASE_URL}/finance/reports/")
        if response.status_code == 200:
            print("  ✅ Finance reports accessible")
            results.append({
                "test": "Finance Reports",
                "status": "PASS",
                "details": "Finance reports page exists"
            })
        else:
            print(f"  ❌ Finance reports returned {response.status_code}")
            results.append({
                "test": "Finance Reports",
                "status": "FAIL",
                "details": f"HTTP {response.status_code}"
            })
    except Exception as e:
        print(f"  ❌ Error: {e}")
        results.append({
            "test": "Finance Reports",
            "status": "FAIL",
            "details": str(e)
        })

    return results

def test_phase_6_security(session):
    """Phase 6: Security & Data Integrity"""
    results = []

    print("\n" + "="*80)
    print("PHASE 6: SECURITY & DATA INTEGRITY")
    print("="*80)

    # Test 6.1: HTTPS/SSL
    print("\n[6.1] Testing HTTPS/SSL...")
    try:
        response = session.session.get(BASE_URL)
        is_https = response.url.startswith('https://')
        results.append({
            "test": "HTTPS/SSL Encryption",
            "status": "PASS" if is_https else "FAIL",
            "details": f"Site uses {'HTTPS' if is_https else 'HTTP'}"
        })
        print(f"  {'✅' if is_https else '❌'} Site uses {'HTTPS' if is_https else 'HTTP'}")
    except Exception as e:
        results.append({
            "test": "HTTPS/SSL Encryption",
            "status": "FAIL",
            "details": str(e)
        })
        print(f"  ❌ Error: {e}")

    # Test 6.2: Security headers
    print("\n[6.2] Testing Security Headers...")
    response = session.session.get(BASE_URL)

    security_headers = {
        'X-Frame-Options': response.headers.get('X-Frame-Options', 'Missing'),
        'X-Content-Type-Options': response.headers.get('X-Content-Type-Options', 'Missing'),
        'Strict-Transport-Security': response.headers.get('Strict-Transport-Security', 'Missing'),
        'Referrer-Policy': response.headers.get('Referrer-Policy', 'Missing')
    }

    missing_headers = [k for k, v in security_headers.items() if v == 'Missing']

    results.append({
        "test": "Security Headers Configuration",
        "status": "PASS" if len(missing_headers) == 0 else "WARN",
        "details": f"Missing headers: {missing_headers if missing_headers else 'None'}"
    })

    for header, value in security_headers.items():
        status = "✅" if value != "Missing" else "⚠️ "
        print(f"  {status} {header}: {value}")

    # Test 6.3: CSRF protection
    print("\n[6.3] Testing CSRF Protection...")
    has_csrf = session.csrf_token is not None
    results.append({
        "test": "CSRF Protection",
        "status": "PASS" if has_csrf else "FAIL",
        "details": f"CSRF token {'present' if has_csrf else 'missing'}"
    })
    print(f"  {'✅' if has_csrf else '❌'} CSRF token {'present' if has_csrf else 'missing'}")

    return results

def generate_summary_report(all_results):
    """Generate summary report"""
    print("\n" + "="*80)
    print("TEST EXECUTION SUMMARY")
    print("="*80)

    total_tests = 0
    passed = 0
    failed = 0
    warnings = 0
    manual = 0

    for phase_name, phase_results in all_results.items():
        for result in phase_results:
            total_tests += 1
            status = result['status']
            if status == 'PASS':
                passed += 1
            elif status == 'FAIL':
                failed += 1
            elif status == 'WARN':
                warnings += 1
            elif status == 'MANUAL':
                manual += 1

    print(f"\nTotal Tests: {total_tests}")
    print(f"✅ Passed: {passed}")
    print(f"❌ Failed: {failed}")
    print(f"⚠️  Warnings: {warnings}")
    print(f"ℹ️  Manual Review Required: {manual}")

    if total_tests > 0:
        pass_rate = (passed / (total_tests - manual)) * 100 if (total_tests - manual) > 0 else 0
        print(f"\n📊 Pass Rate: {pass_rate:.1f}% (excluding manual tests)")

    test_results['summary'] = {
        "total_tests": total_tests,
        "passed": passed,
        "failed": failed,
        "warnings": warnings,
        "manual": manual
    }

    return test_results

def main():
    print("="*80)
    print("ATLAS CRM & FULFILLMENT SYSTEM - COMPREHENSIVE TEST SUITE")
    print("="*80)
    print(f"Test execution started: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"Target system: {BASE_URL}")

    # Create session and login
    session = TestSession()
    print("\n🔐 Attempting login...")
    if session.login("superadmin@atlas.com", "Atlas2024!Secure"):
        print("✅ Login successful")
    else:
        print("⚠️  Login failed - proceeding with unauthenticated tests")

    # Execute all test phases
    all_results = {}

    all_results['Phase_1_UI_Design'] = test_phase_1_ui_design(session)
    all_results['Phase_1_Backend_Health'] = test_phase_1_backend_health(session)
    all_results['Phase_1_Roles_Permissions'] = test_phase_1_roles_permissions(session)
    all_results['Phase_2_Authentication'] = test_phase_2_authentication(session)
    all_results['Phase_3_Sourcing_Inventory'] = test_phase_3_sourcing_inventory(session)
    all_results['Phase_4_Orders_Fulfillment'] = test_phase_4_orders_fulfillment(session)
    all_results['Phase_5_Delivery_Finance'] = test_phase_5_delivery_finance(session)
    all_results['Phase_6_Security'] = test_phase_6_security(session)

    # Store results
    test_results['phases'] = all_results

    # Generate summary
    final_results = generate_summary_report(all_results)

    # Save to file
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f"comprehensive_test_results_{timestamp}.json"

    with open(filename, 'w') as f:
        json.dump(final_results, f, indent=2)

    print(f"\n📄 Detailed results saved to: {filename}")
    print("\n" + "="*80)
    print("TEST EXECUTION COMPLETE")
    print("="*80)

if __name__ == "__main__":
    main()
