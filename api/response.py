"""
Standardized API response formats for the InventoryPulse application.

This module provides consistent response formats for all API endpoints.
"""
from rest_framework import status
from rest_framework.response import Response


class APIResponse(Response):
    """
    Custom API response class that standardizes the response format.
    
    All responses include:
    - success: boolean indicating if the request was successful
    - message: string message describing the result
    - data: the actual response data (can be null)
    - errors: array of error messages (only present if success is false)
    - meta: metadata about the response (pagination, etc.)
    """
    
    def __init__(self, data=None, message=None, errors=None, meta=None, 
                 status=status.HTTP_200_OK, **kwargs):
        """
        Initialize the response with standardized format.
        
        Args:
            data: The response data
            message: A message describing the result
            errors: List of error messages
            meta: Metadata about the response
            status: HTTP status code
            **kwargs: Additional arguments to pass to the parent class
        """
        # Default values
        success = status < 400
        if message is None:
            message = "Success" if success else "Error"
        
        # Construct the response data
        response_data = {
            "success": success,
            "message": message,
            "data": data
        }
        
        # Add errors if present
        if errors:
            response_data["errors"] = errors if isinstance(errors, list) else [errors]
        
        # Add metadata if present
        if meta:
            response_data["meta"] = meta
        
        super().__init__(data=response_data, status=status, **kwargs)


def success_response(data=None, message="Success", meta=None, status=status.HTTP_200_OK):
    """
    Create a success response.
    
    Args:
        data: The response data
        message: A message describing the result
        meta: Metadata about the response
        status: HTTP status code
        
    Returns:
        APIResponse: A standardized success response
    """
    return APIResponse(data=data, message=message, meta=meta, status=status)


def error_response(errors, message="Error", status=status.HTTP_400_BAD_REQUEST):
    """
    Create an error response.
    
    Args:
        errors: List of error messages or a single error message
        message: A message describing the error
        status: HTTP status code
        
    Returns:
        APIResponse: A standardized error response
    """
    return APIResponse(errors=errors, message=message, status=status)


def not_found_response(message="Resource not found"):
    """
    Create a not found response.
    
    Args:
        message: A message describing the error
        
    Returns:
        APIResponse: A standardized not found response
    """
    return APIResponse(message=message, status=status.HTTP_404_NOT_FOUND)


def validation_error_response(errors, message="Validation error"):
    """
    Create a validation error response.
    
    Args:
        errors: List of validation error messages or a single error message
        message: A message describing the error
        
    Returns:
        APIResponse: A standardized validation error response
    """
    return APIResponse(errors=errors, message=message, status=status.HTTP_400_BAD_REQUEST)


def unauthorized_response(message="Unauthorized"):
    """
    Create an unauthorized response.
    
    Args:
        message: A message describing the error
        
    Returns:
        APIResponse: A standardized unauthorized response
    """
    return APIResponse(message=message, status=status.HTTP_401_UNAUTHORIZED)


def forbidden_response(message="Forbidden"):
    """
    Create a forbidden response.
    
    Args:
        message: A message describing the error
        
    Returns:
        APIResponse: A standardized forbidden response
    """
    return APIResponse(message=message, status=status.HTTP_403_FORBIDDEN)


def server_error_response(message="Internal server error"):
    """
    Create a server error response.
    
    Args:
        message: A message describing the error
        
    Returns:
        APIResponse: A standardized server error response
    """
    return APIResponse(message=message, status=status.HTTP_500_INTERNAL_SERVER_ERROR)