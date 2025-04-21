from django import template

from core.utils.view_helpers import check_permission

register = template.Library()

@register.filter
def has_permission(user, args):
    """
    Template filter to check if a user has permission for an action.
    
    Usage: 
    {{ user|has_permission:args }}
    
    Where args is a tuple containing:
    - For simple permission check: (permission_type)
      Example: {{ user|has_permission:'view' }}
    
    - For Django permission check: (permission_type, django_permission)
      Example: {{ user|has_permission:('view', 'product_management.view_product') }}
    
    - For object permission check: (permission_type, obj)
      Example: {{ user|has_permission:('edit', product) }}
    
    - For object permission with Django permission: (permission_type, obj, django_permission)
      Example: {{ user|has_permission:('edit', product, 'product_management.change_product') }}
    
    - For status check: (permission_type, obj, django_permission, valid_status)
      Example: {{ user|has_permission:('edit', order, 'order.change_order', 'draft') }}
    """
    if not args:
        return False
    
    # Handle different argument patterns
    if isinstance(args, str):
        # Simple permission type only
        return check_permission(user, permission_type=args)
    
    if not isinstance(args, tuple):
        return False
    
    # Extract arguments based on tuple length
    if len(args) == 2:
        # Could be (permission_type, django_permission) or (permission_type, obj)
        if isinstance(args[1], str):
            # It's a Django permission
            return check_permission(user, permission_type=args[0], django_permission=args[1])
        else:
            # It's an object
            return check_permission(user, obj=args[1], permission_type=args[0])
    
    elif len(args) == 3:
        # (permission_type, obj, django_permission)
        return check_permission(user, obj=args[1], permission_type=args[0], django_permission=args[2])
    
    elif len(args) == 4:
        # (permission_type, obj, django_permission, valid_status)
        return check_permission(user, obj=args[1], permission_type=args[0], 
                               django_permission=args[2], valid_status=args[3])
    
    return False