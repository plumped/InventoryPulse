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
    For products, also checks if the user has access to a warehouse containing the product.

    Args:
        user: The user to check permissions for
        obj: The object to check permissions for
        permission_type: The type of permission to check ('view', 'edit', or 'delete')

    Returns:
        Boolean: True if the user has permission, False otherwise
    """
    import logging
    logger = logging.getLogger('accessmanagement')

    # First check direct object permissions
    if ObjectPermission.has_object_permission(user, obj, permission_type):
        return True

    # For products, also check warehouse access
    from product_management.models.products_models import Product
    if isinstance(obj, Product):
        # Get warehouses the user has access to
        accessible_warehouses = get_accessible_warehouses(user, permission_type)

        # Check if the product is in any of these warehouses
        from product_management.models.products_models import ProductWarehouse
        warehouse_query = ProductWarehouse.objects.filter(
            product=obj,
            warehouse__in=accessible_warehouses,
            quantity__gt=0  # Only consider warehouses with stock
        )

        warehouse_count = warehouse_query.count()

        # If the product is in at least one accessible warehouse, grant permission
        if warehouse_count > 0:
            # Get the first warehouse for logging purposes
            first_warehouse = warehouse_query.first().warehouse
            logger.info(f"User {user.username} granted {permission_type} access to product {obj.id} ({obj.name}) via warehouse access to {first_warehouse.name}")
            return True
        else:
            logger.debug(f"User {user.username} denied {permission_type} access to product {obj.id} ({obj.name}) - no accessible warehouses with stock found")

    # No permission found
    return False
