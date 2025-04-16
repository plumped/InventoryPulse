import logging
from decimal import Decimal

from django.core.management.base import BaseCommand

from module_management.models import Module, SubscriptionPackage

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Erstellt die Standard-Subscription-Pakete für InventoryPulse'

    def handle(self, *args, **options):
        self.stdout.write('Erstelle Standard-Subscription-Pakete...')

        # Pakete definieren
        packages_data = [
            {
                'name': 'Basic',
                'code': 'basic',
                'package_type': 'basic',
                'description': 'Grundlegende Funktionen für kleine Unternehmen',
                'price_monthly': Decimal('49.99'),
                'price_yearly': Decimal('499.90'),
                'module_codes': ['product_management', 'master_data', 'inventory', 'order_management'],
                'feature_flags': {
                    'inventory_multi_warehouse': False,
                    'inventory_stock_take': False,
                    'order_templates': False,
                    'order_split_delivery': False,
                    'order_suggestions': False,
                    'analytics_dashboard': False,
                }
            },
            {
                'name': 'Professional',
                'code': 'professional',
                'package_type': 'professional',
                'description': 'Erweiterte Funktionen für wachsende Unternehmen',
                'price_monthly': Decimal('99.99'),
                'price_yearly': Decimal('999.90'),
                'module_codes': [
                    'product_management', 'master_data', 'inventory', 'order_management',
                    'supplier_management', 'tracking', 'document_management'
                ],
                'feature_flags': {
                    'inventory_multi_warehouse': True,
                    'inventory_stock_take': True,
                    'order_templates': True,
                    'order_split_delivery': True,
                    'order_suggestions': True,
                    'analytics_dashboard': False,
                    'document_ocr': False,
                }
            },
            {
                'name': 'Enterprise',
                'code': 'enterprise',
                'package_type': 'enterprise',
                'description': 'Vollständige Funktionalität für große Unternehmen',
                'price_monthly': Decimal('199.99'),
                'price_yearly': Decimal('1999.90'),
                'module_codes': [
                    'product_management', 'master_data', 'inventory', 'order_management',
                    'supplier_management', 'tracking', 'document_management',
                    'interfaces', 'rma_management', 'analytics', 'api_access'
                ],
                'feature_flags': {
                    'inventory_multi_warehouse': True,
                    'inventory_stock_take': True,
                    'order_templates': True,
                    'order_split_delivery': True,
                    'order_suggestions': True,
                    'analytics_dashboard': True,
                    'document_ocr': True,
                    'api_access': True,
                }
            },
        ]

        # Pakete erstellen oder aktualisieren
        for package_data in packages_data:
            module_codes = package_data.pop('module_codes')

            # Paket erstellen oder aktualisieren
            package, created = SubscriptionPackage.objects.update_or_create(
                code=package_data['code'],
                defaults=package_data
            )

            # Module hinzufügen
            modules = Module.objects.filter(code__in=module_codes)
            package.modules.set(modules)

            action = 'erstellt' if created else 'aktualisiert'
            self.stdout.write(f'Paket "{package.name}" ({package.code}) {action}')

        self.stdout.write(self.style.SUCCESS('Subscription-Pakete erfolgreich erstellt!'))
