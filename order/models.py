# order/models.py
from django.db import models
from django.contrib.auth.models import User
from model_utils import FieldTracker

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

    def update_totals(self):
        """Aktualisiert alle Summen basierend auf den Bestellpositionen"""
        # Subtotal ohne Steuern
        self.subtotal = sum(item.line_subtotal for item in self.items.all())

        # Steuern berechnen - gruppiert nach Steuermodell
        tax_groups = {}
        for item in self.items.all():
            if item.tax:
                tax_id = item.tax.id
                if tax_id not in tax_groups:
                    tax_groups[tax_id] = 0
                tax_groups[tax_id] += item.line_tax

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


class PurchaseOrderItem(models.Model):
    purchase_order = models.ForeignKey(PurchaseOrder, related_name='items', on_delete=models.CASCADE)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity_ordered = models.DecimalField(max_digits=10, decimal_places=2)
    quantity_received = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    unit_price = models.DecimalField(max_digits=10, decimal_places=2)

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
        return self.quantity_ordered * self.unit_price

    @property
    def line_tax(self):
        """Steueranteil der Zeile"""
        if self.tax:
            return self.line_subtotal * (self.tax.rate / 100)
        return 0

    @property
    def line_total(self):
        """Zeilensumme inklusive Steuer"""
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

    def __str__(self):
        return f"{self.product.name} ({self.quantity_ordered} {self.product.unit})"

    def save(self, *args, **kwargs):
        # Wenn neu erstellt und kein Steuersatz gesetzt ist, den Produktsteuersatz verwenden
        if not self.pk and not self.tax and self.product and self.product.tax:
            self.tax = self.product.tax
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