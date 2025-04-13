import random
import string
import uuid
from datetime import datetime, timedelta
from decimal import Decimal

import factory
from django.contrib.auth.models import User
from django.utils import timezone
from factory.django import DjangoModelFactory
from faker import Faker

from accessmanagement.models import UserProfile
from admin_dashboard.models import CompanyAddress
from core.models import SerialNumber, BatchNumber
from data_operations.models.importers import ImportError as ImportErrorModel, ImportLog
from inventory.models import Warehouse, StockTakeItem, StockTake, StockMovement
from master_data.models.currency import Currency
from master_data.models.tax import Tax
from order.models import PurchaseOrderComment, OrderTemplateItem, OrderTemplate, OrderSuggestion, \
    PurchaseOrderReceiptItem, OrderSplit, PurchaseOrderReceipt, OrderSplitItem, PurchaseOrderItem, PurchaseOrder
from organization.models import Department
from product_management.models.categories import Category
from product_management.models.products import Product, ProductWarehouse, ProductPhoto, ProductAttachment, \
    ProductVariantType, ProductVariant
from rma.models import RMA, RMAStatus, RMAResolutionType, RMAItem, RMAComment, RMAHistory, RMAPhoto, RMADocument
from rma.models import RMAIssueType
from suppliers.models import Supplier

# Faker mit Schweizer Lokalisierung
fake = Faker(['de_CH'])


class UserFactory(DjangoModelFactory):
    class Meta:
        model = User

    username = factory.Sequence(lambda n: f"{fake.user_name()}_{n}")
    email = factory.LazyAttribute(lambda _: fake.email())
    first_name = factory.LazyAttribute(lambda _: fake.first_name())
    last_name = factory.LazyAttribute(lambda _: fake.last_name())
    is_active = True
    password = factory.PostGenerationMethodCall('set_password', 'password123')


class DepartmentFactory(DjangoModelFactory):
    class Meta:
        model = Department
        django_get_or_create = ('code',)

    name = factory.LazyAttribute(lambda _: fake.company_suffix())
    code = factory.Sequence(lambda n: f"DEPT-{n:03d}")  # Eindeutiger Code für jede Abteilung
    description = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=200))


class WarehouseFactory(DjangoModelFactory):
    class Meta:
        model = Warehouse

    name = factory.LazyAttribute(lambda _: f"Lager {fake.city()}")
    location = factory.LazyAttribute(lambda _: fake.address())
    is_active = True


class TaxFactory(DjangoModelFactory):
    """Factory für Schweizer Mehrwertsteuersätze."""

    class Meta:
        model = Tax
        django_get_or_create = ('code',)

    @factory.lazy_attribute
    def name(self):
        if self.rate == Decimal('7.7'):
            return "Normalsatz"
        elif self.rate == Decimal('2.5'):
            return "Reduzierter Satz"
        elif self.rate == Decimal('3.7'):
            return "Sondersatz"
        else:
            return "Befreiter Satz"

    @factory.lazy_attribute
    def code(self):
        if self.rate == Decimal('7.7'):
            return "MWST-N"
        elif self.rate == Decimal('2.5'):
            return "MWST-R"
        elif self.rate == Decimal('3.7'):
            return "MWST-S"
        else:
            return "MWST-0"

    rate = factory.Iterator([
        Decimal('7.7'),  # Normalsatz (Standard)
        Decimal('2.5'),  # Reduzierter Satz (Lebensmittel, Bücher, Medikamente)
        Decimal('3.7'),  # Sondersatz (Beherbergung)
        Decimal('0'),  # Steuerbefreit oder Export
    ])

    description = factory.LazyAttribute(lambda o: {
        Decimal('7.7'): "Normalsatz für die meisten Waren und Dienstleistungen",
        Decimal('2.5'): "Reduzierter Satz für Lebensmittel, Bücher, Medikamente, etc.",
        Decimal('3.7'): "Sondersatz für Beherbergungsleistungen",
        Decimal('0'): "Steuerbefreite Leistungen oder Exporte",
    }[o.rate])

    is_default = factory.LazyAttribute(lambda o: o.rate == Decimal('7.7'))
    is_active = True


class CategoryFactory(DjangoModelFactory):
    class Meta:
        model = Category
        django_get_or_create = ('name',)

    name = factory.Iterator([
        "Bürobedarf",
        "Elektronik",
        "Lebensmittel",
        "Möbel",
        "Kosmetik",
        "Haushaltswaren",
        "Werkzeuge",
        "Sport",
        "Spielzeug",
        "Kleidung",
        "Schreibwaren",
        "Baumarkt",
        "Pharma",
        "Getränke",
        "Hygiene"
    ])

    description = factory.LazyAttribute(lambda o: f"Kategorie für {o.name} Produkte")


class ProductFactory(DjangoModelFactory):
    class Meta:
        model = Product

    name = factory.LazyAttribute(lambda _: fake.catch_phrase())

    @factory.lazy_attribute
    def sku(self):
        # Erzeugt SKU im Format "CH-XXXXX" (X = alphanumerisch)
        chars = string.ascii_uppercase + string.digits
        return f"CH-{''.join(random.choice(chars) for _ in range(5))}"

    @factory.lazy_attribute
    def barcode(self):
        # EAN-13 Format (Schweizer Präfix 760-769)
        prefix = str(random.randint(760, 769))
        rest = ''.join(random.choice('0123456789') for _ in range(9))
        return f"{prefix}{rest}"

    description = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=200))
    category = factory.SubFactory(CategoryFactory)
    minimum_stock = factory.LazyAttribute(lambda _: random.randint(5, 50))

    @factory.lazy_attribute
    def unit(self):
        return random.choice([
            "Stück", "Karton", "Palette", "kg", "Liter", "Meter", "Paar", "Set"
        ])

    @factory.lazy_attribute
    def tax(self):
        # Zuweisung eines Steuersatzes basierend auf Wahrscheinlichkeiten
        rates = {
            Decimal('7.7'): 70,  # 70% Wahrscheinlichkeit Normalsatz
            Decimal('2.5'): 20,  # 20% Wahrscheinlichkeit Reduzierter Satz
            Decimal('3.7'): 5,  # 5% Wahrscheinlichkeit Sondersatz
            Decimal('0'): 5  # 5% Wahrscheinlichkeit Befreiter Satz
        }

        selected_rate = random.choices(
            population=list(rates.keys()),
            weights=list(rates.values()),
            k=1
        )[0]

        return Tax.objects.filter(rate=selected_rate).first()

    has_variants = factory.LazyAttribute(lambda _: random.random() < 0.3)  # 30% haben Varianten
    has_serial_numbers = factory.LazyAttribute(lambda _: random.random() < 0.2)  # 20% haben Seriennummern
    has_batch_tracking = factory.LazyAttribute(lambda _: random.random() < 0.25)  # 25% haben Charge-Tracking
    has_expiry_tracking = factory.LazyAttribute(lambda _: random.random() < 0.15)  # 15% haben Haltbarkeitsdatum

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Standard Factory-Boy create
        product = super()._create(model_class, *args, **kwargs)

        # Zuweisung zu Lagern
        warehouses = list(Warehouse.objects.all())
        if warehouses:
            # Produkt zu 1-3 zufälligen Lagern zuweisen
            selected_warehouses = random.sample(warehouses, min(random.randint(1, 3), len(warehouses)))

            for warehouse in selected_warehouses:
                ProductWarehouse.objects.create(
                    product=product,
                    warehouse=warehouse,
                    quantity=Decimal(str(random.randint(10, 1000)))
                )

        return product


class ProductWarehouseFactory(DjangoModelFactory):
    class Meta:
        model = ProductWarehouse
        django_get_or_create = ('product', 'warehouse')

    product = factory.SubFactory(ProductFactory)
    warehouse = factory.SubFactory(WarehouseFactory)
    quantity = factory.LazyAttribute(lambda _: Decimal(str(random.randint(10, 1000))))


