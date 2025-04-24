import logging

from django.core.management.base import BaseCommand

from accessmanagement.models import Role, UserRole
from master_data.models.organisations_models import Organization

logger = logging.getLogger('accessmanagement')

class Command(BaseCommand):
    help = 'Fixes permissions for existing roles and users'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Fixing permissions...'))
        
        try:
            # First, run the setup_default_roles command to ensure all roles exist
            from django.core.management import call_command
            call_command('setup_default_roles')
            
            # Now, ensure all users with Administrator role have the correct permissions
            self._fix_administrator_permissions()
            
            self.stdout.write(self.style.SUCCESS('Successfully fixed permissions'))
        except Exception as e:
            logger.error(f"Error fixing permissions: {str(e)}")
            self.stdout.write(self.style.ERROR(f'Error fixing permissions: {str(e)}'))
    
    def _fix_administrator_permissions(self):
        """Ensure all users with Administrator role have the correct permissions"""
        # Get the Administrator role
        try:
            admin_role = Role.objects.get(name='Administrator')
        except Role.DoesNotExist:
            self.stdout.write(self.style.ERROR('Administrator role not found'))
            return
        
        # Get all UserRole objects with Administrator role
        admin_user_roles = UserRole.objects.filter(role=admin_role)
        
        # Log the number of administrators found
        self.stdout.write(f"Found {admin_user_roles.count()} users with Administrator role")
        
        # Ensure each administrator has the correct permissions
        for user_role in admin_user_roles:
            user = user_role.user
            organization = user_role.organization
            
            self.stdout.write(f"Fixing permissions for {user.username} in {organization.name if organization else 'global scope'}")
            
            # Ensure the user has the Admin Dashboard User role
            try:
                admin_dashboard_role = Role.objects.get(name='Admin Dashboard User')
                UserRole.objects.get_or_create(
                    user=user,
                    role=admin_dashboard_role,
                    organization=organization,
                    defaults={'created_at': user_role.created_at}
                )
                self.stdout.write(f"  - Added Admin Dashboard User role")
            except Role.DoesNotExist:
                self.stdout.write(self.style.WARNING('  - Admin Dashboard User role not found'))
            
            # Ensure the user has the Inventory Manager role
            try:
                inventory_role = Role.objects.get(name='Inventory Manager')
                UserRole.objects.get_or_create(
                    user=user,
                    role=inventory_role,
                    organization=organization,
                    defaults={'created_at': user_role.created_at}
                )
                self.stdout.write(f"  - Added Inventory Manager role")
            except Role.DoesNotExist:
                self.stdout.write(self.style.WARNING('  - Inventory Manager role not found'))
            
            # Ensure the user has the Supplier Manager role
            try:
                supplier_role = Role.objects.get(name='Supplier Manager')
                UserRole.objects.get_or_create(
                    user=user,
                    role=supplier_role,
                    organization=organization,
                    defaults={'created_at': user_role.created_at}
                )
                self.stdout.write(f"  - Added Supplier Manager role")
            except Role.DoesNotExist:
                self.stdout.write(self.style.WARNING('  - Supplier Manager role not found'))
            
            # Ensure the user has the Order Manager role
            try:
                order_role = Role.objects.get(name='Order Manager')
                UserRole.objects.get_or_create(
                    user=user,
                    role=order_role,
                    organization=organization,
                    defaults={'created_at': user_role.created_at}
                )
                self.stdout.write(f"  - Added Order Manager role")
            except Role.DoesNotExist:
                self.stdout.write(self.style.WARNING('  - Order Manager role not found'))
            
            # Ensure the user has the Import Manager role
            try:
                import_role = Role.objects.get(name='Import Manager')
                UserRole.objects.get_or_create(
                    user=user,
                    role=import_role,
                    organization=organization,
                    defaults={'created_at': user_role.created_at}
                )
                self.stdout.write(f"  - Added Import Manager role")
            except Role.DoesNotExist:
                self.stdout.write(self.style.WARNING('  - Import Manager role not found'))
            
            # Ensure the user has the Document Manager role
            try:
                document_role = Role.objects.get(name='Document Manager')
                UserRole.objects.get_or_create(
                    user=user,
                    role=document_role,
                    organization=organization,
                    defaults={'created_at': user_role.created_at}
                )
                self.stdout.write(f"  - Added Document Manager role")
            except Role.DoesNotExist:
                self.stdout.write(self.style.WARNING('  - Document Manager role not found'))
            
            # Ensure the user has the RMA Manager role
            try:
                rma_role = Role.objects.get(name='RMA Manager')
                UserRole.objects.get_or_create(
                    user=user,
                    role=rma_role,
                    organization=organization,
                    defaults={'created_at': user_role.created_at}
                )
                self.stdout.write(f"  - Added RMA Manager role")
            except Role.DoesNotExist:
                self.stdout.write(self.style.WARNING('  - RMA Manager role not found'))