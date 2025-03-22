# documents/management/commands/setup_standard_fields.py

from django.core.management.base import BaseCommand
from documents.models import DocumentType, StandardField
from documents.field_suggestions import FIELD_SUGGESTIONS


class Command(BaseCommand):
    help = 'Setup initial standard fields for document types'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset all standard fields before creating new ones',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Resetting standard fields...')
            StandardField.objects.all().delete()

        # Get all document types
        document_types = DocumentType.objects.all()

        created_count = 0
        skipped_count = 0

        for doc_type in document_types:
            # Get suggestions from field_suggestions.py
            suggestions = FIELD_SUGGESTIONS.get(doc_type.code, [])

            for idx, field_data in enumerate(suggestions):
                # Create a unique code for each document type to avoid conflicts
                # Format: doc_type_code + "_" + field_code
                unique_code = f"{doc_type.code}_{field_data['code']}"

                try:
                    # Try to find an existing field for this document type and code
                    standard_field = StandardField.objects.filter(
                        document_type=doc_type,
                        code=unique_code
                    ).first()

                    if standard_field:
                        # Update existing field
                        standard_field.name = field_data['name']
                        standard_field.field_type = field_data['field_type']
                        standard_field.extraction_method = field_data.get('extraction_method', 'label_based')
                        standard_field.search_pattern = field_data.get('search_pattern', '')
                        standard_field.is_key_field = field_data.get('is_key_field', False)
                        standard_field.is_required = field_data.get('is_required', False)
                        standard_field.order = idx
                        standard_field.description = field_data.get('description', '')
                        standard_field.save()

                        skipped_count += 1
                        self.stdout.write(self.style.WARNING(
                            f"Updated existing standard field: {field_data['name']} for {doc_type.name}"
                        ))
                    else:
                        # Create new field
                        StandardField.objects.create(
                            name=field_data['name'],
                            code=unique_code,
                            field_type=field_data['field_type'],
                            document_type=doc_type,
                            extraction_method=field_data.get('extraction_method', 'label_based'),
                            search_pattern=field_data.get('search_pattern', ''),
                            is_key_field=field_data.get('is_key_field', False),
                            is_required=field_data.get('is_required', False),
                            order=idx,
                            description=field_data.get('description', '')
                        )

                        created_count += 1
                        self.stdout.write(self.style.SUCCESS(
                            f"Created standard field: {field_data['name']} for {doc_type.name}"
                        ))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(
                        f"Error creating field {field_data['name']} for {doc_type.name}: {str(e)}"
                    ))

        self.stdout.write(self.style.SUCCESS(
            f"Setup complete. Created: {created_count}, Updated: {skipped_count}"
        ))