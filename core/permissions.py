from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import models

# Berechtigungsgruppen
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
}

# Funktionsbereiche
PERMISSION_AREAS = {
    'inventory': 'Lagerverwaltung',
    'product': 'Produktverwaltung',
    'supplier': 'Lieferantenverwaltung',
    'report': 'Berichtswesen',
    'import': 'Datenimport',
}

# Berechtigungsstufen
PERMISSION_LEVELS = {
    'view': 'Ansehen',
    'edit': 'Bearbeiten',
    'create': 'Erstellen',
    'delete': 'Löschen',
    'admin': 'Administrieren',
}


def create_permission_groups():
    """Erstellt alle Berechtigungsgruppen, falls sie nicht existieren."""
    for code, name in PERMISSION_GROUPS.items():
        Group.objects.get_or_create(name=name)


def get_permission_name(area, action):
    """Generiert einen einheitlichen Berechtigungsnamen."""
    return f'can_{action}_{area}'


def setup_permissions():
    """Richtet alle Berechtigungen im System ein."""
    # Berechtigungsgruppen erstellen
    create_permission_groups()

    # ContentType für eigene Berechtigung
    ct, _ = ContentType.objects.get_or_create(
        app_label='core',
        model='custompermission'
    )

    # Berechtigungen erstellen
    for area in PERMISSION_AREAS.keys():
        for level in PERMISSION_LEVELS.keys():
            perm_name = get_permission_name(area, level)
            perm_display = f'Kann {PERMISSION_LEVELS[level]} in {PERMISSION_AREAS[area]}'

            perm, created = Permission.objects.get_or_create(
                codename=perm_name,
                name=perm_display,
                content_type=ct,
            )

    # Berechtigungen den Gruppen zuweisen
    # Admin-Gruppe erhält alle Berechtigungen
    admin_group = Group.objects.get(name=PERMISSION_GROUPS['inventory_admin'])
    inventory_perms = Permission.objects.filter(codename__startswith='can_', codename__contains='_inventory')
    admin_group.permissions.add(*inventory_perms)

    # Manager-Gruppe erhält Ansehen, Bearbeiten und Erstellen
    manager_group = Group.objects.get(name=PERMISSION_GROUPS['inventory_manager'])
    manager_perms = Permission.objects.filter(
        codename__in=[
            get_permission_name('inventory', 'view'),
            get_permission_name('inventory', 'edit'),
            get_permission_name('inventory', 'create')
        ]
    )
    manager_group.permissions.add(*manager_perms)

    # Viewer-Gruppe erhält nur Ansehen
    viewer_group = Group.objects.get(name=PERMISSION_GROUPS['inventory_viewer'])
    viewer_perms = Permission.objects.filter(
        codename=get_permission_name('inventory', 'view')
    )
    viewer_group.permissions.add(*viewer_perms)

    # Ähnlich für andere Bereiche...


def has_permission(user, area, action):
    """Prüft, ob ein Benutzer eine bestimmte Berechtigung hat."""
    if user.is_superuser:
        return True

    perm_name = get_permission_name(area, action)
    return user.has_perm(f'core.{perm_name}')


class CustomPermission(models.Model):
    """Dummy-Model für ContentType der benutzerdefinierten Berechtigungen."""

    class Meta:
        managed = False  # Keine Tabelle in der Datenbank erstellen
        default_permissions = ()
        permissions = (
            ('can_view_inventory', 'Kann Lagerverwaltung ansehen'),
            ('can_edit_inventory', 'Kann Lagerverwaltung bearbeiten'),
            ('can_create_inventory', 'Kann in Lagerverwaltung erstellen'),
            ('can_delete_inventory', 'Kann in Lagerverwaltung löschen'),
            ('can_admin_inventory', 'Kann Lagerverwaltung administrieren'),
            # Weitere Berechtigungen...
        )