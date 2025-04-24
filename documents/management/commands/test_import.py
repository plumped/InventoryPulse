from django.core.management.base import BaseCommand

class Command(BaseCommand):
    help = 'Test importing DocumentType from documents.models.document_type'

    def handle(self, *args, **options):
        try:
            from documents.models.document_type import DocumentType
            self.stdout.write(self.style.SUCCESS('Import successful! The issue is fixed.'))
        except ImportError as e:
            self.stdout.write(self.style.ERROR(f'Import failed: {e}'))