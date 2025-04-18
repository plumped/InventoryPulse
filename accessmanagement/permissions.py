import logging

from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from .models import UserRole, ObjectPermission

logger = logging.getLogger('accessmanagement')


def user_has_permission(user, permission_codename, organization=None, department=None):
    """
    Check if a user has a specific permission, optionally within a specific organization or department.

    Args:
        user: The user to check permissions for
        permission_codename: The codename of the permission to check (can be in format 'app_label.codename')
        organization: Optional organization to scope the permission check to
        department: Optional department to scope the permission check to

    Returns:
        bool: True if the user has the permission, False otherwise
    """
    # Superusers have all permissions
    if user.is_superuser:
        return True

    # Check if the user has the permission directly
    if user.has_perm(permission_codename):
        return True

    # Build the query for user roles
    query = Q(user=user)

    # If organization is specified, include roles for that organization or global roles
    if organization:
        query &= (
                Q(organization=organization) |
                Q(organization__isnull=True)
        )

    # If department is specified, include roles for that department or global roles
    if department:
        query &= (
                Q(department=department) |
                Q(department__isnull=True)
        )

    # Get all matching user roles
    user_roles = UserRole.objects.filter(query).select_related('role')

    # Check if any of the roles have the permission
    for user_role in user_roles:
        if user_role.role.has_permission(permission_codename):
            return True

    return False


def user_has_role(user, role_name, organization=None, department=None):
    """
    Check if a user has a specific role, optionally within a specific organization or department.

    Args:
        user: The user to check roles for
        role_name: The name of the role to check
        organization: Optional organization to scope the role check to
        department: Optional department to scope the role check to

    Returns:
        bool: True if the user has the role, False otherwise
    """
    # Build the query for user roles
    query = Q(user=user, role__name=role_name)

    # If organization is specified, include roles for that organization or global roles
    if organization:
        query &= (
                Q(organization=organization) |
                Q(organization__isnull=True)
        )

    # If department is specified, include roles for that department or global roles
    if department:
        query &= (
                Q(department=department) |
                Q(department__isnull=True)
        )

    # Check if any matching user roles exist
    return UserRole.objects.filter(query).exists()


def get_user_roles(user, organization=None, department=None):
    """
    Get all roles for a user, optionally filtered by organization or department.

    Args:
        user: The user to get roles for
        organization: Optional organization to filter roles by
        department: Optional department to filter roles by

    Returns:
        QuerySet: A queryset of UserRole objects
    """
    # Build the query for user roles
    query = Q(user=user)

    # If organization is specified, filter by that organization
    if organization:
        query &= Q(organization=organization) | Q(organization__isnull=True)

    # If department is specified, filter by that department
    if department:
        query &= Q(department=department) | Q(department__isnull=True)

    # Return the filtered user roles
    return UserRole.objects.filter(query).select_related('role', 'organization', 'department')


def get_users_with_permission(permission_codename, organization=None, department=None):
    """
    Get all users who have a specific permission, optionally within a specific organization or department.

    Args:
        permission_codename: The codename of the permission to check
        organization: Optional organization to scope the permission check to
        department: Optional department to scope the permission check to

    Returns:
        QuerySet: A queryset of User objects
    """
    # Get all roles that have the permission
    from django.contrib.auth.models import Permission

    if '.' in permission_codename:
        app_label, codename = permission_codename.split('.')
        permission = Permission.objects.filter(
            content_type__app_label=app_label,
            codename=codename
        ).first()
    else:
        permission = Permission.objects.filter(codename=permission_codename).first()

    if not permission:
        return User.objects.none()

    # Get all roles that have this permission
    roles_with_permission = permission.roles.all()

    # Build the query for user roles
    query = Q(role__in=roles_with_permission)

    # If organization is specified, filter by that organization
    if organization:
        query &= Q(organization=organization) | Q(organization__isnull=True)

    # If department is specified, filter by that department
    if department:
        query &= Q(department=department) | Q(department__isnull=True)

    # Get all user IDs from matching user roles
    user_ids = UserRole.objects.filter(query).values_list('user_id', flat=True).distinct()

    # Return all users with those IDs
    return User.objects.filter(
        Q(id__in=user_ids) |
        Q(user_permissions=permission) |
        Q(groups__permissions=permission)
    ).distinct()


