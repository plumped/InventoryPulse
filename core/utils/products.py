
from django.db.models import Q

import logging
from core.utils.access import get_accessible_warehouses
from core.utils.error import log_exception, ValidationError, DatabaseError
from core.utils.stock import get_accessible_stock
from product_management.models.products_models import Product

logger = logging.getLogger('core')


def get_filtered_products(request, filter_low_stock=False):
    """
    Get a filtered list of products based on request parameters.

    Args:
        request: The HTTP request object
        filter_low_stock: Whether to filter for products with low stock only

    Returns:
        A sorted list of products matching the filter criteria

    Raises:
        ValidationError: If the filter parameters are invalid
        DatabaseError: If there's an error querying the database
    """
    try:
        # Get accessible warehouses for the user
        warehouses = get_accessible_warehouses(request.user)

        # Get filter parameters from request
        search = request.GET.get('search', '')
        category = request.GET.get('category', '')
        stock_status = request.GET.get('stock_status', '')

        # Validate stock_status if provided
        if stock_status and stock_status not in ['low', 'ok', 'out']:
            raise ValidationError(
                message=f"Invalid stock status: {stock_status}",
                details={'valid_values': ['low', 'ok', 'out']}
            )

        # Query products with select_related for better performance
        try:
            products = Product.objects.select_related('category').all()

            # Apply search filter if provided
            if search:
                products = products.filter(
                    Q(name__icontains=search) | 
                    Q(sku__icontains=search) | 
                    Q(barcode__icontains=search)
                )

            # Apply category filter if provided
            if category:
                products = products.filter(category_id=category)

        except Exception as e:
            # Log the database error
            log_exception(
                exception=e,
                module='core.utils.products',
                function='get_filtered_products',
                extra_context={'request_params': request.GET}
            )
            # Wrap in a DatabaseError
            raise DatabaseError(
                message="Error querying products",
                details={'original_error': str(e)}
            ) from e

        # Filter products based on stock status
        filtered = []
        for product in products:
            try:
                # Get accessible stock for the product
                stock = get_accessible_stock(product, warehouses)
                product.accessible_stock = stock

                # Apply stock filters
                if filter_low_stock and stock < product.minimum_stock:
                    filtered.append(product)
                elif not filter_low_stock:
                    if stock_status == 'low' and (stock <= product.minimum_stock and stock > 0):
                        filtered.append(product)
                    elif stock_status == 'ok' and stock > product.minimum_stock:
                        filtered.append(product)
                    elif stock_status == 'out' and stock == 0:
                        filtered.append(product)
                    elif not stock_status:
                        filtered.append(product)
            except Exception as e:
                # Log the error but continue processing other products
                logger.warning(
                    f"Error processing product {product.id}: {str(e)}",
                    extra={
                        'product_id': product.id,
                        'exception': str(e)
                    }
                )
                # Skip this product and continue with others
                continue

        # Sort the filtered products by name
        return sorted(filtered, key=lambda p: p.name)

    except ValidationError:
        # Re-raise validation errors
        raise
    except DatabaseError:
        # Re-raise database errors
        raise
    except Exception as e:
        # Log unexpected errors
        log_exception(
            exception=e,
            module='core.utils.products',
            function='get_filtered_products',
            extra_context={'request_params': request.GET}
        )
        # Wrap in a generic error
        raise DatabaseError(
            message="An unexpected error occurred while filtering products",
            details={'original_error': str(e)}
        ) from e
