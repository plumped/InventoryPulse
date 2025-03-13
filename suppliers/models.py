from django.db import models
from core.models import Product


class Supplier(models.Model):
    """Model for suppliers."""
    name = models.CharField(max_length=200)
    contact_person = models.CharField(max_length=100, blank=True)
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    address = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)

    # Neue Felder hinzufügen
    shipping_cost = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                        verbose_name="Versandkosten")
    minimum_order_value = models.DecimalField(max_digits=10, decimal_places=2, default=0,
                                              verbose_name="Mindestbestellwert")

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class SupplierProduct(models.Model):
    """Model for linking products to suppliers with additional information."""
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='supplier_products')
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='supplier_products')
    supplier_sku = models.CharField(max_length=50, blank=True, verbose_name="Supplier SKU")
    purchase_price = models.DecimalField(max_digits=10, decimal_places=2)
    lead_time_days = models.IntegerField(default=7)
    is_preferred = models.BooleanField(default=False)
    notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.supplier.name} - {self.product.name}"

    class Meta:
        unique_together = ('supplier', 'product')
        ordering = ['supplier', 'product']