class ImportLogFactory(DjangoModelFactory):
    class Meta:
        model = ImportLog

    file_name = factory.LazyAttribute(lambda _: f"{fake.word()}_{fake.date_time().strftime('%Y%m%d%H%M%S')}.csv")
    import_type = factory.Iterator([i[0] for i in ImportLog.IMPORT_TYPE_CHOICES])
    status = factory.Iterator([i[0] for i in ImportLog.STATUS_CHOICES])
    rows_processed = factory.LazyAttribute(lambda _: random.randint(50, 500))

    @factory.lazy_attribute
    def rows_created(self):
        # Etwa 80% der verarbeiteten Zeilen wurden erstellt
        return int(self.rows_processed * 0.8)

    @factory.lazy_attribute
    def rows_updated(self):
        # Etwa 10% der verarbeiteten Zeilen wurden aktualisiert
        return int(self.rows_processed * 0.1)

    @factory.lazy_attribute
    def rows_error(self):
        # Die übrigen 10% sind Fehler
        return self.rows_processed - self.rows_created - self.rows_updated

    created_by = factory.SubFactory(UserFactory)
    notes = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=100) if random.random() < 0.3 else "")

    @factory.lazy_attribute
    def error_details(self):
        if self.rows_error > 0 and random.random() < 0.7:
            return fake.text(max_nb_chars=150)
        return ""


class ImportErrorFactory(DjangoModelFactory):
    class Meta:
        model = ImportErrorModel

    import_log = factory.SubFactory(ImportLogFactory)
    row_number = factory.Sequence(lambda n: n + 2)  # Startet bei Zeile 2 (nach Header)

    @factory.lazy_attribute
    def error_message(self):
        errors = [
            "Ungültiger Wert",
            "Fehlendes Pflichtfeld",
            "Duplizierter Wert",
            "Unbekannte Kategorie",
            "Fehler beim Datumformat",
            "Ungültiger Preis",
            "Ungültige SKU",
            "Steuersatz nicht gefunden",
            "Lager nicht gefunden",
            "Ungültiges Zahlenformat"
        ]
        return random.choice(errors)

    row_data = factory.LazyAttribute(lambda _: ",".join(fake.words(nb=10)))

    @factory.lazy_attribute
    def field_name(self):
        fields = [
            "name", "sku", "barcode", "category", "price", "tax_rate",
            "warehouse", "quantity", "minimum_stock", "unit"
        ]
        return random.choice(fields)

    field_value = factory.LazyAttribute(lambda _: fake.word())


class UserProfileFactory(DjangoModelFactory):
    class Meta:
        model = UserProfile
        django_get_or_create = ('user',)

    user = factory.SubFactory(UserFactory)

    @factory.post_generation
    def departments(self, create, extracted, **kwargs):
        if not create:
            return

        if extracted:
            # Verwende die übergebenen Abteilungen
            for department in extracted:
                self.departments.add(department)
        else:
            # Füge 1-3 zufällige Abteilungen hinzu
            departments = Department.objects.all()
            if departments:
                num_departments = min(random.randint(1, 3), departments.count())
                departments_to_add = random.sample(list(departments), num_departments)
                for department in departments_to_add:
                    self.departments.add(department)


class ProductPhotoFactory(DjangoModelFactory):
    class Meta:
        model = ProductPhoto

    product = factory.SubFactory(ProductFactory)
    # Hinweis: image-Feld kann in Tests nicht automatisch befüllt werden ohne echte Dateien
    # Für Tests müsste hier ein Mock oder eine temporäre Testdatei verwendet werden
    is_primary = factory.LazyAttribute(lambda _: random.random() < 0.25)  # 25% sind primäre Fotos
    caption = factory.LazyAttribute(lambda _: fake.sentence())


class ProductAttachmentFactory(DjangoModelFactory):
    class Meta:
        model = ProductAttachment

    product = factory.SubFactory(ProductFactory)
    # Hinweis: file-Feld kann in Tests nicht automatisch befüllt werden ohne echte Dateien
    title = factory.LazyAttribute(lambda _: fake.sentence(nb_words=4))
    description = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=100))

    @factory.lazy_attribute
    def file_type(self):
        return random.choice(["pdf", "docx", "xlsx", "jpg", "png", "zip"])


class ProductVariantTypeFactory(DjangoModelFactory):
    class Meta:
        model = ProductVariantType
        django_get_or_create = ('name',)

    name = factory.Iterator([
        "Farbe",
        "Größe",
        "Material",
        "Ausführung",
        "Geschmack",
        "Gewicht",
        "Breite",
        "Länge",
        "Höhe",
        "Stärke"
    ])

    description = factory.LazyAttribute(lambda o: f"Variantentyp für {o.name}")


class ProductVariantFactory(DjangoModelFactory):
    class Meta:
        model = ProductVariant
        django_get_or_create = ('parent_product', 'variant_type', 'value')

    parent_product = factory.SubFactory(ProductFactory, has_variants=True)

    @factory.lazy_attribute
    def sku(self):
        # Erzeugt SKU im Format "Parent-SKU-XXX"
        chars = string.ascii_uppercase + string.digits
        return f"{self.parent_product.sku}-{''.join(random.choice(chars) for _ in range(3))}"

    @factory.lazy_attribute
    def variant_type(self):
        # Um die Unique-Constraint zu respektieren, werden wir die bereits
        # verwendeten Typen für dieses Produkt ausschließen
        used_types = ProductVariant.objects.filter(
            parent_product=self.parent_product
        ).values_list('variant_type_id', flat=True)

        available_types = ProductVariantType.objects.exclude(id__in=used_types)

        if not available_types.exists():
            # Wenn keine Typen mehr verfügbar sind, erstellen wir einen neuen
            return ProductVariantTypeFactory()

        return available_types.order_by('?').first()

    @factory.lazy_attribute
    def value(self):
        type_values = {
            "Farbe": ["Rot", "Blau", "Grün", "Schwarz", "Weiss", "Grau", "Gelb"],
            "Größe": ["XS", "S", "M", "L", "XL", "XXL", "3XL"],
            "Material": ["Holz", "Metall", "Kunststoff", "Glas", "Karton", "Papier", "Stoff"],
            "Ausführung": ["Standard", "Premium", "Basic", "Professional"],
            "Geschmack": ["Schokolade", "Vanille", "Erdbeer", "Haselnuss", "Zitrone"],
            "Gewicht": ["100g", "250g", "500g", "1kg", "2kg", "5kg"],
            "Breite": ["50cm", "75cm", "100cm", "125cm", "150cm"],
            "Länge": ["1m", "1.5m", "2m", "2.5m", "3m"],
            "Höhe": ["10cm", "20cm", "30cm", "40cm", "50cm"],
            "Stärke": ["dünn", "mittel", "stark", "extra stark"]
        }

        # Prüfen, welche Werte für diesen Typ und dieses Produkt bereits verwendet wurden
        used_values = ProductVariant.objects.filter(
            parent_product=self.parent_product,
            variant_type=self.variant_type
        ).values_list('value', flat=True)

        # Wähle aus verfügbaren Werten aus
        if self.variant_type.name in type_values:
            available_values = [v for v in type_values[self.variant_type.name] if v not in used_values]
            if available_values:
                return random.choice(available_values)

        # Falls keine vordefinierte Werte mehr verfügbar, generiere einen eindeutigen Wert
        return f"{fake.word()}-{uuid.uuid4().hex[:6]}"

    @factory.lazy_attribute
    def name(self):
        return f"{self.parent_product.name} {self.variant_type.name} {self.value}"

    price_adjustment = factory.LazyAttribute(lambda _:
                                             Decimal(str(random.choice([-10.00, -5.00, 0.00, 5.00, 10.00, 15.00])))
                                             )

    @factory.lazy_attribute
    def barcode(self):
        # EAN-13 Format (Schweizer Präfix 760-769)
        prefix = str(random.randint(760, 769))
        rest = ''.join(random.choice('0123456789') for _ in range(9))
        return f"{prefix}{rest}"

    is_active = True


class SerialNumberFactory(DjangoModelFactory):
    class Meta:
        model = SerialNumber
        exclude = ('create_variant',)  # Dieses Feld von der Modell-Erstellung ausschließen

    product = factory.SubFactory(ProductFactory, has_serial_numbers=True)
    create_variant = factory.LazyAttribute(lambda _: random.random() < 0.3)  # 30% haben Varianten

    @factory.lazy_attribute
    def variant(self):
        # Nur Variante erstellen, wenn das Produkt Varianten hat UND zufällig eine Variante erstellt werden soll
        if self.create_variant and self.product.has_variants:
            return ProductVariantFactory(parent_product=self.product)
        return None

    @factory.lazy_attribute
    def serial_number(self):
        # Schweizer Seriennummern mit Präfix CH
        chars = string.ascii_uppercase + string.digits
        return f"CH-{''.join(random.choice(chars) for _ in range(8))}"

    status = factory.Iterator([i[0] for i in SerialNumber.status_choices])
    purchase_date = factory.LazyAttribute(lambda _: fake.date_between(start_date='-2y', end_date='today'))

    @factory.lazy_attribute
    def expiry_date(self):
        if self.product.has_expiry_tracking:
            # Verfallsdatum zwischen 1 und 5 Jahren nach Einkaufsdatum
            if self.purchase_date:
                days = random.randint(365, 365 * 5)
                return self.purchase_date + timedelta(days=days)
        return None

    notes = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=100) if random.random() < 0.3 else "")
    warehouse = factory.SubFactory(WarehouseFactory)


