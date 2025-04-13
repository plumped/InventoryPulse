from datetime import date

from django.db import models

from product_management.models.products_models import Product, ProductVariant


# Batch/Lot - für Chargennummern
class BatchNumber(models.Model):
    """Model for tracking batch or lot numbers."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='batches')
    variant = models.ForeignKey(ProductVariant, on_delete=models.CASCADE, related_name='batches',
                                null=True, blank=True)  # Optional, falls die Charge zu einer Variante gehört
    batch_number = models.CharField(max_length=100)
    quantity = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Menge in dieser Charge
    production_date = models.DateField(null=True, blank=True)
    expiry_date = models.DateField(null=True, blank=True)
    supplier = models.ForeignKey('suppliers.Supplier', on_delete=models.SET_NULL, null=True, blank=True)
    warehouse = models.ForeignKey('inventory.Warehouse', on_delete=models.SET_NULL, null=True, blank=True)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.product.name} - {self.batch_number}"

    @property
    def is_expired(self):
        """Check if the batch is expired."""
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
        unique_together = ('product', 'batch_number', 'warehouse')
        ordering = ['-created_at']
