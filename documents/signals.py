from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db import transaction
from .models import Document
from .tasks import process_document_ocr


@receiver(post_save, sender=Document)
def trigger_document_processing(sender, instance, created, **kwargs):
    """Trigger document OCR processing when a new document is created."""
    if created:
        # Update status to processing
        instance.processing_status = 'processing'
        instance.save(update_fields=['processing_status'])

        # Process document synchronously for now (no Celery)
        # In a real project with Celery, you would use:
        # transaction.on_commit(lambda: process_document_ocr.delay(instance.id))
        transaction.on_commit(lambda: process_document_ocr(instance.id))