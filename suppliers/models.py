from django.db import models

from master_data.models.currency_models import Currency
from product_management.models.products_models import Product


class Supplier(models.Model):
    """Model for suppliers."""
    name = models.CharField(max_length=200)
    # Diese Felder beibehalten für Abwärtskompatibilität, aber als deprecated markieren
    contact_person = models.CharField(max_length=100, blank=True,
                                      help_text="Deprecated - Bitte Kontaktpersonen-Modell verwenden")
    email = models.EmailField(blank=True, help_text="Deprecated - Bitte Kontaktpersonen-Modell verwenden")
    phone = models.CharField(max_length=20, blank=True, help_text="Deprecated - Bitte Kontaktpersonen-Modell verwenden")
    address = models.TextField(blank=True, help_text="Deprecated - Bitte Adressen-Modell verwenden")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    website = models.URLField(blank=True, null=True)
    notes = models.TextField(blank=True, null=True)

    # Behalten Sie bestehende Felder bei
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                        verbose_name="Versandkosten")
    minimum_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                              verbose_name="Mindestbestellwert")
    default_currency = models.ForeignKey('master_data.Currency', on_delete=models.SET_NULL,
                                         null=True, blank=True,
                                         verbose_name="Standardwährung",
                                         related_name='suppliers')

    def __str__(self):
        return self.name

    def get_default_address(self, address_type='billing'):
        """Gibt die Standardadresse für den angegebenen Adresstyp zurück."""
        try:
            return self.addresses.get(address_type=address_type, is_default=True)
        except SupplierAddress.DoesNotExist:
            # Fallback auf erste Adresse dieses Typs
            addresses = self.addresses.filter(address_type=address_type)
            if addresses.exists():
                return addresses.first()
            # Fallback auf allgemeine Standardadresse
            addresses = self.addresses.filter(is_default=True)
            if addresses.exists():
                return addresses.first()
            # Fallback auf beliebige Adresse
            if self.addresses.exists():
                return self.addresses.first()
            return None

    def get_default_contact(self, contact_type='general'):
        """Gibt den Standardkontakt für den angegebenen Kontakttyp zurück."""
        try:
            return self.contacts.get(contact_type=contact_type, is_default=True)
        except SupplierContact.DoesNotExist:
            # Fallback auf ersten Kontakt dieses Typs
            contacts = self.contacts.filter(contact_type=contact_type)
            if contacts.exists():
                return contacts.first()
            # Fallback auf allgemeinen Standardkontakt
            contacts = self.contacts.filter(is_default=True)
            if contacts.exists():
                return contacts.first()
            # Fallback auf beliebigen Kontakt
            if self.contacts.exists():
                return self.contacts.first()
            return None

    def get_rma_address(self):
        """Gibt die RMA-Adresse zurück."""
        return self.get_default_address(address_type='rma')

    def get_rma_contact(self):
        """Gibt den RMA-Kontakt zurück."""
        return self.get_default_contact(contact_type='rma')

    def save(self, *args, **kwargs):
        # Wenn keine Standardwährung gesetzt ist, setze die Systemstandardwährung
        if not self.default_currency:
            self.default_currency = Currency.get_default_currency()
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['name']


class SupplierProduct(models.Model):
    """Model for linking products to suppliers with additional information."""
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='supplier_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='supplier_products')
    supplier_sku = models.CharField(max_length=50, blank=True, verbose_name="Supplier SKU")
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)

    # Währung als optionales Override für die Lieferanten-Standardwährung
    currency = models.ForeignKey('master_data.Currency', on_delete=models.SET_NULL, null=True, blank=True,
                                 verbose_name="Währung", related_name='supplier_products')

    lead_time_days = models.IntegerField(default=7)
    is_preferred = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.supplier.name} - {self.product.name}"

    @property
    def effective_currency(self):
        """Gibt die effektive Währung zurück - entweder die spezifische Währung dieser Produktzuordnung
        oder die Standardwährung des Lieferanten."""
        if self.currency:
            return self.currency
        elif self.supplier and self.supplier.default_currency:
            return self.supplier.default_currency
        else:
            return Currency.get_default_currency()

    class Meta:
        unique_together = ('supplier', 'product')
        ordering = ['supplier', 'product']


class AddressType(models.TextChoices):
    """Typen von Adressen, die ein Lieferant haben kann."""
    BILLING = 'billing', 'Rechnungsadresse'
    SHIPPING = 'shipping', 'Lieferadresse'
    RMA = 'rma', 'RMA-Rücksendeadresse'
    WAREHOUSE = 'warehouse', 'Lageradresse'
    OFFICE = 'office', 'Büro'
    OTHER = 'other', 'Sonstige'


