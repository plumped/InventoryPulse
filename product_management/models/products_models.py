import os

from django.db import models

from core.models import Warehouse
from core.models.stock import BaseProductWarehouse
from inventory.models import VariantWarehouse
from master_data.models.tax_models import Tax
from product_management.models.categories_models import Category


class Product(models.Model):
    name = models.CharField(max_length=200)
    sku = models.CharField(max_length=50, unique=True)
    barcode = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    category = models.ForeignKey(Category, on_delete=models.SET_NULL, null=True)
    minimum_stock = models.IntegerField(default=0)
    unit = models.CharField(max_length=20, default="Stück")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    warehouses = models.ManyToManyField(Warehouse, through='ProductWarehouse')
    has_variants = models.BooleanField(default=False)
    has_serial_numbers = models.BooleanField(default=False)
    has_batch_tracking = models.BooleanField(default=False)
    has_expiry_tracking = models.BooleanField(default=False)

    tax = models.ForeignKey(Tax, on_delete=models.SET_NULL, null=True, blank=True,
                            verbose_name="Mehrwertsteuersatz",
                            help_text="Der auf dieses Produkt anzuwendende Mehrwertsteuersatz")

    def __str__(self):
        return self.name

    @property
    def total_stock(self):
        """Berechnet den Gesamtbestand über alle Lager."""
        from django.db.models import Sum
        return self.productwarehouse_set.aggregate(Sum('quantity'))['quantity__sum'] or 0

    @property
    def get_tax_rate(self):
        """Gibt den anzuwendenden Steuersatz zurück oder den Standard falls keiner hinterlegt ist."""
        if self.tax and self.tax.is_active:
            return self.tax.rate
        # Standard-Steuersatz verwenden
        default_tax = Tax.get_default_tax()
        if default_tax:
            return default_tax.rate
        # Fallback, falls kein Steuersatz definiert ist
        return 0


class ProductWarehouse(BaseProductWarehouse):
    """
    Model for tracking product stock in warehouses.

    This model extends the BaseProductWarehouse class from core.models.stock.
    """
    product = models.ForeignKey(Product, on_delete=models.CASCADE, verbose_name="Product")

    class Meta(BaseProductWarehouse.Meta):
        unique_together = ('product', 'warehouse')
        verbose_name = "Product Warehouse"
        verbose_name_plural = "Product Warehouses"


class ProductPhoto(models.Model):
    """Model for product photos."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='photos')
    image = models.ImageField(upload_to='product_photos/')
    is_primary = models.BooleanField(default=False)
    caption = models.CharField(max_length=255, blank=True)
    upload_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Foto für {self.product.name}"

    def save(self, *args, **kwargs):
        # Wenn dieses Foto als primär markiert wird, alle anderen Fotos dieses Produkts auf nicht-primär setzen
        if self.is_primary:
            ProductPhoto.objects.filter(product=self.product, is_primary=True).update(is_primary=False)
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-is_primary', '-upload_date']


# ProductAttachment - für Dokumente und andere Anhänge
def attachment_path(instance, filename):
    # Datei wird hochgeladen zu MEDIA_ROOT/product_attachments/product_<id>/<filename>
    return os.path.join('product_attachments', f'product_{instance.product.id}', filename)


class ProductAttachment(models.Model):
    """Model for product attachments (documents, manuals, etc.)."""
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='attachments')
    file = models.FileField(upload_to=attachment_path)
    title = models.CharField(max_length=255)
    description = models.TextField(blank=True)
    file_type = models.CharField(max_length=100, blank=True)  # PDF, DOCX, etc.
    upload_date = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title

    def save(self, *args, **kwargs):
        # Automatisch den Dateityp anhand der Dateierweiterung bestimmen
        if self.file and not self.file_type:
            extension = os.path.splitext(self.file.name)[1].lower()[1:]
            self.file_type = extension
        super().save(*args, **kwargs)

    class Meta:
        ordering = ['-upload_date']


# ProductVariantType - definiert Variationstypen wie "Farbe", "Größe", etc.
class ProductVariantType(models.Model):
    """Model for types of product variants (e.g., color, size)."""
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ['name']


class ProductVariant(models.Model):
    """Model for product variants (e.g., 'XL', 'Red')."""
    parent_product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='variants')
    sku = models.CharField(max_length=50, unique=True)  # Eigene SKU für jede Variante
    name = models.CharField(max_length=255)  # Name der konkreten Variante z.B. "T-Shirt Rot XL"
    variant_type = models.ForeignKey(ProductVariantType, on_delete=models.CASCADE)
    value = models.CharField(max_length=100)  # Der Wert für den Typ, z.B. "Rot" für Farbe
    price_adjustment = models.DecimalField(max_digits=10, decimal_places=2, default=0)  # Preisanpassung (+/-)
    barcode = models.CharField(max_length=100, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        unique_together = ('parent_product', 'variant_type', 'value')
        ordering = ['parent_product', 'variant_type', 'value']

    @property
    def total_stock(self):
        """Berechnet den Gesamtbestand über alle Lager."""
        from django.db.models import Sum

        # Prüfen, ob ein VariantWarehouse-Model existiert
        try:
            return VariantWarehouse.objects.filter(variant=self).aggregate(Sum('quantity'))['quantity__sum'] or 0
        except:
            # Fallback, falls kein VariantWarehouse existiert
            return 0
