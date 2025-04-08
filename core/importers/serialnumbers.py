import csv
import io
from datetime import datetime

from django.utils.timezone import make_aware

from core.models import Product, SerialNumber
from inventory.models import Warehouse


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