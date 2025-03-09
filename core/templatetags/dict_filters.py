from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Get an item from a dictionary by key.
    Usage example: {{ mydict|get_item:item_key }}
    """
    return dictionary.get(key, [])