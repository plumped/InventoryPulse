# accessmanagement/templatetags/permission_tags.py
from django import template
from accessmanagement.permissions import has_permission

register = template.Library()


@register.filter
def has_perm(user, permission_string):
    """
    Check in templates if a user has a permission.
    
    Usage:
    {% if user|has_perm:'inventory:view' %}
        <!-- Show content -->
    {% endif %}
    """
    try:
        area, action = permission_string.split(':')
        return has_permission(user, area, action)
    except (ValueError, TypeError):
        return False


@register.filter
def has_warehouse_access(user, warehouse, permission_type='view'):
    """
    Check in templates if a user has access to a warehouse.
    
    Usage:
    {% if user|has_warehouse_access:warehouse %}
        <!-- Show content -->
    {% endif %}
    
    Or with permission type:
    {% if user|has_warehouse_access:warehouse,'edit' %}
        <!-- Show edit buttons -->
    {% endif %}
    """
    from accessmanagement.models import WarehouseAccess
    return WarehouseAccess.has_access(user, warehouse, permission_type)