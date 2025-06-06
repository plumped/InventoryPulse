import csv
import io
import logging

from core.models import ImportLog

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