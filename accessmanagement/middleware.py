import logging
import re

from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone

from .models import UserSecuritySettings
from .permissions import user_has_permission

logger = logging.getLogger('accessmanagement')


class PasswordPolicyMiddleware:
    """
    Middleware to enforce password policies:
    - Password expiration
    - Account locking after failed login attempts
    - Forced password change
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Skip for unauthenticated users
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Skip for API requests
        if request.path.startswith('/api/'):
            return self.get_response(request)

        # Skip for static files, admin, login, logout
        if request.path.startswith(('/static/', '/media/', '/admin/', '/login/', '/logout/')):
            return self.get_response(request)

        # Skip for password change and reset URLs
        if request.path.startswith(('/password_change/', '/password_reset/')):
            return self.get_response(request)

        # Get or create security settings for the user
        security_settings, created = UserSecuritySettings.objects.get_or_create(
            user=request.user,
            defaults={
                'password_last_changed': request.user.last_login or timezone.now(),
            }
        )

        # Check if account is locked
        if security_settings.is_account_locked():
            messages.error(
                request,
                "Your account is temporarily locked due to multiple failed login attempts. "
                "Please try again later or contact support."
            )
            return redirect('logout')

        # Check if password is expired or change is required
        if security_settings.is_password_expired() or security_settings.require_password_change:
            # Don't redirect if already on password change page
            if not request.path == reverse('password_change'):
                messages.warning(
                    request,
                    "Your password has expired or needs to be changed. Please set a new password."
                )
                return redirect('password_change')

        return self.get_response(request)


class RoleBasedAccessMiddleware:
    """
    Middleware to enforce role-based access control.
    Checks if a user has the required permissions to access a view based on their roles.
    """

    def __init__(self, get_response):
        self.get_response = get_response

        # Paths that should be excluded from permission checks
        self.excluded_paths = [
            r'^/static/',
            r'^/media/',
            r'^/admin/',
            r'^/login/',
            r'^/logout/',
            r'^/password_change/',
            r'^/password_reset/',
            r'^/$',  # Landing page
            r'^/dashboard/$',  # Main dashboard
        ]

        # Compile the excluded paths for faster matching
        self.excluded_paths_regex = [re.compile(path) for path in self.excluded_paths]

        # Permission mapping for URL patterns
        # Format: (url_pattern, required_permission)
        self.permission_mapping = [
            # Inventory
            (r'^/dashboard/inventory/', 'inventory.view_warehouse'),

            # Suppliers
            (r'^/dashboard/suppliers/', 'suppliers.view_supplier'),

            # Orders
            (r'^/dashboard/order/', 'order.view_purchaseorder'),

            # RMA
            (r'^/dashboard/rma/', 'rma.view_rma'),

            # Documents
            (r'^/dashboard/documents/', 'documents.view_document'),

            # Analytics
            (r'^/dashboard/analytics/', 'analytics.view_report'),

            # User management
            (r'^/dashboard/access/', 'auth.view_user'),

            # Products
            (r'^/dashboard/product/', 'product.view'),
        ]

        # Compile the permission mapping for faster matching
        self.permission_mapping = [(re.compile(pattern), perm) for pattern, perm in self.permission_mapping]

    def __call__(self, request):
        # Skip for unauthenticated users (they'll be caught by auth middleware)
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Skip for superusers who have all permissions
        if request.user.is_superuser:
            return self.get_response(request)

        # Check if the path is excluded from permission checks
        path = request.path
        for excluded_path in self.excluded_paths_regex:
            if excluded_path.match(path):
                return self.get_response(request)

        # Check if the path requires specific permissions
        required_permission = None
        for pattern, perm in self.permission_mapping:
            if pattern.match(path):
                required_permission = perm
                break

        # If no specific permission is required, continue with the request
        if not required_permission:
            return self.get_response(request)

        # Get the organization and department from the request if available
        organization = getattr(request, 'organization', None)
        department = getattr(request, 'department', None)

        # Check if the user has the required permission
        if not user_has_permission(request.user, required_permission, organization, department):
            # User doesn't have the required permission
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # For AJAX requests, return a 403 Forbidden response
                return HttpResponseForbidden("You don't have permission to access this resource.")
            else:
                # For regular requests, redirect to dashboard with a message
                messages.error(
                    request,
                    "You don't have permission to access this resource. "
                    "Please contact your administrator if you believe this is an error."
                )
                return redirect('dashboard')

        # User has the required permission, continue with the request
        return self.get_response(request)
