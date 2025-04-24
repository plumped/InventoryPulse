from django.db.models import Sum

import logging
from core.utils.error import log_exception, DatabaseError
from product_management.models.products_models import ProductWarehouse

logger = logging.getLogger('core')


def get_accessible_stock(product, warehouses):
    """
    Get the total stock for a product across the specified warehouses.

    Args:
        product: The product to get stock for
        warehouses: List of warehouses to check

    Returns:
        The total stock quantity (int)

    Raises:
        DatabaseError: If there's an error querying the database
    """
    try:
        # Validate input parameters
        if product is None:
            logger.warning("get_accessible_stock called with None product")
            return 0

        if not warehouses:
            logger.debug(f"get_accessible_stock called with empty warehouses for product {product.id}")
            return 0

        # Query the database for stock information
        total_stock = ProductWarehouse.objects.filter(
            product=product,
            warehouse__in=warehouses
        ).aggregate(total=Sum('quantity'))['total'] or 0

        return total_stock

    except Exception as e:
        # Log the error
        log_exception(
            exception=e,
            module='core.utils.stock',
            function='get_accessible_stock',
            extra_context={
                'product_id': getattr(product, 'id', None),
                'warehouse_ids': [getattr(w, 'id', None) for w in warehouses] if warehouses else None
            }
        )

        # Wrap in a DatabaseError
        raise DatabaseError(
            message=f"Error retrieving stock for product {getattr(product, 'id', 'unknown')}",
            details={'original_error': str(e)}
        ) from e
