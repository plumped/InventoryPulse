"""
Error handling utility functions.

This module provides utility functions for common error handling patterns.
"""

import logging
import traceback
from functools import wraps

from django.conf import settings
from django.db import transaction
from django.http import JsonResponse

from .exceptions import (
    BaseError, DatabaseError, ExternalServiceError
)

logger = logging.getLogger('core')


def api_error_response(exception, request_id=None):
    """
    Create a standardized error response for API endpoints.
    
    Args:
        exception: The exception that occurred
        request_id: The ID of the request (optional)
        
    Returns:
        A JsonResponse with standardized error format
    """
    if isinstance(exception, BaseError):
        status_code = exception.status_code
        error_code = exception.code
        error_message = exception.message
        error_details = exception.details
    else:
        status_code = 500
        error_code = 'internal_server_error'
        error_message = str(exception) if settings.DEBUG else 'An unexpected error occurred'
        error_details = {}
    
    response_data = {
        'error': error_code,
        'message': error_message,
    }
    
    if request_id:
        response_data['request_id'] = request_id
        
    if error_details and settings.DEBUG:
        response_data['details'] = error_details
        
    return JsonResponse(response_data, status=status_code)


def log_exception(exception, module=None, function=None, extra_context=None):
    """
    Log an exception with detailed context.
    
    Args:
        exception: The exception to log
        module: The module where the exception occurred (optional)
        function: The function where the exception occurred (optional)
        extra_context: Additional context to include in the log (optional)
    """
    log_data = {
        'exception_type': type(exception).__name__,
        'exception_message': str(exception),
        'traceback': traceback.format_exc(),
    }
    
    if module:
        log_data['module'] = module
        
    if function:
        log_data['function'] = function
        
    if extra_context:
        log_data.update(extra_context)
    
    logger.error(
        f"Exception in {module or ''}.{function or ''}: {str(exception)}",
        extra=log_data
    )


def transaction_handler(func):
    """
    Decorator for functions that need to be executed in a transaction.
    
    This decorator wraps the function in a transaction and handles database errors.
    If a database error occurs, it rolls back the transaction and raises a DatabaseError.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            with transaction.atomic():
                return func(*args, **kwargs)
        except Exception as e:
            # Log the exception
            log_exception(
                exception=e,
                module=func.__module__,
                function=func.__name__
            )
            
            # If it's already a BaseError, re-raise it
            if isinstance(e, BaseError):
                raise
                
            # Otherwise, wrap it in a DatabaseError
            raise DatabaseError(
                message=f"Database operation failed: {str(e)}",
                details={'original_exception': str(e)}
            ) from e
    
    return wrapper


def api_view_handler(func):
    """
    Decorator for API view functions.
    
    This decorator catches all exceptions raised by the decorated function and:
    1. Logs the exception with detailed context
    2. Returns a standardized JSON response based on the exception type
    """
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        try:
            return func(request, *args, **kwargs)
        except Exception as e:
            # Get request ID
            request_id = getattr(request, 'request_id', None)
            
            # Log the exception
            log_extra = {
                'request_id': request_id,
                'path': request.path,
                'method': request.method,
            }
            
            # Add user info if available
            if hasattr(request, 'user') and request.user.is_authenticated:
                log_extra.update({
                    'user_id': request.user.id,
                    'username': request.user.username,
                })
            
            log_exception(
                exception=e,
                module=func.__module__,
                function=func.__name__,
                extra_context=log_extra
            )
            
            # Return a standardized error response
            return api_error_response(e, request_id)
    
    return wrapper


def service_call_handler(service_name):
    """
    Decorator for functions that call external services.
    
    This decorator catches exceptions raised when calling external services and
    wraps them in an ExternalServiceError with additional context.
    
    Args:
        service_name: The name of the external service being called
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Log the exception
                log_exception(
                    exception=e,
                    module=func.__module__,
                    function=func.__name__,
                    extra_context={'service_name': service_name}
                )
                
                # If it's already a BaseError, re-raise it
                if isinstance(e, BaseError):
                    raise
                    
                # Otherwise, wrap it in an ExternalServiceError
                raise ExternalServiceError(
                    message=f"Error calling {service_name}: {str(e)}",
                    details={
                        'service_name': service_name,
                        'original_exception': str(e)
                    }
                ) from e
        
        return wrapper
    
    return decorator