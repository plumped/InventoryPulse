import logging

from django.conf import settings
from django.contrib import messages
from django.core.cache import cache
from django.shortcuts import redirect

logger = logging.getLogger('accessmanagement')

class LoginRateLimitMiddleware:
    """
    Middleware to implement rate limiting for login attempts.
    This helps prevent brute force attacks by limiting the number of login attempts
    from a single IP address within a specified timeframe.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Only apply rate limiting to login page
        if request.path == settings.LOGIN_URL and request.method == 'POST':
            # Get client IP
            client_ip = self._get_client_ip(request)
            
            # Get rate limit settings
            attempts = settings.LOGIN_RATE_LIMIT['attempts']
            timeframe = settings.LOGIN_RATE_LIMIT['timeframe']
            lockout_time = settings.LOGIN_RATE_LIMIT['lockout_time']
            
            # Check if IP is locked out
            lockout_key = f"login_lockout_{client_ip}"
            if cache.get(lockout_key):
                # IP is locked out
                logger.warning(f"Login attempt from locked out IP: {client_ip}")
                
                # Create audit log for lockout
                from core.models import AuditLog
                AuditLog.objects.create(
                    user=None,  # No user yet as this is a login attempt
                    action='other',
                    ip_address=client_ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    data={
                        'message': 'Login attempt from locked out IP',
                        'path': request.path,
                    }
                )
                
                # Calculate remaining lockout time
                lockout_expires = cache.ttl(lockout_key)
                minutes = int(lockout_expires / 60)
                seconds = lockout_expires % 60
                
                # Show message to user
                messages.error(
                    request,
                    f"Too many failed login attempts. Your IP has been temporarily blocked. "
                    f"Please try again in {minutes} minutes and {seconds} seconds."
                )
                
                # Redirect to login page (GET request)
                return redirect(settings.LOGIN_URL)
            
            # Check current attempt count
            attempts_key = f"login_attempts_{client_ip}"
            attempts_count = cache.get(attempts_key, 0)
            
            # Increment attempt count
            cache.set(attempts_key, attempts_count + 1, timeout=timeframe)
            
            # If too many attempts, lock out the IP
            if attempts_count + 1 >= attempts:
                logger.warning(f"IP {client_ip} locked out due to too many login attempts")
                
                # Create audit log for lockout
                from core.models import AuditLog
                AuditLog.objects.create(
                    user=None,  # No user yet as this is a login attempt
                    action='other',
                    ip_address=client_ip,
                    user_agent=request.META.get('HTTP_USER_AGENT', ''),
                    data={
                        'message': 'IP locked out due to too many login attempts',
                        'path': request.path,
                        'attempts': attempts_count + 1,
                        'timeframe_seconds': timeframe,
                        'lockout_seconds': lockout_time
                    }
                )
                
                # Lock out the IP
                cache.set(lockout_key, True, timeout=lockout_time)
                
                # Show message to user
                messages.error(
                    request,
                    f"Too many failed login attempts. Your IP has been temporarily blocked for {lockout_time // 60} minutes."
                )
                
                # Redirect to login page (GET request)
                return redirect(settings.LOGIN_URL)
        
        # Continue with the request
        response = self.get_response(request)
        
        # If this was a successful login, reset the attempt counter
        if request.path == settings.LOGIN_URL and request.method == 'POST' and hasattr(request, 'user') and request.user.is_authenticated:
            client_ip = self._get_client_ip(request)
            attempts_key = f"login_attempts_{client_ip}"
            cache.delete(attempts_key)
        
        return response

    def _get_client_ip(self, request):
        """Get the client IP address from the request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip