"""
Error handling utility functions.

This package contains utility functions related to error handling and exception management.
"""

from .exceptions import (
    BaseError,
    ValidationError,
    PermissionDeniedError,
    NotFoundError,
    ConflictError,
    ServiceUnavailableError,
    DatabaseError,
    ExternalServiceError,
    BusinessLogicError,
)

from .handlers import (
    api_error_response,
    log_exception,
    transaction_handler,
    api_view_handler,
    service_call_handler,
)

__all__ = [
    # Exception classes
    'BaseError',
    'ValidationError',
    'PermissionDeniedError',
    'NotFoundError',
    'ConflictError',
    'ServiceUnavailableError',
    'DatabaseError',
    'ExternalServiceError',
    'BusinessLogicError',

    # Handler functions
    'api_error_response',
    'log_exception',
    'transaction_handler',
    'api_view_handler',
    'service_call_handler',
]
