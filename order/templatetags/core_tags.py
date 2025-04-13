from django import template

from master_data.models.currency_models import Currency

register = template.Library()

@register.simple_tag
def get_default_currency():
    """
    Returns the default currency for the system.
    """
    return Currency.get_default_currency()