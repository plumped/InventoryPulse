import logging
from .models import Document
from .utils import process_document_with_ocr

logger = logging.getLogger(__name__)


# In a real application, this would be a Celery task
# @celery.task(bind=True, max_retries=3)
def process_document_ocr(document_id):
    """
    Process a document with OCR.

    Args:
        document_id: ID of the document to process
    """
    try:
        document = Document.objects.get(id=document_id)

        # Process document with OCR
        success = process_document_with_ocr(document)

        return success
    except Document.DoesNotExist:
        logger.error(f"Document with ID {document_id} not found")
        return False
    except Exception as e:
        logger.error(f"Error processing document {document_id}: {str(e)}")
        # In a real Celery task, we'd retry here
        # self.retry(exc=e, countdown=60*5)  # Retry after 5 minutes
        return False