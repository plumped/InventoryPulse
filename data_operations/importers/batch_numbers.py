from datetime import datetime

from django.db import transaction

from data_operations.importers.base import BaseImporter
from data_operations.importers.suppliers import Supplier
from inventory.models import Warehouse
from product_management.models.products import Product
from tracking.models import BatchNumber


class BatchNumberImporter(BaseImporter):
    """Importer für Chargen."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.required_fields = ['product_sku', 'batch_number', 'quantity']

    @transaction.atomic
    def run_import(self):
        """Import batches from CSV file."""
        self.start_import('batch')
        rows = self.read_csv()

        for i, row in enumerate(rows, start=1):
            try:
                # Validate required fields
                self.validate_required_fields(row, i)

                # Find the product
                try:
                    product = Product.objects.get(sku=row['product_sku'])
                except Product.DoesNotExist:
                    self.log_error(i, f"Produkt mit SKU '{row['product_sku']}' nicht gefunden.", row)
                    continue

                # Check if batch exists for this product
                batch_number = row['batch_number']
                try:
                    batch = BatchNumber.objects.get(product=product, batch_number=batch_number)
                    if not self.update_existing:
                        self.log_error(i, f"Charge '{batch_number}' für Produkt '{product.name}' existiert bereits.", row)
                        continue
                except BatchNumber.DoesNotExist:
                    batch = BatchNumber(product=product, batch_number=batch_number)

                # Set quantity
                try:
                    batch.quantity = float(row.get('quantity', 0))
                except ValueError:
                    self.log_error(i, f"Ungültiger Wert für Menge: '{row.get('quantity')}'", row)
                    continue

                # Find optional warehouse
                warehouse = None
                if 'warehouse_name' in row and row['warehouse_name']:
                    try:
                        warehouse = Warehouse.objects.get(name=row['warehouse_name'])
                        batch.warehouse = warehouse
                    except Warehouse.DoesNotExist:
                        self.log_error(i, f"Lager '{row['warehouse_name']}' nicht gefunden.", row)
                        continue

                # Find optional supplier
                supplier = None
                if 'supplier_name' in row and row['supplier_name']:
                    try:
                        supplier = Supplier.objects.get(name=row['supplier_name'])
                        batch.supplier = supplier
                    except Supplier.DoesNotExist:
                        self.log_error(i, f"Lieferant '{row['supplier_name']}' nicht gefunden.", row)
                        continue

                # Parse dates
                if 'production_date' in row and row['production_date']:
                    try:
                        batch.production_date = datetime.strptime(row['production_date'], '%Y-%m-%d').date()
                    except ValueError:
                        self.log_error(i, f"Ungültiges Produktionsdatum: '{row['production_date']}'. Format: YYYY-MM-DD", row)
                        continue

                if 'expiry_date' in row and row['expiry_date']:
                    try:
                        batch.expiry_date = datetime.strptime(row['expiry_date'], '%Y-%m-%d').date()
                    except ValueError:
                        self.log_error(i, f"Ungültiges Ablaufdatum: '{row['expiry_date']}'. Format: YYYY-MM-DD", row)
                        continue

                # Set other optional fields
                batch.notes = row.get('notes', '')

                # Ensure product is configured for batch tracking
                if not product.has_batch_tracking:
                    product.has_batch_tracking = True
                    product.save()

                # Save batch
                batch.save()
                self.successful_rows += 1

            except Exception as e:
                self.log_error(i, str(e), row)

        return self.finalize_import(len(rows))