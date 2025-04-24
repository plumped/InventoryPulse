import logging
from accessmanagement.models import WarehouseAccess, ObjectPermission
from core.utils.error import log_exception, DatabaseError, PermissionDeniedError
from inventory.models import Warehouse

logger = logging.getLogger('accessmanagement')

def get_accessible_warehouses(user, permission_type='view'):
    """
    Get all warehouses that the user has access to with the specified permission type.
    Uses the WarehouseAccess.has_access method to check permissions.

    Args:
        user: The user to check permissions for
        permission_type: The type of permission to check ('view', 'edit', or 'manage_stock')

    Returns:
        QuerySet of Warehouse objects that the user has access to

    Raises:
        PermissionDeniedError: If the permission_type is invalid
        DatabaseError: If there's an error querying the database
    """
    try:
        # Validate permission type
        valid_permission_types = ['view', 'edit', 'manage_stock']
        if permission_type not in valid_permission_types:
            raise PermissionDeniedError(
                message=f"Invalid permission type: {permission_type}",
                details={'valid_types': valid_permission_types}
            )

        # Validate user
        if user is None:
            logger.warning("get_accessible_warehouses called with None user")
            return Warehouse.objects.none()

        # Superusers have access to all active warehouses
        if user.is_superuser:
            return Warehouse.objects.filter(is_active=True)

        # For regular users, get all active warehouses and filter based on access
        try:
            all_warehouses = Warehouse.objects.filter(is_active=True)
        except Exception as e:
            log_exception(
                exception=e,
                module='core.utils.access',
                function='get_accessible_warehouses',
                extra_context={'user_id': user.id if user else None}
            )
            raise DatabaseError(
                message="Error retrieving warehouses",
                details={'original_error': str(e)}
            ) from e

        accessible_warehouse_ids = []

        for warehouse in all_warehouses:
            try:
                if WarehouseAccess.has_access(user, warehouse, permission_type):
                    accessible_warehouse_ids.append(warehouse.id)
            except Exception as e:
                # Log the error but continue checking other warehouses
                logger.warning(
                    f"Error checking access for warehouse {warehouse.id}: {str(e)}",
                    extra={
                        'user_id': user.id if user else None,
                        'warehouse_id': warehouse.id,
                        'permission_type': permission_type,
                        'exception': str(e)
                    }
                )
                # Skip this warehouse and continue with others
                continue

        try:
            return Warehouse.objects.filter(id__in=accessible_warehouse_ids)
        except Exception as e:
            log_exception(
                exception=e,
                module='core.utils.access',
                function='get_accessible_warehouses',
                extra_context={
                    'user_id': user.id if user else None,
                    'warehouse_ids': accessible_warehouse_ids
                }
            )
            raise DatabaseError(
                message="Error retrieving accessible warehouses",
                details={'original_error': str(e)}
            ) from e

    except (PermissionDeniedError, DatabaseError):
        # Re-raise these specific exceptions
        raise
    except Exception as e:
        # Log and wrap any other exceptions
        log_exception(
            exception=e,
            module='core.utils.access',
            function='get_accessible_warehouses',
            extra_context={'user_id': user.id if user else None}
        )
        raise DatabaseError(
            message="An unexpected error occurred while retrieving accessible warehouses",
            details={'original_error': str(e)}
        ) from e


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

    Raises:
        PermissionDeniedError: If the permission_type is invalid
        DatabaseError: If there's an error querying the database
    """
    try:
        # Validate permission type
        valid_permission_types = ['view', 'edit', 'delete']
        if permission_type not in valid_permission_types:
            raise PermissionDeniedError(
                message=f"Invalid permission type: {permission_type}",
                details={'valid_types': valid_permission_types}
            )

        # Validate user and object
        if user is None:
            logger.warning("has_object_permission called with None user")
            return False

        if obj is None:
            logger.warning("has_object_permission called with None object")
            return False

        # First check direct object permissions
        try:
            if ObjectPermission.has_object_permission(user, obj, permission_type):
                logger.debug(f"User {user.username} granted {permission_type} access to {obj.__class__.__name__} {getattr(obj, 'id', 'unknown')} via direct permission")
                return True
        except Exception as e:
            log_exception(
                exception=e,
                module='core.utils.access',
                function='has_object_permission',
                extra_context={
                    'user_id': user.id if user else None,
                    'object_type': obj.__class__.__name__ if obj else None,
                    'object_id': getattr(obj, 'id', None) if obj else None,
                    'permission_type': permission_type
                }
            )
            raise DatabaseError(
                message="Error checking direct object permission",
                details={'original_error': str(e)}
            ) from e

        # For products, also check warehouse access
        from product_management.models.products_models import Product
        if isinstance(obj, Product):
            try:
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
            except (PermissionDeniedError, DatabaseError):
                # Re-raise these specific exceptions
                raise
            except Exception as e:
                log_exception(
                    exception=e,
                    module='core.utils.access',
                    function='has_object_permission',
                    extra_context={
                        'user_id': user.id if user else None,
                        'product_id': obj.id if isinstance(obj, Product) else None,
                        'permission_type': permission_type
                    }
                )
                raise DatabaseError(
                    message="Error checking warehouse access for product",
                    details={'original_error': str(e)}
                ) from e

        # No permission found
        logger.debug(f"User {user.username} denied {permission_type} access to {obj.__class__.__name__} {getattr(obj, 'id', 'unknown')} - no permission found")
        return False

    except (PermissionDeniedError, DatabaseError):
        # Re-raise these specific exceptions
        raise
    except Exception as e:
        # Log and wrap any other exceptions
        log_exception(
            exception=e,
            module='core.utils.access',
            function='has_object_permission',
            extra_context={
                'user_id': user.id if user else None,
                'object_type': obj.__class__.__name__ if obj else None,
                'object_id': getattr(obj, 'id', None) if obj else None,
                'permission_type': permission_type
            }
        )
        raise DatabaseError(
            message="An unexpected error occurred while checking object permission",
            details={'original_error': str(e)}
        ) from e
