import logging

from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.core.cache import cache
from django.db import models
from django.utils import timezone

from inventory.models import Warehouse
from master_data.models.organisations_models import Department

logger = logging.getLogger('accessmanagement')


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    departments = models.ManyToManyField(Department, related_name='user_profiles', blank=True)

    def __str__(self):
        return f"Profil von {self.user.username}"

    @classmethod
    def create_for_user(cls, user):
        """
        Standardized method to create a user profile.
        This ensures all users have a profile.
        """
        profile, created = cls.objects.get_or_create(user=user)
        return profile

class WarehouseAccess(models.Model):
    """Model for warehouse access rights per department."""
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    # Access rights
    can_view = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)
    can_manage_stock = models.BooleanField(default=False)

    class Meta:
        unique_together = ('warehouse', 'department')
        verbose_name_plural = 'Warehouse Access Rights'

    def __str__(self):
        return f"{self.department} -> {self.warehouse}"

    @classmethod
    def has_access(cls, user, warehouse, permission_type='view'):
        """
        Check if a user has access to a specific warehouse.
        Uses caching to reduce database queries for frequently accessed permissions.
        """
        # Admin always has access
        if user.is_superuser:
            logger.info(f"Superuser {user.username} granted {permission_type} access to warehouse {warehouse.name}")
            return True

        # Generate a cache key
        cache_key = f"warehouse_access:{user.id}:{warehouse.id}:{permission_type}"

        # Try to get the result from cache
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Flag to track if a permission was found but denied
        permission_found_but_denied = False

        # Get departments from user profile
        try:
            # Try to get user's departments
            if hasattr(user, 'profile'):
                user_departments = user.profile.departments.all()
            else:
                try:
                    # Try to create profile if it doesn't exist
                    UserProfile.create_for_user(user)
                    user_departments = user.profile.departments.all()
                except Exception as e:
                    logger.error(f"Error creating user profile for {user.username}: {str(e)}")
                    # Cache the negative result for 5 minutes
                    cache.set(cache_key, False, 300)
                    return False

            for department in user_departments:
                try:
                    access = cls.objects.get(warehouse=warehouse, department=department)

                    # Permission exists, mark as found
                    permission_found_but_denied = True

                    # Check if the required permission type is granted
                    if permission_type == 'view' and access.can_view:
                        logger.debug(f"User {user.username} granted view access to warehouse {warehouse.name} via department {department.name}")
                        # Cache the positive result for 15 minutes
                        cache.set(cache_key, True, 900)
                        return True
                    elif permission_type == 'edit' and access.can_edit:
                        logger.debug(f"User {user.username} granted edit access to warehouse {warehouse.name} via department {department.name}")
                        # Cache the positive result for 15 minutes
                        cache.set(cache_key, True, 900)
                        return True
                    elif permission_type == 'manage_stock' and access.can_manage_stock:
                        logger.debug(f"User {user.username} granted manage_stock access to warehouse {warehouse.name} via department {department.name}")
                        # Cache the positive result for 15 minutes
                        cache.set(cache_key, True, 900)
                        return True
                    else:
                        # Permission exists but doesn't grant the required type
                        logger.debug(f"Department {department.name} has access to warehouse {warehouse.name} but {permission_type} is not granted")
                        # Continue checking other departments
                except cls.DoesNotExist:
                    # This department doesn't have explicit access to this warehouse
                    continue
        except AttributeError as e:
            logger.error(f"AttributeError in has_access for user {user.username}: {str(e)}")
            # Cache the negative result for 5 minutes
            cache.set(cache_key, False, 300)
            return False
        except Exception as e:
            logger.error(f"Unexpected error in has_access for user {user.username}: {str(e)}")
            # Cache the negative result for 5 minutes
            cache.set(cache_key, False, 300)
            return False

        # If a permission was found but denied, cache for a shorter time
        if permission_found_but_denied:
            logger.debug(f"User {user.username} denied {permission_type} access to warehouse {warehouse.name} (permission found but denied)")
            cache.set(cache_key, False, 300)  # Cache for 5 minutes
        else:
            # No permission found at all
            logger.debug(f"User {user.username} denied {permission_type} access to warehouse {warehouse.name} (no permission found)")
            cache.set(cache_key, False, 600)  # Cache for 10 minutes

        return False


