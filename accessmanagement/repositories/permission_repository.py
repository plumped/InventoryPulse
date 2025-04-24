"""
Repository for ObjectPermission and PermissionDashboard models.

This module contains the ObjectPermissionRepository and PermissionDashboardRepository classes
that handle all data access operations related to permissions.
"""

from django.contrib.contenttypes.models import ContentType

from .base import BaseRepository
from ..models.permission_models import ObjectPermission, PermissionDashboard


class ObjectPermissionRepository(BaseRepository):
    """Repository for ObjectPermission model."""
    
    model_class = ObjectPermission
    
    def get_permission_by_id(self, permission_id):
        """
        Get an object permission by its ID.
        
        Args:
            permission_id: The ID of the object permission
            
        Returns:
            The object permission with the given ID
            
        Raises:
            ObjectPermission.DoesNotExist: If the object permission does not exist
        """
        return self.get_by_id(permission_id)
    
    def get_permissions_for_object(self, obj):
        """
        Get all permissions for an object.
        
        Args:
            obj: The object
            
        Returns:
            QuerySet of object permissions for the object
        """
        content_type = ContentType.objects.get_for_model(obj)
        return self.filter(content_type=content_type, object_id=obj.id)
    
    def get_permissions_for_user(self, user):
        """
        Get all permissions for a user.
        
        Args:
            user: The user object or user ID
            
        Returns:
            QuerySet of object permissions for the user
        """
        if isinstance(user, int):
            return self.filter(user_id=user)
        return self.filter(user=user)
    
    def get_permissions_for_department(self, department):
        """
        Get all permissions for a department.
        
        Args:
            department: The department object or department ID
            
        Returns:
            QuerySet of object permissions for the department
        """
        if isinstance(department, int):
            return self.filter(department_id=department)
        return self.filter(department=department)
    
    def get_permission_for_user_and_object(self, user, obj):
        """
        Get a permission for a user and object.
        
        Args:
            user: The user object or user ID
            obj: The object
            
        Returns:
            The object permission for the user and object or None if it doesn't exist
        """
        content_type = ContentType.objects.get_for_model(obj)
        
        if isinstance(user, int):
            return self.filter(user_id=user, content_type=content_type, object_id=obj.id).first()
        return self.filter(user=user, content_type=content_type, object_id=obj.id).first()
    
    def get_permission_for_department_and_object(self, department, obj):
        """
        Get a permission for a department and object.
        
        Args:
            department: The department object or department ID
            obj: The object
            
        Returns:
            The object permission for the department and object or None if it doesn't exist
        """
        content_type = ContentType.objects.get_for_model(obj)
        
        if isinstance(department, int):
            return self.filter(department_id=department, content_type=content_type, object_id=obj.id).first()
        return self.filter(department=department, content_type=content_type, object_id=obj.id).first()
    
    def create_permission_for_user(self, user, obj, **kwargs):
        """
        Create a new object permission for a user.
        
        Args:
            user: The user object or user ID
            obj: The object
            **kwargs: Additional permission attributes
            
        Returns:
            The created object permission
        """
        content_type = ContentType.objects.get_for_model(obj)
        
        if isinstance(user, int):
            user_id = user
        else:
            user_id = user.id
            
        return self.create(
            user_id=user_id,
            department=None,
            content_type=content_type,
            object_id=obj.id,
            **kwargs
        )
    
    def create_permission_for_department(self, department, obj, **kwargs):
        """
        Create a new object permission for a department.
        
        Args:
            department: The department object or department ID
            obj: The object
            **kwargs: Additional permission attributes
            
        Returns:
            The created object permission
        """
        content_type = ContentType.objects.get_for_model(obj)
        
        if isinstance(department, int):
            department_id = department
        else:
            department_id = department.id
            
        return self.create(
            user=None,
            department_id=department_id,
            content_type=content_type,
            object_id=obj.id,
            **kwargs
        )
    
    def update_permission(self, permission, **kwargs):
        """
        Update an existing object permission.
        
        Args:
            permission: The object permission to update
            **kwargs: Attributes to update
            
        Returns:
            The updated object permission
        """
        return self.update(permission, **kwargs)
    
    def delete_permission(self, permission):
        """
        Delete an object permission.
        
        Args:
            permission: The object permission to delete
        """
        self.delete(permission)
    
    def has_object_permission(self, user, obj, permission_type='view'):
        """
        Check if a user has permission for an object.
        
        Args:
            user: The user object
            obj: The object
            permission_type: The type of permission to check ('view', 'edit', or 'delete')
            
        Returns:
            True if the user has permission, False otherwise
        """
        return ObjectPermission.has_object_permission(user, obj, permission_type)


class PermissionDashboardRepository(BaseRepository):
    """Repository for PermissionDashboard model."""
    
    model_class = PermissionDashboard
    
    def get_dashboard_by_id(self, dashboard_id):
        """
        Get a permission dashboard by its ID.
        
        Args:
            dashboard_id: The ID of the permission dashboard
            
        Returns:
            The permission dashboard with the given ID
            
        Raises:
            PermissionDashboard.DoesNotExist: If the permission dashboard does not exist
        """
        return self.get_by_id(dashboard_id)
    
    def get_all_dashboards(self):
        """
        Get all permission dashboards.
        
        Returns:
            QuerySet of all permission dashboards
        """
        return self.get_all()
    
    def create_dashboard(self, **kwargs):
        """
        Create a new permission dashboard.
        
        Args:
            **kwargs: Dashboard attributes
            
        Returns:
            The created permission dashboard
        """
        return self.create(**kwargs)
    
    def update_dashboard(self, dashboard, **kwargs):
        """
        Update an existing permission dashboard.
        
        Args:
            dashboard: The permission dashboard to update
            **kwargs: Attributes to update
            
        Returns:
            The updated permission dashboard
        """
        return self.update(dashboard, **kwargs)
    
    def delete_dashboard(self, dashboard):
        """
        Delete a permission dashboard.
        
        Args:
            dashboard: The permission dashboard to delete
        """
        self.delete(dashboard)