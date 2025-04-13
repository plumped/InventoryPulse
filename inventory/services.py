from django.db.models import F

from product_management.models.products import Product


def check_low_stock_products():
    """
    Überprüft alle Produkte auf kritischen Bestand.

    Returns:
        list: Liste von Produkten mit kritischem Bestand
    """
    return Product.objects.filter(current_stock__lte=F('minimum_stock')).order_by('name')