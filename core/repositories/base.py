"""
Base repository classes for the core app.

This module provides base repository classes that can be used across all applications
to standardize data access patterns and reduce code duplication.
"""


class RepositoryError(Exception):
    """
    Exception raised for repository-related errors.
    
    Attributes:
        message -- explanation of the error
    """
    
    def __init__(self, message="Repository operation failed"):
        self.message = message
        super().__init__(self.message)


class BaseRepository:
    """
    Base repository class that provides common data access methods.
    
    This class should be subclassed by specific repository implementations,
    which should set the model_class attribute to the appropriate model.
    """
    
    model_class = None
    
    def __init__(self):
        """Initialize the repository."""
        if self.model_class is None:
            raise RepositoryError("Repository model_class is not defined")
    
    def all(self):
        """
        Get all objects.
        
        Returns:
            QuerySet of all objects
        """
        return self.model_class.objects.all()
    
    def filter(self, **kwargs):
        """
        Filter objects by the given criteria.
        
        Args:
            **kwargs: Filter criteria
            
        Returns:
            QuerySet of filtered objects
        """
        return self.model_class.objects.filter(**kwargs)
    
    def filter_with_q(self, q_object):
        """
        Filter objects using a Q object.
        
        Args:
            q_object: Q object for complex queries
            
        Returns:
            QuerySet of filtered objects
        """
        return self.model_class.objects.filter(q_object)
    
    def get(self, **kwargs):
        """
        Get a single object by the given criteria.
        
        Args:
            **kwargs: Lookup criteria
            
        Returns:
            The matching object
            
        Raises:
            model_class.DoesNotExist: If no object matches the criteria
            model_class.MultipleObjectsReturned: If multiple objects match the criteria
        """
        return self.model_class.objects.get(**kwargs)
    
    def get_by_id(self, id):
        """
        Get an object by its ID.
        
        Args:
            id: The ID of the object
            
        Returns:
            The object with the given ID
            
        Raises:
            model_class.DoesNotExist: If no object with the given ID exists
        """
        return self.get(id=id)
    
    def create(self, **kwargs):
        """
        Create a new object.
        
        Args:
            **kwargs: Object attributes
            
        Returns:
            The created object
        """
        return self.model_class.objects.create(**kwargs)
    
    def update(self, instance, **kwargs):
        """
        Update an existing object.
        
        Args:
            instance: The object to update
            **kwargs: Attributes to update
            
        Returns:
            The updated object
        """
        for key, value in kwargs.items():
            setattr(instance, key, value)
        instance.save()
        return instance
    
    def delete(self, instance):
        """
        Delete an object.
        
        Args:
            instance: The object to delete
        """
        instance.delete()
    
    def count(self):
        """
        Count the number of objects.
        
        Returns:
            The number of objects
        """
        return self.model_class.objects.count()