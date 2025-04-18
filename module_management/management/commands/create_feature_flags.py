import logging

from django.core.management.base import BaseCommand
from django.db import transaction

from module_management.models import Module, FeatureFlag

logger = logging.getLogger('module_management')

class Command(BaseCommand):
    help = 'Creates feature flags defined in the documentation'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Creating feature flags...'))

        try:
            with transaction.atomic():
                self._create_feature_flags()

            self.stdout.write(self.style.SUCCESS('Successfully created feature flags'))
        except Exception as e:
            logger.error(f"Error creating feature flags: {str(e)}")
            self.stdout.write(self.style.ERROR(f'Error creating feature flags: {str(e)}'))

    def _create_feature_flags(self):
        """Create feature flags if they don't exist"""

        # Make sure modules exist first
        modules = Module.objects.filter(is_active=True)
        if not modules.exists():
            self.stdout.write(self.style.WARNING('No active modules found. Run setup_default_modules first.'))
            return

        # Get module references
        try:
            inventory_module = Module.objects.get(code='inventory')
            suppliers_module = Module.objects.get(code='suppliers')
            order_module = Module.objects.get(code='order')
            analytics_module = Module.objects.get(code='analytics')
            rma_module = Module.objects.get(code='rma')
            documents_module = Module.objects.get(code='documents')
        except Module.DoesNotExist as e:
            self.stdout.write(self.style.ERROR(f'Module not found: {str(e)}'))
            return

        # Define feature flags
        feature_flags = [
            # Inventory Module
            {
                'name': 'Stock Take Reports',
                'code': 'stock_take_reports',
                'description': 'Enables detailed reporting for stock takes',
                'module': inventory_module,
                'is_active': True,
                'feature_type': 'boolean',
                'default_value': 'false',
            },
            {
                'name': 'CSV Export',
                'code': 'export_csv',
                'description': 'Enables CSV export functionality',
                'module': inventory_module,
                'is_active': True,
                'feature_type': 'boolean',
                'default_value': 'false',
            },
            {
                'name': 'PDF Export',
                'code': 'export_pdf',
                'description': 'Enables PDF export functionality',
                'module': inventory_module,
                'is_active': True,
                'feature_type': 'boolean',
                'default_value': 'false',
            },
            {
                'name': 'Bulk Warehouse Transfer',
                'code': 'bulk_warehouse_transfer',
                'description': 'Enables bulk transfer of products between warehouses',
                'module': inventory_module,
                'is_active': True,
                'feature_type': 'boolean',
                'default_value': 'false',
            },
            {
                'name': 'Bulk Product Management',
                'code': 'bulk_product_management',
                'description': 'Enables bulk product management operations',
                'module': inventory_module,
                'is_active': True,
                'feature_type': 'boolean',
                'default_value': 'false',
            },
            
            # Suppliers Module
            {
                'name': 'Supplier Analytics',
                'code': 'supplier_analytics',
                'description': 'Enables analytics for supplier performance',
                'module': suppliers_module,
                'is_active': True,
                'feature_type': 'boolean',
                'default_value': 'false',
            },
            {
                'name': 'Supplier Documents',
                'code': 'supplier_documents',
                'description': 'Enables document management for suppliers',
                'module': suppliers_module,
                'is_active': True,
                'feature_type': 'boolean',
                'default_value': 'false',
            },
            
            # Order Module
            {
                'name': 'Advanced Order Processing',
                'code': 'advanced_order_processing',
                'description': 'Enables advanced order processing features',
                'module': order_module,
                'is_active': True,
                'feature_type': 'boolean',
                'default_value': 'false',
            },
            {
                'name': 'Order Tracking',
                'code': 'order_tracking',
                'description': 'Enables order tracking functionality',
                'module': order_module,
                'is_active': True,
                'feature_type': 'boolean',
                'default_value': 'false',
            },
            
            # Analytics Module
            {
                'name': 'Basic Reports',
                'code': 'basic_reports',
                'description': 'Enables basic reporting functionality',
                'module': analytics_module,
                'is_active': True,
                'feature_type': 'boolean',
                'default_value': 'true',
            },
            {
                'name': 'Advanced Analytics',
                'code': 'advanced_analytics',
                'description': 'Enables advanced analytics and reporting',
                'module': analytics_module,
                'is_active': True,
                'feature_type': 'boolean',
                'default_value': 'false',
            },
            {
                'name': 'Data Export',
                'code': 'data_export',
                'description': 'Enables data export functionality',
                'module': analytics_module,
                'is_active': True,
                'feature_type': 'boolean',
                'default_value': 'false',
            },
            
            # RMA Module
            {
                'name': 'Basic RMA',
                'code': 'basic_rma',
                'description': 'Enables basic RMA processing',
                'module': rma_module,
                'is_active': True,
                'feature_type': 'boolean',
                'default_value': 'true',
            },
            {
                'name': 'Advanced RMA',
                'code': 'advanced_rma',
                'description': 'Enables advanced RMA features',
                'module': rma_module,
                'is_active': True,
                'feature_type': 'boolean',
                'default_value': 'false',
            },
            
            # Documents Module
            {
                'name': 'Document Upload',
                'code': 'document_upload',
                'description': 'Enables document upload functionality',
                'module': documents_module,
                'is_active': True,
                'feature_type': 'boolean',
                'default_value': 'true',
            },
            {
                'name': 'Advanced Document Search',
                'code': 'advanced_document_search',
                'description': 'Enables advanced document search functionality',
                'module': documents_module,
                'is_active': True,
                'feature_type': 'boolean',
                'default_value': 'false',
            },
        ]

        for flag_data in feature_flags:
            # Create or update the feature flag
            flag, created = FeatureFlag.objects.update_or_create(
                code=flag_data['code'],
                defaults={
                    'name': flag_data['name'],
                    'description': flag_data['description'],
                    'module': flag_data['module'],
                    'is_active': flag_data['is_active'],
                    'feature_type': flag_data['feature_type'],
                    'default_value': flag_data['default_value'],
                }
            )

            if created:
                self.stdout.write(f"Created feature flag: {flag.name}")
            else:
                self.stdout.write(f"Updated feature flag: {flag.name}")