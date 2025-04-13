from django.db import transaction

from data_operations.importers.base import BaseImporter
from suppliers.models import Supplier


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