class BatchNumberFactory(DjangoModelFactory):
    class Meta:
        model = BatchNumber
        exclude = ('create_variant',)  # Dieses Feld von der Modell-Erstellung ausschließen

    product = factory.SubFactory(ProductFactory, has_batch_tracking=True)
    create_variant = factory.LazyAttribute(lambda _: random.random() < 0.3)  # 30% haben Varianten

    @factory.lazy_attribute
    def variant(self):
        # Nur Variante erstellen, wenn das Produkt Varianten hat UND zufällig eine Variante erstellt werden soll
        if self.create_variant and self.product.has_variants:
            return ProductVariantFactory(parent_product=self.product)
        return None

    @factory.lazy_attribute
    def batch_number(self):
        # Schweizer Batchnummern mit Jahr-Monat-Präfix
        year = datetime.now().year
        month = random.randint(1, 12)
        number = random.randint(1000, 9999)
        return f"{year}-{month:02d}-{number}"

    quantity = factory.LazyAttribute(lambda _: Decimal(str(random.randint(10, 1000))))
    production_date = factory.LazyAttribute(lambda _: fake.date_between(start_date='-1y', end_date='today'))

    @factory.lazy_attribute
    def expiry_date(self):
        if self.product.has_expiry_tracking and self.production_date:
            # Verfallsdatum zwischen 6 Monaten und 3 Jahren nach Produktionsdatum
            days = random.randint(180, 365 * 3)
            return self.production_date + timedelta(days=days)
        return None

    warehouse = factory.SubFactory(WarehouseFactory)
    notes = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=100) if random.random() < 0.3 else "")


class CurrencyFactory(DjangoModelFactory):
    class Meta:
        model = Currency
        django_get_or_create = ('code',)

    code = factory.Iterator(['CHF', 'EUR', 'USD', 'GBP'])

    @factory.lazy_attribute
    def name(self):
        currency_names = {
            'CHF': 'Schweizer Franken',
            'EUR': 'Euro',
            'USD': 'US-Dollar',
            'GBP': 'Britisches Pfund'
        }
        return currency_names[self.code]

    @factory.lazy_attribute
    def symbol(self):
        currency_symbols = {
            'CHF': 'Fr.',
            'EUR': '€',
            'USD': '$',
            'GBP': '£'
        }
        return currency_symbols[self.code]

    decimal_places = 2
    is_default = factory.LazyAttribute(lambda self: self.code == 'CHF')
    is_active = True

    @factory.lazy_attribute
    def exchange_rate(self):
        rates = {
            'CHF': Decimal('1.0'),
            'EUR': Decimal('0.96'),
            'USD': Decimal('0.91'),
            'GBP': Decimal('1.12')
        }
        return rates[self.code]

    # Ersthelfer-Funktion zur Generierung von Testdaten


