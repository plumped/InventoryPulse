from django.db.models import Sum

from product_management.models.products import ProductWarehouse


def get_accessible_stock(product, warehouses):
    return ProductWarehouse.objects.filter(
        product=product,
        warehouse__in=warehouses
    ).aggregate(total=Sum('quantity'))['total'] or 0
