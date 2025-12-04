#!/usr/bin/env python
"""
Comprehensive API Test Script for Atlas CRM System
Tests all major endpoints with proper authentication
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:8070"
ADMIN_EMAIL = "admin@atlas.com"
ADMIN_PASSWORD = "admin123"  # Default password - change if different

class Colors:
    """Terminal colors for output"""
    GREEN = '\033[92m'
    RED = '\033[91m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    END = '\033[0m'

class AtlasAPITester:
    def __init__(self):
        self.session = requests.Session()
        self.csrf_token = None
        self.auth_token = None
        self.results = {
            'passed': 0,
            'failed': 0,
            'errors': []
        }

    def print_header(self, text):
        """Print formatted section header"""
        print(f"\n{Colors.BLUE}{'='*80}")
        print(f"{text}")
        print(f"{'='*80}{Colors.END}\n")

    def print_success(self, text):
        """Print success message"""
        print(f"{Colors.GREEN}✓ {text}{Colors.END}")
        self.results['passed'] += 1

    def print_error(self, text, details=None):
        """Print error message"""
        print(f"{Colors.RED}✗ {text}{Colors.END}")
        if details:
            print(f"  Details: {details}")
        self.results['failed'] += 1
        self.results['errors'].append({'test': text, 'details': details})

    def print_info(self, text):
        """Print info message"""
        print(f"{Colors.YELLOW}ℹ {text}{Colors.END}")

    def get_csrf_token(self):
        """Get CSRF token from login page"""
        try:
            response = self.session.get(f"{BASE_URL}/users/login/")
            if 'csrftoken' in self.session.cookies:
                self.csrf_token = self.session.cookies['csrftoken']
                self.print_success("CSRF token obtained")
                return True
            else:
                self.print_error("Failed to get CSRF token")
                return False
        except Exception as e:
            self.print_error("Exception getting CSRF token", str(e))
            return False

    def login(self):
        """Login to get session authentication"""
        self.print_header("AUTHENTICATION TEST")

        if not self.get_csrf_token():
            return False

        try:
            login_data = {
                'email': ADMIN_EMAIL,
                'password': ADMIN_PASSWORD,
                'csrfmiddlewaretoken': self.csrf_token
            }

            response = self.session.post(
                f"{BASE_URL}/users/login/",
                data=login_data,
                headers={
                    'Referer': f"{BASE_URL}/users/login/",
                    'X-CSRFToken': self.csrf_token
                }
            )

            if response.status_code in [200, 302] and 'sessionid' in self.session.cookies:
                self.print_success(f"Login successful as {ADMIN_EMAIL}")

                # Try to get auth token for REST API
                try:
                    token_response = self.session.post(
                        f"{BASE_URL}/api/users/token/",
                        json={'email': ADMIN_EMAIL, 'password': ADMIN_PASSWORD}
                    )
                    if token_response.status_code == 200:
                        data = token_response.json()
                        self.auth_token = data.get('token')
                        if self.auth_token:
                            self.print_success("REST API token obtained")
                except:
                    self.print_info("REST API token endpoint not available, using session auth")

                return True
            else:
                self.print_error(f"Login failed - Status: {response.status_code}")
                return False

        except Exception as e:
            self.print_error("Exception during login", str(e))
            return False

    def test_endpoint(self, name, url, method='GET', data=None, params=None):
        """Test a single endpoint"""
        try:
            headers = {}
            if self.auth_token:
                headers['Authorization'] = f'Token {self.auth_token}'

            if method == 'GET':
                response = self.session.get(url, params=params, headers=headers)
            elif method == 'POST':
                headers['X-CSRFToken'] = self.csrf_token
                response = self.session.post(url, json=data, headers=headers)

            if response.status_code == 200:
                try:
                    json_data = response.json()
                    self.print_success(f"{name} - Status: {response.status_code}")
                    return json_data
                except:
                    self.print_success(f"{name} - Status: {response.status_code} (HTML response)")
                    return None
            elif response.status_code == 403:
                self.print_error(f"{name} - Permission Denied (403)")
                return None
            elif response.status_code == 404:
                self.print_error(f"{name} - Not Found (404)")
                return None
            else:
                self.print_error(f"{name} - Status: {response.status_code}")
                return None

        except Exception as e:
            self.print_error(f"{name} - Exception", str(e))
            return None

    def test_analytics_endpoints(self):
        """Test all analytics API endpoints"""
        self.print_header("ANALYTICS API ENDPOINTS")

        endpoints = [
            ("Executive Summary", f"{BASE_URL}/analytics/api/executive-summary/", {'days': 30}),
            ("Order Analytics", f"{BASE_URL}/analytics/api/orders/", {'days': 30}),
            ("Inventory Analytics", f"{BASE_URL}/analytics/api/inventory/", {'days': 30, 'limit': 10}),
            ("Finance Analytics", f"{BASE_URL}/analytics/api/finance/", {'days': 30}),
            ("Delivery Analytics", f"{BASE_URL}/analytics/api/delivery/", {'days': 30}),
            ("Call Center Analytics", f"{BASE_URL}/analytics/api/callcenter/", {'days': 30, 'limit': 10}),
            ("User Analytics", f"{BASE_URL}/analytics/api/users/", {'days': 30}),
            ("Operations KPIs", f"{BASE_URL}/analytics/api/operations/", {'days': 30}),
            ("Sales KPIs", f"{BASE_URL}/analytics/api/sales/", {'days': 30}),
        ]

        for name, url, params in endpoints:
            data = self.test_endpoint(name, url, params=params)
            if data:
                # Print sample data structure
                keys = list(data.keys()) if isinstance(data, dict) else []
                self.print_info(f"  Response keys: {', '.join(keys[:5])}")

    def test_dashboard_endpoints(self):
        """Test dashboard endpoints"""
        self.print_header("DASHBOARD ENDPOINTS")

        endpoints = [
            ("Main Dashboard", f"{BASE_URL}/dashboard/"),
            ("Admin Dashboard", f"{BASE_URL}/dashboard/admin/"),
            ("JSON Executive Summary", f"{BASE_URL}/analytics/json/executive-summary/"),
            ("JSON Orders", f"{BASE_URL}/analytics/json/orders/"),
            ("JSON Inventory", f"{BASE_URL}/analytics/json/inventory/"),
            ("JSON Finance", f"{BASE_URL}/analytics/json/finance/"),
        ]

        for name, url in endpoints:
            self.test_endpoint(name, url)

    def test_user_endpoints(self):
        """Test user management endpoints"""
        self.print_header("USER MANAGEMENT ENDPOINTS")

        endpoints = [
            ("User List", f"{BASE_URL}/users/"),
            ("Profile", f"{BASE_URL}/users/profile/"),
            ("User Roles", f"{BASE_URL}/roles/"),
        ]

        for name, url in endpoints:
            self.test_endpoint(name, url)

    def test_order_endpoints(self):
        """Test order management endpoints"""
        self.print_header("ORDER MANAGEMENT ENDPOINTS")

        endpoints = [
            ("Order List", f"{BASE_URL}/orders/"),
            ("Order Create", f"{BASE_URL}/orders/create/"),
            ("Order Statistics", f"{BASE_URL}/orders/statistics/"),
        ]

        for name, url in endpoints:
            self.test_endpoint(name, url)

    def test_inventory_endpoints(self):
        """Test inventory endpoints"""
        self.print_header("INVENTORY ENDPOINTS")

        endpoints = [
            ("Inventory List", f"{BASE_URL}/inventory/"),
            ("Product List", f"{BASE_URL}/products/"),
            ("Low Stock Alerts", f"{BASE_URL}/inventory/low-stock/"),
        ]

        for name, url in endpoints:
            self.test_endpoint(name, url)

    def test_callcenter_endpoints(self):
        """Test call center endpoints"""
        self.print_header("CALL CENTER ENDPOINTS")

        endpoints = [
            ("Call Center Dashboard", f"{BASE_URL}/callcenter/"),
            ("Call Center Manager", f"{BASE_URL}/callcenter/manager/"),
            ("Call Center Agent", f"{BASE_URL}/callcenter/agent/"),
        ]

        for name, url in endpoints:
            self.test_endpoint(name, url)

    def test_delivery_endpoints(self):
        """Test delivery endpoints"""
        self.print_header("DELIVERY ENDPOINTS")

        endpoints = [
            ("Delivery List", f"{BASE_URL}/delivery/"),
            ("Delivery Dashboard", f"{BASE_URL}/delivery/dashboard/"),
        ]

        for name, url in endpoints:
            self.test_endpoint(name, url)

    def test_finance_endpoints(self):
        """Test finance endpoints"""
        self.print_header("FINANCE ENDPOINTS")

        endpoints = [
            ("Finance Dashboard", f"{BASE_URL}/finance/"),
            ("Finance Reports", f"{BASE_URL}/finance/reports/"),
        ]

        for name, url in endpoints:
            self.test_endpoint(name, url)

    def print_summary(self):
        """Print test results summary"""
        self.print_header("TEST RESULTS SUMMARY")

        total = self.results['passed'] + self.results['failed']
        pass_rate = (self.results['passed'] / total * 100) if total > 0 else 0

        print(f"Total Tests: {total}")
        print(f"{Colors.GREEN}Passed: {self.results['passed']}{Colors.END}")
        print(f"{Colors.RED}Failed: {self.results['failed']}{Colors.END}")
        print(f"Pass Rate: {pass_rate:.1f}%\n")

        if self.results['errors']:
            print(f"{Colors.RED}Failed Tests:{Colors.END}")
            for error in self.results['errors']:
                print(f"  • {error['test']}")
                if error['details']:
                    print(f"    {error['details']}")

    def run_all_tests(self):
        """Run all test suites"""
        print(f"\n{Colors.BLUE}╔═══════════════════════════════════════════════════════════════════════════╗")
        print(f"║          ATLAS CRM COMPREHENSIVE API TEST SUITE                          ║")
        print(f"║          {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}                                              ║")
        print(f"╚═══════════════════════════════════════════════════════════════════════════╝{Colors.END}\n")

        # Authentication
        if not self.login():
            print(f"\n{Colors.RED}Authentication failed. Cannot proceed with tests.{Colors.END}")
            return

        # Run all test suites
        self.test_analytics_endpoints()
        self.test_dashboard_endpoints()
        self.test_user_endpoints()
        self.test_order_endpoints()
        self.test_inventory_endpoints()
        self.test_callcenter_endpoints()
        self.test_delivery_endpoints()
        self.test_finance_endpoints()

        # Print summary
        self.print_summary()

        # Save results to file
        results_file = f"/root/new-python-code/test_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(results_file, 'w') as f:
            json.dump(self.results, f, indent=2)

        print(f"\n{Colors.BLUE}Results saved to: {results_file}{Colors.END}\n")


if __name__ == "__main__":
    tester = AtlasAPITester()
    tester.run_all_tests()