def create_sample_data(num_users=5, num_departments=3, num_warehouses=3, num_products=20, num_suppliers=5,
                       num_orders=10):
    """Erzeugt einen kompletten Satz von Testdaten für die Anwendung."""

    # Benutzer erstellen
    users = UserFactory.create_batch(num_users)

    # Abteilungen erstellen
    departments = DepartmentFactory.create_batch(num_departments)

    # Lager erstellen
    warehouses = WarehouseFactory.create_batch(num_warehouses)

    # Währungen erstellen (feste Anzahl für Standardwährungen)
    currencies = CurrencyFactory.create_batch(4)  # CHF, EUR, USD, GBP

    # Steuersätze erstellen (feste Anzahl für Schweizer Steuersätze)
    taxes = TaxFactory.create_batch(4)  # 7.7%, 2.5%, 3.7%, 0%

    # Kategorien erstellen
    categories = []
    for category_name in [
        "Bürobedarf", "Elektronik", "Lebensmittel", "Möbel", "Kosmetik",
        "Haushaltswaren", "Werkzeuge", "Sport", "Spielzeug", "Kleidung"
    ]:
        categories.append(CategoryFactory(name=category_name))

    # Varianten-Typen erstellen
    variant_types = []
    for variant_type_name in [
        "Farbe", "Größe", "Material", "Ausführung", "Geschmack"
    ]:
        variant_types.append(ProductVariantTypeFactory(name=variant_type_name))

    # Benutzerprofile erstellen
    for user in users:
        profile = UserProfileFactory(user=user)

    # Produkte erstellen
    products = ProductFactory.create_batch(num_products)

    # Für Produkte mit Varianten, Varianten erstellen
    variants = []
    for product in products:
        if product.has_variants:
            # Zufällige Anzahl von Varianten erstellen (1-5)
            variant_count = random.randint(1, 5)

            # Zufällige Varianten-Typen auswählen (maximal so viele wie verfügbar)
            available_types = list(ProductVariantType.objects.all())
            selected_types = random.sample(available_types, min(variant_count, len(available_types)))

            # Für jeden ausgewählten Typ eine Variante erstellen
            for variant_type in selected_types:
                try:
                    # Wähle einen noch nicht verwendeten Wert für diesen Typ
                    type_values = {
                        "Farbe": ["Rot", "Blau", "Grün", "Schwarz", "Weiss", "Grau", "Gelb"],
                        "Größe": ["XS", "S", "M", "L", "XL", "XXL", "3XL"],
                        "Material": ["Holz", "Metall", "Kunststoff", "Glas", "Karton", "Papier", "Stoff"],
                        "Ausführung": ["Standard", "Premium", "Basic", "Professional"],
                        "Geschmack": ["Schokolade", "Vanille", "Erdbeer", "Haselnuss", "Zitrone"],
                        "Gewicht": ["100g", "250g", "500g", "1kg", "2kg", "5kg"],
                        "Breite": ["50cm", "75cm", "100cm", "125cm", "150cm"],
                        "Länge": ["1m", "1.5m", "2m", "2.5m", "3m"],
                        "Höhe": ["10cm", "20cm", "30cm", "40cm", "50cm"],
                        "Stärke": ["dünn", "mittel", "stark", "extra stark"]
                    }

                    # Bereits verwendete Werte für dieses Produkt und diesen Typ finden
                    used_values = ProductVariant.objects.filter(
                        parent_product=product,
                        variant_type=variant_type
                    ).values_list('value', flat=True)

                    # Verfügbare Werte ermitteln
                    if variant_type.name in type_values:
                        available_values = [v for v in type_values[variant_type.name] if v not in used_values]
                        if available_values:
                            value = random.choice(available_values)
                            variant = ProductVariantFactory(
                                parent_product=product,
                                variant_type=variant_type,
                                value=value
                            )
                            variants.append(variant)
                except Exception as e:
                    print(f"Fehler beim Erstellen der Variante: {str(e)}")
                    continue

    # Für Produkte mit Seriennummern, Seriennummern erstellen
    serial_numbers = []
    for product in products:
        if product.has_serial_numbers:
            # Zufällige Anzahl von Seriennummern erstellen (5-20)
            serial_count = random.randint(5, 20)
            serial_numbers.extend(SerialNumberFactory.create_batch(
                serial_count, product=product
            ))

    # Für Produkte mit Chargen-Tracking, Chargen erstellen
    batch_numbers = []
    for product in products:
        if product.has_batch_tracking:
            # Zufällige Anzahl von Chargen erstellen (1-5)
            batch_count = random.randint(1, 5)
            batch_numbers.extend(BatchNumberFactory.create_batch(
                batch_count, product=product
            ))

    # Import-Logs erstellen
    import_logs = ImportLogFactory.create_batch(10)

    # Import-Fehler erstellen
    import_errors = []
    for log in import_logs:
        if log.rows_error > 0:
            # Für jeden Fehler ein ImportError erstellen
            error_count = min(log.rows_error, 5)  # Maximal 5 Fehler pro Log
            import_errors.extend(ImportErrorFactory.create_batch(
                error_count, import_log=log
            ))

    # Lagerbewegungen erstellen
    stock_movements = []
    for product in products:
        # Pro Produkt 1-10 Lagerbewegungen erstellen
        movement_count = random.randint(1, 10)
        stock_movements.extend(StockMovementFactory.create_batch(
            movement_count, product=product
        ))

    # Inventuren erstellen (1-3 pro Lager)
    stock_takes = []
    for warehouse in warehouses:
        # 1-3 Inventuren pro Lager
        take_count = random.randint(1, 3)
        for _ in range(take_count):
            stock_take = StockTakeFactory(
                warehouse=warehouse,
                created_by=random.choice(users)
            )
            stock_takes.append(stock_take)

            # Überprüfen, ob StockTakeItems automatisch erstellt wurden
            if stock_take.stocktakeitem_set.count() == 0:
                print(f"Warnung: Keine StockTakeItems für {stock_take.name} erstellt.")

                # Manuell einige StockTakeItems erstellen
                count = min(random.randint(5, 15), len(products))
                selected_products = random.sample(list(products), count)

                for product in selected_products:
                    StockTakeItemFactory(
                        stock_take=stock_take,
                        product=product,
                        is_counted=(stock_take.status in ['completed', 'in_progress'] and random.random() < 0.7)
                    )

    # ------ Bestellverwaltung ------

    # Firmenadresse für Rechnungs- und Lieferadressen erstellen
    company_addresses = []

    # Eine Adresse von jedem Typ erstellen
    for address_type in ['headquarters', 'warehouse', 'shipping', 'return', 'billing', 'other']:
        try:
            # Erstelle eine Standard-Adresse für jeden Typ
            address = CompanyAddressFactory(address_type=address_type, is_default=True)
            company_addresses.append(address)

            # Für shipping und billing noch 1-2 zusätzliche Nicht-Standard-Adressen
            if address_type in ['shipping', 'billing']:
                extra_count = random.randint(1, 2)
                for _ in range(extra_count):
                    extra_address = CompanyAddressFactory(address_type=address_type, is_default=False)
                    company_addresses.append(extra_address)

        except Exception as e:
            print(f"Fehler beim Erstellen der Adresse vom Typ {address_type}: {str(e)}")
            continue

    # Lieferanten erstellen
    try:
        from suppliers.factories import SupplierFactory
        suppliers = SupplierFactory.create_batch(num_suppliers)
    except ImportError:
        # Wenn keine SupplierFactory verfügbar ist, schauen wir nach Supplier im gleichen Modul
        try:
            from order.models import Supplier

            class SupplierFactory(DjangoModelFactory):
                class Meta:
                    model = Supplier

                name = factory.LazyAttribute(lambda _: fake.company())
                contact_person = factory.LazyAttribute(lambda _: fake.name())
                email = factory.LazyAttribute(lambda _: fake.email())
                phone = factory.LazyAttribute(lambda _: fake.phone_number())
                website = factory.LazyAttribute(lambda _: f"https://www.{fake.domain_name()}")
                notes = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=200) if random.random() < 0.3 else "")

            suppliers = SupplierFactory.create_batch(num_suppliers)

        except ImportError:
            # Fallback: Keine Suppliers erstellen
            suppliers = []
            print("Keine Supplier-Modelle verfügbar. Überspringe Erstellung von Bestellungen.")

    # Bestellungen erstellen, wenn Lieferanten verfügbar sind
    purchase_orders = []
    if suppliers:
        # Bestellungen erstellen
        for _ in range(num_orders):
            try:
                order = PurchaseOrderFactory(
                    supplier=random.choice(suppliers),
                    created_by=random.choice(users),
                    billing_address=random.choice(company_addresses) if company_addresses else None,
                    shipping_address=random.choice(company_addresses) if company_addresses else None
                )
                purchase_orders.append(order)

                # Prüfen, ob Bestellpositionen erstellt wurden
                if order.items.count() == 0:
                    print(f"Warnung: Keine Bestellpositionen für {order.order_number} erstellt.")

                    # Manuell einige Bestellpositionen erstellen
                    count = min(random.randint(3, 8), len(products))
                    selected_products = random.sample(list(products), count)

                    for product in selected_products:
                        PurchaseOrderItemFactory(
                            purchase_order=order,
                            product=product
                        )

                # Kommentare zu Bestellungen hinzufügen
                comment_count = random.randint(0, 5)
                for _ in range(comment_count):
                    PurchaseOrderCommentFactory(
                        purchase_order=order,
                        user=random.choice(users)
                    )

                # Teillieferungen für manche Bestellungen hinzufügen
                if order.status in ['sent', 'partially_received'] and random.random() < 0.7:
                    split_count = random.randint(1, 3)
                    for _ in range(split_count):
                        order_split = OrderSplitFactory(
                            purchase_order=order,
                            created_by=random.choice(users)
                        )

                # Wareneingänge für manche Bestellungen hinzufügen
                if order.status in ['partially_received', 'received', 'received_with_issues']:
                    receipt_count = random.randint(1, 3)
                    for _ in range(receipt_count):
                        receipt = PurchaseOrderReceiptFactory(
                            purchase_order=order,
                            received_by=random.choice(users)
                        )

            except Exception as e:
                print(f"Fehler beim Erstellen der Bestellung: {str(e)}")
                continue

    # Bestellvorlagen erstellen
    order_templates = []
    if suppliers:
        template_count = min(random.randint(3, 8), len(suppliers))
        for i in range(template_count):
            try:
                template = OrderTemplateFactory(
                    supplier=suppliers[i % len(suppliers)],
                    created_by=random.choice(users)
                )
                order_templates.append(template)
            except Exception as e:
                print(f"Fehler beim Erstellen der Bestellvorlage: {str(e)}")
                continue

    # Bestellvorschläge erstellen
    order_suggestions = []
    for product in products[:min(20, len(products))]:  # Maximal 20 Vorschläge
        if suppliers:
            suggestion = OrderSuggestionFactory(
                product=product,
                preferred_supplier=random.choice(suppliers)
            )
            order_suggestions.append(suggestion)

    rmas = []
    for _ in range(random.randint(5, 15)):  # z.B. 5–15 RMAs
        try:
            rma = RMAFactory()

            # 1–3 Items pro RMA
            items = RMAItemFactory.create_batch(random.randint(1, 3), rma=rma)

            # Kommentare (optional)
            for _ in range(random.randint(0, 2)):
                RMACommentFactory(rma=rma)

            # Status-History
            RMAHistoryFactory(rma=rma, status_from='new', status_to=rma.status, changed_by=rma.created_by)

            # Dokumente & Fotos (optional)
            for item in items:
                if item.has_photos:
                    RMAPhotoFactory(rma_item=item)
                if random.random() < 0.3:
                    RMADocumentFactory(rma=rma)

            rmas.append(rma)
        except Exception as e:
            print(f"Fehler beim Erstellen von RMA: {e}")

    return {
        'users': users,
        'departments': departments,
        'warehouses': warehouses,
        'currencies': currencies,
        'taxes': taxes,
        'categories': categories,
        'variant_types': variant_types,
        'products': products,
        'variants': variants,
        'serial_numbers': serial_numbers,
        'batch_numbers': batch_numbers,
        'import_logs': import_logs,
        'import_errors': import_errors,
        'stock_movements': stock_movements,
        'stock_takes': stock_takes,
        'company_addresses': company_addresses,
        'suppliers': suppliers,
        'purchase_orders': purchase_orders,
        'order_templates': order_templates,
        'order_suggestions': order_suggestions,
        'rmas': rmas
    }


is_active = True


# Ersthelfer-Funktion zur Generierung von Testdaten


class StockMovementFactory(DjangoModelFactory):
    class Meta:
        model = StockMovement

    product = factory.SubFactory(ProductFactory)
    warehouse = factory.SubFactory(WarehouseFactory)
    quantity = factory.LazyAttribute(lambda _: Decimal(str(random.randint(1, 100))))

    movement_type = factory.Iterator([
        'in',
        'out',
        'adj'
    ])

    @factory.lazy_attribute
    def reference(self):
        references = {
            'in': [f"Lieferung-{fake.bothify(text='??-####')}",
                   f"Rücksendung-{fake.bothify(text='RET-####')}",
                   f"Übertrag-{fake.bothify(text='T-####')}"],
            'out': [f"Verkauf-{fake.bothify(text='S-####')}",
                    f"Auslieferung-{fake.bothify(text='DEL-####')}",
                    f"Übertrag-{fake.bothify(text='T-####')}"],
            'adj': [f"Inventur-{fake.bothify(text='INV-####')}",
                    f"Korrektur-{fake.bothify(text='ADJ-####')}",
                    f"Abschreibung-{fake.bothify(text='WO-####')}"]
        }
        return random.choice(references[self.movement_type])

    notes = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=100) if random.random() < 0.3 else "")
    created_by = factory.SubFactory(UserFactory)
    created_at = factory.LazyAttribute(lambda _: fake.date_time_between(start_date='-1y', end_date='now'))


