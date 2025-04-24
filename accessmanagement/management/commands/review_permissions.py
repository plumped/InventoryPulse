import csv
import os
from datetime import timedelta

from django.contrib.auth.models import User
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from accessmanagement.models import WarehouseAccess, ObjectPermission, UserProfile


class Command(BaseCommand):
    help = 'Generate permission review reports for regular security audits'

    def add_arguments(self, parser):
        parser.add_argument(
            '--output',
            default='permission_review',
            help='Output directory name (default: permission_review)'
        )
        parser.add_argument(
            '--inactive-days',
            type=int,
            default=90,
            help='Number of days of inactivity to flag (default: 90)'
        )
        parser.add_argument(
            '--format',
            choices=['csv', 'json'],
            default='csv',
            help='Output format (default: csv)'
        )

    def handle(self, *args, **options):
        output_dir = options['output']
        inactive_days = options['inactive_days']
        output_format = options['format']

        # Create output directory if it doesn't exist
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # Generate timestamp for filenames
        timestamp = timezone.now().strftime('%Y%m%d_%H%M%S')

        # Generate reports
        self.generate_user_permissions_report(output_dir, timestamp, inactive_days, output_format)
        self.generate_warehouse_access_report(output_dir, timestamp, output_format)
        self.generate_object_permissions_report(output_dir, timestamp, output_format)
        self.generate_expired_permissions_report(output_dir, timestamp, output_format)

        self.stdout.write(self.style.SUCCESS(f'Permission review reports generated in {output_dir}'))

    def generate_user_permissions_report(self, output_dir, timestamp, inactive_days, output_format):
        """Generate report of all user permissions with inactive users flagged."""
        filename = os.path.join(output_dir, f'user_permissions_{timestamp}.csv')
        inactive_date = timezone.now() - timedelta(days=inactive_days)

        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Username', 'Email', 'Is Active', 'Is Staff', 'Is Superuser', 
                'Last Login', 'Date Joined', 'Groups', 'Direct Permissions',
                'Inactive Flag', 'Departments'
            ])

            for user in User.objects.all().order_by('username'):
                # Check if user is inactive based on last login
                inactive_flag = ''
                try:
                    if user.last_login and user.last_login < inactive_date:
                        inactive_flag = f'Inactive for {inactive_days}+ days'
                    elif not user.last_login and user.date_joined < inactive_date:
                        inactive_flag = 'Never logged in'
                except TypeError:
                    # Handle datetime comparison errors
                    self.stderr.write(self.style.WARNING(f"Warning: Could not compare datetimes for user {user.username}"))
                    inactive_flag = 'Unknown (datetime error)'

                # Get user's groups
                groups = ', '.join([g.name for g in user.groups.all()])

                # Get user's direct permissions
                direct_permissions = ', '.join([p.name for p in user.user_permissions.all()])

                # Get user's departments
                departments = ''
                if hasattr(user, 'profile'):
                    departments = ', '.join([d.name for d in user.profile.departments.all()])

                writer.writerow([
                    user.username,
                    user.email,
                    user.is_active,
                    user.is_staff,
                    user.is_superuser,
                    user.last_login,
                    user.date_joined,
                    groups,
                    direct_permissions,
                    inactive_flag,
                    departments
                ])

        self.stdout.write(f'User permissions report generated: {filename}')

    def generate_warehouse_access_report(self, output_dir, timestamp, output_format):
        """Generate report of all warehouse access permissions."""
        filename = os.path.join(output_dir, f'warehouse_access_{timestamp}.csv')

        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Warehouse', 'Department', 'Can View', 'Can Edit', 'Can Manage Stock',
                'Users with Access'
            ])

            for access in WarehouseAccess.objects.all().select_related('warehouse', 'department'):
                # Get users in this department
                users_with_access = UserProfile.objects.filter(departments=access.department)
                user_list = ', '.join([p.user.username for p in users_with_access])

                writer.writerow([
                    access.warehouse.name,
                    access.department.name,
                    access.can_view,
                    access.can_edit,
                    access.can_manage_stock,
                    user_list
                ])

        self.stdout.write(f'Warehouse access report generated: {filename}')

    def generate_object_permissions_report(self, output_dir, timestamp, output_format):
        """Generate report of all object-level permissions."""
        filename = os.path.join(output_dir, f'object_permissions_{timestamp}.csv')

        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Object Type', 'Object ID', 'User/Department', 'Can View', 'Can Edit', 
                'Can Delete', 'Valid From', 'Valid Until', 'Is Currently Valid'
            ])

            for perm in ObjectPermission.objects.all().select_related('content_type', 'user', 'department'):
                # Determine if user or department permission
                target = perm.user.username if perm.user else f"Department: {perm.department.name}"

                writer.writerow([
                    perm.content_type.model,
                    perm.object_id,
                    target,
                    perm.can_view,
                    perm.can_edit,
                    perm.can_delete,
                    perm.valid_from,
                    perm.valid_until,
                    perm.is_valid()
                ])

        self.stdout.write(f'Object permissions report generated: {filename}')

    def generate_expired_permissions_report(self, output_dir, timestamp, output_format):
        """Generate report of expired or soon-to-expire permissions."""
        filename = os.path.join(output_dir, f'expired_permissions_{timestamp}.csv')

        # Define soon-to-expire as within the next 30 days
        soon_expire_date = timezone.now() + timedelta(days=30)

        with open(filename, 'w', newline='') as csvfile:
            writer = csv.writer(csvfile)
            writer.writerow([
                'Permission Type', 'Object', 'User/Department', 'Valid Until', 'Status'
            ])

            # Check object permissions
            try:
                permissions = ObjectPermission.objects.filter(
                    Q(valid_until__lt=soon_expire_date) & ~Q(valid_until=None)
                ).select_related('content_type', 'user', 'department')
            except Exception as e:
                self.stderr.write(self.style.ERROR(f"Error filtering permissions: {str(e)}"))
                permissions = []

            for perm in permissions:
                target = perm.user.username if perm.user else f"Department: {perm.department.name}"
                try:
                    status = 'Expired' if perm.valid_until < timezone.now() else 'Expiring Soon'
                except TypeError:
                    # Handle datetime comparison errors
                    self.stderr.write(self.style.WARNING(f"Warning: Could not compare datetimes for permission {perm.id}"))
                    status = 'Unknown (datetime error)'

                writer.writerow([
                    'Object Permission',
                    f"{perm.content_type.model}:{perm.object_id}",
                    target,
                    perm.valid_until,
                    status
                ])

        self.stdout.write(f'Expired permissions report generated: {filename}')
