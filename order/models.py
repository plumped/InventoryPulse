# order/models.py
from decimal import Decimal

from django.db import models
from django.contrib.auth.models import User
from model_utils import FieldTracker
from django.utils import timezone

from core.models import Product, Tax
from suppliers.models import Supplier


class PurchaseOrder(models.Model):
    STATUS_CHOICES = [
        ('draft', 'Entwurf'),
        ('pending', 'Wartend auf Genehmigung'),
        ('approved', 'Genehmigt'),
        ('sent', 'Bestellt'),
        ('partially_received', 'Teilweise erhalten'),
        ('received', 'Vollständig erhalten'),
        ('cancelled', 'Storniert')
    ]

    order_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT)
    order_date = models.DateField(auto_now_add=True)
    expected_delivery = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='purchase_orders_created')
    approved_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='purchase_orders_approved', null=True,
                                    blank=True)

    shipping_address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    # Finanzinformationen
    subtotal = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    tracker = FieldTracker(['status'])
    template_source = models.ForeignKey('OrderTemplate', on_delete=models.SET_NULL,
                                        null=True, blank=True,
                                        related_name='generated_orders',
                                        verbose_name="Erstellungsvorlage",
                                        help_text="Die Vorlage, aus der diese Bestellung erstellt wurde")

    def update_totals(self):
        """Aktualisiert alle Summen basierend auf den Bestellpositionen unter Berücksichtigung von Stornierungen"""
        # Subtotal ohne Steuern - verwende die display_line_subtotal Eigenschaft
        self.subtotal = sum(item.display_line_subtotal for item in self.items.all() if not item.is_canceled)

        # Steuern berechnen - gruppiert nach Steuermodell
        tax_groups = {}
        for item in self.items.all():
            # Stornierte Positionen überspringen
            if item.is_canceled:
                continue

            if item.tax:
                tax_id = item.tax.id
                if tax_id not in tax_groups:
                    tax_groups[tax_id] = 0
                # Verwende die display_line_tax Eigenschaft für stornierte Mengen
                tax_groups[tax_id] += item.display_line_tax

        # Gesamtsteuern
        self.tax = sum(tax_groups.values())

        # Gesamtsumme inkl. Steuern und Versandkosten
        self.total = self.subtotal + self.tax + self.shipping_cost
        self.save()

    def __str__(self):
        return f"Bestellung {self.order_number} ({self.get_status_display()})"

    class Meta:
        ordering = ['-order_date']
        verbose_name = "Bestellung"
        verbose_name_plural = "Bestellungen"

    def update_status_after_item_change(self):
        """Update order status based on item statuses after a cancellation."""
        # Skip for orders that are already in final states
        if self.status in ['received', 'canceled']:
            return

        # Check if all items are canceled
        all_items = self.items.all()
        active_items = all_items.exclude(status='canceled')

        if not active_items.exists():
            # All items are canceled, so cancel the entire order
            self.status = 'canceled'
            self.save()
        elif active_items.count() < all_items.count():
            # Some items are canceled, but not all - we could add a 'partially_canceled' status
            # to the PurchaseOrder model, but for now we'll keep the current status
            pass


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity_ordered = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_received = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

    # Status field for the order item
    STATUS_CHOICES = [
        ('active', 'Active'),
        ('canceled', 'Canceled'),
        ('partially_canceled', 'Partially Canceled')
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    # Original quantity before any cancellations
    original_quantity = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    canceled_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    cancellation_reason = models.TextField(blank=True)
    canceled_at = models.DateTimeField(null=True, blank=True)
    canceled_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                    related_name='canceled_order_items')

    # Add currency field to capture the currency at time of order
    currency = models.ForeignKey('core.Currency', on_delete=models.PROTECT, null=True,
                                 verbose_name="Währung",
                                 help_text="Die Währung, in der der Artikel bestellt wird")

    # Optional: Lieferantenartikelnummer
    supplier_sku = models.CharField(max_length=100, blank=True)

    # Optional: Spezielle Hinweise für diesen Artikel
    item_notes = models.TextField(blank=True)

    # Neues Feld für den Steuersatz (beim Anlegen der Bestellung kopiert)
    tax_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0,
                                   verbose_name="MwSt-Satz",
                                   help_text="Der zum Zeitpunkt der Bestellung gültige Mehrwertsteuersatz")

    # Referenz auf das Tax-Modell anstatt ein Dezimalfeld
    tax = models.ForeignKey(Tax, on_delete=models.PROTECT, null=True,
                            verbose_name="Mehrwertsteuersatz",
                            help_text="Der zum Zeitpunkt der Bestellung gültige Mehrwertsteuersatz")

    @property
    def line_subtotal(self):
        """Zeilensumme ohne Steuer"""
        if self.quantity_ordered is None or self.unit_price is None:
            return Decimal('0.00')
        return self.quantity_ordered * self.unit_price

    @property
    def line_tax(self):
        """Steueranteil der Zeile"""
        if self.tax is None or self.line_subtotal is None:
            return Decimal('0.00')
        return self.line_subtotal * (self.tax.rate / 100)

    @property
    def line_total(self):
        """Zeilensumme inklusive Steuer"""
        if self.line_subtotal is None or self.line_tax is None:
            return Decimal('0.00')
        return self.line_subtotal + self.line_tax

    @property
    def is_fully_received(self):
        return self.quantity_received >= self.quantity_ordered

    @property
    def receipt_status(self):
        if self.quantity_received == 0:
            return 'not_received'
        elif self.quantity_received < self.quantity_ordered:
            return 'partially_received'
        else:
            return 'fully_received'

    @property
    def is_canceled(self):
        """Check if the item is completely canceled."""
        return self.status == 'canceled'

    @property
    def is_partially_canceled(self):
        """Check if the item is partially canceled."""
        return self.status == 'partially_canceled'

    @property
    def effective_quantity(self):
        """Return the effective quantity after considering cancellations."""
        return self.quantity_ordered - self.canceled_quantity

    @property
    def display_quantity(self):
        """
        Gibt die für den Lieferanten relevante anzuzeigende Menge zurück.
        Bei stornierten oder teilweise stornierten Positionen ist dies die effektive Menge,
        sonst die ursprünglich bestellte Menge.
        """
        if self.status in ['canceled', 'partially_canceled']:
            return self.effective_quantity
        if self.quantity_ordered is None:
            return Decimal('0.00')
        return self.quantity_ordered

    @property
    def display_line_subtotal(self):
        """Gibt die anzuzeigende Zeilensumme ohne Steuer zurück basierend auf display_quantity."""
        if self.display_quantity is None or self.unit_price is None:
            return Decimal('0.00')
        return self.display_quantity * self.unit_price

    @property
    def display_line_tax(self):
        """Gibt den anzuzeigenden Steueranteil der Zeile zurück basierend auf display_quantity."""
        if self.tax is None or self.display_line_subtotal is None:
            return Decimal('0.00')
        return self.display_line_subtotal * (self.tax.rate / 100)

    @property
    def display_line_total(self):
        """Gibt die anzuzeigende Zeilensumme inkl. Steuer zurück basierend auf display_quantity."""
        if self.display_line_subtotal is None or self.display_line_tax is None:
            return Decimal('0.00')
        return self.display_line_subtotal + self.display_line_tax

    @property
    def effective_quantity(self):
        """Return the effective quantity after considering cancellations."""
        if self.quantity_ordered is None:
            return Decimal('0.00')
        if self.canceled_quantity is None:
            return self.quantity_ordered
        return self.quantity_ordered - self.canceled_quantity

    def cancel(self, user, quantity=None, reason=''):
        """Cancel this item or a specific quantity of it."""
        # Prüfen, ob die Bestellung bereits bestellt oder in einem späteren Status ist
        if self.purchase_order.status in ['sent', 'partially_received', 'received', 'canceled']:
            raise ValueError(
                f"Bestellpositionen können nicht storniert werden, wenn die Bestellung bereits den Status '{self.purchase_order.get_status_display()}' hat.")

        # Bestehende Prüfungen
        if self.purchase_order.status in ['received', 'canceled']:
            raise ValueError("Cannot cancel items for orders that are already received or canceled.")

        # Store original quantity on first cancellation
        if self.original_quantity is None:
            self.original_quantity = self.quantity_ordered

        # If quantity not specified or equals the total quantity, cancel the entire item
        if quantity is None or quantity >= self.quantity_ordered:
            self.status = 'canceled'
            self.canceled_quantity = self.quantity_ordered
        else:
            # Partial cancellation
            if quantity <= 0:
                raise ValueError("Cancellation quantity must be positive.")

            if quantity > self.quantity_ordered:
                raise ValueError("Cannot cancel more than the ordered quantity.")

            self.canceled_quantity = quantity
            self.status = 'partially_canceled'

        # Record cancellation details
        self.cancellation_reason = reason
        self.canceled_at = timezone.now()
        self.canceled_by = user
        self.save()

        # Update the order status if needed
        self.purchase_order.update_status_after_item_change()

    def __str__(self):
        return f"{self.product.name} ({self.quantity_ordered} {self.product.unit})"

    def save(self, *args, **kwargs):
        # Wenn neu erstellt und kein Steuersatz gesetzt ist, den Produktsteuersatz verwenden
        if not self.pk and not self.tax and self.product and self.product.tax:
            self.tax = self.product.tax

        # Wenn keine Währung gesetzt ist, die Standardwährung verwenden
        if not self.currency:
            from core.models import Currency
            self.currency = Currency.get_default_currency()

        if self.canceled_quantity > self.quantity_ordered:
            self.canceled_quantity = self.quantity_ordered

        super().save(*args, **kwargs)


