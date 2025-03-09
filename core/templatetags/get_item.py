# core/templatetags/core_tags.py

from django import template

register = template.Library()


@register.filter
def get_item(dictionary, key):
    """
    Ermöglicht den Zugriff auf Dictionary-Elemente über einen Schlüssel in Templates.
    Verwendung: {{ my_dict|get_item:key_var }}
    """
    if dictionary is None:
        return None

    return dictionary.get(key)