class SupplierAddress(models.Model):
    """Modell für verschiedene Adressen eines Lieferanten."""
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='addresses')
    address_type = models.CharField(max_length=20, choices=AddressType.choices, default=AddressType.BILLING)
    is_default = models.BooleanField(default=False, verbose_name="Standardadresse für diesen Typ")
    name = models.CharField(max_length=200, blank=True, verbose_name="Adressname")
    street = models.CharField(max_length=200, verbose_name="Straße")
    street_number = models.CharField(max_length=20, blank=True, verbose_name="Hausnummer")
    postal_code = models.CharField(max_length=20, verbose_name="PLZ")
    city = models.CharField(max_length=100, verbose_name="Stadt")
    state = models.CharField(max_length=100, blank=True, verbose_name="Bundesland/Region")
    country = models.CharField(max_length=100, verbose_name="Land")
    notes = models.TextField(blank=True, verbose_name="Anmerkungen")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.name} ({self.get_address_type_display()})" if self.name else f"{self.get_address_type_display()}: {self.street}, {self.city}"

    def full_address(self):
        """Gibt die vollständige formatierte Adresse zurück."""
        address_parts = []
        if self.name:
            address_parts.append(self.name)

        street_line = self.street
        if self.street_number:
            street_line += " " + self.street_number
        address_parts.append(street_line)

        city_line = f"{self.postal_code} {self.city}"
        address_parts.append(city_line)

        if self.state:
            address_parts.append(self.state)

        address_parts.append(self.country)

        return "\n".join(address_parts)

    class Meta:
        verbose_name = "Lieferantenadresse"
        verbose_name_plural = "Lieferantenadressen"
        ordering = ['supplier', 'address_type', '-is_default']
        # Sicherstellen, dass es nur eine Standardadresse pro Adresstyp gibt
        constraints = [
            models.UniqueConstraint(
                fields=['supplier', 'address_type', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_address_per_type'
            )
        ]


class ContactType(models.TextChoices):
    """Typen von Kontaktpersonen bei einem Lieferanten."""
    GENERAL = 'general', 'Allgemeiner Kontakt'
    SALES = 'sales', 'Vertrieb'
    SUPPORT = 'support', 'Support'
    ACCOUNTING = 'accounting', 'Buchhaltung'
    RMA = 'rma', 'RMA/Reklamationen'
    TECHNICAL = 'technical', 'Technischer Kontakt'
    MANAGEMENT = 'management', 'Geschäftsführung'
    OTHER = 'other', 'Sonstiger Kontakt'


class SupplierContact(models.Model):
    """Modell für verschiedene Kontaktpersonen eines Lieferanten."""
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='contacts')
    contact_type = models.CharField(max_length=20, choices=ContactType.choices, default=ContactType.GENERAL)
    is_default = models.BooleanField(default=False, verbose_name="Standardkontakt für diesen Typ")
    title = models.CharField(max_length=50, blank=True, verbose_name="Titel/Anrede")
    first_name = models.CharField(max_length=100, verbose_name="Vorname")
    last_name = models.CharField(max_length=100, verbose_name="Nachname")
    position = models.CharField(max_length=100, blank=True, verbose_name="Position/Abteilung")
    email = models.EmailField(blank=True, verbose_name="E-Mail")
    phone = models.CharField(max_length=50, blank=True, verbose_name="Telefon")
    mobile = models.CharField(max_length=50, blank=True, verbose_name="Mobiltelefon")
    notes = models.TextField(blank=True, verbose_name="Anmerkungen")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.first_name} {self.last_name} ({self.get_contact_type_display()})"

    def full_name(self):
        """Gibt den vollständigen Namen inklusive Titel zurück."""
        if self.title:
            return f"{self.title} {self.first_name} {self.last_name}"
        return f"{self.first_name} {self.last_name}"

    class Meta:
        verbose_name = "Kontaktperson"
        verbose_name_plural = "Kontaktpersonen"
        ordering = ['supplier', 'contact_type', '-is_default', 'last_name']
        # Sicherstellen, dass es nur einen Standardkontakt pro Kontakttyp gibt
        constraints = [
            models.UniqueConstraint(
                fields=['supplier', 'contact_type', 'is_default'],
                condition=models.Q(is_default=True),
                name='unique_default_contact_per_type'
            )
        ]