import logging
from decimal import Decimal

from django.core.management.base import BaseCommand
from django.db import transaction

from module_management.models import Module, FeatureFlag

logger = logging.getLogger('module_management')


class Command(BaseCommand):
    help = 'Sets up default modules and feature flags in the system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Setting up default modules...'))

        try:
            with transaction.atomic():
                # Create default modules
                self._create_modules()

                # Create feature flags for modules
                self._create_feature_flags()

            self.stdout.write(self.style.SUCCESS('Successfully set up default modules and feature flags'))
        except Exception as e:
            logger.error(f"Error setting up default modules: {str(e)}")
            self.stdout.write(self.style.ERROR(f'Error setting up default modules: {str(e)}'))

    def _create_modules(self):
        """Create default modules if they don't exist"""
        modules = [
            {
                'name': 'Inventory Management',
                'code': 'inventory',
                'description': 'Manage inventory, stock levels, and warehouse operations',
                'price_monthly': Decimal('49.99'),
                'price_yearly': Decimal('499.90'),
            },
            {
                'name': 'Supplier Management',
                'code': 'suppliers',
                'description': 'Manage suppliers, purchase orders, and supplier relationships',
                'price_monthly': Decimal('39.99'),
                'price_yearly': Decimal('399.90'),
            },
            {
                'name': 'Order Management',
                'code': 'order',
                'description': 'Manage customer orders, order processing, and fulfillment',
                'price_monthly': Decimal('49.99'),
                'price_yearly': Decimal('499.90'),
            },
            {
                'name': 'Analytics',
                'code': 'analytics',
                'description': 'Advanced analytics, reporting, and business intelligence',
                'price_monthly': Decimal('59.99'),
                'price_yearly': Decimal('599.90'),
            },
            {
                'name': 'RMA Management',
                'code': 'rma',
                'description': 'Manage returns, warranties, and RMA processes',
                'price_monthly': Decimal('29.99'),
                'price_yearly': Decimal('299.90'),
            },
            {
                'name': 'Document Management',
                'code': 'documents',
                'description': 'Manage documents, OCR processing, and document workflows',
                'price_monthly': Decimal('19.99'),
                'price_yearly': Decimal('199.90'),
            },
        ]

        for module_data in modules:
            module, created = Module.objects.update_or_create(
                code=module_data['code'],
                defaults={
                    'name': module_data['name'],
                    'description': module_data['description'],
                    'price_monthly': module_data['price_monthly'],
                    'price_yearly': module_data['price_yearly'],
                    'is_active': True,
                }
            )

            if created:
                self.stdout.write(f"Created module: {module.name}")
            else:
                self.stdout.write(f"Updated module: {module.name}")

    def _create_feature_flags(self):
        """Create feature flags for modules if they don't exist"""
        feature_flags = [
            # Inventory module features
            {
                'module_code': 'inventory',
                'name': 'Multi-warehouse Support',
                'code': 'multi_warehouse',
                'description': 'Support for multiple warehouses and locations',
            },
            {
                'module_code': 'inventory',
                'name': 'Barcode Scanning',
                'code': 'barcode_scanning',
                'description': 'Support for barcode scanning and generation',
            },
            {
                'module_code': 'inventory',
                'name': 'Batch/Lot Tracking',
                'code': 'batch_tracking',
                'description': 'Track inventory by batch or lot number',
            },

            # Supplier module features
            {
                'module_code': 'suppliers',
                'name': 'Supplier Portal',
                'code': 'supplier_portal',
                'description': 'External portal for suppliers to manage orders',
            },
            {
                'module_code': 'suppliers',
                'name': 'Automated Purchasing',
                'code': 'auto_purchasing',
                'description': 'Automatically generate purchase orders based on stock levels',
            },

            # Order module features
            {
                'module_code': 'order',
                'name': 'Customer Portal',
                'code': 'customer_portal',
                'description': 'External portal for customers to place and track orders',
            },
            {
                'module_code': 'order',
                'name': 'Shipping Integration',
                'code': 'shipping_integration',
                'description': 'Integration with shipping carriers for label generation and tracking',
            },

            # Analytics module features
            {
                'module_code': 'analytics',
                'name': 'Advanced Reports',
                'code': 'advanced_reports',
                'description': 'Access to advanced reporting and analytics',
            },
            {
                'module_code': 'analytics',
                'name': 'Custom Dashboards',
                'code': 'custom_dashboards',
                'description': 'Create custom dashboards and visualizations',
            },

            # RMA module features
            {
                'module_code': 'rma',
                'name': 'Warranty Tracking',
                'code': 'warranty_tracking',
                'description': 'Track warranty information and expiration dates',
            },

            # Document module features
            {
                'module_code': 'documents',
                'name': 'OCR Processing',
                'code': 'ocr_processing',
                'description': 'Optical character recognition for document processing',
            },
        ]

        for flag_data in feature_flags:
            try:
                module = Module.objects.get(code=flag_data['module_code'])

                flag, created = FeatureFlag.objects.update_or_create(
                    code=flag_data['code'],
                    defaults={
                        'name': flag_data['name'],
                        'description': flag_data['description'],
                        'module': module,
                        'is_active': True,
                    }
                )

                if created:
                    self.stdout.write(f"Created feature flag: {flag.name} for module {module.name}")
                else:
                    self.stdout.write(f"Updated feature flag: {flag.name} for module {module.name}")
            except Module.DoesNotExist:
                self.stdout.write(self.style.WARNING(
                    f"Module {flag_data['module_code']} not found, skipping feature flag {flag_data['name']}"))
