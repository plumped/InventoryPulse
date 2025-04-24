"""
Repository for WarehouseAccess model.

This module contains the WarehouseAccessRepository class that handles all data access
operations related to the WarehouseAccess model.
"""

from django.core.cache import cache

from .base import BaseRepository
from ..models.warehouse_access_models import WarehouseAccess


class WarehouseAccessRepository(BaseRepository):
    """Repository for WarehouseAccess model."""
    
    model_class = WarehouseAccess
    
    def get_access_by_id(self, access_id):
        """
        Get a warehouse access by its ID.
        
        Args:
            access_id: The ID of the warehouse access
            
        Returns:
            The warehouse access with the given ID
            
        Raises:
            WarehouseAccess.DoesNotExist: If the warehouse access does not exist
        """
        return self.get_by_id(access_id)
    
    def get_access_by_warehouse_and_department(self, warehouse, department):
        """
        Get a warehouse access by warehouse and department.
        
        Args:
            warehouse: The warehouse object or warehouse ID
            department: The department object or department ID
            
        Returns:
            The warehouse access for the given warehouse and department or None if it doesn't exist
        """
        if isinstance(warehouse, int):
            warehouse_id = warehouse
        else:
            warehouse_id = warehouse.id
            
        if isinstance(department, int):
            department_id = department
        else:
            department_id = department.id
            
        return self.filter(warehouse_id=warehouse_id, department_id=department_id).first()
    
    def get_access_for_warehouse(self, warehouse):
        """
        Get all access rights for a warehouse.
        
        Args:
            warehouse: The warehouse object or warehouse ID
            
        Returns:
            QuerySet of warehouse access rights for the warehouse
        """
        if isinstance(warehouse, int):
            return self.filter(warehouse_id=warehouse)
        return self.filter(warehouse=warehouse)
    
    def get_access_for_department(self, department):
        """
        Get all access rights for a department.
        
        Args:
            department: The department object or department ID
            
        Returns:
            QuerySet of warehouse access rights for the department
        """
        if isinstance(department, int):
            return self.filter(department_id=department)
        return self.filter(department=department)
    
    def create_access(self, warehouse, department, **kwargs):
        """
        Create a new warehouse access.
        
        Args:
            warehouse: The warehouse object or warehouse ID
            department: The department object or department ID
            **kwargs: Additional access attributes
            
        Returns:
            The created warehouse access
        """
        if isinstance(warehouse, int):
            warehouse_id = warehouse
        else:
            warehouse_id = warehouse.id
            
        if isinstance(department, int):
            department_id = department
        else:
            department_id = department.id
            
        return self.create(warehouse_id=warehouse_id, department_id=department_id, **kwargs)
    
    def update_access(self, access, **kwargs):
        """
        Update an existing warehouse access.
        
        Args:
            access: The warehouse access to update
            **kwargs: Attributes to update
            
        Returns:
            The updated warehouse access
        """
        # Clear cache for this access
        self._clear_access_cache(access)
        
        return self.update(access, **kwargs)
    
    def delete_access(self, access):
        """
        Delete a warehouse access.
        
        Args:
            access: The warehouse access to delete
        """
        # Clear cache for this access
        self._clear_access_cache(access)
        
        self.delete(access)
    
    def has_access(self, user, warehouse, permission_type='view'):
        """
        Check if a user has access to a specific warehouse.
        
        Args:
            user: The user object
            warehouse: The warehouse object
            permission_type: The type of permission to check ('view', 'edit', or 'manage_stock')
            
        Returns:
            True if the user has access, False otherwise
        """
        return WarehouseAccess.has_access(user, warehouse, permission_type)
    
    def _clear_access_cache(self, access):
        """
        Clear cache for a warehouse access.
        
        Args:
            access: The warehouse access
        """
        # Clear cache for all users that might have access to this warehouse through this department
        from ..models.user_models import UserProfile
        
        # Get all users in the department
        user_profiles = UserProfile.objects.filter(departments=access.department)
        
        for profile in user_profiles:
            # Clear cache for all permission types
            for permission_type in ['view', 'edit', 'manage_stock']:
                cache_key = f"warehouse_access:{profile.user.id}:{access.warehouse.id}:{permission_type}"
                cache.delete(cache_key)