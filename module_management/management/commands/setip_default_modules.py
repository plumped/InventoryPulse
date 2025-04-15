import logging

from django.core.management.base import BaseCommand

from module_management.models import Module, ModuleDependency

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Erstellt die Standard-Module für InventoryPulse'

    def handle(self, *args, **options):
        self.stdout.write('Erstelle Standard-Module...')

        # Liste der Standard-Module mit Abhängigkeiten
        modules_data = [
            {
                'name': 'Produktverwaltung',
                'code': 'product_management',
                'description': 'Verwaltung von Produkten, Kategorien und Varianten.',
                'icon': 'bi bi-box',
                'order': 10,
                'price_monthly': 49.99,
                'price_yearly': 499.90,
                'dependencies': []
            },
            {
                'name': 'Lagerverwaltung',
                'code': 'inventory',
                'description': 'Bestandsführung, Lagerbewegungen und Inventurprozesse.',
                'icon': 'bi bi-boxes',
                'order': 20,
                'price_monthly': 59.99,
                'price_yearly': 599.90,
                'dependencies': ['product_management']
            },
            {
                'name': 'Lieferantenmanagement',
                'code': 'supplier_management',
                'description': 'Lieferantenstammdaten und Lieferantenbewertungen.',
                'icon': 'bi bi-building',
                'order': 30,
                'price_monthly': 39.99,
                'price_yearly': 399.90,
                'dependencies': ['product_management']
            },
            {
                'name': 'Bestellwesen',
                'code': 'order_management',
                'description': 'Bestellungen, Wareneingänge und Bestellvorlagen.',
                'icon': 'bi bi-cart',
                'order': 40,
                'price_monthly': 69.99,
                'price_yearly': 699.90,
                'dependencies': ['product_management', 'supplier_management', 'inventory']
            },
            {
                'name': 'Reklamationsmanagement',
                'code': 'rma_management',
                'description': 'Verwaltung von Rücksendungen und Reklamationen.',
                'icon': 'bi bi-arrow-return-left',
                'order': 50,
                'price_monthly': 29.99,
                'price_yearly': 299.90,
                'dependencies': ['order_management', 'inventory']
            },
            {
                'name': 'Chargenverwaltung',
                'code': 'tracking',
                'description': 'Verwaltung von Chargen und Seriennummern.',
                'icon': 'bi bi-upc-scan',
                'order': 60,
                'price_monthly': 39.99,
                'price_yearly': 399.90,
                'dependencies': ['product_management', 'inventory']
            },
            {
                'name': 'Dokumentenmanagement',
                'code': 'document_management',
                'description': 'Verwaltung und OCR-Erkennung von Dokumenten.',
                'icon': 'bi bi-file-earmark-text',
                'order': 70,
                'price_monthly': 49.99,
                'price_yearly': 499.90,
                'dependencies': []
            },
            {
                'name': 'Schnittstellen',
                'code': 'interfaces',
                'description': 'Integration mit externen Systemen und Lieferanten.',
                'icon': 'bi bi-link-45deg',
                'order': 80,
                'price_monthly': 69.99,
                'price_yearly': 699.90,
                'dependencies': ['supplier_management']
            },
            {
                'name': 'Datenoperationen',
                'code': 'data_operations',
                'description': 'Import/Export und Datenvalidierung.',
                'icon': 'bi bi-database',
                'order': 90,
                'price_monthly': 29.99,
                'price_yearly': 299.90,
                'dependencies': []
            },
            {
                'name': 'Analytics',
                'code': 'analytics',
                'description': 'Berichte, Dashboards und Kennzahlen.',
                'icon': 'bi bi-graph-up',
                'order': 100,
                'price_monthly': 59.99,
                'price_yearly': 599.90,
                'dependencies': []
            },
            {
                'name': 'API-Zugriff',
                'code': 'api_access',
                'description': 'Zugriff auf die REST-API für externe Anwendungen.',
                'icon': 'bi bi-code-slash',
                'order': 110,
                'price_monthly': 79.99,
                'price_yearly': 799.90,
                'dependencies': []
            },
        ]

        # Module erstellen
        created_modules = {}
        for module_data in modules_data:
            dependencies = module_data.pop('dependencies')

            module, created = Module.objects.update_or_create(
                code=module_data['code'],
                defaults=module_data
            )

            created_modules[module.code] = {
                'module': module,
                'dependencies': dependencies
            }

            status = 'erstellt' if created else 'aktualisiert'
            self.stdout.write(f'Modul "{module.name}" ({module.code}) {status}')

        # Abhängigkeiten erstellen
        ModuleDependency.objects.all().delete()
        for code, data in created_modules.items():
            module = data['module']
            dependencies = data['dependencies']

            for dep_code in dependencies:
                if dep_code in created_modules:
                    required_module = created_modules[dep_code]['module']

                    ModuleDependency.objects.create(
                        module=module,
                        required_module=required_module
                    )

                    self.stdout.write(f'Abhängigkeit erstellt: {module.name} -> {required_module.name}')
                else:
                    self.stdout.write(self.style.WARNING(f'Abhängigkeit nicht gefunden: {dep_code}'))

        self.stdout.write(self.style.SUCCESS('Module erfolgreich erstellt!'))
