"""
Custom exception classes for the application.

This module defines custom exception classes that can be used throughout the application
to represent different types of errors. These exceptions can be caught and handled
appropriately by the error handling middleware and decorators.
"""

from django.utils.translation import gettext_lazy as _


class BaseError(Exception):
    """
    Base class for all custom exceptions in the application.
    
    Attributes:
        message (str): Human-readable error message
        code (str): Error code for programmatic identification
        status_code (int): HTTP status code to use in API responses
        details (dict): Additional details about the error
    """
    default_message = _("An error occurred")
    default_code = "error"
    default_status_code = 500
    
    def __init__(self, message=None, code=None, status_code=None, details=None):
        self.message = message or self.default_message
        self.code = code or self.default_code
        self.status_code = status_code or self.default_status_code
        self.details = details or {}
        
        super().__init__(self.message)


class ValidationError(BaseError):
    """
    Exception raised when data validation fails.
    """
    default_message = _("Invalid data provided")
    default_code = "validation_error"
    default_status_code = 400


class PermissionDeniedError(BaseError):
    """
    Exception raised when a user doesn't have permission to perform an action.
    """
    default_message = _("You don't have permission to perform this action")
    default_code = "permission_denied"
    default_status_code = 403


class NotFoundError(BaseError):
    """
    Exception raised when a requested resource is not found.
    """
    default_message = _("The requested resource was not found")
    default_code = "not_found"
    default_status_code = 404


class ConflictError(BaseError):
    """
    Exception raised when there's a conflict with the current state of the resource.
    """
    default_message = _("The request conflicts with the current state of the resource")
    default_code = "conflict"
    default_status_code = 409


class ServiceUnavailableError(BaseError):
    """
    Exception raised when a service is temporarily unavailable.
    """
    default_message = _("The service is temporarily unavailable")
    default_code = "service_unavailable"
    default_status_code = 503


class DatabaseError(BaseError):
    """
    Exception raised when a database operation fails.
    """
    default_message = _("A database error occurred")
    default_code = "database_error"
    default_status_code = 500


class ExternalServiceError(BaseError):
    """
    Exception raised when an external service call fails.
    """
    default_message = _("An external service error occurred")
    default_code = "external_service_error"
    default_status_code = 502


class BusinessLogicError(BaseError):
    """
    Exception raised when a business rule is violated.
    """
    default_message = _("A business rule was violated")
    default_code = "business_logic_error"
    default_status_code = 400