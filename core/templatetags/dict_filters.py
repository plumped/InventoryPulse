from django import template

register = template.Library()

@register.filter
def get(dictionary, key):
    """
    Get an item from a dictionary by key.
    Usage example: {{ mydict|get:item_key }}
    """
    return dictionary.get(key, None)

@register.filter
def dictmap(queryset, attr):
    """
    Extrahiert ein Attribut aus jedem Objekt in einem QuerySet oder einer Liste.
    Beispiel: {% for warehouse in warehouse_stocks|dictmap:"warehouse" %}
    """
    if not queryset:
        return []
    
    result = []
    for item in queryset:
        # Unterstützt verschachtelte Attribute mit Punktnotation (z.B. "warehouse.name")
        if '.' in attr:
            parts = attr.split('.')
            value = item
            for part in parts:
                value = getattr(value, part, None)
            result.append(value)
        else:
            result.append(getattr(item, attr, None))
    
    return result