class StockTakeFactory(DjangoModelFactory):
    class Meta:
        model = StockTake

    name = factory.LazyAttribute(lambda _: f"Inventur {fake.date_this_year().strftime('%d.%m.%Y')}")
    description = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=200) if random.random() < 0.7 else "")

    status = factory.Iterator([
        'draft',
        'in_progress',
        'completed',
        'cancelled'
    ], getter=lambda c: c)

    start_date = factory.LazyAttribute(lambda _: fake.date_time_this_year())

    @factory.lazy_attribute
    def end_date(self):
        if self.status in ['completed', 'cancelled']:
            # Für abgeschlossene/abgebrochene Inventuren, Ende 1-14 Tage nach Start
            return self.start_date + timedelta(days=random.randint(1, 14))
        elif self.status == 'in_progress':
            # Für laufende Inventuren, eventuell kein Enddatum
            if random.random() < 0.3:
                return None
            return self.start_date + timedelta(days=random.randint(1, 7))
        # Für Entwürfe, kein Enddatum
        return None

    created_by = factory.SubFactory(UserFactory)

    @factory.lazy_attribute
    def completed_by(self):
        if self.status == 'completed':
            # Der Abschließende kann der Ersteller sein oder ein anderer Benutzer
            if random.random() < 0.7:
                return self.created_by
            return UserFactory()
        return None

    notes = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=150) if random.random() < 0.4 else "")
    warehouse = factory.SubFactory(WarehouseFactory)

    inventory_type = factory.Iterator([
        'full',
        'rolling',
        'blind',
        'sample'
    ])

    @factory.lazy_attribute
    def display_expected_quantity(self):
        # Bei Blindzählung nie erwartete Mengen anzeigen
        if self.inventory_type == 'blind':
            return False
        # Bei anderen Inventurtypen meistens anzeigen
        return random.random() < 0.8

    @factory.lazy_attribute
    def cycle_count_category(self):
        # Kategorien nur für rollierende Inventur
        if self.inventory_type == 'rolling':
            return random.choice(['A', 'B', 'C'])
        return ''

    @factory.lazy_attribute
    def count_frequency(self):
        # Zyklus nur für rollierende Inventur
        if self.inventory_type == 'rolling':
            frequencies = [30, 60, 90, 180, 365]  # Typische Zyklen: monatlich, quartalsweise, halbjährlich, jährlich
            return random.choice(frequencies)
        return 0

    @factory.lazy_attribute
    def last_cycle_date(self):
        # Letztes Zyklusdatum nur für rollierende Inventur mit Frequenz
        if self.inventory_type == 'rolling' and self.count_frequency > 0:
            return fake.date_between(start_date='-1y', end_date='-1d')
        return None

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Standard Factory-Boy create
        stock_take = super()._create(model_class, *args, **kwargs)

        # Automatisch Inventurpositionen erstellen
        products = list(Product.objects.all())
        if products:
            # Zufällige Auswahl von 5-25 Produkten für die Inventur
            count = min(random.randint(5, 25), len(products))
            selected_products = random.sample(products, count)

            for product in selected_products:
                # Je nach Status der Inventur, Gezählt-Status festlegen
                if stock_take.status == 'completed':
                    is_counted = True
                elif stock_take.status == 'in_progress':
                    is_counted = random.random() < 0.7  # 70% der Produkte gezählt
                else:
                    is_counted = random.random() < 0.2  # 20% der Produkte in Entwurf gezählt

                # Erwartete Menge
                expected_qty = Decimal(str(random.randint(1, 1000)))

                # Gezählte Menge, leicht von der erwarteten abweichend
                if is_counted:
                    # Genau gleiche Menge in 60% der Fälle
                    if random.random() < 0.6:
                        counted_qty = expected_qty
                    else:
                        # Abweichung von bis zu 10%
                        deviation = expected_qty * Decimal(str(random.uniform(-0.1, 0.1)))
                        counted_qty = (expected_qty + deviation).quantize(Decimal('0.01'))
                        # Sicherstellen, dass die Menge nicht negativ ist
                        if counted_qty < 0:
                            counted_qty = Decimal('0')
                else:
                    counted_qty = None

                # Zählzeitpunkt
                counted_at = None
                if is_counted:
                    if stock_take.end_date:
                        counted_at = fake.date_time_between(
                            start_date=stock_take.start_date,
                            end_date=stock_take.end_date
                        )
                    else:
                        counted_at = fake.date_time_between(
                            start_date=stock_take.start_date,
                            end_date=datetime.now()
                        )

                # Zähler
                counted_by = None
                if is_counted:
                    if random.random() < 0.8:
                        counted_by = stock_take.created_by
                    else:
                        counted_by = UserFactory()

                StockTakeItem.objects.create(
                    stock_take=stock_take,
                    product=product,
                    expected_quantity=expected_qty,
                    counted_quantity=counted_qty,
                    is_counted=is_counted,
                    notes="" if random.random() < 0.7 else fake.sentence(),
                    counted_by=counted_by,
                    counted_at=counted_at
                )

        return stock_take


class StockTakeItemFactory(DjangoModelFactory):
    class Meta:
        model = StockTakeItem
        django_get_or_create = ('stock_take', 'product')

    stock_take = factory.SubFactory(StockTakeFactory)
    product = factory.SubFactory(ProductFactory)
    expected_quantity = factory.LazyAttribute(lambda _: Decimal(str(random.randint(1, 1000))))

    is_counted = factory.LazyAttribute(lambda _: random.random() < 0.7)  # 70% sind gezählt

    @factory.lazy_attribute
    def counted_quantity(self):
        if not self.is_counted:
            return None

        # Genau gleiche Menge in 60% der Fälle
        if random.random() < 0.6:
            return self.expected_quantity

        # Abweichung von bis zu 10%
        deviation = self.expected_quantity * Decimal(str(random.uniform(-0.1, 0.1)))
        result = (self.expected_quantity + deviation).quantize(Decimal('0.01'))

        # Sicherstellen, dass die Menge nicht negativ ist
        if result < 0:
            return Decimal('0')
        return result

    notes = factory.LazyAttribute(lambda _: fake.sentence() if random.random() < 0.3 else "")

    @factory.lazy_attribute
    def counted_by(self):
        if not self.is_counted:
            return None
        return UserFactory()

    @factory.lazy_attribute
    def counted_at(self):
        if not self.is_counted:
            return None

        if self.stock_take.end_date:
            return fake.date_time_between(
                start_date=self.stock_take.start_date,
                end_date=self.stock_take.end_date
            )

        return fake.date_time_between(
            start_date=self.stock_take.start_date,
            end_date=datetime.now()
        )


class CompanyAddressFactory(DjangoModelFactory):
    class Meta:
        model = CompanyAddress
        django_get_or_create = ('name', 'address_type')

    name = factory.LazyAttribute(lambda _: f"Adresse {fake.company()}")
    address_type = factory.Iterator([
        'headquarters',
        'warehouse',
        'shipping',
        'return',
        'billing',
        'other'
    ])
    is_default = factory.LazyAttribute(lambda _: random.random() < 0.3)  # 30% sind Standardadressen
    street = factory.LazyAttribute(lambda _: fake.street_address())
    zip_code = factory.LazyAttribute(lambda _: fake.postcode())
    city = factory.LazyAttribute(lambda _: fake.city())
    country = factory.LazyAttribute(lambda _: "Schweiz")  # Schweizer Standard
    contact_person = factory.LazyAttribute(lambda _: fake.name() if random.random() < 0.7 else "")
    phone = factory.LazyAttribute(lambda _: fake.phone_number() if random.random() < 0.6 else "")
    email = factory.LazyAttribute(lambda _: fake.email() if random.random() < 0.6 else "")
    notes = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=100) if random.random() < 0.3 else "")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        """Override die create-Methode, um mit dem unique_default_company_address_per_type Constraint umzugehen."""
        # Wir müssen sicherstellen, dass wir nicht zwei default-Adressen vom gleichen Typ erstellen
        try:
            if kwargs.get('is_default', False):
                # Wenn wir eine Standardadresse erstellen wollen, prüfen wir, ob schon eine existiert
                # Falls ja, setzen wir is_default auf False
                address_type = kwargs.get('address_type')
                if address_type and CompanyAddress.objects.filter(address_type=address_type, is_default=True).exists():
                    kwargs['is_default'] = False

            return super()._create(model_class, *args, **kwargs)
        except Exception as e:
            print(f"Fehler beim Erstellen der CompanyAddress: {str(e)}")
            # Versuche es erneut ohne is_default
            if 'is_default' in kwargs:
                del kwargs['is_default']
                return super()._create(model_class, *args, **kwargs)
            # Falls das nicht funktioniert, werfe den Fehler erneut
            raise