class PurchaseOrderReceipt(models.Model):
    """Dokumentiert den Wareneingang für eine Bestellung"""
    purchase_order = models.ForeignKey(PurchaseOrder, related_name='receipts', on_delete=models.CASCADE)
    receipt_date = models.DateField(auto_now_add=True)
    received_by = models.ForeignKey(User, on_delete=models.PROTECT)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Wareneingang für {self.purchase_order} am {self.receipt_date}"


class PurchaseOrderReceiptItem(models.Model):
    """Detaillierte Positionen eines Wareneingangs"""
    receipt = models.ForeignKey(PurchaseOrderReceipt, related_name='items', on_delete=models.CASCADE)
    order_item = models.ForeignKey(PurchaseOrderItem, on_delete=models.CASCADE)
    quantity_received = models.DecimalField(max_digits=10, decimal_places=2)

    # Für Chargenverfolgung
    batch_number = models.CharField(max_length=100, blank=True)
    expiry_date = models.DateField(null=True, blank=True)

    # Ziel-Lager
    warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.PROTECT)

    def __str__(self):
        return f"{self.order_item.product.name}: {self.quantity_received} {self.order_item.product.unit}"


class OrderSuggestion(models.Model):
    """Automatische Bestellvorschläge basierend auf Mindestbestand"""
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    current_stock = models.DecimalField(max_digits=10, decimal_places=2)
    minimum_stock = models.DecimalField(max_digits=10, decimal_places=2)
    suggested_order_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    preferred_supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True)
    last_calculated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Bestellvorschlag: {self.product.name} ({self.suggested_order_quantity})"


