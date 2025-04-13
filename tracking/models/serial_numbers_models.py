from datetime import date

from django.db import models

from product_management.models.products_models import Product, ProductVariant


# SerialNumber - für Seriennummern
class SerialNumber(models.Model):
    """Model for tracking serial numbers."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='serial_numbers')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='serial_numbers',
                                null=True, blank=True)  # Optional, falls die Seriennummer zu einer Variante gehört
    serial_number = models.CharField(max_length=100, unique=True)
    status_choices = [
        ('in_stock', 'Auf Lager'),
        ('sold', 'Verkauft'),
        ('reserved', 'Reserviert'),
        ('defective', 'Defekt'),
        ('returned', 'Zurückgegeben'),
    ]
    status = models.CharField(max_length=20, choices=status_choices, default='in_stock')
    purchase_date = models.DateField(null=True, blank=True)  # Einkaufsdatum
    expiry_date = models.DateField(null=True, blank=True)  # Verfallsdatum
    notes = models.TextField(blank=True)
    warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.serial_number

    @property
    def is_expired(self):
        """Check if the product is expired."""
        if self.expiry_date:
            return self.expiry_date < date.today()
        return False

    @property
    def days_until_expiry(self):
        """Calculate days until expiry."""
        if self.expiry_date:
            delta = self.expiry_date - date.today()
            return delta.days
        return None

    class Meta:
        ordering = ['-created_at']
