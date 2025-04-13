from django.db import transaction

from data_operations.importers.base import BaseImporter
from data_operations.importers.suppliers import Supplier
from product_management.models.categories import Category
from product_management.models.products import Product
from suppliers.models import SupplierProduct


class ProductImporter(BaseImporter):
    """Importer for products."""

    def __init__(self, *args, **kwargs):
        self.default_category = kwargs.pop('default_category', None)
        super().__init__(*args, **kwargs)
        self.required_fields = ['name', 'sku']

    def get_category(self, category_name):
        """Get or create a category by name."""
        if not category_name:
            return self.default_category

        try:
            return Category.objects.get(name=category_name)
        except Category.DoesNotExist:
            return Category.objects.create(name=category_name)

    @transaction.atomic
    def run_import(self):
        """Import products from CSV file."""
        self.start_import('product')
        rows = self.read_csv()

        for i, row in enumerate(rows, start=1):
            try:
                # Validate required fields
                self.validate_required_fields(row, i)

                # Process category
                category = None
                if 'category' in row and row['category']:
                    category = self.get_category(row['category'])
                elif self.default_category:
                    category = self.default_category

                # Check if product exists
                try:
                    product = Product.objects.get(sku=row['sku'])
                    if not self.update_existing:
                        self.log_error(i, f"Produkt mit Artikelnummer {row['sku']} existiert bereits.", row)
                        continue
                except Product.DoesNotExist:
                    product = Product(sku=row['sku'])

                # Update product fields
                product.name = row['name']
                product.description = row.get('description', '')
                product.barcode = row.get('barcode', '')
                product.category = category

                # Handle numeric fields
                try:
                    product.current_stock = float(row.get('current_stock', 0))
                except ValueError:
                    product.current_stock = 0

                try:
                    product.minimum_stock = float(row.get('minimum_stock', 0))
                except ValueError:
                    product.minimum_stock = 0

                product.unit = row.get('unit', 'Stück')

                product.save()
                self.successful_rows += 1

            except Exception as e:
                self.log_error(i, str(e), row)

        return self.finalize_import(len(rows))


class SupplierProductImporter(BaseImporter):
    """Importer for supplier-product relationships."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.required_fields = ['supplier_name', 'product_sku']

    @transaction.atomic
    def run_import(self):
        """Import supplier-product relationships from CSV file."""
        self.start_import('supplier_product')
        rows = self.read_csv()

        for i, row in enumerate(rows, start=1):
            try:
                # Validate required fields
                self.validate_required_fields(row, i)

                # Find supplier and product
                try:
                    supplier = Supplier.objects.get(name=row['supplier_name'])
                except Supplier.DoesNotExist:
                    self.log_error(i, f"Lieferant '{row['supplier_name']}' nicht gefunden.", row)
                    continue

                try:
                    product = Product.objects.get(sku=row['product_sku'])
                except Product.DoesNotExist:
                    self.log_error(i, f"Produkt mit Artikelnummer '{row['product_sku']}' nicht gefunden.", row)
                    continue

                # Check if relationship exists
                try:
                    sp = SupplierProduct.objects.get(supplier=supplier, product=product)
                    if not self.update_existing:
                        self.log_error(i,
                                       f"Zuordnung zwischen Lieferant '{supplier.name}' und Produkt '{product.name}' existiert bereits.",
                                       row)
                        continue
                except SupplierProduct.DoesNotExist:
                    sp = SupplierProduct(supplier=supplier, product=product)

                # Update fields
                sp.supplier_sku = row.get('supplier_sku', '')

                try:
                    sp.purchase_price = float(row.get('purchase_price', 0))
                except ValueError:
                    sp.purchase_price = 0

                try:
                    sp.lead_time_days = int(row.get('lead_time_days', 7))
                except ValueError:
                    sp.lead_time_days = 7

                sp.is_preferred = row.get('is_preferred', '').lower() in ('true', 'yes', '1', 'ja', 'wahr', 'y', 'j')
                sp.notes = row.get('notes', '')

                # If this is marked as preferred, update other relationships for this product
                if sp.is_preferred:
                    SupplierProduct.objects.filter(product=product).exclude(pk=sp.pk if sp.pk else -1).update(
                        is_preferred=False)

                sp.save()
                self.successful_rows += 1

            except Exception as e:
                self.log_error(i, str(e), row)

        return self.finalize_import(len(rows))