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