"""
Custom exception handlers for the InventoryPulse API.

This module provides exception handlers that convert Django REST framework
exceptions into standardized API responses.
"""
import logging

from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.http import Http404
from rest_framework import exceptions
from rest_framework.views import set_rollback

from .response import APIResponse

logger = logging.getLogger('api')


def api_exception_handler(exc, context):
    """
    Custom exception handler that returns standardized API responses.
    
    Args:
        exc: The exception
        context: The context of the exception
        
    Returns:
        APIResponse: A standardized API response
    """
    # Log the exception
    logger.error(f"Exception in {context['view'].__class__.__name__}: {str(exc)}")
    
    # Set rollback flag to prevent transaction commit
    set_rollback()
    
    # Handle Django exceptions
    if isinstance(exc, Http404):
        return APIResponse(
            message="Resource not found",
            status=404
        )
    
    if isinstance(exc, ObjectDoesNotExist):
        return APIResponse(
            message=f"{exc.__class__.__name__} not found",
            status=404
        )
    
    if isinstance(exc, PermissionDenied):
        return APIResponse(
            message="Permission denied",
            status=403
        )
    
    # Handle DRF exceptions
    if isinstance(exc, exceptions.APIException):
        headers = {}
        if getattr(exc, 'auth_header', None):
            headers['WWW-Authenticate'] = exc.auth_header
        if getattr(exc, 'wait', None):
            headers['Retry-After'] = '%d' % exc.wait
        
        if isinstance(exc, exceptions.ValidationError):
            return APIResponse(
                message="Validation error",
                errors=exc.detail,
                status=exc.status_code,
                headers=headers
            )
        
        if isinstance(exc, exceptions.NotAuthenticated):
            return APIResponse(
                message="Authentication required",
                status=exc.status_code,
                headers=headers
            )
        
        if isinstance(exc, exceptions.AuthenticationFailed):
            return APIResponse(
                message="Authentication failed",
                status=exc.status_code,
                headers=headers
            )
        
        if isinstance(exc, exceptions.PermissionDenied):
            return APIResponse(
                message="Permission denied",
                status=exc.status_code,
                headers=headers
            )
        
        if isinstance(exc, exceptions.NotFound):
            return APIResponse(
                message="Resource not found",
                status=exc.status_code,
                headers=headers
            )
        
        if isinstance(exc, exceptions.MethodNotAllowed):
            return APIResponse(
                message=f"Method {context['request'].method} not allowed",
                status=exc.status_code,
                headers=headers
            )
        
        if isinstance(exc, exceptions.NotAcceptable):
            return APIResponse(
                message="Not acceptable",
                status=exc.status_code,
                headers=headers
            )
        
        if isinstance(exc, exceptions.UnsupportedMediaType):
            return APIResponse(
                message="Unsupported media type",
                status=exc.status_code,
                headers=headers
            )
        
        if isinstance(exc, exceptions.Throttled):
            return APIResponse(
                message="Request throttled",
                errors=[f"Request was throttled. Expected available in {exc.wait} seconds."],
                status=exc.status_code,
                headers=headers
            )
        
        # Generic API exception
        return APIResponse(
            message=str(exc),
            status=exc.status_code,
            headers=headers
        )
    
    # Handle unexpected exceptions
    logger.exception("Unexpected exception", exc_info=exc)
    return APIResponse(
        message="Internal server error",
        status=500
    )