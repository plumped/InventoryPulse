"""
This module extends Django's built-in models with additional functionality.
It adds properties and methods to the Group model to support predefined roles.
"""

from django.contrib.auth.models import Group
from django.db.models.signals import post_migrate
from django.dispatch import receiver

# Add a description property to the Group model
Group.add_to_class('description', property(lambda self: getattr(self, '_description', None)))
Group.add_to_class('description', property(
    lambda self: getattr(self, '_description', None),
    lambda self, value: setattr(self, '_description', value)
))

# Add a category property to the Group model
Group.add_to_class('category', property(lambda self: getattr(self, '_category', None)))
Group.add_to_class('category', property(
    lambda self: getattr(self, '_category', None),
    lambda self, value: setattr(self, '_category', value)
))

# Add a role_key property to the Group model
Group.add_to_class('role_key', property(lambda self: getattr(self, '_role_key', None)))
Group.add_to_class('role_key', property(
    lambda self: getattr(self, '_role_key', None),
    lambda self, value: setattr(self, '_role_key', value)
))

# Add a is_predefined property to the Group model
Group.add_to_class('is_predefined', property(lambda self: getattr(self, '_is_predefined', False)))
Group.add_to_class('is_predefined', property(
    lambda self: getattr(self, '_is_predefined', False),
    lambda self, value: setattr(self, '_is_predefined', value)
))

@receiver(post_migrate)
def create_predefined_roles(sender, **kwargs):
    """
    Create predefined roles after migration.
    This ensures that the predefined roles are created when the application is first installed.
    """
    if sender.name == 'accessmanagement':
        from .predefined_roles import create_all_predefined_roles
        create_all_predefined_roles()