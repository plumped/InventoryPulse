import functools
import inspect
import logging

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType

from core.models import AuditLog

logger = logging.getLogger('core')


def log_audit(action, user=None, obj=None, request=None, data=None, before_state=None, after_state=None):
    """
    Log an audit entry for a sensitive operation.

    Args:
        action (str): The type of action being performed
        user (User): The user performing the action
        obj: The object being affected
        request: The HTTP request
        data (dict): Additional data about the action
        before_state (dict): The state of the object before the action
        after_state (dict): The state of the object after the action

    Returns:
        AuditLog: The created audit log entry
    """
    try:
        # Create the audit log entry
        audit_log = AuditLog(
            user=user,
            action=action,
            data=data,
            before_state=before_state,
            after_state=after_state,
        )

        # Add request information if available
        if request:
            audit_log.ip_address = request.META.get('REMOTE_ADDR')
            audit_log.user_agent = request.META.get('HTTP_USER_AGENT')

            # If user is not provided, try to get it from the request
            if user is None and hasattr(request, 'user') and request.user.is_authenticated:
                audit_log.user = request.user

        # Add object information if available
        if obj:
            content_type = ContentType.objects.get_for_model(obj)
            audit_log.content_type = content_type
            audit_log.object_id = obj.pk

        # Save the audit log
        audit_log.save()

        return audit_log
    except Exception as e:
        logger.error(f"Error logging audit: {str(e)}")
        return None


def audit_sensitive_operation(action=None, include_args=False, exclude_fields=None):
    """
    Decorator for auditing sensitive operations.

    Args:
        action (str): The type of action being performed
        include_args (bool): Whether to include function arguments in the audit log
        exclude_fields (list): Fields to exclude from the audit log

    Returns:
        function: The decorated function
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # Determine the action type
            action_type = action or func.__name__

            # Get the user and request from the arguments
            user = None
            request = None
            obj = None

            # Try to find the user and request in the arguments
            for arg in args:
                if isinstance(arg, User):
                    user = arg
                elif hasattr(arg, 'user') and hasattr(arg, 'META'):
                    request = arg
                    if hasattr(request, 'user') and request.user.is_authenticated:
                        user = request.user

            # Try to find the user and request in the keyword arguments
            if 'user' in kwargs and isinstance(kwargs['user'], User):
                user = kwargs['user']
            if 'request' in kwargs and hasattr(kwargs['request'], 'META'):
                request = kwargs['request']
                if hasattr(request, 'user') and request.user.is_authenticated and user is None:
                    user = request.user

            # Try to find the object in the arguments
            for arg in args:
                if hasattr(arg, 'pk') and not isinstance(arg, User) and not hasattr(arg, 'META'):
                    obj = arg
                    break

            # Try to find the object in the keyword arguments
            for key, value in kwargs.items():
                if hasattr(value, 'pk') and not isinstance(value, User) and not hasattr(value, 'META'):
                    obj = value
                    break

            # Prepare data for the audit log
            data = {}

            # Include function arguments if requested
            if include_args:
                # Get the function signature
                sig = inspect.signature(func)

                # Get the parameter names
                param_names = list(sig.parameters.keys())

                # Map positional arguments to parameter names
                for i, arg in enumerate(args):
                    if i < len(param_names):
                        param_name = param_names[i]
                        # Skip request, user, and object
                        if param_name not in ['request', 'user'] and arg is not obj:
                            # Convert to string to ensure it can be serialized
                            data[param_name] = str(arg)

                # Add keyword arguments
                for key, value in kwargs.items():
                    # Skip request, user, and object
                    if key not in ['request', 'user'] and value is not obj:
                        # Convert to string to ensure it can be serialized
                        data[key] = str(value)

            # Exclude specified fields
            if exclude_fields:
                for field in exclude_fields:
                    if field in data:
                        del data[field]

            # Get the state of the object before the operation
            before_state = None
            if obj and hasattr(obj, '__dict__'):
                before_state = {
                    k: str(v) for k, v in obj.__dict__.items()
                    if not k.startswith('_') and k not in (exclude_fields or [])
                }

            # Call the original function
            result = func(*args, **kwargs)

            # Get the state of the object after the operation
            after_state = None
            if obj and hasattr(obj, '__dict__'):
                after_state = {
                    k: str(v) for k, v in obj.__dict__.items()
                    if not k.startswith('_') and k not in (exclude_fields or [])
                }

            # Log the audit entry
            log_audit(
                action=action_type,
                user=user,
                obj=obj,
                request=request,
                data=data,
                before_state=before_state,
                after_state=after_state,
            )

            return result

        return wrapper

    return decorator
