from django import template

register = template.Library()

@register.filter
def get(dictionary, key):
    """
    Get an item from a dictionary by key.
    Usage example: {{ mydict|get:item_key }}
    """
    return dictionary.get(key, None)