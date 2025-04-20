from accessmanagement.models import WarehouseAccess, ObjectPermission
from inventory.models import Warehouse

def get_accessible_warehouses(user, permission_type='view'):
    """
    Get all warehouses that the user has access to with the specified permission type.
    Uses the WarehouseAccess.has_access method to check permissions.

    Args:
        user: The user to check permissions for
        permission_type: The type of permission to check ('view', 'edit', or 'manage_stock')

    Returns:
        QuerySet of Warehouse objects that the user has access to
    """
    # Superusers have access to all active warehouses
    if user.is_superuser:
        return Warehouse.objects.filter(is_active=True)

    # For regular users, get all active warehouses and filter based on access
    all_warehouses = Warehouse.objects.filter(is_active=True)
    accessible_warehouse_ids = []

    for warehouse in all_warehouses:
        if WarehouseAccess.has_access(user, warehouse, permission_type):
            accessible_warehouse_ids.append(warehouse.id)

    return Warehouse.objects.filter(id__in=accessible_warehouse_ids)


def has_object_permission(user, obj, permission_type='view'):
    """
    Check if a user has permission for a specific object.
    Uses ObjectPermission.has_object_permission for the permission check.

    Args:
        user: The user to check permissions for
        obj: The object to check permissions for
        permission_type: The type of permission to check ('view', 'edit', or 'delete')

    Returns:
        Boolean: True if the user has permission, False otherwise
    """
    return ObjectPermission.has_object_permission(user, obj, permission_type)
