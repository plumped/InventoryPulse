import logging
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from module_management.models import Module, FeatureFlag, SubscriptionPackage

logger = logging.getLogger('module_management')


class Command(BaseCommand):
    help = 'Creates default subscription packages in the system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Creating subscription packages...'))

        try:
            with transaction.atomic():
                self._create_subscription_packages()

            self.stdout.write(self.style.SUCCESS('Successfully created subscription packages'))
        except Exception as e:
            logger.error(f"Error creating subscription packages: {str(e)}")
            self.stdout.write(self.style.ERROR(f'Error creating subscription packages: {str(e)}'))

    def _create_subscription_packages(self):
        """Create default subscription packages if they don't exist"""

        # Make sure modules exist first
        modules = Module.objects.filter(is_active=True)
        if not modules.exists():
            self.stdout.write(self.style.WARNING('No active modules found. Run setup_default_modules first.'))
            return

        # Define packages
        packages = [
            {
                'name': 'Basic',
                'code': 'basic',
                'description': 'Basic inventory management for small businesses',
                'price_monthly': Decimal('49.99'),
                'price_yearly': Decimal('499.90'),
                'modules': ['inventory'],
                'feature_flags': [],
            },
            {
                'name': 'Standard',
                'code': 'standard',
                'description': 'Standard package with inventory and supplier management',
                'price_monthly': Decimal('89.99'),
                'price_yearly': Decimal('899.90'),
                'modules': ['inventory', 'suppliers'],
                'feature_flags': ['multi_warehouse', 'barcode_scanning'],
            },
            {
                'name': 'Professional',
                'code': 'professional',
                'description': 'Professional package with inventory, supplier, and order management',
                'price_monthly': Decimal('129.99'),
                'price_yearly': Decimal('1299.90'),
                'modules': ['inventory', 'suppliers', 'order'],
                'feature_flags': ['multi_warehouse', 'barcode_scanning', 'batch_tracking', 'auto_purchasing'],
            },
            {
                'name': 'Enterprise',
                'code': 'enterprise',
                'description': 'Complete enterprise solution with all modules',
                'price_monthly': Decimal('199.99'),
                'price_yearly': Decimal('1999.90'),
                'modules': ['inventory', 'suppliers', 'order', 'analytics', 'rma', 'documents'],
                'feature_flags': [
                    'multi_warehouse', 'barcode_scanning', 'batch_tracking',
                    'supplier_portal', 'auto_purchasing', 'customer_portal',
                    'shipping_integration', 'advanced_reports', 'warranty_tracking',
                    'ocr_processing'
                ],
            },
        ]

        for package_data in packages:
            # Create or update the package
            package, created = SubscriptionPackage.objects.update_or_create(
                code=package_data['code'],
                defaults={
                    'name': package_data['name'],
                    'description': package_data['description'],
                    'price_monthly': package_data['price_monthly'],
                    'price_yearly': package_data['price_yearly'],
                    'is_active': True,
                }
            )

            # Add modules to the package
            module_codes = package_data['modules']
            modules = Module.objects.filter(code__in=module_codes, is_active=True)
            package.modules.set(modules)

            # Add feature flags to the package
            feature_codes = package_data['feature_flags']
            features = FeatureFlag.objects.filter(code__in=feature_codes, is_active=True)
            package.feature_flags.set(features)

            if created:
                self.stdout.write(f"Created package: {package.name}")
            else:
                self.stdout.write(f"Updated package: {package.name}")

            # Log the modules and features in the package
            module_names = ', '.join([m.name for m in package.modules.all()])
            feature_names = ', '.join([f.name for f in package.feature_flags.all()])

            self.stdout.write(f"  - Modules: {module_names}")
            self.stdout.write(f"  - Features: {feature_names}")
