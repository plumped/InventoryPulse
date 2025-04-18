import logging

from django.conf import settings
from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect

logger = logging.getLogger('superadmin')

class SuperAdminMiddleware:
    """
    Middleware to restrict access to superadmin routes to superusers only.
    This middleware checks if the user is a superuser and blocks access to
    superadmin routes for non-superusers.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Check if the request path starts with /superadmin/
        if request.path.startswith('/superadmin/'):
            # Get client IP
            client_ip = self._get_client_ip(request)

            # Check if IP is allowed
            allowed_ips = getattr(settings, 'SUPERADMIN_ALLOWED_IPS', [])
            ip_allowed = not allowed_ips or client_ip in allowed_ips

            # Check if the user is authenticated and is a superuser
            if not request.user.is_authenticated or not request.user.is_superuser or not ip_allowed:
                # Log the unauthorized access attempt
                if not request.user.is_authenticated:
                    logger.warning(
                        f"Unauthorized access attempt to superadmin area by unauthenticated user "
                        f"from IP {client_ip}"
                    )
                elif not request.user.is_superuser:
                    logger.warning(
                        f"Unauthorized access attempt to superadmin area by non-superuser {request.user.username} "
                        f"from IP {client_ip}"
                    )
                elif not ip_allowed:
                    logger.warning(
                        f"Unauthorized access attempt to superadmin area by superuser {request.user.username} "
                        f"from disallowed IP {client_ip}"
                    )

                    # Create audit log for IP restriction
                    from core.models import AuditLog

                    if request.user.is_authenticated:
                        AuditLog.objects.create(
                            user=request.user,
                            action='other',
                            ip_address=client_ip,
                            user_agent=request.META.get('HTTP_USER_AGENT', ''),
                            data={
                                'message': 'Superadmin access blocked due to IP restriction',
                                'path': request.path,
                                'allowed_ips': allowed_ips
                            }
                        )

                # If it's an AJAX request, return a 403 Forbidden response
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    return HttpResponseForbidden("You don't have access to the superadmin area.")

                # For regular requests, redirect to dashboard with a message
                if not ip_allowed and request.user.is_superuser:
                    messages.error(
                        request,
                        f"Access denied. Your IP address ({client_ip}) is not in the allowed list for superadmin access. "
                        f"This incident has been logged."
                    )
                else:
                    messages.error(
                        request,
                        "You don't have access to the superadmin area. This incident has been logged."
                    )
                return redirect('dashboard')

        # User has access or not accessing superadmin routes, continue with the request
        return self.get_response(request)

    def _get_client_ip(self, request):
        """Get the client IP address from the request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
