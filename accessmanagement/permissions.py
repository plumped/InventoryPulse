# accessmanagement/permissions.py
"""
Central module for all permission-related constants and functions.
Consolidated from core/permissions.py
"""
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models

# Permission groups
PERMISSION_GROUPS = {
    'inventory_admin': 'Lager-Administrator',
    'inventory_manager': 'Lager-Manager',
    'inventory_viewer': 'Lager-Betrachter',
    'product_admin': 'Produkt-Administrator',
    'product_manager': 'Produkt-Manager',
    'product_viewer': 'Produkt-Betrachter',
    'supplier_admin': 'Lieferanten-Administrator',
    'supplier_manager': 'Lieferanten-Manager',
    'supplier_viewer': 'Lieferanten-Betrachter',
    'report_viewer': 'Bericht-Betrachter',
    'import_admin': 'Import-Administrator',
    'order_admin': 'Bestellungs-Administrator',
    'order_manager': 'Bestellungs-Manager',
    'order_viewer': 'Bestellungs-Betrachter',
}

# Functional areas
PERMISSION_AREAS = {
    'inventory': 'Lagerverwaltung',
    'product': 'Produktverwaltung',
    'supplier': 'Lieferantenverwaltung',
    'report': 'Berichtswesen',
    'import': 'Datenimport',
    'order': 'Bestellverwaltung',
}

# Permission levels
PERMISSION_LEVELS = {
    'view': 'Ansehen',
    'edit': 'Bearbeiten',
    'create': 'Erstellen',
    'delete': 'Löschen',
    'admin': 'Administrieren',
    'approve': 'Genehmigen',
}


def create_permission_groups():
    """Creates all permission groups if they don't exist."""
    for code, name in PERMISSION_GROUPS.items():
        Group.objects.get_or_create(name=name)


def get_permission_name(area, action):
    """Generates a standardized permission name."""
    return f'can_{action}_{area}'


def setup_permissions():
    """Sets up all permissions in the system."""
    # Create permission groups
    create_permission_groups()

    # ContentType for custom permission
    ct, _ = ContentType.objects.get_or_create(
        app_label='accessmanagement',
        model='custompermission'
    )

    # Create permissions
    for area in PERMISSION_AREAS.keys():
        for level in PERMISSION_LEVELS.keys():
            perm_name = get_permission_name(area, level)
            perm_display = f'Kann {PERMISSION_LEVELS[level]} in {PERMISSION_AREAS[area]}'

            perm, created = Permission.objects.get_or_create(
                codename=perm_name,
                name=perm_display,
                content_type=ct,
            )

    # Assign permissions to groups
    # Admin group gets all permissions for inventory
    admin_group = Group.objects.get(name=PERMISSION_GROUPS['inventory_admin'])
    inventory_perms = Permission.objects.filter(codename__startswith='can_', codename__contains='_inventory')
    admin_group.permissions.add(*inventory_perms)

    # Manager group gets view, edit, create for inventory
    manager_group = Group.objects.get(name=PERMISSION_GROUPS['inventory_manager'])
    manager_perms = Permission.objects.filter(
        codename__in=[
            get_permission_name('inventory', 'view'),
            get_permission_name('inventory', 'edit'),
            get_permission_name('inventory', 'create')
        ]
    )
    manager_group.permissions.add(*manager_perms)

    # Viewer group only gets view permission for inventory
    viewer_group = Group.objects.get(name=PERMISSION_GROUPS['inventory_viewer'])
    viewer_perms = Permission.objects.filter(
        codename=get_permission_name('inventory', 'view')
    )
    viewer_group.permissions.add(*viewer_perms)

    # Permissions for orders
    # Admin group for orders
    order_admin_group = Group.objects.get(name=PERMISSION_GROUPS['order_admin'])
    order_perms = Permission.objects.filter(codename__startswith='can_', codename__contains='_order')
    order_admin_group.permissions.add(*order_perms)

    # Manager group for orders
    order_manager_group = Group.objects.get(name=PERMISSION_GROUPS['order_manager'])
    order_manager_perms = Permission.objects.filter(
        codename__in=[
            get_permission_name('order', 'view'),
            get_permission_name('order', 'edit'),
            get_permission_name('order', 'create')
        ]
    )
    order_manager_group.permissions.add(*order_manager_perms)

    # Viewer group for orders
    order_viewer_group = Group.objects.get(name=PERMISSION_GROUPS['order_viewer'])
    order_viewer_perms = Permission.objects.filter(
        codename=get_permission_name('order', 'view')
    )
    order_viewer_group.permissions.add(*order_viewer_perms)


def has_permission(user, area, action):
    """Checks if a user has a specific permission."""
    if user.is_superuser:
        return True

    perm_name = get_permission_name(area, action)
    return user.has_perm(f'accessmanagement.{perm_name}')