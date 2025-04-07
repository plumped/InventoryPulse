import csv
import io
import logging
from datetime import datetime

from django.db import transaction
from django.utils.text import slugify
from django.utils.timezone import make_aware

from inventory.models import Warehouse
from .models import Product, Category, ImportLog, ImportError, SerialNumber
from suppliers.models import Supplier, SupplierProduct

logger = logging.getLogger(__name__)


class BaseImporter:
    """Base class for all importers."""

    def __init__(self, file_obj, delimiter=',', encoding='utf-8', skip_header=True,
                 update_existing=True, user=None):
        self.file_obj = file_obj
        self.delimiter = delimiter
        self.encoding = encoding
        self.skip_header = skip_header
        self.update_existing = update_existing
        self.user = user
        self.import_log = None
        self.errors = []
        self.successful_rows = 0
        self.required_fields = []

    def validate_required_fields(self, row, row_num):
        """Validate that all required fields are present in the row."""
        for field in self.required_fields:
            if not row.get(field) or row[field].strip() == '':
                raise ValueError(f"Feld '{field}' ist erforderlich, aber leer oder nicht vorhanden.")
        return True

    def read_csv(self):
        """Read the CSV file and return a list of dictionaries."""
        # Check if file is a string (file path) or a file object
        if isinstance(self.file_obj, str):
            with open(self.file_obj, 'r', encoding=self.encoding) as f:
                csvreader = csv.reader(f, delimiter=self.delimiter)
                rows = list(csvreader)
        else:
            # Ensure we're at the beginning of the file
            self.file_obj.seek(0)
            # Read the file content as text
            content = self.file_obj.read().decode(self.encoding)
            # Parse CSV
            csvreader = csv.reader(io.StringIO(content), delimiter=self.delimiter)
            rows = list(csvreader)

        if not rows:
            return []

        # Extract header and use it as keys for dictionaries
        header = rows[0]
        if self.skip_header:
            data = rows[1:]
        else:
            data = rows
            # If no header, generate field names
            header = [f"field{i}" for i in range(len(data[0]))]

        # Convert to list of dictionaries
        result = []
        for i, row in enumerate(data):
            if not row or (len(row) == 1 and not row[0]):  # Skip empty rows
                continue
            if len(row) < len(header):
                # Pad row with empty strings if it's shorter than the header
                row.extend([''] * (len(header) - len(row)))
            elif len(row) > len(header):
                # Truncate row if it's longer than the header
                row = row[:len(header)]
            result.append(dict(zip(header, row)))

        return result

    def start_import(self, import_type):
        """Initialize the import process and create an import log."""
        file_name = getattr(self.file_obj, 'name', 'Unknown file')
        self.import_log = ImportLog.objects.create(
            import_type=import_type,
            file_name=file_name,
            created_by=self.user,
            status='processing'
        )
        return self.import_log

    def log_error(self, row_num, error_message, row_data=None, field_name="", field_value=""):
        """Log an error during import."""
        if row_data and isinstance(row_data, dict):
            row_data_str = ', '.join([f"{k}: {v}" for k, v in row_data.items()])
        else:
            row_data_str = str(row_data) if row_data else ''

        ImportError.objects.create(
            import_log=self.import_log,
            row_number=row_num,
            error_message=str(error_message),
            row_data=row_data_str,
            field_name=field_name,
            field_value=field_value
        )
        self.errors.append((row_num, error_message, row_data_str))

    def finalize_import(self, total_rows):
        """Update the import log with final statistics."""
        self.import_log.total_rows = total_rows
        self.import_log.successful_rows = self.successful_rows
        self.import_log.failed_rows = total_rows - self.successful_rows
        self.import_log.status = 'completed' if self.successful_rows == total_rows else 'completed_with_errors'

        # Also update new fields directly for consistency
        self.import_log.rows_processed = total_rows
        self.import_log.rows_created = self.successful_rows
        self.import_log.rows_error = total_rows - self.successful_rows

        self.import_log.save()
        return self.import_log

    def run_import(self):
        """Run the import process (to be implemented by subclasses)."""
        raise NotImplementedError("Subclasses must implement run_import method")


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


class SupplierImporter(BaseImporter):
    """Importer for suppliers."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.required_fields = ['name']

    @transaction.atomic
    def run_import(self):
        """Import suppliers from CSV file."""
        self.start_import('supplier')
        rows = self.read_csv()

        for i, row in enumerate(rows, start=1):
            try:
                # Validate required fields
                self.validate_required_fields(row, i)

                # Check if supplier exists
                try:
                    supplier = Supplier.objects.get(name=row['name'])
                    if not self.update_existing:
                        self.log_error(i, f"Lieferant mit Namen {row['name']} existiert bereits.", row)
                        continue
                except Supplier.DoesNotExist:
                    supplier = Supplier(name=row['name'])

                # Update supplier fields
                supplier.contact_person = row.get('contact_person', '')
                supplier.email = row.get('email', '')
                supplier.phone = row.get('phone', '')
                supplier.address = row.get('address', '')

                supplier.save()
                self.successful_rows += 1

            except Exception as e:
                self.log_error(i, str(e), row)

        return self.finalize_import(len(rows))


class CategoryImporter(BaseImporter):
    """Importer for categories."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.required_fields = ['name']

    @transaction.atomic
    def run_import(self):
        """Import categories from CSV file."""
        self.start_import('category')
        rows = self.read_csv()

        for i, row in enumerate(rows, start=1):
            try:
                # Validate required fields
                self.validate_required_fields(row, i)

                # Check if category exists
                try:
                    category = Category.objects.get(name=row['name'])
                    if not self.update_existing:
                        self.log_error(i, f"Kategorie mit Namen {row['name']} existiert bereits.", row)
                        continue
                except Category.DoesNotExist:
                    category = Category(name=row['name'])

                # Update category fields
                category.description = row.get('description', '')

                category.save()
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

class SerialNumberImporter:
    def __init__(self, user, file):
        self.user = user
        self.file = file

    def run_import(self):
        decoded_file = io.TextIOWrapper(self.file, encoding='utf-8')
        reader = csv.DictReader(decoded_file)

        successful = 0
        failed = 0
        total = 0

        for row in reader:
            total += 1
            try:
                product = Product.objects.get(sku=row['product_sku'])
                warehouse = Warehouse.objects.get(name=row['warehouse_name']) if row.get('warehouse_name') else None

                SerialNumber.objects.create(
                    product=product,
                    serial_number=row['serial_number'],
                    status=row.get('status', 'in_stock'),
                    warehouse=warehouse,
                    purchase_date=self._parse_date(row.get('purchase_date')),
                    expiry_date=self._parse_date(row.get('expiry_date')),
                    notes=row.get('notes', ''),
                    created_by=self.user
                )
                successful += 1

            except Exception as e:
                failed += 1
                # Optional: Logging für Debugging

        return type('ImportLog', (), {
            'successful_rows': successful,
            'failed_rows': failed,
            'total_rows': total,
            'pk': 0  # Falls du irgendwann echte Logs speichern willst
        })()

    def _parse_date(self, date_str):
        if not date_str:
            return None
        try:
            return make_aware(datetime.strptime(date_str, '%Y-%m-%d'))
        except Exception:
            return None