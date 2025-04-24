import traceback
import uuid
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.template.response import TemplateResponse

import logging
from core.utils.error import (
    BaseError
)

logger = logging.getLogger('core')

class RequestIDMiddleware:
    """
    Middleware that adds a unique request ID to each request.
    This ID can be used to track a request through the system and correlate log entries.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Generate a unique request ID
        request_id = str(uuid.uuid4())

        # Add it to the request object
        request.request_id = request_id

        # Add it to the thread-local storage for logging
        from threading import local
        _thread_locals = local()
        _thread_locals.request_id = request_id

        # Process the request
        response = self.get_response(request)

        # Add the request ID to the response headers
        response['X-Request-ID'] = request_id

        return response


def get_current_request_id():
    """
    Get the current request ID from thread-local storage.
    Returns None if no request ID is set.
    """
    from threading import local
    _thread_locals = local()
    return getattr(_thread_locals, 'request_id', None)


class ErrorLoggingMiddleware:
    """
    Middleware that catches and logs all unhandled exceptions.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            return self.get_response(request)
        except Exception as e:
            # Log the exception with request details
            self.log_exception(request, e)

            # Return an appropriate error response
            return self.handle_exception(request, e)

    def log_exception(self, request, exception):
        """
        Log the exception with detailed information about the request.
        """
        request_id = getattr(request, 'request_id', 'no-request-id')

        logger.error(
            f"Unhandled exception in request {request_id} to {request.method} {request.path}",
            extra={
                'request_id': request_id,
                'method': request.method,
                'path': request.path,
                'user_id': getattr(request.user, 'id', None),
                'username': getattr(request.user, 'username', None),
                'ip': request.META.get('REMOTE_ADDR'),
                'exception_type': type(exception).__name__,
                'exception_message': str(exception),
                'traceback': traceback.format_exc(),
            }
        )

    def handle_exception(self, request, exception):
        """
        Handle the exception and return an appropriate response.
        """
        # Get request ID
        request_id = getattr(request, 'request_id', None)

        # Handle custom exceptions
        if isinstance(exception, BaseError):
            status_code = exception.status_code
            error_code = exception.code
            error_message = exception.message
            error_details = exception.details
        else:
            # Default for standard exceptions
            status_code = 500
            error_code = 'internal_server_error'
            error_message = str(exception) if settings.DEBUG else 'An unexpected error occurred'
            error_details = {}

        # For API requests, return a JSON response
        if request.path.startswith('/api/'):
            response_data = {
                'error': error_code,
                'message': error_message,
                'request_id': request_id,
            }

            # Include details if available and in debug mode
            if error_details and settings.DEBUG:
                response_data['details'] = error_details

            return JsonResponse(response_data, status=status_code)

        # For regular requests, return an error page
        context = {
            'error_message': error_message,
            'request_id': request_id,
            'debug': settings.DEBUG,
            'status_code': status_code,
        }

        if settings.DEBUG:
            context['traceback'] = traceback.format_exc()
            context['error_details'] = error_details

        # Use appropriate error template based on status code
        template = f'error/{status_code}.html'

        # Fallback to 500.html if specific template doesn't exist
        try:
            from django.template.loader import get_template
            get_template(template)
        except:
            template = 'error/500.html'

        return TemplateResponse(
            request=request,
            template=template,
            context=context,
            status=status_code
        )


def exception_handler(func):
    """
    Decorator for view functions to handle exceptions.

    This decorator catches all exceptions raised by the decorated function and:
    1. Logs the exception with detailed context
    2. Returns an appropriate response based on the exception type and request type

    For custom exceptions (subclasses of BaseError), the response will include:
    - The exception's status code
    - The exception's error code
    - The exception's message
    - The exception's details (in debug mode)

    For standard exceptions, a generic 500 error response will be returned.
    """
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        try:
            return func(request, *args, **kwargs)
        except Exception as e:
            # Get request ID
            request_id = getattr(request, 'request_id', 'no-request-id')

            # Log the exception with context
            log_extra = {
                'request_id': request_id,
                'function': func.__name__,
                'exception_type': type(e).__name__,
                'exception_message': str(e),
                'traceback': traceback.format_exc(),
            }

            # Add user info if available
            if hasattr(request, 'user') and request.user.is_authenticated:
                log_extra.update({
                    'user_id': request.user.id,
                    'username': request.user.username,
                })

            logger.error(f"Exception in {func.__name__}: {str(e)}", extra=log_extra)

            # Handle custom exceptions
            if isinstance(e, BaseError):
                status_code = e.status_code
                error_code = e.code
                error_message = e.message
                error_details = e.details
            else:
                # Default for standard exceptions
                status_code = 500
                error_code = 'internal_server_error'
                error_message = str(e) if settings.DEBUG else 'An unexpected error occurred'
                error_details = {}

            # For API views, return a JSON response
            if request.path.startswith('/api/'):
                response_data = {
                    'error': error_code,
                    'message': error_message,
                    'request_id': request_id,
                }

                # Include details if available and in debug mode
                if error_details and settings.DEBUG:
                    response_data['details'] = error_details

                return JsonResponse(response_data, status=status_code)

            # For regular views, return an error page
            context = {
                'error_message': error_message,
                'request_id': request_id,
                'debug': settings.DEBUG,
                'status_code': status_code,
            }

            if settings.DEBUG:
                context['traceback'] = traceback.format_exc()
                context['error_details'] = error_details

            # Use appropriate error template based on status code
            template = f'error/{status_code}.html'

            # Fallback to 500.html if specific template doesn't exist
            try:
                from django.template.loader import get_template
                get_template(template)
            except:
                template = 'error/500.html'

            return TemplateResponse(
                request=request,
                template=template,
                context=context,
                status=status_code
            )

    return wrapper