class PurchaseOrderFactory(DjangoModelFactory):
    class Meta:
        model = PurchaseOrder
        django_get_or_create = ('order_number',)

    order_number = factory.Sequence(lambda n: f"PO-{datetime.now().strftime('%Y%m')}-{n:04d}")
    supplier = factory.SubFactory('suppliers.factories.SupplierFactory')  # Annahme: Es gibt eine SupplierFactory
    order_date = factory.LazyAttribute(lambda _: fake.date_between(start_date='-1y', end_date='today'))

    @factory.lazy_attribute
    def expected_delivery(self):
        # Lieferdatum 2-30 Tage nach Bestelldatum
        if self.order_date:
            return self.order_date + timedelta(days=random.randint(2, 30))
        return None

    status = factory.Iterator([
        'draft',
        'pending',
        'approved',
        'sent',
        'partially_received',
        'received',
        'received_with_issues',
        'cancelled'
    ])

    created_by = factory.SubFactory(UserFactory)

    @factory.lazy_attribute
    def approved_by(self):
        if self.status in ['approved', 'sent', 'partially_received', 'received', 'received_with_issues']:
            return UserFactory()
        return None

    @factory.lazy_attribute
    def billing_address(self):
        try:
            # Prüfe, ob das CompanyAddress-Modell das address_type Feld hat
            has_address_type = 'address_type' in [f.name for f in CompanyAddress._meta.get_fields()]

            if has_address_type:
                # Wenn das Modell ein address_type Feld hat, suche nach Rechnungsadressen
                billing_addresses = CompanyAddress.objects.filter(address_type='billing')
                if billing_addresses.exists():
                    # Prüfe, ob eine Standardadresse vorhanden ist
                    if hasattr(CompanyAddress, 'is_default'):
                        default_addresses = billing_addresses.filter(is_default=True)
                        if default_addresses.exists():
                            return default_addresses.first()
                    # Sonst nimm eine zufällige Rechnungsadresse
                    return random.choice(list(billing_addresses))

                # Erstelle eine neue Rechnungsadresse, wenn keine existiert
                address_kwargs = {'address_type': 'billing'}
                if hasattr(CompanyAddress, 'is_default'):
                    address_kwargs['is_default'] = True
                return CompanyAddressFactory(**address_kwargs)
            else:
                # Wenn kein address_type Feld vorhanden ist, nimm eine beliebige Adresse
                addresses = CompanyAddress.objects.all()
                if addresses.exists():
                    return random.choice(list(addresses))
                # Oder erstelle eine neue Adresse
                return CompanyAddressFactory()

        except Exception as e:
            print(f"Fehler beim Zuweisen der Rechnungsadresse: {str(e)}")
            return None

    @factory.lazy_attribute
    def shipping_address(self):
        try:
            # 70% der Fälle gleiche Adresse wie Rechnungsadresse, wenn eine existiert
            if self.billing_address and random.random() < 0.7:
                return self.billing_address

            # Prüfe, ob das CompanyAddress-Modell das address_type Feld hat
            has_address_type = 'address_type' in [f.name for f in CompanyAddress._meta.get_fields()]

            if has_address_type:
                # Wenn das Modell ein address_type Feld hat, suche nach Versandadressen
                shipping_addresses = CompanyAddress.objects.filter(address_type='shipping')
                if shipping_addresses.exists():
                    # Prüfe, ob eine Standardadresse vorhanden ist
                    if hasattr(CompanyAddress, 'is_default'):
                        default_addresses = shipping_addresses.filter(is_default=True)
                        if default_addresses.exists():
                            return default_addresses.first()
                    # Sonst nimm eine zufällige Versandadresse
                    return random.choice(list(shipping_addresses))

                # Erstelle eine neue Versandadresse, wenn keine existiert
                address_kwargs = {'address_type': 'shipping'}
                if hasattr(CompanyAddress, 'is_default'):
                    address_kwargs['is_default'] = True
                return CompanyAddressFactory(**address_kwargs)
            else:
                # Wenn kein address_type Feld vorhanden ist, nimm eine beliebige Adresse
                addresses = CompanyAddress.objects.all()
                if addresses.exists():
                    return random.choice(list(addresses))
                # Oder erstelle eine neue Adresse
                return CompanyAddressFactory()

        except Exception as e:
            print(f"Fehler beim Zuweisen der Versandadresse: {str(e)}")
            return None

    notes = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=200) if random.random() < 0.3 else "")

    # Finanzinformationen
    subtotal = factory.LazyAttribute(lambda _: Decimal(str(random.uniform(100, 5000))).quantize(Decimal('0.01')))

    @factory.lazy_attribute
    def tax(self):
        # Etwa 7.7% Schweizer MwSt (kann variieren)
        return (self.subtotal * Decimal('0.077')).quantize(Decimal('0.01'))

    shipping_cost = factory.LazyAttribute(lambda _:
                                          Decimal(str(random.choice([0, 10, 15, 20, 25, 30]))).quantize(
                                              Decimal('0.01')))

    @factory.lazy_attribute
    def total(self):
        return (self.subtotal + self.tax + self.shipping_cost).quantize(Decimal('0.01'))

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Standard Factory-Boy create
        order = super()._create(model_class, *args, **kwargs)

        # Bestellpositionen erstellen (3-10 pro Bestellung)
        item_count = random.randint(3, 10)

        # Produkte aus der Datenbank holen
        products = list(Product.objects.all())
        if products:
            # Zufällige Auswahl von Produkten für die Bestellung
            selected_products = random.sample(products, min(item_count, len(products)))

            for product in selected_products:
                # Zufällige Menge zwischen 1 und 100
                quantity = Decimal(str(random.randint(1, 100)))

                # Zufälliger Preis (für Testzwecke)
                unit_price = Decimal(str(random.uniform(1, 200))).quantize(Decimal('0.01'))

                # Erstelle Bestellposition
                order_item = PurchaseOrderItemFactory(
                    purchase_order=order,
                    product=product,
                    quantity_ordered=quantity,
                    unit_price=unit_price
                )

        return order


class PurchaseOrderItemFactory(DjangoModelFactory):
    class Meta:
        model = PurchaseOrderItem

    purchase_order = factory.SubFactory(PurchaseOrderFactory)
    product = factory.SubFactory(ProductFactory)
    quantity_ordered = factory.LazyAttribute(lambda _: Decimal(str(random.randint(1, 100))))
    unit_price = factory.LazyAttribute(lambda _: Decimal(str(random.uniform(1, 200))).quantize(Decimal('0.01')))

    @factory.lazy_attribute
    def quantity_received(self):
        # Je nach Status der Bestellung
        order_status = self.purchase_order.status

        if order_status == 'received':
            # Vollständig erhalten
            return self.quantity_ordered
        elif order_status in ['partially_received', 'received_with_issues']:
            # Teilweise erhalten
            return Decimal(str(random.uniform(0, float(self.quantity_ordered)))).quantize(Decimal('0.01'))
        else:
            # Noch nichts erhalten
            return Decimal('0')

    @factory.lazy_attribute
    def status(self):
        if self.purchase_order.status == 'cancelled':
            return 'canceled'
        elif random.random() < 0.1:  # 10% Chance auf teilweise Stornierung
            return 'partially_canceled'
        else:
            return 'active'

    @factory.lazy_attribute
    def original_quantity(self):
        if self.status in ['canceled', 'partially_canceled']:
            return self.quantity_ordered + Decimal(str(random.randint(1, 10)))
        return None

    @factory.lazy_attribute
    def canceled_quantity(self):
        if self.status == 'canceled':
            return self.quantity_ordered
        elif self.status == 'partially_canceled':
            return Decimal(str(random.uniform(1, float(self.quantity_ordered) - 1))).quantize(Decimal('0.01'))
        return Decimal('0')

    @factory.lazy_attribute
    def cancellation_reason(self):
        if self.status in ['canceled', 'partially_canceled']:
            reasons = [
                "Produkt nicht mehr benötigt",
                "Preis zu hoch",
                "Lieferzeit zu lang",
                "Fehlerhafte Bestellung",
                "Alternative gefunden"
            ]
            return random.choice(reasons)
        return ""

    @factory.lazy_attribute
    def canceled_at(self):
        if self.status in ['canceled', 'partially_canceled']:
            return fake.date_time_between(
                start_date=self.purchase_order.order_date,
                end_date='now'
            )
        return None

    @factory.lazy_attribute
    def canceled_by(self):
        if self.status in ['canceled', 'partially_canceled']:
            return UserFactory()
        return None

    @factory.lazy_attribute
    def has_quality_issues(self):
        return self.purchase_order.status == 'received_with_issues' and random.random() < 0.7

    @factory.lazy_attribute
    def defective_quantity(self):
        if self.has_quality_issues:
            max_defective = min(self.quantity_received, self.quantity_ordered)
            if max_defective > 0:
                return Decimal(str(random.uniform(1, float(max_defective)))).quantize(Decimal('0.01'))
        return Decimal('0')

    currency = factory.SubFactory('core.factories.CurrencyFactory')

    supplier_sku = factory.LazyAttribute(lambda _:
                                         f"SUP-{fake.bothify(text='??-####')}" if random.random() < 0.7 else "")

    item_notes = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=100) if random.random() < 0.2 else "")

    @factory.lazy_attribute
    def tax(self):
        # Verwende den Steuersatz des Produkts oder einen Standardsatz
        if self.product and self.product.tax:
            return self.product.tax
        return TaxFactory(rate=Decimal('7.7'), is_default=True)  # Schweizer Standardsatz

    @factory.lazy_attribute
    def tax_rate(self):
        if self.tax:
            return self.tax.rate
        return Decimal('7.7')  # Schweizer Standardsatz


