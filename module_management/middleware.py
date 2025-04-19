from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

from .models import Module


class ModuleAccessMiddleware:
    """
    Middleware to control access to module-specific views based on user's subscription.
    This middleware checks if the user has access to the requested module and redirects
    or blocks access accordingly.
    """

    def __init__(self, get_response):
        self.get_response = get_response
        # Module URL prefixes that should be checked for access control
        self.module_prefixes = {
            'inventory': 'inventory',
            'suppliers': 'suppliers',
            'order': 'order',
            'analytics': 'analytics',
            'rma': 'rma',
            'documents': 'documents',
            # Add more modules as they are created
        }

    def __call__(self, request):
        # Skip middleware for unauthenticated users (they'll be caught by auth middleware)
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Skip for superusers who have access to everything
        if request.user.is_superuser:
            return self.get_response(request)

        # Get the current URL path
        path = request.path_info.lstrip('/')

        # Skip for certain paths (login, admin, static, etc.)
        if path.startswith(('admin/', 'login/', 'logout/', 'static/', 'media/')):
            return self.get_response(request)

        # Check if the path is for a module that requires access control
        module_code = None
        for prefix, code in self.module_prefixes.items():
            if path.startswith(f"{prefix}/"):
                module_code = code
                break

        # If not a module path, continue with the request
        if not module_code:
            return self.get_response(request)

        # Check if the user has access to this module
        if not self.has_module_access(request.user, module_code):
            # User doesn't have access to this module
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # For AJAX requests, return a 403 Forbidden response
                return HttpResponseForbidden("You don't have access to this module.")
            else:
                # For regular requests, redirect to dashboard with a message
                messages.error(
                    request,
                    f"You don't have access to the {module_code} module. "
                    f"Please contact your administrator to upgrade your subscription."
                )
                return redirect('dashboard')

        # User has access, continue with the request
        return self.get_response(request)

    def has_module_access(self, user, module_code):
        """
        Check if a user has access to a specific module based on their organization's subscription.

        Args:
            user: The user requesting access
            module_code: The code of the module being accessed

        Returns:
            bool: True if the user has access, False otherwise
        """
        # Superusers always have access
        if user.is_superuser:
            return True

        try:
            # First check if the module exists and is active
            module = Module.objects.get(code=module_code, is_active=True)

            # If the module doesn't exist or is inactive, no access
            if not module:
                return False

            # Get the user's organization from the request
            from core.middleware import TenantMiddleware
            from master_data.models.organisations_models import Organization

            # Try to get the organization from the current tenant context
            organization = TenantMiddleware.get_current_tenant()

            # If no organization is found in the tenant context, try to get it from the user's profile
            if not organization:
                # Try to get the organization from the user's profile
                if hasattr(user, 'profile') and hasattr(user.profile, 'organization'):
                    organization = user.profile.organization
                else:
                    # Try to get the organization from the user's departments
                    user_departments = []

                    # Try to get departments from user profile
                    if hasattr(user, 'profile') and hasattr(user.profile, 'departments'):
                        user_departments = user.profile.departments.all()
                    # Fallback: try direct relationship
                    elif hasattr(user, 'departments'):
                        user_departments = user.departments.all()

                    if user_departments:
                        # Get the organization from the first department
                        organization = user_departments[0].organization

            # If still no organization is found, deny access
            if not organization:
                return False

            # Check if the organization has an active subscription
            if not organization.subscription_active:
                return False

            # Check if the organization has a subscription package
            if not organization.subscription_package:
                return False

            # Check if the module is included in the organization's subscription package
            if organization.subscription_package.modules.filter(code=module_code, is_active=True).exists():
                return True

            # Check if the organization has any active subscriptions that include this module
            from module_management.models import Subscription
            active_subscriptions = Subscription.objects.filter(
                organization=organization,
                is_active=True
            )

            for subscription in active_subscriptions:
                if subscription.has_module_access(module_code):
                    return True

            return False

        except Module.DoesNotExist:
            return False
        except Exception as e:
            # Log the error
            import logging
            logger = logging.getLogger('module_management')
            logger.error(f"Error checking module access: {str(e)}")
            return False