def user_has_object_permission(user, obj, permission_type='view', organization=None):
    """
    Check if a user has permission to perform a specific action on a specific object.

    Args:
        user: The user to check permissions for
        obj: The object to check permissions for
        permission_type: The type of permission to check ('view', 'change', 'delete', 'full')
        organization: Optional organization context

    Returns:
        bool: True if the user has permission, False otherwise
    """
    # Superusers have all permissions
    if user.is_superuser:
        return True

    # Get the content type for the object
    content_type = ContentType.objects.get_for_model(obj)

    # Check if the user has direct object permission
    direct_permission = ObjectPermission.objects.filter(
        content_type=content_type,
        object_id=obj.pk,
        permission_type__in=[permission_type, 'full'],
        user=user
    ).exists()

    if direct_permission:
        return True

    # Check if any of the user's roles have object permission
    user_roles = get_user_roles(user, organization)
    role_ids = [role.role_id for role in user_roles]

    role_permission = ObjectPermission.objects.filter(
        content_type=content_type,
        object_id=obj.pk,
        permission_type__in=[permission_type, 'full'],
        role_id__in=role_ids
    ).exists()

    if role_permission:
        return True

    # Check if any of the user's departments have object permission
    if hasattr(user, 'profile') and hasattr(user.profile, 'departments'):
        department_ids = user.profile.departments.values_list('id', flat=True)

        department_permission = ObjectPermission.objects.filter(
            content_type=content_type,
            object_id=obj.pk,
            permission_type__in=[permission_type, 'full'],
            department_id__in=department_ids
        ).exists()

        if department_permission:
            return True

    # If we get here, the user doesn't have permission
    return False


def get_objects_for_user(user, model, permission_type='view', organization=None):
    """
    Get all objects of a specific type that a user has permission to access.

    Args:
        user: The user to get objects for
        model: The model class to get objects for
        permission_type: The type of permission to check ('view', 'change', 'delete', 'full')
        organization: Optional organization context

    Returns:
        QuerySet: A queryset of objects that the user has permission to access
    """
    # Superusers can access all objects
    if user.is_superuser:
        return model.objects.all()

    # Get the content type for the model
    content_type = ContentType.objects.get_for_model(model)

    # Get all object IDs that the user has direct permission for
    direct_object_ids = ObjectPermission.objects.filter(
        content_type=content_type,
        permission_type__in=[permission_type, 'full'],
        user=user
    ).values_list('object_id', flat=True)

    # Get all object IDs that the user's roles have permission for
    user_roles = get_user_roles(user, organization)
    role_ids = [role.role_id for role in user_roles]

    role_object_ids = ObjectPermission.objects.filter(
        content_type=content_type,
        permission_type__in=[permission_type, 'full'],
        role_id__in=role_ids
    ).values_list('object_id', flat=True)

    # Get all object IDs that the user's departments have permission for
    department_object_ids = []
    if hasattr(user, 'profile') and hasattr(user.profile, 'departments'):
        department_ids = user.profile.departments.values_list('id', flat=True)

        department_object_ids = ObjectPermission.objects.filter(
            content_type=content_type,
            permission_type__in=[permission_type, 'full'],
            department_id__in=department_ids
        ).values_list('object_id', flat=True)

    # Combine all object IDs
    all_object_ids = list(direct_object_ids) + list(role_object_ids) + list(department_object_ids)

    # If the user has model-level permission, they can access all objects
    if user_has_permission(user, f"{content_type.app_label}.{permission_type}_{content_type.model}", organization):
        return model.objects.all()

    # Otherwise, return only the objects they have permission for
    if all_object_ids:
        return model.objects.filter(pk__in=all_object_ids)
    else:
        return model.objects.none()


def grant_object_permission(obj, permission_type, user=None, role=None, department=None, organization=None):
    """
    Grant permission on an object to a user, role, or department.

    Args:
        obj: The object to grant permission for
        permission_type: The type of permission to grant ('view', 'change', 'delete', 'full')
        user: Optional user to grant permission to
        role: Optional role to grant permission to
        department: Optional department to grant permission to
        organization: Optional organization context

    Returns:
        ObjectPermission: The created or updated object permission
    """
    # Get the content type for the object
    content_type = ContentType.objects.get_for_model(obj)

    # Create or update the object permission
    permission, created = ObjectPermission.objects.update_or_create(
        content_type=content_type,
        object_id=obj.pk,
        permission_type=permission_type,
        user=user,
        role=role,
        department=department,
        defaults={
            'organization': organization
        }
    )

    return permission


def revoke_object_permission(obj, permission_type, user=None, role=None, department=None):
    """
    Revoke permission on an object from a user, role, or department.

    Args:
        obj: The object to revoke permission for
        permission_type: The type of permission to revoke ('view', 'change', 'delete', 'full')
        user: Optional user to revoke permission from
        role: Optional role to revoke permission from
        department: Optional department to revoke permission from

    Returns:
        bool: True if permission was revoked, False if it didn't exist
    """
    # Get the content type for the object
    content_type = ContentType.objects.get_for_model(obj)

    # Build the query for the object permission
    query = Q(
        content_type=content_type,
        object_id=obj.pk,
        permission_type=permission_type
    )

    if user:
        query &= Q(user=user)
    if role:
        query &= Q(role=role)
    if department:
        query &= Q(department=department)

    # Delete the object permission
    deleted, _ = ObjectPermission.objects.filter(query).delete()

    return deleted > 0
