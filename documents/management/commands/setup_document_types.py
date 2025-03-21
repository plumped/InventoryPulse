from django.core.management.base import BaseCommand
from documents.models import DocumentType


class Command(BaseCommand):
    help = 'Setup initial document types'

    def add_arguments(self, parser):
        parser.add_argument(
            '--reset',
            action='store_true',
            help='Reset all document types before creating new ones',
        )

    def handle(self, *args, **options):
        if options['reset']:
            self.stdout.write('Resetting document types...')
            DocumentType.objects.all().delete()

        # Create document types
        document_types = [
            {
                'name': 'Lieferschein',
                'code': 'delivery_note',
                'description': 'Lieferschein für empfangene Waren',
                'is_active': True,
            },
            {
                'name': 'Rechnung',
                'code': 'invoice',
                'description': 'Rechnung für Lieferungen',
                'is_active': True,
            },
            {
                'name': 'Angebot',
                'code': 'quote',
                'description': 'Angebot von Lieferanten',
                'is_active': True,
            },
            {
                'name': 'Auftragsbestätigung',
                'code': 'order_confirmation',
                'description': 'Bestätigung einer Bestellung',
                'is_active': True,
            },
            {
                'name': 'Zahlungsbestätigung',
                'code': 'payment_confirmation',
                'description': 'Bestätigung einer Zahlung',
                'is_active': True,
            },
            {
                'name': 'Lieferantenkatalog',
                'code': 'supplier_catalog',
                'description': 'Produktkatalog eines Lieferanten',
                'is_active': True,
            },
        ]

        created_count = 0
        skipped_count = 0

        # Add document types to the database
        for doc_type in document_types:
            _, created = DocumentType.objects.get_or_create(
                code=doc_type['code'],
                defaults=doc_type
            )
            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Created document type: {doc_type['name']}"))
            else:
                skipped_count += 1
                self.stdout.write(self.style.WARNING(f"Skipped existing document type: {doc_type['name']}"))

        self.stdout.write(self.style.SUCCESS(f"Setup complete. Created: {created_count}, Skipped: {skipped_count}"))