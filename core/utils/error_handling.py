import logging
import traceback
import uuid
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.template.response import TemplateResponse
from rest_framework import status

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
        # For API requests, return a JSON response
        if request.path.startswith('/api/'):
            return JsonResponse({
                'error': 'Internal Server Error',
                'message': str(exception) if settings.DEBUG else 'An unexpected error occurred',
                'request_id': getattr(request, 'request_id', None),
            }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # For regular requests, return an error page
        context = {
            'error_message': str(exception) if settings.DEBUG else 'An unexpected error occurred',
            'request_id': getattr(request, 'request_id', None),
            'debug': settings.DEBUG,
        }
        
        if settings.DEBUG:
            context['traceback'] = traceback.format_exc()
        
        return TemplateResponse(
            request=request,
            template='error/500.html',
            context=context,
            status=500
        )


def exception_handler(func):
    """
    Decorator for view functions to handle exceptions.
    """
    @wraps(func)
    def wrapper(request, *args, **kwargs):
        try:
            return func(request, *args, **kwargs)
        except Exception as e:
            # Log the exception
            request_id = getattr(request, 'request_id', 'no-request-id')
            
            logger.error(
                f"Exception in {func.__name__}: {str(e)}",
                extra={
                    'request_id': request_id,
                    'function': func.__name__,
                    'exception_type': type(e).__name__,
                    'exception_message': str(e),
                    'traceback': traceback.format_exc(),
                }
            )
            
            # For API views, return a JSON response
            if request.path.startswith('/api/'):
                return JsonResponse({
                    'error': type(e).__name__,
                    'message': str(e) if settings.DEBUG else 'An unexpected error occurred',
                    'request_id': request_id,
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
            
            # For regular views, return an error page
            context = {
                'error_message': str(e) if settings.DEBUG else 'An unexpected error occurred',
                'request_id': request_id,
                'debug': settings.DEBUG,
            }
            
            if settings.DEBUG:
                context['traceback'] = traceback.format_exc()
            
            return TemplateResponse(
                request=request,
                template='error/500.html',
                context=context,
                status=500
            )
    
    return wrapper