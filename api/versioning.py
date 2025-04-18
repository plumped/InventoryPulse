"""
API versioning configuration for the InventoryPulse application.

This module provides versioning classes and utilities for the API.
"""
from rest_framework.versioning import URLPathVersioning, NamespaceVersioning


class InventoryPulseAPIVersioning(URLPathVersioning):
    """
    Custom API versioning class that uses URL path versioning.
    
    Example: /api/v1/products/, /api/v2/products/
    """
    default_version = 'v1'
    allowed_versions = ['v1', 'v2']
    version_param = 'version'


class InventoryPulseNamespaceVersioning(NamespaceVersioning):
    """
    Custom API versioning class that uses namespace versioning.
    
    This is used as a fallback for views that don't use URL path versioning.
    """
    default_version = 'v1'
    allowed_versions = ['v1', 'v2']