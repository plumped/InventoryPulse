from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from core.models import Product
from suppliers.models import Supplier, SupplierProduct


class PurchaseOrder(models.Model):
    """Model for purchase orders to suppliers."""
    STATUS_CHOICES = (
        ('draft', 'Entwurf'),
        ('sent', 'Bestellt'),
        ('partially_received', 'Teilweise erhalten'),
        ('received', 'Vollständig erhalten'),
        ('cancelled', 'Storniert'),
    )

    order_number = models.CharField(max_length=50, unique=True)
    supplier = models.ForeignKey(Supplier, on_delete=models.PROTECT, related_name='purchase_orders')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    order_date = models.DateField(null=True, blank=True)
    expected_delivery_date = models.DateField(null=True, blank=True)
    delivery_date = models.DateField(null=True, blank=True)

    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    total = models.DecimalField(max_digits=12, decimal_places=2, default=0)

    shipping_address = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    reference = models.CharField(max_length=100, blank=True, help_text="Externe Referenznummer")
    internal_notes = models.TextField(blank=True, help_text="Interne Notizen (nicht für Lieferanten)")

    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_purchase_orders')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Bestellung {self.order_number} ({self.get_status_display()})"

    def save(self, *args, **kwargs):
        # Generiere Bestellnummer, falls nicht vorhanden
        if not self.order_number:
            last_order = PurchaseOrder.objects.all().order_by('-id').first()
            if last_order:
                last_number = int(last_order.order_number.split('-')[1])
                self.order_number = f"PO-{last_number + 1:06d}"
            else:
                self.order_number = "PO-000001"

        # Berechne Summen
        self.subtotal = sum(item.line_total for item in self.items.all())
        self.total = self.subtotal + self.tax + self.shipping_cost

        super().save(*args, **kwargs)

    def get_item_count(self):
        """Return the number of unique items in this order."""
        return self.items.count()

    def get_total_quantity(self):
        """Return the total quantity of all items."""
        return sum(item.quantity for item in self.items.all())

    def get_received_quantity(self):
        """Return the total quantity received so far."""
        return sum(item.received_quantity for item in self.items.all())

    def update_status_based_on_items(self):
        """Update the status based on receipt status of items."""
        items = self.items.all()

        if not items:
            return  # No items, leave status as is

        # Calculate what percentage of items have been received
        total_ordered = sum(item.quantity for item in items)
        total_received = sum(item.received_quantity for item in items)

        if total_received == 0:
            if self.status == 'cancelled':
                pass  # Leave as cancelled
            else:
                self.status = 'sent'
        elif total_received < total_ordered:
            self.status = 'partially_received'
        else:
            self.status = 'received'
            if not self.delivery_date:
                self.delivery_date = timezone.now().date()

        self.save()


class PurchaseOrderItem(models.Model):
    """Model for items in a purchase order."""
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    supplier_product = models.ForeignKey(SupplierProduct, on_delete=models.SET_NULL, null=True, blank=True)

    quantity = models.DecimalField(max_digits=10, decimal_places=2)
    received_quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)

    unit_price = models.DecimalField(max_digits=10, decimal_places=2)
    discount_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)
    tax_percentage = models.DecimalField(max_digits=5, decimal_places=2, default=0)

    supplier_sku = models.CharField(max_length=50, blank=True)
    description = models.TextField(blank=True)
    notes = models.TextField(blank=True)

    expected_delivery_date = models.DateField(null=True, blank=True)

    def __str__(self):
        return f"{self.product.name} - {self.quantity} {self.product.unit}"

    @property
    def line_total(self):
        """Calculate the total for this line item."""
        # Calculate price after discount
        discounted_price = self.unit_price * (1 - (self.discount_percentage / 100))
        # Calculate total before tax
        return discounted_price * self.quantity

    @property
    def received_percentage(self):
        """Calculate the percentage of received items."""
        if self.quantity == 0:
            return 0
        return (self.received_quantity / self.quantity) * 100

    def save(self, *args, **kwargs):
        # If supplier_product is set, get data from it
        if self.supplier_product and not self.unit_price:
            self.unit_price = self.supplier_product.purchase_price
            self.supplier_sku = self.supplier_product.supplier_sku

        super().save(*args, **kwargs)

        # Update the status of the purchase order
        self.purchase_order.update_status_based_on_items()


