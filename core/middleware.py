import threading

from django.utils.deprecation import MiddlewareMixin

from master_data.models.organisations_models import Organization

# Thread-local storage for the current tenant
_thread_local = threading.local()


class TenantMiddleware(MiddlewareMixin):
    """
    Middleware that identifies the current tenant based on the subdomain
    and sets it in thread-local storage for use by the TenantModel and other components.
    """

    def process_request(self, request):
        """
        Process the request to identify the tenant and set it in thread-local storage.
        """
        # Clear any existing tenant
        self.clear_tenant()

        # Skip for admin, static, and media URLs
        if request.path.startswith('/admin/') or request.path.startswith('/static/') or request.path.startswith(
                '/media/'):
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

            try:
                # Try to get the organization by subdomain
                organization = Organization.objects.get(subdomain=subdomain, is_active=True)

                # Set the organization as the current tenant
                self.set_tenant(organization)

                # Add the organization to the request for easy access
                request.organization = organization

            except Organization.DoesNotExist:
                # If no organization is found, continue without setting a tenant
                pass

        return None

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
