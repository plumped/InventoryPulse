"""
This module defines predefined roles for the InventoryPulse system.
Each role is defined with a name, description, and a set of permissions.
These roles can be applied to users to grant them appropriate permissions.
"""

from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

# Define role categories
ROLE_CATEGORIES = {
    'ADMIN': 'Administrative Roles',
    'INVENTORY': 'Inventory Management Roles',
    'PURCHASING': 'Purchasing Roles',
    'SALES': 'Sales Roles',
    'DOCUMENT': 'Document Management Roles',
    'REPORTING': 'Reporting Roles',
}

# Define predefined roles with their permissions
PREDEFINED_ROLES = {
    # Administrative Roles
    'system_administrator': {
        'name': 'System Administrator',
        'description': 'Full access to all system functions',
        'category': 'ADMIN',
        'permissions': {
            'all': ['view', 'add', 'change', 'delete'],
        },
    },
    'user_manager': {
        'name': 'User Manager',
        'description': 'Manage users and their permissions',
        'category': 'ADMIN',
        'permissions': {
            'auth.user': ['view', 'add', 'change', 'delete'],
            'auth.group': ['view', 'add', 'change', 'delete'],
            'accessmanagement': ['view', 'add', 'change', 'delete'],
        },
    },

    # Inventory Management Roles
    'inventory_manager': {
        'name': 'Inventory Manager',
        'description': 'Full management of inventory and warehouses',
        'category': 'INVENTORY',
        'permissions': {
            'inventory': ['view', 'add', 'change', 'delete'],
            'product_management': ['view', 'add', 'change', 'delete'],
            'tracking': ['view', 'add', 'change'],
        },
    },
    'warehouse_manager': {
        'name': 'Warehouse Manager',
        'description': 'Manage warehouse operations and stock',
        'category': 'INVENTORY',
        'permissions': {
            'inventory.warehouse': ['view', 'change'],
            'inventory.stockmovement': ['view', 'add', 'change'],
            'inventory.stocktake': ['view', 'add', 'change', 'delete'],
            'product_management.product': ['view'],
            'product_management.productwarehouse': ['view', 'change'],
        },
    },
    'inventory_clerk': {
        'name': 'Inventory Clerk',
        'description': 'Basic inventory operations',
        'category': 'INVENTORY',
        'permissions': {
            'inventory.warehouse': ['view'],
            'inventory.stockmovement': ['view', 'add'],
            'inventory.stocktake': ['view', 'add'],
            'product_management.product': ['view'],
            'product_management.productwarehouse': ['view'],
        },
    },

    # Purchasing Roles
    'purchasing_manager': {
        'name': 'Purchasing Manager',
        'description': 'Full management of purchasing and suppliers',
        'category': 'PURCHASING',
        'permissions': {
            'order': ['view', 'add', 'change', 'delete'],
            'suppliers': ['view', 'add', 'change', 'delete'],
            'rma': ['view', 'add', 'change', 'delete'],
        },
    },
    'purchaser': {
        'name': 'Purchaser',
        'description': 'Create and manage purchase orders',
        'category': 'PURCHASING',
        'permissions': {
            'order.purchaseorder': ['view', 'add', 'change'],
            'order.purchaseorderitem': ['view', 'add', 'change'],
            'suppliers.supplier': ['view'],
            'suppliers.supplierproduct': ['view', 'add', 'change'],
        },
    },
    'order_approver': {
        'name': 'Order Approver',
        'description': 'Review and approve purchase orders',
        'category': 'PURCHASING',
        'permissions': {
            'order.purchaseorder': ['view', 'change'],
            'order.purchaseorderitem': ['view'],
            'suppliers.supplier': ['view'],
        },
    },

    # Document Management Roles
    'document_manager': {
        'name': 'Document Manager',
        'description': 'Full management of documents',
        'category': 'DOCUMENT',
        'permissions': {
            'documents': ['view', 'add', 'change', 'delete'],
        },
    },
    'document_clerk': {
        'name': 'Document Clerk',
        'description': 'Upload and process documents',
        'category': 'DOCUMENT',
        'permissions': {
            'documents.document': ['view', 'add', 'change'],
            'documents.documenttemplate': ['view'],
        },
    },

    # Reporting Roles
    'report_viewer': {
        'name': 'Report Viewer',
        'description': 'View reports and analytics',
        'category': 'REPORTING',
        'permissions': {
            'analytics': ['view'],
            'data_operations': ['view'],
        },
    },

    # Basic Role
    'basic_user': {
        'name': 'Basic User',
        'description': 'Basic read-only access to the system',
        'category': 'ADMIN',
        'permissions': {
            'product_management.product': ['view'],
            'inventory.warehouse': ['view'],
            'suppliers.supplier': ['view'],
        },
    },
}


