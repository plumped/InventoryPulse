"""
Repository for UserProfile model.

This module contains the UserProfileRepository class that handles all data access
operations related to the UserProfile model.
"""

from django.contrib.auth.models import User

from .base import BaseRepository
from ..models.user_models import UserProfile


class UserProfileRepository(BaseRepository):
    """Repository for UserProfile model."""
    
    model_class = UserProfile
    
    def get_profile_by_id(self, profile_id):
        """
        Get a user profile by its ID.
        
        Args:
            profile_id: The ID of the user profile
            
        Returns:
            The user profile with the given ID
            
        Raises:
            UserProfile.DoesNotExist: If the user profile does not exist
        """
        return self.get_by_id(profile_id)
    
    def get_profile_by_user(self, user):
        """
        Get a user profile by its user.
        
        Args:
            user: The user object or user ID
            
        Returns:
            The user profile for the given user or None if it doesn't exist
        """
        if isinstance(user, int):
            return self.filter(user_id=user).first()
        return self.filter(user=user).first()
    
    def get_or_create_profile(self, user):
        """
        Get or create a user profile for a user.
        
        Args:
            user: The user object or user ID
            
        Returns:
            A tuple of (user_profile, created) where created is a boolean
            indicating whether the profile was created
        """
        if isinstance(user, int):
            user = User.objects.get(pk=user)
            
        return self.model_class.objects.get_or_create(user=user)
    
    def create_profile(self, user, **kwargs):
        """
        Create a new user profile.
        
        Args:
            user: The user object or user ID
            **kwargs: Additional profile attributes
            
        Returns:
            The created user profile
        """
        if isinstance(user, int):
            user = User.objects.get(pk=user)
            
        return self.create(user=user, **kwargs)
    
    def update_profile(self, profile, **kwargs):
        """
        Update an existing user profile.
        
        Args:
            profile: The user profile to update
            **kwargs: Attributes to update
            
        Returns:
            The updated user profile
        """
        return self.update(profile, **kwargs)
    
    def delete_profile(self, profile):
        """
        Delete a user profile.
        
        Args:
            profile: The user profile to delete
        """
        self.delete(profile)
    
    def add_department(self, profile, department):
        """
        Add a department to a user profile.
        
        Args:
            profile: The user profile
            department: The department to add
            
        Returns:
            The updated user profile
        """
        profile.departments.add(department)
        return profile
    
    def remove_department(self, profile, department):
        """
        Remove a department from a user profile.
        
        Args:
            profile: The user profile
            department: The department to remove
            
        Returns:
            The updated user profile
        """
        profile.departments.remove(department)
        return profile
    
    def get_profiles_by_department(self, department):
        """
        Get all user profiles in a department.
        
        Args:
            department: The department object or department ID
            
        Returns:
            QuerySet of user profiles in the department
        """
        if isinstance(department, int):
            return self.filter(departments__id=department)
        return self.filter(departments=department)