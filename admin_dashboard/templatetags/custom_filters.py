# admin_dashboard/templatetags/custom_filters.py
from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """
    Template filter to access dictionary values by variable key.
    Usage: {{ mydict|get_item:key_variable }}
    """
    return dictionary.get(key)

@register.filter
def has_perm(permission_list, permission):
    """
    Template filter to check if a permission is in a permission list.
    Usage: {{ group_permissions|has_perm:permission }}
    """
    return permission in permission_list