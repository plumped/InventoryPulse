from django import template
from core.models import Currency

register = template.Library()

@register.simple_tag
def get_default_currency():
    """
    Returns the default currency for the system.
    """
    return Currency.get_default_currency()