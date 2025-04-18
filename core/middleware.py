import logging
import threading
from functools import wraps

from django.conf import settings
from django.core.cache import cache
from django.http import HttpResponseNotFound
from django.utils.deprecation import MiddlewareMixin

from master_data.models.organisations_models import Organization

# Thread-local storage for the current tenant
_thread_local = threading.local()

# Get logger
logger = logging.getLogger('core')


def tenant_context(tenant_id_or_obj):
    """
    Decorator to set a specific tenant context for a function.

    Usage:
        @tenant_context(tenant_id)
        def my_function():
            # This function will run with the specified tenant context
            pass
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # Get the original tenant
            original_tenant = TenantMiddleware.get_current_tenant()

            try:
                # Set the new tenant
                if isinstance(tenant_id_or_obj, int):
                    tenant = Organization.objects.get(id=tenant_id_or_obj, is_active=True)
                else:
                    tenant = tenant_id_or_obj

                TenantMiddleware.set_tenant(tenant)

                # Execute the function
                return func(*args, **kwargs)
            finally:
                # Restore the original tenant
                if original_tenant:
                    TenantMiddleware.set_tenant(original_tenant)
                else:
                    TenantMiddleware.clear_tenant()

        return wrapper

    return decorator


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware that identifies the current tenant based on the subdomain
    and sets it in thread-local storage for use by the TenantModel and other components.

    This middleware provides tenant isolation by:
    1. Identifying the tenant from the subdomain
    2. Setting the tenant in thread-local storage
    3. Adding the tenant to the request object
    4. Providing methods for getting and setting the tenant context
    """

    CACHE_PREFIX = 'tenant_subdomain_'
    CACHE_TIMEOUT = 3600  # 1 hour

    def process_request(self, request):
        """
        Process the request to identify the tenant and set it in thread-local storage.
        """
        # Clear any existing tenant
        self.clear_tenant()

        # Skip for excluded paths
        if self._should_skip_tenant_identification(request):
            return None

        # Get the host from the request
        host = request.get_host().split(':')[0]  # Remove port if present

        # Extract subdomain
        domain_parts = host.split('.')

        # If we're using a subdomain
        if len(domain_parts) > 2:
            subdomain = domain_parts[0]

            # Skip for 'www' subdomain
            if subdomain == 'www':
                return None

            # Try to get the organization from cache first
            organization = self._get_organization_from_cache(subdomain)

            if organization is None:
                try:
                    # Try to get the organization by subdomain
                    organization = Organization.objects.select_related('subscription_package').get(
                        subdomain=subdomain, 
                        is_active=True
                    )

                    # Cache the organization
                    self._cache_organization(subdomain, organization)

                except Organization.DoesNotExist:
                    # If no organization is found, return 404 if configured to do so
                    if getattr(settings, 'TENANT_SUBDOMAIN_REQUIRED', False):
                        logger.warning(f"Invalid subdomain accessed: {subdomain}")
                        return HttpResponseNotFound("Organization not found")
                    # Otherwise continue without setting a tenant
                    pass

            if organization:
                # Set the organization as the current tenant
                self.set_tenant(organization)

                # Add the organization to the request for easy access
                request.organization = organization

                # Log tenant identification
                logger.debug(f"Tenant identified: {organization.name} (subdomain: {subdomain})")

        return None

    def _should_skip_tenant_identification(self, request):
        """
        Determine if tenant identification should be skipped for this request.
        """
        # Define paths that should skip tenant identification
        skip_paths = [
            '/admin/',
            '/static/',
            '/media/',
            '/superadmin/',
            '/api/v1/auth/',  # Auth endpoints
        ]

        # Check if the path starts with any of the skip paths
        for path in skip_paths:
            if request.path.startswith(path):
                return True

        return False

    def _get_organization_from_cache(self, subdomain):
        """
        Get an organization from the cache by subdomain.
        """
        cache_key = f"{self.CACHE_PREFIX}{subdomain}"
        return cache.get(cache_key)

    def _cache_organization(self, subdomain, organization):
        """
        Cache an organization by subdomain.
        """
        cache_key = f"{self.CACHE_PREFIX}{subdomain}"
        cache.set(cache_key, organization, self.CACHE_TIMEOUT)

    @staticmethod
    def set_tenant(tenant):
        """
        Set the current tenant in thread-local storage.
        """
        _thread_local.tenant = tenant

    @staticmethod
    def clear_tenant():
        """
        Clear the current tenant from thread-local storage.
        """
        if hasattr(_thread_local, 'tenant'):
            del _thread_local.tenant

    @staticmethod
    def get_current_tenant():
        """
        Get the current tenant from thread-local storage.
        """
        return getattr(_thread_local, 'tenant', None)
