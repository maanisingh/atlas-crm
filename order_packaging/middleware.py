from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.utils.deprecation import MiddlewareMixin
from utils.views import permission_denied_authenticated
import re


class PackagingAgentAccessMiddleware(MiddlewareMixin):
    """
    Middleware to restrict Packaging Agent access to only packaging-related URLs.
    Packaging Agent can only access:
    - /packaging/* URLs
    - /users/logout/ (to logout)
    - /static/ and /media/ (for static files)
    - /users/login/ (if not authenticated)
    """
    
    # Allowed paths for Packaging Agent
    ALLOWED_PATHS = [
        '/packaging/',
        '/users/logout/',
        '/users/login/',
        '/static/',
        '/media/',
        '/users/profile/',  # Allow profile access
        '/users/edit-profile/',  # Allow profile editing
    ]
    
    # Blocked paths (even if they start with allowed paths)
    BLOCKED_PATHS = [
        '/orders/create/',
        '/orders/import/',
        '/orders/export/',
    ]
    
    def process_request(self, request):
        # Skip check for anonymous users
        if not request.user.is_authenticated:
            return None
        
        # Skip check if user is not Packaging Agent
        if not request.user.has_role('Packaging Agent'):
            return None
        
        # If user has Admin or Super Admin role in addition to Packaging Agent, allow access
        if (request.user.has_role('Admin') or 
            request.user.has_role('Super Admin') or 
            request.user.is_superuser):
            return None
        
        # Check if the current path is allowed
        path = request.path
        
        # First check if path is explicitly blocked
        if any(path.startswith(blocked_path) for blocked_path in self.BLOCKED_PATHS):
            return permission_denied_authenticated(
                request,
                message="You don't have permission to access this page. Packaging Agent can only view orders, not create or modify them."
            )
        
        # Check if path is an order operation
        if path.startswith('/orders/'):
            # Block order list view
            if path == '/orders/':
                return permission_denied_authenticated(
                    request,
                    message="You don't have permission to access this page. Packaging Agent can only view specific order details and invoices."
                )
            
            # Block edit, delete, update, create operations
            blocked_order_operations = [
                '/edit/',
                '/delete/',
                '/update/',
                '/create/',
                '/import/',
                '/export/',
                '/change-seller/',
                '/callcenter-approve/',
            ]
            
            # Check if this is a blocked operation
            if any(operation in path for operation in blocked_order_operations):
                return permission_denied_authenticated(
                    request,
                    message="You don't have permission to modify orders. Packaging Agent can only view order details and invoices."
                )
            
            # Allow ONLY order detail view (format: /orders/<order_id>/)
            # Check if path matches /orders/<number>/ pattern
            if re.match(r'^/orders/\d+/$', path):
                return None  # Allow access
            
            # Allow ONLY order invoice view (format: /orders/<order_id>/invoice/)
            if re.match(r'^/orders/\d+/invoice/$', path):
                return None  # Allow access
            
            # Block any other order paths (including public view, etc.)
            return permission_denied_authenticated(
                request,
                message="You don't have permission to access this page. Packaging Agent can only view order details (/orders/<id>/) and invoices (/orders/<id>/invoice/)."
            )
        
        # Allow if path starts with any allowed path
        is_allowed = any(path.startswith(allowed_path) for allowed_path in self.ALLOWED_PATHS)
        
        if not is_allowed:
            # Block access and show permission denied
            return permission_denied_authenticated(
                request,
                message="You don't have permission to access this page. Packaging Agent can only access packaging-related pages and view orders."
            )
        
        return None