def get_permission_codename(app_label, model, action):
    """
    Get the codename for a permission.

    Args:
        app_label (str): The app label (e.g., 'auth')
        model (str): The model name (e.g., 'user')
        action (str): The action (e.g., 'view', 'add', 'change', 'delete')

    Returns:
        str: The permission codename (e.g., 'view_user')
    """
    return f"{action}_{model}"


def get_permissions_for_role(role_config):
    """
    Get all permissions for a role based on its configuration.

    Args:
        role_config (dict): The role configuration

    Returns:
        list: A list of Permission objects
    """
    permissions = []

    for permission_spec, actions in role_config['permissions'].items():
        if permission_spec == 'all':
            # Special case: all permissions
            permissions.extend(Permission.objects.all())
            continue

        if '.' in permission_spec:
            # Format: 'app_label.model'
            app_label, model = permission_spec.split('.')
            try:
                content_type = ContentType.objects.get(app_label=app_label, model=model)

                for action in actions:
                    codename = get_permission_codename(app_label, model, action)
                    try:
                        permission = Permission.objects.get(
                            content_type=content_type,
                            codename=codename
                        )
                        permissions.append(permission)
                    except Permission.DoesNotExist:
                        # Skip if permission doesn't exist
                        continue
            except ContentType.DoesNotExist:
                # Skip if content type doesn't exist yet
                continue
        else:
            # Format: 'app_label'
            app_label = permission_spec
            try:
                content_types = ContentType.objects.filter(app_label=app_label)

                for content_type in content_types:
                    for action in actions:
                        codename = get_permission_codename(app_label, content_type.model, action)
                        try:
                            permission = Permission.objects.get(
                                content_type=content_type,
                                codename=codename
                            )
                            permissions.append(permission)
                        except Permission.DoesNotExist:
                            # Skip if permission doesn't exist
                            continue
            except Exception as e:
                # Skip if there's an error with content types
                # This could happen if the app doesn't exist yet
                continue

    return permissions


def create_predefined_role(role_key):
    """
    Create a predefined role.

    Args:
        role_key (str): The key of the role in PREDEFINED_ROLES

    Returns:
        Group: The created or updated Group object
    """
    if role_key not in PREDEFINED_ROLES:
        raise ValueError(f"Unknown role key: {role_key}")

    role_config = PREDEFINED_ROLES[role_key]

    # Create or get the group
    group, created = Group.objects.get_or_create(name=role_config['name'])

    # Set properties on the group
    group.description = role_config['description']
    group.category = role_config['category']
    group.role_key = role_key
    group.is_predefined = True

    # Get permissions for the role
    permissions = get_permissions_for_role(role_config)

    # Set permissions on the group
    group.permissions.set(permissions)

    return group


@transaction.atomic
def create_all_predefined_roles():
    """
    Create all predefined roles.

    Returns:
        dict: A dictionary mapping role keys to Group objects
    """
    roles = {}

    for role_key in PREDEFINED_ROLES:
        try:
            roles[role_key] = create_predefined_role(role_key)
        except Exception as e:
            # Log the error but continue with other roles
            import logging
            logger = logging.getLogger('accessmanagement')
            logger.warning(f"Error creating predefined role '{role_key}': {str(e)}")
            continue

    return roles


def get_roles_by_category():
    """
    Get all roles organized by category.

    Returns:
        dict: A dictionary mapping categories to lists of roles
    """
    roles_by_category = {category: [] for category in ROLE_CATEGORIES.values()}

    for role_key, role_config in PREDEFINED_ROLES.items():
        category = ROLE_CATEGORIES[role_config['category']]
        try:
            group = Group.objects.get(name=role_config['name'])
            roles_by_category[category].append(group)
        except Group.DoesNotExist:
            # Skip if the role doesn't exist
            continue

    return roles_by_category