class ObjectPermission(models.Model):
    """
    Model for object-level permissions.
    This allows granting permissions to specific objects for specific users or departments.
    """
    # The user who has the permission (optional - can be null if department is set)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True, related_name='object_permissions')

    # The department that has the permission (optional - can be null if user is set)
    department = models.ForeignKey(Department, on_delete=models.CASCADE, null=True, blank=True, 
                                  related_name='object_permissions')

    # Content type and object ID for the generic relation
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')

    # Permission types
    can_view = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)
    can_delete = models.BooleanField(default=False)

    # Time-based access control
    valid_from = models.DateTimeField(null=True, blank=True)
    valid_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        unique_together = [
            ('user', 'content_type', 'object_id'),
            ('department', 'content_type', 'object_id')
        ]
        verbose_name_plural = 'Object Permissions'

    def __str__(self):
        target = self.user.username if self.user else self.department.name
        return f"{target} -> {self.content_type.model}:{self.object_id}"

    def is_valid(self):
        """Check if the permission is currently valid based on time constraints."""
        try:
            now = timezone.now()
            if self.valid_from and now < self.valid_from:
                return False
            if self.valid_until and now > self.valid_until:
                return False
            return True
        except TypeError as e:
            # Log the error if there's a datetime comparison issue
            logger.error(f"Error comparing datetimes in is_valid: {str(e)}")
            # If there's an error, assume the permission is not valid to be safe
            return False

    @classmethod
    def has_object_permission(cls, user, obj, permission_type='view'):
        """
        Check if a user has permission for a specific object.
        """
        # Admin always has access
        if user.is_superuser:
            logger.info(f"Superuser {user.username} granted {permission_type} access to {obj.__class__.__name__}:{obj.id}")
            return True

        # Generate cache key
        content_type = ContentType.objects.get_for_model(obj)
        cache_key = f"obj_perm:{user.id}:{content_type.id}:{obj.id}:{permission_type}"

        # Try to get from cache
        cached_result = cache.get(cache_key)
        if cached_result is not None:
            return cached_result

        # Flag to track if a permission was found but denied
        permission_found_but_denied = False

        # Check direct user permission
        try:
            user_perm = cls.objects.get(
                user=user,
                content_type=content_type,
                object_id=obj.id
            )

            # Permission exists, mark as found
            permission_found_but_denied = True

            if not user_perm.is_valid():
                # Permission exists but is not valid due to time constraints
                logger.debug(f"User {user.username} has permission for {obj.__class__.__name__}:{obj.id} but it's not valid due to time constraints")
                # Don't return yet, continue checking department permissions
            else:
                # Permission is valid, check if the required type is granted
                if permission_type == 'view' and user_perm.can_view:
                    cache.set(cache_key, True, 900)  # Cache for 15 minutes
                    return True
                elif permission_type == 'edit' and user_perm.can_edit:
                    cache.set(cache_key, True, 900)
                    return True
                elif permission_type == 'delete' and user_perm.can_delete:
                    cache.set(cache_key, True, 900)
                    return True
                else:
                    # Permission exists but doesn't grant the required type
                    logger.debug(f"User {user.username} has permission for {obj.__class__.__name__}:{obj.id} but {permission_type} is not granted")
                    # Don't return yet, continue checking department permissions
        except cls.DoesNotExist:
            # No direct user permission, continue checking
            pass

        # Check department permissions
        try:
            # Get user's departments
            if hasattr(user, 'profile'):
                departments = user.profile.departments.all()
            else:
                try:
                    # Try to create profile if it doesn't exist
                    UserProfile.create_for_user(user)
                    departments = user.profile.departments.all()
                except Exception as e:
                    logger.error(f"Error creating user profile for {user.username}: {str(e)}")
                    departments = []

            for department in departments:
                try:
                    dept_perm = cls.objects.get(
                        department=department,
                        content_type=content_type,
                        object_id=obj.id
                    )

                    # Permission exists, mark as found
                    permission_found_but_denied = True

                    if not dept_perm.is_valid():
                        # Permission exists but is not valid due to time constraints
                        logger.debug(f"Department {department.name} has permission for {obj.__class__.__name__}:{obj.id} but it's not valid due to time constraints")
                        continue

                    # Permission is valid, check if the required type is granted
                    if permission_type == 'view' and dept_perm.can_view:
                        cache.set(cache_key, True, 900)  # Cache for 15 minutes
                        return True
                    elif permission_type == 'edit' and dept_perm.can_edit:
                        cache.set(cache_key, True, 900)
                        return True
                    elif permission_type == 'delete' and dept_perm.can_delete:
                        cache.set(cache_key, True, 900)
                        return True
                    else:
                        # Permission exists but doesn't grant the required type
                        logger.debug(f"Department {department.name} has permission for {obj.__class__.__name__}:{obj.id} but {permission_type} is not granted")
                        # Continue checking other departments
                except cls.DoesNotExist:
                    continue  # This department doesn't have permission for this object
        except Exception as e:
            logger.error(f"Error checking department permissions for user {user.username}: {str(e)}")

        # If a permission was found but denied, cache for a shorter time
        if permission_found_but_denied:
            cache.set(cache_key, False, 300)  # Cache for 5 minutes
        else:
            # No permission found at all
            cache.set(cache_key, False, 600)  # Cache for 10 minutes

        return False


class RoleHierarchy(models.Model):
    """
    Model for role-based inheritance.
    This allows creating a hierarchy of roles where permissions are inherited.
    """
    parent_role = models.ForeignKey('auth.Group', on_delete=models.CASCADE, related_name='child_roles')
    child_role = models.ForeignKey('auth.Group', on_delete=models.CASCADE, related_name='parent_roles')

    class Meta:
        unique_together = ('parent_role', 'child_role')
        verbose_name_plural = 'Role Hierarchies'

    def __str__(self):
        return f"{self.parent_role.name} -> {self.child_role.name}"

    @classmethod
    def get_all_parent_roles(cls, role):
        """
        Get all parent roles for a given role (recursive).
        """
        parent_roles = set()
        direct_parents = cls.objects.filter(child_role=role).select_related('parent_role')

        for hierarchy in direct_parents:
            parent_roles.add(hierarchy.parent_role)
            parent_roles.update(cls.get_all_parent_roles(hierarchy.parent_role))

        return parent_roles
