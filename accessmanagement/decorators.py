# accessmanagement/decorators.py
from functools import wraps
from django.contrib.auth.decorators import user_passes_test
from django.http import HttpResponseForbidden
from .permissions import has_permission


def permission_required(area, action):
    """
    Decorator for views to check if the user has the required permission.
    
    Example:
    @permission_required('inventory', 'view')
    def my_view(request):
        # ...
    """
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if has_permission(request.user, area, action):
                return view_func(request, *args, **kwargs)
            return HttpResponseForbidden("Sie haben keine Berechtigung für diese Aktion.")
        
        return _wrapped_view
    
    return decorator


def is_admin(user):
    """Check if user has admin privileges."""
    return user.is_superuser or user.has_perm('accessmanagement.access_admin')