class GoodsReceipt(models.Model):
    """Model for goods receiving."""
    STATUS_CHOICES = (
        ('draft', 'Entwurf'),
        ('completed', 'Abgeschlossen'),
        ('cancelled', 'Storniert'),
    )

    receipt_number = models.CharField(max_length=50, unique=True)
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.CASCADE, related_name='goods_receipts')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='draft')

    receipt_date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True)

    delivery_note_number = models.CharField(max_length=100, blank=True, help_text="Lieferscheinnummer des Lieferanten")
    carrier = models.CharField(max_length=100, blank=True, help_text="Transporteur/Spediteur")
    package_count = models.IntegerField(default=1, help_text="Anzahl der Packstücke")

    created_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='created_goods_receipts')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Wareneingang {self.receipt_number}"

    def save(self, *args, **kwargs):
        # Generiere Eingangsnummer, falls nicht vorhanden
        if not self.receipt_number:
            last_receipt = GoodsReceipt.objects.all().order_by('-id').first()
            if last_receipt:
                last_number = int(last_receipt.receipt_number.split('-')[1])
                self.receipt_number = f"GR-{last_number + 1:06d}"
            else:
                self.receipt_number = "GR-000001"

        super().save(*args, **kwargs)


class GoodsReceiptItem(models.Model):
    """Model for items in goods receipt."""
    goods_receipt = models.ForeignKey(GoodsReceipt, on_delete=models.CASCADE, related_name='items')
    purchase_order_item = models.ForeignKey(PurchaseOrderItem, on_delete=models.CASCADE, related_name='receipt_items')

    received_quantity = models.DecimalField(max_digits=10, decimal_places=2)
    is_defective = models.BooleanField(default=False)
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"{self.purchase_order_item.product.name} - {self.received_quantity}"

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)

        # Update the received quantity on the purchase order item
        if self.goods_receipt.status == 'completed':
            # Get all completed receipt items for this PO item
            completed_receipts = GoodsReceiptItem.objects.filter(
                purchase_order_item=self.purchase_order_item,
                goods_receipt__status='completed'
            )

            # Sum up all received quantities
            total_received = sum(item.received_quantity for item in completed_receipts)

            # Update the PO item
            self.purchase_order_item.received_quantity = total_received
            self.purchase_order_item.save()


class PurchaseOrderTemplate(models.Model):
    """Model for purchase order templates."""
    name = models.CharField(max_length=100)
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='order_templates')
    notes = models.TextField(blank=True)
    created_by = models.ForeignKey(User, on_delete=models.PROTECT)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Vorlage: {self.name} ({self.supplier.name})"


class PurchaseOrderTemplateItem(models.Model):
    """Model for items in a purchase order template."""
    template = models.ForeignKey(PurchaseOrderTemplate, on_delete=models.CASCADE, related_name='items')
    product = models.ForeignKey(Product, on_delete=models.CASCADE)
    supplier_product = models.ForeignKey(SupplierProduct, on_delete=models.SET_NULL, null=True, blank=True)
    quantity = models.DecimalField(max_digits=10, decimal_places=2)

    def __str__(self):
        return f"{self.product.name} - {self.quantity}"


class PurchaseRecommendation(models.Model):
    """Model for storing purchase recommendations."""
    STATUS_CHOICES = (
        ('new', 'Neu'),
        ('in_process', 'In Bearbeitung'),
        ('ordered', 'Bestellt'),
        ('ignored', 'Ignoriert'),
    )

    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='purchase_recommendations')
    supplier_product = models.ForeignKey(SupplierProduct, on_delete=models.SET_NULL, null=True, blank=True)

    current_stock = models.DecimalField(max_digits=10, decimal_places=2)
    min_stock = models.DecimalField(max_digits=10, decimal_places=2)
    recommended_quantity = models.DecimalField(max_digits=10, decimal_places=2)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='new')
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True)

    recommended_date = models.DateField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Empfehlung: {self.product.name} ({self.recommended_quantity})"

    class Meta:
        ordering = ['status', 'recommended_date']