class OrderSplitFactory(DjangoModelFactory):
    class Meta:
        model = OrderSplit

    purchase_order = factory.SubFactory(PurchaseOrderFactory)
    name = factory.LazyAttribute(lambda _: f"Teillieferung {fake.bothify(text='##')}")

    @factory.lazy_attribute
    def expected_delivery(self):
        if self.purchase_order.expected_delivery:
            # Lieferung +/- 5 Tage um das erwartete Lieferdatum der Bestellung
            delta = random.randint(-5, 5)
            return self.purchase_order.expected_delivery + timedelta(days=delta)
        return fake.date_between(start_date='+1d', end_date='+30d')

    status = factory.Iterator([
        'planned',
        'in_transit',
        'received',
        'cancelled'
    ])

    tracking_number = factory.LazyAttribute(lambda _:
                                            fake.bothify(text='CH#########') if random.random() < 0.7 else "")

    @factory.lazy_attribute
    def carrier(self):
        carriers = [
            "Die Schweizerische Post",
            "DHL Schweiz",
            "DPD Schweiz",
            "UPS Schweiz",
            "FedEx Schweiz",
            "Planzer",
            "Camion Transport",
            "DB Schenker Schweiz",
            "Dreier Transport"
        ]
        return random.choice(carriers) if random.random() < 0.8 else ""

    notes = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=150) if random.random() < 0.3 else "")
    created_by = factory.SubFactory(UserFactory)

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Standard Factory-Boy create
        split = super()._create(model_class, *args, **kwargs)

        # Füge einige Bestellpositionen hinzu
        items = list(split.purchase_order.items.all())
        if items:
            # Wähle eine zufällige Anzahl von Positionen aus (mindestens eine, höchstens alle)
            count = random.randint(1, len(items))
            selected_items = random.sample(items, count)

            for item in selected_items:
                # Zufällige Menge zwischen 1 und der bestellten Menge
                max_qty = float(item.quantity_ordered)
                if max_qty > 0:
                    qty = Decimal(str(random.uniform(1, max_qty))).quantize(Decimal('0.01'))
                    OrderSplitItemFactory(
                        order_split=split,
                        order_item=item,
                        quantity=qty
                    )

        return split


class OrderSplitItemFactory(DjangoModelFactory):
    class Meta:
        model = OrderSplitItem
        django_get_or_create = ('order_split', 'order_item')

    order_split = factory.SubFactory(OrderSplitFactory)
    order_item = factory.SubFactory(PurchaseOrderItemFactory)

    @factory.lazy_attribute
    def quantity(self):
        # Menge zwischen 1 und der bestellten Menge
        max_qty = float(self.order_item.quantity_ordered)
        if max_qty > 0:
            return Decimal(str(random.uniform(1, max_qty))).quantize(Decimal('0.01'))
        return Decimal('1')


class PurchaseOrderReceiptFactory(DjangoModelFactory):
    class Meta:
        model = PurchaseOrderReceipt

    purchase_order = factory.SubFactory(PurchaseOrderFactory,
                                        status=factory.Iterator(
                                            ['partially_received', 'received', 'received_with_issues']))
    receipt_date = factory.LazyAttribute(lambda _: fake.date_time_this_year())
    received_by = factory.SubFactory(UserFactory)
    notes = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=150) if random.random() < 0.4 else "")

    @factory.lazy_attribute
    def order_split(self):
        # Prüfe, ob es Splits für diese Bestellung gibt
        splits = OrderSplit.objects.filter(purchase_order=self.purchase_order, status='in_transit')
        if splits.exists() and random.random() < 0.7:
            return random.choice(splits)
        return None

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Standard Factory-Boy create
        receipt = super()._create(model_class, *args, **kwargs)

        # Füge einige Bestellpositionen hinzu
        items = list(receipt.purchase_order.items.all())
        if items:
            # Wähle eine zufällige Anzahl von Positionen aus (mindestens eine, höchstens alle)
            count = random.randint(1, len(items))
            selected_items = random.sample(items, count)

            for item in selected_items:
                # Zufällige Menge zwischen 1 und der bestellten Menge
                max_qty = float(item.quantity_ordered)
                if max_qty > 0:
                    qty = Decimal(str(random.uniform(1, max_qty))).quantize(Decimal('0.01'))

                    # Prüfe, ob es Lager gibt
                    warehouses = list(Warehouse.objects.all())
                    if not warehouses:
                        warehouses = [WarehouseFactory()]

                    PurchaseOrderReceiptItemFactory(
                        receipt=receipt,
                        order_item=item,
                        quantity_received=qty,
                        warehouse=random.choice(warehouses)
                    )

        return receipt


class PurchaseOrderReceiptItemFactory(DjangoModelFactory):
    class Meta:
        model = PurchaseOrderReceiptItem

    receipt = factory.SubFactory(PurchaseOrderReceiptFactory)
    order_item = factory.SubFactory(PurchaseOrderItemFactory)
    quantity_received = factory.LazyAttribute(lambda _: Decimal(str(random.randint(1, 100))))

    @factory.lazy_attribute
    def batch_number(self):
        # Nur für Produkte mit Chargenverfolgung
        if self.order_item.product.has_batch_tracking:
            # Schweizer Batchnummern mit Jahr-Monat-Präfix
            year = datetime.now().year
            month = random.randint(1, 12)
            number = random.randint(1000, 9999)
            return f"{year}-{month:02d}-{number}"
        return ""

    @factory.lazy_attribute
    def expiry_date(self):
        # Nur für Produkte mit Ablaufdatum
        if self.order_item.product.has_expiry_tracking and self.batch_number:
            # Verfallsdatum zwischen 1 und 3 Jahren in der Zukunft
            days = random.randint(365, 365 * 3)
            return fake.date_between(start_date='today', end_date=f'+{days}d')
        return None

    warehouse = factory.SubFactory(WarehouseFactory)


class OrderSuggestionFactory(DjangoModelFactory):
    class Meta:
        model = OrderSuggestion

    product = factory.SubFactory(ProductFactory)

    @factory.lazy_attribute
    def current_stock(self):
        return Decimal(str(random.randint(0, 100)))

    @factory.lazy_attribute
    def minimum_stock(self):
        return Decimal(str(random.randint(10, 50)))

    @factory.lazy_attribute
    def suggested_order_quantity(self):
        if self.current_stock < self.minimum_stock:
            return self.minimum_stock - self.current_stock + Decimal(str(random.randint(5, 20)))
        return Decimal('0')

    preferred_supplier = factory.SubFactory('suppliers.factories.SupplierFactory')
    last_calculated = factory.LazyAttribute(lambda _: fake.date_time_this_month())


