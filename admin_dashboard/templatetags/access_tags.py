from django import template

from accessmanagement.models import WarehouseAccess, ObjectPermission

register = template.Library()

@register.filter
def has_warehouse_access(user, warehouse):
    """
    Template filter to check if a user has view access to a warehouse.
    Usage: {{ user|has_warehouse_access:warehouse }}
    """
    return WarehouseAccess.has_access(user, warehouse, 'view')

@register.filter
def has_warehouse_edit(user, warehouse):
    """
    Template filter to check if a user has edit access to a warehouse.
    Usage: {{ user|has_warehouse_edit:warehouse }}
    """
    return WarehouseAccess.has_access(user, warehouse, 'edit')

@register.filter
def has_warehouse_manage(user, warehouse):
    """
    Template filter to check if a user has manage_stock access to a warehouse.
    Usage: {{ user|has_warehouse_manage:warehouse }}
    """
    return WarehouseAccess.has_access(user, warehouse, 'manage_stock')

@register.filter
def has_object_permission(user, obj_and_perm):
    """
    Template filter to check if a user has permission for an object.
    Usage: {{ user|has_object_permission:obj_and_perm }}
    
    obj_and_perm should be a tuple of (object, permission_type)
    Example: {{ user|has_object_permission:(product, 'view') }}
    """
    if not isinstance(obj_and_perm, tuple) or len(obj_and_perm) != 2:
        return False
    
    obj, permission_type = obj_and_perm
    return ObjectPermission.has_object_permission(user, obj, permission_type)