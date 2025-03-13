from django.db import transaction
from django.db.models import F
from core.models import Product
from .models import StockMovement


def check_low_stock_products():
    """
    Überprüft alle Produkte auf kritischen Bestand.

    Returns:
        list: Liste von Produkten mit kritischem Bestand
    """
    return Product.objects.filter(current_stock__lte=F('minimum_stock')).order_by('name')