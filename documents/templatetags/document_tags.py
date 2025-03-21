from django import template
from django.utils.safestring import mark_safe
import json

register = template.Library()

@register.filter
def field_color(field_type):
    """Return color for field type."""
    colors = {
        'text': '#28a745',       # Green
        'number': '#dc3545',     # Red
        'date': '#fd7e14',       # Orange
        'currency': '#6f42c1',   # Purple
        'boolean': '#20c997',    # Teal
        'list': '#17a2b8',       # Cyan
        'table': '#6610f2'       # Indigo
    }
    return colors.get(field_type, '#6c757d')  # Default gray

@register.filter
def pprint(value):
    """Pretty print JSON data."""
    if isinstance(value, dict):
        return mark_safe('<pre>' + json.dumps(value, indent=2) + '</pre>')
    return value

@register.filter
def multiply(value, arg):
    try:
        return float(value) * arg
    except (ValueError, TypeError):
        return value