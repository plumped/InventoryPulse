from django import template
from decimal import Decimal

register = template.Library()

@register.filter
def sub(value, arg):
    """Subtracts the arg from the value."""
    try:
        return value - arg
    except (ValueError, TypeError):
        try:
            return Decimal(value) - Decimal(arg)
        except:
            return ""

@register.simple_tag
def get_canceled_items(order):
    """
    Gibt alle stornierten oder teilweise stornierten Bestellpositionen zurück.
    """
    return order.items.filter(status__in=["canceled", "partially_canceled"])

@register.simple_tag
def has_canceled_items(order):
    """
    Überprüft, ob eine Bestellung stornierte Positionen hat.
    """
    return order.items.filter(status__in=["canceled", "partially_canceled"]).exists()