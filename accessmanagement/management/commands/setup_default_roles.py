import logging

from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.management.base import BaseCommand
from django.db import transaction

from accessmanagement.models import Role

logger = logging.getLogger('accessmanagement')

class Command(BaseCommand):
    help = 'Sets up default roles with appropriate permissions'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Setting up default roles...'))

        try:
            with transaction.atomic():
                # Create default roles
                self._create_roles()

            self.stdout.write(self.style.SUCCESS('Successfully set up default roles'))
        except Exception as e:
            logger.error(f"Error setting up default roles: {str(e)}")
            self.stdout.write(self.style.ERROR(f'Error setting up default roles: {str(e)}'))

    def _create_roles(self):
        """Create default roles if they don't exist"""

        # Define the roles and their permissions
        roles = [
            {
                'name': 'Administrator',
                'description': 'Full access to all system features',
                'is_system_role': True,
                'permissions': self._get_all_permissions(),
            },
            {
                'name': 'Admin Dashboard User',
                'description': 'Access to the admin dashboard',
                'is_system_role': True,
                'permissions': self._get_permissions_for_apps(['admin_dashboard']),
            },
            {
                'name': 'Inventory Manager',
                'description': 'Manages inventory, stock levels, and warehouse operations',
                'is_system_role': True,
                'permissions': self._get_permissions_for_apps(['inventory', 'product_management', 'product', 'serialnumber']),
            },
            {
                'name': 'Order Manager',
                'description': 'Manages customer orders, order processing, and fulfillment',
                'is_system_role': True,
                'permissions': self._get_permissions_for_apps(['order']),
            },
            {
                'name': 'Import Manager',
                'description': 'Manages imports and exports',
                'is_system_role': True,
                'permissions': self._get_permissions_for_apps(['import']),
            },
            {
                'name': 'Supplier Manager',
                'description': 'Manages suppliers, purchase orders, and supplier relationships',
                'is_system_role': True,
                'permissions': self._get_permissions_for_apps(['suppliers', 'supplier']),
            },
            {
                'name': 'Analytics User',
                'description': 'Access to analytics and reporting features',
                'is_system_role': True,
                'permissions': self._get_permissions_for_apps(['analytics'], exclude_actions=['add', 'change', 'delete']),
            },
            {
                'name': 'Document Manager',
                'description': 'Manages documents, OCR processing, and document workflows',
                'is_system_role': True,
                'permissions': self._get_permissions_for_apps(['documents']),
            },
            {
                'name': 'RMA Manager',
                'description': 'Manages returns, warranties, and RMA processes',
                'is_system_role': True,
                'permissions': self._get_permissions_for_apps(['rma']),
            },
            {
                'name': 'Read-Only User',
                'description': 'Read-only access to all system features',
                'is_system_role': True,
                'permissions': self._get_all_permissions(exclude_actions=['add', 'change', 'delete']),
            },
        ]

        for role_data in roles:
            role, created = Role.objects.update_or_create(
                name=role_data['name'],
                defaults={
                    'description': role_data['description'],
                    'is_system_role': role_data['is_system_role'],
                }
            )

            # Set permissions
            role.permissions.set(role_data['permissions'])

            if created:
                self.stdout.write(f"Created role: {role.name}")
            else:
                self.stdout.write(f"Updated role: {role.name}")

    def _get_all_permissions(self, exclude_actions=None):
        """Get all permissions in the system, optionally excluding certain actions"""
        exclude_actions = exclude_actions or []

        # Get all permissions
        permissions = Permission.objects.all()

        # Exclude certain actions if specified
        if exclude_actions:
            for action in exclude_actions:
                permissions = permissions.exclude(codename__startswith=f"{action}_")

        return permissions

    def _get_permissions_for_apps(self, app_labels, exclude_actions=None):
        """Get permissions for specific apps, optionally excluding certain actions"""
        exclude_actions = exclude_actions or []

        # Get content types for the specified apps
        content_types = ContentType.objects.filter(app_label__in=app_labels)

        # Get permissions for those content types
        permissions = Permission.objects.filter(content_type__in=content_types)

        # Exclude certain actions if specified
        if exclude_actions:
            for action in exclude_actions:
                permissions = permissions.exclude(codename__startswith=f"{action}_")

        return permissions
