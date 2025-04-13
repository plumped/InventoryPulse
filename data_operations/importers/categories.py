from django.db import transaction

from data_operations.importers.base import BaseImporter
from product_management.models.categories_models import Category


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