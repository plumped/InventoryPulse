import logging
import re

from django.http import HttpResponseForbidden

from .models import WarehouseAccess

logger = logging.getLogger('accessmanagement')

class WarehouseAccessMiddleware:
    """
    Middleware to check warehouse access permissions globally.
    This middleware checks if the user has access to the warehouse specified in the URL.
    """
    
    def __init__(self, get_response):
        self.get_response = get_response
        # Compile regex patterns for URL paths that contain warehouse IDs
        self.warehouse_url_patterns = [
            re.compile(r'^/inventory/warehouse/(?P<warehouse_id>\d+)/'),
            re.compile(r'^/api/warehouses/(?P<warehouse_id>\d+)/'),
            # Add more patterns as needed
        ]
        
    def __call__(self, request):
        # Skip middleware for unauthenticated users (they'll be redirected to login)
        if not request.user.is_authenticated:
            return self.get_response(request)
            
        # Skip middleware for superusers (they have access to everything)
        if request.user.is_superuser:
            return self.get_response(request)
            
        # Check if the URL contains a warehouse ID
        warehouse_id = None
        permission_type = 'view'  # Default permission type
        
        # Extract warehouse ID from URL
        for pattern in self.warehouse_url_patterns:
            match = pattern.match(request.path)
            if match:
                warehouse_id = match.group('warehouse_id')
                break
                
        # If no warehouse ID found, continue with the request
        if not warehouse_id:
            return self.get_response(request)
            
        # Determine permission type based on request method
        if request.method in ['POST', 'PUT', 'PATCH']:
            permission_type = 'edit'
        elif 'manage_stock' in request.path or 'inventory/adjust' in request.path:
            permission_type = 'manage_stock'
            
        try:
            # Get the warehouse object
            from inventory.models import Warehouse
            warehouse = Warehouse.objects.get(id=warehouse_id)
            
            # Check if user has access
            if not WarehouseAccess.has_access(request.user, warehouse, permission_type):
                logger.warning(
                    f"Access denied: User {request.user.username} attempted to access warehouse {warehouse.name} "
                    f"with permission type {permission_type}"
                )
                return HttpResponseForbidden("You don't have permission to access this warehouse.")
                
        except Exception as e:
            logger.error(f"Error in WarehouseAccessMiddleware: {str(e)}")
            # Continue with the request in case of error
            
        # Continue with the request if access is granted
        return self.get_response(request)