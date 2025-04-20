import json
import logging
from datetime import datetime

from django.contrib.auth.models import User
from django.db import models

logger = logging.getLogger('accessmanagement')

class SecurityEvent(models.Model):
    """
    Model for logging security events.
    This provides a comprehensive audit trail of security-related actions.
    """
    # Event types
    EVENT_LOGIN = 'login'
    EVENT_LOGOUT = 'logout'
    EVENT_LOGIN_FAILED = 'login_failed'
    EVENT_PERMISSION_DENIED = 'permission_denied'
    EVENT_PERMISSION_GRANTED = 'permission_granted'
    EVENT_PERMISSION_CHANGED = 'permission_changed'
    EVENT_PROFILE_CHANGED = 'profile_changed'
    EVENT_PASSWORD_CHANGED = 'password_changed'
    EVENT_PASSWORD_RESET = 'password_reset'
    EVENT_USER_CREATED = 'user_created'
    EVENT_USER_DELETED = 'user_deleted'
    EVENT_SENSITIVE_DATA_ACCESS = 'sensitive_data_access'
    
    EVENT_TYPES = [
        (EVENT_LOGIN, 'Login'),
        (EVENT_LOGOUT, 'Logout'),
        (EVENT_LOGIN_FAILED, 'Login Failed'),
        (EVENT_PERMISSION_DENIED, 'Permission Denied'),
        (EVENT_PERMISSION_GRANTED, 'Permission Granted'),
        (EVENT_PERMISSION_CHANGED, 'Permission Changed'),
        (EVENT_PROFILE_CHANGED, 'Profile Changed'),
        (EVENT_PASSWORD_CHANGED, 'Password Changed'),
        (EVENT_PASSWORD_RESET, 'Password Reset'),
        (EVENT_USER_CREATED, 'User Created'),
        (EVENT_USER_DELETED, 'User Deleted'),
        (EVENT_SENSITIVE_DATA_ACCESS, 'Sensitive Data Access'),
    ]
    
    # Event data
    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='security_events')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)
    resource = models.CharField(max_length=255, null=True, blank=True)  # URL, object, etc.
    details = models.JSONField(null=True, blank=True)  # Additional details as JSON
    
    class Meta:
        verbose_name_plural = 'Security Events'
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['timestamp']),
            models.Index(fields=['event_type']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        return f"{self.get_event_type_display()} - {self.user} - {self.timestamp}"
    
    @classmethod
    def log_event(cls, event_type, user=None, ip_address=None, user_agent=None, resource=None, details=None):
        """
        Log a security event.
        """
        try:
            event = cls.objects.create(
                event_type=event_type,
                user=user,
                ip_address=ip_address,
                user_agent=user_agent,
                resource=resource,
                details=details
            )
            
            # Also log to the security log file
            log_message = {
                'timestamp': datetime.now().isoformat(),
                'event_type': event_type,
                'user': user.username if user else None,
                'ip_address': ip_address,
                'resource': resource,
                'details': details
            }
            
            logger.info(f"SECURITY_EVENT: {json.dumps(log_message)}")
            
            return event
        except Exception as e:
            logger.error(f"Error logging security event: {str(e)}")
            return None


class SecurityAuditMiddleware:
    """
    Middleware to log security-related events.
    """
    def __init__(self, get_response):
        self.get_response = get_response
        
    def __call__(self, request):
        # Process the request
        response = self.get_response(request)
        
        # Log certain security events based on response status
        if hasattr(request, 'user') and request.user.is_authenticated:
            # Log 403 Forbidden responses
            if response.status_code == 403:
                SecurityEvent.log_event(
                    event_type=SecurityEvent.EVENT_PERMISSION_DENIED,
                    user=request.user,
                    ip_address=self._get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT'),
                    resource=request.path,
                    details={'method': request.method}
                )
                
            # Log access to sensitive endpoints
            if self._is_sensitive_endpoint(request.path):
                SecurityEvent.log_event(
                    event_type=SecurityEvent.EVENT_SENSITIVE_DATA_ACCESS,
                    user=request.user,
                    ip_address=self._get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT'),
                    resource=request.path,
                    details={'method': request.method}
                )
                
        return response
        
    def _get_client_ip(self, request):
        """Get the client IP address from the request."""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
        
    def _is_sensitive_endpoint(self, path):
        """Check if the path is a sensitive endpoint that should be logged."""
        sensitive_patterns = [
            '/admin/',
            '/api/users/',
            '/api/auth/',
            '/accessmanagement/',
            '/permissions/',
        ]
        
        return any(pattern in path for pattern in sensitive_patterns)


def setup_security_signals():
    """
    Set up signals for security events.
    This function should be called in the app's ready() method.
    """
    from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
    from django.db.models.signals import post_save, post_delete
    from django.dispatch import receiver
    
    @receiver(user_logged_in)
    def log_user_login(sender, request, user, **kwargs):
        SecurityEvent.log_event(
            event_type=SecurityEvent.EVENT_LOGIN,
            user=user,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT')
        )
    
    @receiver(user_logged_out)
    def log_user_logout(sender, request, user, **kwargs):
        if user:
            SecurityEvent.log_event(
                event_type=SecurityEvent.EVENT_LOGOUT,
                user=user,
                ip_address=request.META.get('REMOTE_ADDR'),
                user_agent=request.META.get('HTTP_USER_AGENT')
            )
    
    @receiver(user_login_failed)
    def log_user_login_failed(sender, credentials, request, **kwargs):
        SecurityEvent.log_event(
            event_type=SecurityEvent.EVENT_LOGIN_FAILED,
            ip_address=request.META.get('REMOTE_ADDR'),
            user_agent=request.META.get('HTTP_USER_AGENT'),
            details={'username': credentials.get('username', '')}
        )
    
    @receiver(post_save, sender=User)
    def log_user_changes(sender, instance, created, **kwargs):
        if created:
            SecurityEvent.log_event(
                event_type=SecurityEvent.EVENT_USER_CREATED,
                user=instance,
                details={'username': instance.username}
            )
    
    @receiver(post_delete, sender=User)
    def log_user_deletion(sender, instance, **kwargs):
        SecurityEvent.log_event(
            event_type=SecurityEvent.EVENT_USER_DELETED,
            details={'username': instance.username}
        )