class OrderTemplate(models.Model):
    """Template for frequently used orders"""
    RECURRENCE_CHOICES = [
        ('none', 'Keine Wiederholung'),
        ('daily', 'Täglich'),
        ('weekly', 'Wöchentlich'),
        ('biweekly', 'Alle zwei Wochen'),
        ('monthly', 'Monatlich'),
        ('quarterly', 'Vierteljährlich'),
        ('semiannual', 'Halbjährlich'),
        ('annual', 'Jährlich'),
    ]

    name = models.CharField(max_length=100, verbose_name="Vorlagenname")
    description = models.TextField(blank=True, verbose_name="Beschreibung")
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, verbose_name="Lieferant")
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='order_templates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True, verbose_name="Aktiv")

    # Recurrence settings
    is_recurring = models.BooleanField(default=False, verbose_name="Wiederkehrend")
    recurrence_frequency = models.CharField(
        max_length=20,
        choices=RECURRENCE_CHOICES,
        default='none',
        verbose_name="Häufigkeit"
    )
    next_order_date = models.DateField(null=True, blank=True, verbose_name="Nächstes Bestelldatum")
    shipping_address = models.TextField(blank=True, verbose_name="Lieferadresse")
    notes = models.TextField(blank=True, verbose_name="Anmerkungen")

    def __str__(self):
        return f"{self.name} ({self.supplier.name})"

    class Meta:
        verbose_name = "Bestellvorlage"
        verbose_name_plural = "Bestellvorlagen"
        ordering = ['supplier__name', 'name']


class OrderTemplateItem(models.Model):
    """Line items for order templates"""
    template = models.ForeignKey(OrderTemplate, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, verbose_name="Menge")
    supplier_sku = models.CharField(max_length=100, blank=True, verbose_name="Lieferanten-Artikelnummer")

    def __str__(self):
        return f"{self.product.name} ({self.quantity} {self.product.unit})"

    class Meta:
        verbose_name = "Vorlagenposition"
        verbose_name_plural = "Vorlagenpositionen"
        unique_together = ['template', 'product']