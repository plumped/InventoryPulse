"""
Repository for RoleHierarchy model.

This module contains the RoleHierarchyRepository class that handles all data access
operations related to the RoleHierarchy model.
"""

from django.contrib.auth.models import Group

from .base import BaseRepository
from ..models.role_models import RoleHierarchy


class RoleHierarchyRepository(BaseRepository):
    """Repository for RoleHierarchy model."""
    
    model_class = RoleHierarchy
    
    def get_hierarchy_by_id(self, hierarchy_id):
        """
        Get a role hierarchy by its ID.
        
        Args:
            hierarchy_id: The ID of the role hierarchy
            
        Returns:
            The role hierarchy with the given ID
            
        Raises:
            RoleHierarchy.DoesNotExist: If the role hierarchy does not exist
        """
        return self.get_by_id(hierarchy_id)
    
    def get_hierarchy_by_parent_and_child(self, parent_role, child_role):
        """
        Get a role hierarchy by parent and child roles.
        
        Args:
            parent_role: The parent role object or role ID
            child_role: The child role object or role ID
            
        Returns:
            The role hierarchy for the given parent and child roles or None if it doesn't exist
        """
        if isinstance(parent_role, int):
            parent_id = parent_role
        else:
            parent_id = parent_role.id
            
        if isinstance(child_role, int):
            child_id = child_role
        else:
            child_id = child_role.id
            
        return self.filter(parent_role_id=parent_id, child_role_id=child_id).first()
    
    def get_hierarchies_by_parent(self, parent_role):
        """
        Get all role hierarchies for a parent role.
        
        Args:
            parent_role: The parent role object or role ID
            
        Returns:
            QuerySet of role hierarchies for the parent role
        """
        if isinstance(parent_role, int):
            return self.filter(parent_role_id=parent_role)
        return self.filter(parent_role=parent_role)
    
    def get_hierarchies_by_child(self, child_role):
        """
        Get all role hierarchies for a child role.
        
        Args:
            child_role: The child role object or role ID
            
        Returns:
            QuerySet of role hierarchies for the child role
        """
        if isinstance(child_role, int):
            return self.filter(child_role_id=child_role)
        return self.filter(child_role=child_role)
    
    def get_child_roles(self, parent_role):
        """
        Get all child roles for a parent role.
        
        Args:
            parent_role: The parent role object or role ID
            
        Returns:
            QuerySet of child roles for the parent role
        """
        if isinstance(parent_role, int):
            hierarchies = self.filter(parent_role_id=parent_role)
        else:
            hierarchies = self.filter(parent_role=parent_role)
            
        return Group.objects.filter(id__in=hierarchies.values_list('child_role_id', flat=True))
    
    def get_parent_roles(self, child_role):
        """
        Get all parent roles for a child role.
        
        Args:
            child_role: The child role object or role ID
            
        Returns:
            QuerySet of parent roles for the child role
        """
        if isinstance(child_role, int):
            hierarchies = self.filter(child_role_id=child_role)
        else:
            hierarchies = self.filter(child_role=child_role)
            
        return Group.objects.filter(id__in=hierarchies.values_list('parent_role_id', flat=True))
    
    def get_all_parent_roles(self, role):
        """
        Get all parent roles for a role (recursive).
        
        Args:
            role: The role object or role ID
            
        Returns:
            Set of parent roles for the role
        """
        if isinstance(role, int):
            role = Group.objects.get(pk=role)
            
        return RoleHierarchy.get_all_parent_roles(role)
    
    def create_hierarchy(self, parent_role, child_role):
        """
        Create a new role hierarchy.
        
        Args:
            parent_role: The parent role object or role ID
            child_role: The child role object or role ID
            
        Returns:
            The created role hierarchy
        """
        if isinstance(parent_role, int):
            parent_id = parent_role
        else:
            parent_id = parent_role.id
            
        if isinstance(child_role, int):
            child_id = child_role
        else:
            child_id = child_role.id
            
        return self.create(parent_role_id=parent_id, child_role_id=child_id)
    
    def delete_hierarchy(self, hierarchy):
        """
        Delete a role hierarchy.
        
        Args:
            hierarchy: The role hierarchy to delete
        """
        self.delete(hierarchy)
    
    def delete_hierarchy_by_parent_and_child(self, parent_role, child_role):
        """
        Delete a role hierarchy by parent and child roles.
        
        Args:
            parent_role: The parent role object or role ID
            child_role: The child role object or role ID
            
        Returns:
            True if the hierarchy was deleted, False if it didn't exist
        """
        hierarchy = self.get_hierarchy_by_parent_and_child(parent_role, child_role)
        
        if hierarchy:
            self.delete(hierarchy)
            return True
        return False