class OrderTemplateFactory(DjangoModelFactory):
    class Meta:
        model = OrderTemplate
        django_get_or_create = ('name', 'supplier')

    name = factory.LazyAttribute(lambda _: f"Vorlage {fake.word()} {fake.word()}")
    description = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=200) if random.random() < 0.7 else "")
    supplier = factory.SubFactory('suppliers.factories.SupplierFactory')
    created_by = factory.SubFactory(UserFactory)
    is_active = factory.LazyAttribute(lambda _: random.random() < 0.9)  # 90% sind aktiv

    is_recurring = factory.LazyAttribute(lambda _: random.random() < 0.5)  # 50% sind wiederkehrend

    @factory.lazy_attribute
    def recurrence_frequency(self):
        if self.is_recurring:
            return random.choice(['weekly', 'biweekly', 'monthly', 'quarterly', 'semiannual', 'annual'])
        return 'none'

    @factory.lazy_attribute
    def next_order_date(self):
        if self.is_recurring:
            return fake.date_between(start_date='today', end_date='+60d')
        return None

    shipping_address = factory.LazyAttribute(lambda _: fake.address() if random.random() < 0.5 else "")
    notes = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=150) if random.random() < 0.3 else "")

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        # Standard Factory-Boy create
        template = super()._create(model_class, *args, **kwargs)

        # Einige Vorlagenpositionen erstellen
        products = list(Product.objects.all())
        if products:
            # Zufällige Auswahl von 3-10 Produkten
            count = min(random.randint(3, 10), len(products))
            selected_products = random.sample(products, count)

            for product in selected_products:
                OrderTemplateItemFactory(
                    template=template,
                    product=product
                )

        return template


class OrderTemplateItemFactory(DjangoModelFactory):
    class Meta:
        model = OrderTemplateItem
        django_get_or_create = ('template', 'product')

    template = factory.SubFactory(OrderTemplateFactory)
    product = factory.SubFactory(ProductFactory)
    quantity = factory.LazyAttribute(lambda _: Decimal(str(random.randint(1, 100))))
    supplier_sku = factory.LazyAttribute(lambda _:
                                         f"SUP-{fake.bothify(text='??-####')}" if random.random() < 0.6 else "")


class PurchaseOrderCommentFactory(DjangoModelFactory):
    class Meta:
        model = PurchaseOrderComment

    purchase_order = factory.SubFactory(PurchaseOrderFactory)
    user = factory.SubFactory(UserFactory)

    comment_type = factory.Iterator([
        'note',
        'status_change',
        'system'
    ])

    @factory.lazy_attribute
    def comment(self):
        if self.comment_type == 'note':
            return fake.paragraph()
        elif self.comment_type == 'status_change':
            return f"Status geändert von {self.old_status} zu {self.new_status}"
        else:  # 'system'
            system_messages = [
                "Bestellung automatisch erstellt",
                "Erinnerung: Liefertermin in 3 Tagen",
                "Bestellung automatisch an Lieferanten gesendet",
                "Datei zur Bestellung hinzugefügt"
            ]
            return random.choice(system_messages)

    is_public = factory.LazyAttribute(lambda obj:
                                      random.random() < 0.8 if obj.comment_type == 'note' else random.random() < 0.3)

    @factory.lazy_attribute
    def old_status(self):
        if self.comment_type == 'status_change':
            return random.choice(['draft', 'pending', 'approved', 'sent'])
        return None

    @factory.lazy_attribute
    def new_status(self):
        if self.comment_type == 'status_change':
            status_progression = {
                'draft': ['pending', 'cancelled'],
                'pending': ['approved', 'cancelled'],
                'approved': ['sent', 'cancelled'],
                'sent': ['partially_received', 'received', 'received_with_issues', 'cancelled']
            }
            if self.old_status in status_progression:
                return random.choice(status_progression[self.old_status])
            return 'approved'
        return None


class RMAFactory(DjangoModelFactory):
    class Meta:
        model = RMA

    rma_number = factory.Sequence(lambda n: f"RMA-{timezone.now().strftime('%Y%m')}-{n:04d}")
    supplier = factory.LazyAttribute(lambda _: Supplier.objects.order_by('?').first())
    related_order = factory.LazyAttribute(
        lambda _: random.choice(PurchaseOrder.objects.all()) if PurchaseOrder.objects.exists() else None)
    status = factory.Iterator([s[0] for s in RMAStatus.choices])
    resolution_type = factory.Iterator([r[0] for r in RMAResolutionType.choices])
    resolution_notes = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=100))
    rma_warehouse = factory.LazyAttribute(lambda _: Warehouse.objects.order_by('?').first() or WarehouseFactory())
    created_by = factory.SubFactory(UserFactory)
    approved_by = factory.SubFactory(UserFactory)
    contact_person = factory.LazyAttribute(lambda _: fake.name())
    contact_email = factory.LazyAttribute(lambda _: fake.email())
    contact_phone = factory.LazyAttribute(lambda _: fake.phone_number())
    shipping_address = factory.LazyAttribute(lambda _: fake.address())
    tracking_number = factory.LazyAttribute(lambda _: fake.bothify(text='CH#########'))
    shipping_date = factory.LazyAttribute(lambda _: fake.date_between(start_date='-1y', end_date='today'))
    notes = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=100))

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        rma = super()._create(model_class, *args, **kwargs)

        # 1–3 Items anhängen
        for _ in range(random.randint(1, 3)):
            RMAItemFactory(rma=rma)

        # History-Eintrag (z. B. Erstellung)
        RMAHistoryFactory(rma=rma, status_from='new', status_to=rma.status, changed_by=rma.created_by)

        return rma


class RMAItemFactory(DjangoModelFactory):
    class Meta:
        model = RMAItem

    rma = factory.SubFactory(RMAFactory)
    product = factory.SubFactory(ProductFactory)
    receipt_item = factory.LazyAttribute(lambda _: random.choice(
        PurchaseOrderReceiptItem.objects.all()) if PurchaseOrderReceiptItem.objects.exists() else None)
    quantity = factory.LazyAttribute(lambda _: Decimal(str(random.randint(1, 10))))
    unit_price = factory.LazyAttribute(lambda _: Decimal(str(random.uniform(10, 200))).quantize(Decimal('0.01')))
    issue_type = factory.Iterator([t[0] for t in RMAIssueType.choices])
    issue_description = factory.LazyAttribute(lambda _: fake.sentence())
    batch_number = factory.LazyAttribute(
        lambda _: f"{random.randint(2020, 2025)}-{random.randint(1, 12):02d}-{random.randint(1000, 9999)}")
    serial_number = factory.LazyAttribute(lambda _: f"SN-{random.randint(100000, 999999)}")
    expiry_date = factory.LazyAttribute(lambda _: fake.future_date(end_date='+3y'))
    is_resolved = factory.LazyAttribute(lambda _: random.random() < 0.5)
    resolution_notes = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=100))
    has_photos = factory.LazyAttribute(lambda _: random.random() < 0.5)


class RMACommentFactory(DjangoModelFactory):
    class Meta:
        model = RMAComment

    rma = factory.SubFactory(RMAFactory)
    user = factory.SubFactory(UserFactory)
    comment = factory.LazyAttribute(lambda _: fake.paragraph())
    is_public = factory.LazyAttribute(lambda _: random.random() < 0.3)
    attachment_name = factory.LazyAttribute(
        lambda _: fake.file_name(extension=random.choice(['pdf', 'jpg', 'png'])))


class RMAHistoryFactory(DjangoModelFactory):
    class Meta:
        model = RMAHistory

    rma = factory.SubFactory(RMAFactory)
    status_from = factory.Iterator([s[0] for s in RMAStatus.choices])
    status_to = factory.Iterator([s[0] for s in RMAStatus.choices])
    changed_by = factory.SubFactory(UserFactory)
    note = factory.LazyAttribute(lambda _: fake.sentence())


class RMAPhotoFactory(DjangoModelFactory):
    class Meta:
        model = RMAPhoto

    rma_item = factory.SubFactory(RMAItemFactory)
    caption = factory.LazyAttribute(lambda _: fake.sentence())


class RMADocumentFactory(DjangoModelFactory):
    class Meta:
        model = RMADocument

    rma = factory.SubFactory(RMAFactory)
    document_type = factory.Iterator(['shipping_label', 'return_auth', 'supplier_response', 'credit_note', 'other'])
    title = factory.LazyAttribute(lambda _: fake.sentence(nb_words=4))
    uploaded_by = factory.SubFactory(UserFactory)
    notes = factory.LazyAttribute(lambda _: fake.text(max_nb_chars=100))
