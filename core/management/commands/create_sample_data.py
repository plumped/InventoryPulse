from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from core.factories import create_sample_data
from core.models import ImportError as ImportErrorModel


class Command(BaseCommand):
    help = 'Erzeugt Schweizer Testdaten für Produktverwaltung, Lagerhaltung und Bestellwesen'

    def add_arguments(self, parser):
        parser.add_argument(
            '--users',
            type=int,
            default=5,
            help='Anzahl der zu erstellenden Benutzer'
        )
        parser.add_argument(
            '--departments',
            type=int,
            default=3,
            help='Anzahl der zu erstellenden Abteilungen'
        )
        parser.add_argument(
            '--warehouses',
            type=int,
            default=3,
            help='Anzahl der zu erstellenden Lager'
        )
        parser.add_argument(
            '--products',
            type=int,
            default=20,
            help='Anzahl der zu erstellenden Produkte'
        )
        parser.add_argument(
            '--suppliers',
            type=int,
            default=5,
            help='Anzahl der zu erstellenden Lieferanten'
        )
        parser.add_argument(
            '--orders',
            type=int,
            default=10,
            help='Anzahl der zu erstellenden Bestellungen'
        )
        parser.add_argument(
            '--clear',
            action='store_true',
            help='Vorhandene Daten löschen, bevor neue erstellt werden'
        )

    @transaction.atomic
    def handle(self, *args, **options):
        try:
            if options['clear']:
                self.clear_existing_data()
                self.stdout.write(self.style.SUCCESS('Bestehende Daten wurden gelöscht.'))

            self.stdout.write('Erstelle Testdaten...')
            result = create_sample_data(
                num_users=options['users'],
                num_departments=options['departments'],
                num_warehouses=options['warehouses'],
                num_products=options['products'],
                num_suppliers=options['suppliers'],
                num_orders=options['orders']
            )

            # Basiselemente
            self.stdout.write(self.style.SUCCESS(f'✓ {len(result["users"])} Benutzer erstellt'))
            self.stdout.write(self.style.SUCCESS(f'✓ {len(result["departments"])} Abteilungen erstellt'))
            self.stdout.write(self.style.SUCCESS(f'✓ {len(result["warehouses"])} Lager erstellt'))
            self.stdout.write(self.style.SUCCESS(f'✓ {len(result["currencies"])} Währungen erstellt'))
            self.stdout.write(self.style.SUCCESS(f'✓ {len(result["taxes"])} Steuersätze erstellt'))

            # Produktverwaltung
            self.stdout.write(self.style.SUCCESS(f'✓ {len(result["categories"])} Kategorien erstellt'))
            self.stdout.write(self.style.SUCCESS(f'✓ {len(result["variant_types"])} Varianten-Typen erstellt'))
            self.stdout.write(self.style.SUCCESS(f'✓ {len(result["products"])} Produkte erstellt'))
            self.stdout.write(self.style.SUCCESS(f'✓ {len(result["variants"])} Produkt-Varianten erstellt'))
            self.stdout.write(self.style.SUCCESS(f'✓ {len(result["serial_numbers"])} Seriennummern erstellt'))
            self.stdout.write(self.style.SUCCESS(f'✓ {len(result["batch_numbers"])} Chargen erstellt'))

            # Import/Export
            self.stdout.write(self.style.SUCCESS(f'✓ {len(result["import_logs"])} Import-Logs erstellt'))
            self.stdout.write(self.style.SUCCESS(f'✓ {len(result["import_errors"])} Import-Fehler erstellt'))

            # Lagerverwaltung
            if "stock_movements" in result and result["stock_movements"]:
                self.stdout.write(self.style.SUCCESS(f'✓ {len(result["stock_movements"])} Lagerbewegungen erstellt'))

            if "stock_takes" in result and result["stock_takes"]:
                self.stdout.write(self.style.SUCCESS(f'✓ {len(result["stock_takes"])} Inventuren erstellt'))

                # Zähle Inventurpositionen, falls verfügbar
                try:
                    stock_take_items_count = sum(st.stocktakeitem_set.count() for st in result["stock_takes"])
                    self.stdout.write(self.style.SUCCESS(f'✓ {stock_take_items_count} Inventurpositionen erstellt'))
                except Exception as e:
                    print(f"Fehler beim Zählen der Inventurpositionen: {e}")

            # Bestellwesen
            if "company_addresses" in result and result["company_addresses"]:
                self.stdout.write(self.style.SUCCESS(f'✓ {len(result["company_addresses"])} Firmenadresse(n) erstellt'))

            if "suppliers" in result and result["suppliers"]:
                self.stdout.write(self.style.SUCCESS(f'✓ {len(result["suppliers"])} Lieferanten erstellt'))

            if "purchase_orders" in result and result["purchase_orders"]:
                self.stdout.write(self.style.SUCCESS(f'✓ {len(result["purchase_orders"])} Bestellungen erstellt'))

                # Zähle Bestellpositionen, falls verfügbar
                try:
                    order_items_count = sum(po.items.count() for po in result["purchase_orders"])
                    self.stdout.write(self.style.SUCCESS(f'✓ {order_items_count} Bestellpositionen erstellt'))
                except Exception as e:
                    print(f"Fehler beim Zählen der Bestellpositionen: {e}")

                # Zähle Kommentare zu Bestellungen
                try:
                    from order.models import PurchaseOrderComment
                    comments = PurchaseOrderComment.objects.count()
                    self.stdout.write(self.style.SUCCESS(f'✓ {comments} Bestellkommentare erstellt'))
                except:
                    pass

                # Zähle Teillieferungen
                try:
                    from order.models import OrderSplit
                    splits = OrderSplit.objects.count()
                    self.stdout.write(self.style.SUCCESS(f'✓ {splits} Teillieferungen erstellt'))
                except:
                    pass

                # Zähle Wareneingänge
                try:
                    from order.models import PurchaseOrderReceipt
                    receipts = PurchaseOrderReceipt.objects.count()
                    self.stdout.write(self.style.SUCCESS(f'✓ {receipts} Wareneingänge erstellt'))
                except:
                    pass

            if "order_templates" in result and result["order_templates"]:
                self.stdout.write(self.style.SUCCESS(f'✓ {len(result["order_templates"])} Bestellvorlagen erstellt'))

                # Zähle Vorlagen-Positionen
                try:
                    template_items_count = sum(ot.items.count() for ot in result["order_templates"])
                    self.stdout.write(self.style.SUCCESS(f'✓ {template_items_count} Vorlagenpositionen erstellt'))
                except Exception as e:
                    print(f"Fehler beim Zählen der Vorlagenpositionen: {e}")

            if "order_suggestions" in result and result["order_suggestions"]:
                self.stdout.write(
                    self.style.SUCCESS(f'✓ {len(result["order_suggestions"])} Bestellvorschläge erstellt'))
            if "rmas" in result and result["rmas"]:
                self.stdout.write(self.style.SUCCESS(f'✓ {len(result["rmas"])} RMAs erstellt'))

                try:
                    from rma.models import RMAItem, RMAComment, RMAHistory, RMAPhoto, RMADocument

                    self.stdout.write(self.style.SUCCESS(f'✓ {RMAItem.objects.count()} RMA-Artikel erstellt'))
                    self.stdout.write(self.style.SUCCESS(f'✓ {RMAComment.objects.count()} RMA-Kommentare erstellt'))
                    self.stdout.write(self.style.SUCCESS(f'✓ {RMAHistory.objects.count()} RMA-Statusverläufe erstellt'))
                    self.stdout.write(self.style.SUCCESS(f'✓ {RMAPhoto.objects.count()} RMA-Fotos erstellt'))
                    self.stdout.write(self.style.SUCCESS(f'✓ {RMADocument.objects.count()} RMA-Dokumente erstellt'))
                except Exception as e:
                    self.stdout.write(f'Fehler beim Zählen der RMA-Daten: {e}')

            self.stdout.write(self.style.SUCCESS('Testdaten wurden erfolgreich erstellt!'))

        except Exception as e:
            raise CommandError(f'Fehler beim Erstellen der Testdaten: {str(e)}')

    def clear_existing_data(self):
        from django.contrib.auth.models import User
        from core.models import (
            Tax, Category, Product, ProductWarehouse, ImportLog, ImportError,
            UserProfile, ProductPhoto, ProductAttachment, ProductVariantType,
            ProductVariant, SerialNumber, BatchNumber, Currency
        )
        from organization.models import Department
        from inventory.models import Warehouse

        # Lösche Bestellwesen-Daten, falls vorhanden
        self.stdout.write('Lösche Bestellwesen-Daten...')
        try:
            from admin_dashboard.models import CompanyAddress
            from order.models import (
                PurchaseOrderComment, PurchaseOrderReceiptItem, PurchaseOrderReceipt,
                OrderSplitItem, OrderSplit, OrderTemplateItem, OrderTemplate,
                OrderSuggestion, PurchaseOrderItem, PurchaseOrder
            )

            # Löschen in einer sinnvollen Reihenfolge, um Fremdschlüsselabhängigkeiten zu respektieren
            PurchaseOrderComment.objects.all().delete()
            PurchaseOrderReceiptItem.objects.all().delete()
            PurchaseOrderReceipt.objects.all().delete()
            OrderSplitItem.objects.all().delete()
            OrderSplit.objects.all().delete()
            OrderTemplateItem.objects.all().delete()
            OrderTemplate.objects.all().delete()
            OrderSuggestion.objects.all().delete()
            PurchaseOrderItem.objects.all().delete()
            PurchaseOrder.objects.all().delete()
            CompanyAddress.objects.all().delete()

            # Wenn Suppliers im Order-Modul sind
            try:
                from order.models import Supplier
                Supplier.objects.all().delete()
            except ImportError:
                pass

            # Wenn Suppliers ein eigenes Modul haben
            try:
                from suppliers.models import Supplier
                Supplier.objects.all().delete()
            except ImportError:
                pass

            self.stdout.write('  Bestellwesen-Daten gelöscht')
        except ImportError:
            self.stdout.write('  Keine Bestellwesen-Modelle gefunden')

        # Löschen von Inventur-Daten
        self.stdout.write('Lösche Inventur-Daten...')
        try:
            from inventory.models import StockTakeItem, StockTake, StockMovement
            StockTakeItem.objects.all().delete()
            StockTake.objects.all().delete()
            StockMovement.objects.all().delete()
            self.stdout.write('  Inventur-Daten gelöscht')
        except ImportError:
            self.stdout.write('  Keine Inventur-Modelle gefunden')
        self.stdout.write('Lösche RMA-Daten...')
        try:
            from rma.models import RMA, RMAItem, RMAComment, RMAHistory, RMAPhoto, RMADocument
            RMADocument.objects.all().delete()
            RMAPhoto.objects.all().delete()
            RMAHistory.objects.all().delete()
            RMAComment.objects.all().delete()
            RMAItem.objects.all().delete()
            RMA.objects.all().delete()
            self.stdout.write('  RMA-Daten gelöscht')
        except ImportError:
            self.stdout.write('  Keine RMA-Modelle gefunden')

        # Löschen von Import-Daten
        self.stdout.write('Lösche Import-Daten...')
        ImportErrorModel.objects.all().delete()
        ImportLog.objects.all().delete()

        # Löschen von Produkt-Tracking-Daten
        self.stdout.write('Lösche Produkt-Tracking-Daten...')
        SerialNumber.objects.all().delete()
        BatchNumber.objects.all().delete()

        # Löschen von Produkt-Beziehungsdaten
        self.stdout.write('Lösche Produkt-Beziehungsdaten...')
        ProductVariant.objects.all().delete()
        ProductPhoto.objects.all().delete()
        ProductAttachment.objects.all().delete()
        ProductWarehouse.objects.all().delete()

        # Löschen von Hauptproduktdaten
        self.stdout.write('Lösche Hauptproduktdaten...')
        Product.objects.all().delete()
        Category.objects.all().delete()
        ProductVariantType.objects.all().delete()

        # Löschen von Benutzerprofilen
        self.stdout.write('Lösche Benutzerprofile...')
        UserProfile.objects.all().delete()

        # Löschen von Konfigurationsdaten
        self.stdout.write('Lösche Konfigurationsdaten...')
        Tax.objects.all().delete()
        Currency.objects.all().delete()

        # Löschen von Organisationsdaten
        self.stdout.write('Lösche Organisationsdaten...')
        Warehouse.objects.all().delete()
        Department.objects.all().delete()

        # Benutzer löschen (außer Superuser)
        self.stdout.write('Lösche Benutzer (außer Superuser)...')
        User.objects.filter(is_superuser=False).delete()
