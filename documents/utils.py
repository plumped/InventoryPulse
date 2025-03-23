import os
import re
import json
import logging
import tempfile
import pytesseract
from PIL import Image
from pdf2image import convert_from_path
from django.conf import settings
from django.utils import timezone
from django.core.files.storage import default_storage
from .models import DocumentProcessingLog, Document, DocumentTemplate, TemplateField

logger = logging.getLogger(__name__)

# Configure Tesseract path if needed
if hasattr(settings, 'TESSERACT_CMD'):
    pytesseract.pytesseract.tesseract_cmd = settings.TESSERACT_CMD


def log_processing_event(document, level, message, details=None):
    """
    Log document processing events to the database.

    Args:
        document: Document instance
        level: Log level ('info', 'warning', 'error', 'debug')
        message: Log message
        details: Optional dictionary with additional details
    """
    try:
        # Convert confidence score to percentage in message if present
        if "with score" in message:
            message = message.replace(
                "with score {:.2f}".format(document.confidence_score),
                "with score {:.0f}%".format(document.confidence_score * 100)
            )

        DocumentProcessingLog.objects.create(
            document=document,
            level=level,
            message=message,
            details=details
        )

        # Also log to the standard logger
        log_method = getattr(logger, level)
        log_method(f"Document {document.id} ({document.title}): {message}")
    except Exception as e:
        logger.error(f"Failed to log document processing event: {e}")


def convert_pdf_to_images(file_path):
    """
    Convert a PDF file to a list of PIL Image objects.

    Args:
        file_path: Path to the PDF file

    Returns:
        List of PIL Image objects, one per page
    """
    try:
        return convert_from_path(file_path, dpi=300)
    except Exception as e:
        logger.error(f"Failed to convert PDF to images: {e}")
        raise


def process_document_with_ocr(document):
    """
    Process a document with OCR and store the results.

    Args:
        document: Document instance to process

    Returns:
        bool: True if processing was successful, False otherwise
    """
    try:
        # Get file path
        file_path = document.file.path

        # Check if file exists
        if not os.path.exists(file_path):
            log_processing_event(
                document, 'error',
                f"File does not exist: {file_path}",
                {'file_path': file_path}
            )
            document.processing_status = 'error'
            document.save(update_fields=['processing_status'])
            return False

        # Convert PDF to images
        log_processing_event(document, 'info', "Converting PDF to images")
        images = convert_pdf_to_images(file_path)

        # Process each page with Tesseract
        log_processing_event(document, 'info', f"Processing {len(images)} pages with OCR")
        ocr_results = []
        ocr_text = ""

        for i, img in enumerate(images):
            try:
                # Get OCR data with word bounding boxes
                page_data = pytesseract.image_to_data(
                    img,
                    output_type=pytesseract.Output.DICT,
                    config='--psm 1'
                )

                # Validate page_data before processing
                if not isinstance(page_data, dict):
                    log_processing_event(
                        document, 'warning',
                        f"Unexpected page data type for page {i+1}: {type(page_data)}",
                        {'page_data': page_data}
                    )
                    continue

                # Safety checks for expected dictionary keys
                expected_keys = ['text', 'conf', 'left', 'top', 'width', 'height']
                if not all(key in page_data for key in expected_keys):
                    log_processing_event(
                        document, 'warning',
                        f"Missing keys in page data for page {i+1}",
                        {'page_data_keys': list(page_data.keys())}
                    )
                    continue

                # Extract full text for this page
                page_text = pytesseract.image_to_string(img)
                ocr_text += f"\n--- Page {i + 1} ---\n" + page_text

                # Calculate relative coordinates (0-1) instead of pixel coordinates
                width, height = img.size

                # Store the word bounding boxes with normalized coordinates
                words_with_coords = []
                for j in range(len(page_data['text'])):
                    if page_data['text'][j].strip():  # Only include non-empty text
                        words_with_coords.append({
                            'text': page_data['text'][j],
                            'conf': page_data['conf'][j],
                            'x': page_data['left'][j] / width,
                            'y': page_data['top'][j] / height,
                            'w': page_data['width'][j] / width,
                            'h': page_data['height'][j] / height,
                            'page': i + 1,
                            # Include original pixel coordinates for reference
                            'orig_x': page_data['left'][j],
                            'orig_y': page_data['top'][j],
                            'orig_w': page_data['width'][j],
                            'orig_h': page_data['height'][j],
                        })

                ocr_results.append({
                    'page': i + 1,
                    'width': width,
                    'height': height,
                    'words': words_with_coords
                })

            except Exception as page_err:
                log_processing_event(
                    document, 'error',
                    f"Error processing page {i+1}: {str(page_err)}",
                    {'page_number': i+1, 'exception': str(page_err)}
                )

        # Update document with OCR results
        document.ocr_text = ocr_text
        document.ocr_data = {'pages': ocr_results}
        document.processing_status = 'processed' if ocr_results else 'error'
        document.is_processed = bool(ocr_results)
        document.save(update_fields=['ocr_text', 'ocr_data', 'processing_status', 'is_processed'])

        if not ocr_results:
            log_processing_event(
                document, 'error',
                "No pages were successfully processed by OCR"
            )
            return False

        log_processing_event(
            document, 'info',
            f"OCR processing completed, {len(ocr_results)} pages processed",
            {'total_words': sum(len(page['words']) for page in ocr_results)}
        )

        # Try to identify document template
        identify_document_template(document)

        return True
    except Exception as e:
        log_processing_event(
            document, 'error',
            f"OCR processing failed: {str(e)}",
            {'exception': str(e), 'exception_type': type(e).__name__}
        )
        document.processing_status = 'error'
        document.save(update_fields=['processing_status'])
        return False


def identify_document_template(document):
    """
    Try to identify the document template based on OCR content.

    Args:
        document: Document instance with OCR data
    """
    try:
        if not document.supplier:
            log_processing_event(document, 'warning', "Cannot identify template: no supplier assigned")
            return

        if not document.ocr_text:
            log_processing_event(document, 'warning', "Cannot identify template: no OCR text available")
            return

        # Get all templates for this supplier
        templates = DocumentTemplate.objects.filter(
            supplier=document.supplier,
            document_type=document.document_type,
            is_active=True
        )

        if not templates.exists():
            log_processing_event(
                document, 'info',
                f"No templates found for supplier {document.supplier.name} and document type {document.document_type.name}"
            )
            return

        # Calculate match scores for each template
        template_scores = []
        for template in templates:
            score = calculate_template_match_score(document, template)
            template_scores.append((template, score))

        # Sort by score descending
        template_scores.sort(key=lambda x: x[1], reverse=True)

        best_template, best_score = template_scores[0]

        # If score is above threshold, consider it a match
        if best_score >= 0.5:  # 70% confidence threshold
            document.matched_template = best_template
            document.confidence_score = best_score

            # Extract field data based on template
            extracted_data = extract_fields_from_document(document, best_template)
            document.extracted_data = extracted_data

            log_processing_event(
                document, 'info',
                f"Matched template: {best_template.name} with score {best_score * 100:.0f}%",
                {'extracted_fields': list(extracted_data.keys())}
            )

            # Look for order number in extracted data and try to match it to an order
            if extracted_data.get('order_number'):
                from order.models import PurchaseOrder
                order_number = extracted_data.get('order_number')
                try:
                    order = PurchaseOrder.objects.get(
                        supplier=document.supplier,
                        order_number=order_number
                    )
                    document.matched_order = order
                    document.processing_status = 'matched'
                    log_processing_event(
                        document, 'info',
                        f"Matched to purchase order: {order.order_number}"
                    )
                except PurchaseOrder.DoesNotExist:
                    log_processing_event(
                        document, 'warning',
                        f"No matching purchase order found for number: {order_number}"
                    )
                except PurchaseOrder.MultipleObjectsReturned:
                    log_processing_event(
                        document, 'warning',
                        f"Multiple purchase orders found for number: {order_number}"
                    )

            document.save(update_fields=[
                'matched_template', 'confidence_score', 'extracted_data',
                'matched_order', 'processing_status'
            ])
        else:
            log_processing_event(
                document, 'info',
                f"No confident template match found. Best match: {best_template.name} with score {best_score:.2f}"
            )

    except Exception as e:
        log_processing_event(
            document, 'error',
            f"Failed to identify document template: {str(e)}",
            {'exception': str(e)}
        )


def calculate_template_match_score(document, template):
    """
    Calculate a match score between a document and a template.

    Args:
        document: Document instance with OCR data
        template: DocumentTemplate instance to match against

    Returns:
        float: Match score between 0 and 1
    """
    score = 0.0

    # Check for header pattern match
    if template.header_pattern and document.ocr_text:
        header_patterns = template.header_pattern.strip().split('\n')
        for pattern in header_patterns:
            if pattern.strip() and re.search(re.escape(pattern.strip()), document.ocr_text, re.IGNORECASE):
                score += 0.3  # Header match provides 30% confidence
                break

    # Check for footer pattern match
    if template.footer_pattern and document.ocr_text:
        footer_patterns = template.footer_pattern.strip().split('\n')
        for pattern in footer_patterns:
            if pattern.strip() and re.search(re.escape(pattern.strip()), document.ocr_text, re.IGNORECASE):
                score += 0.2  # Footer match provides 20% confidence
                break

    # Check for key fields
    key_fields = template.fields.filter(is_key_field=True)
    if key_fields.exists():
        field_score = 0.0
        max_field_score = key_fields.count() * 0.5  # Key fields provide 50% confidence total

        for field in key_fields:
            field_data = extract_field_from_document(document, field)
            if field_data:
                field_score += 0.5 / key_fields.count()

        score += field_score

    return min(score, 1.0)  # Cap score at 1.0


def extract_fields_from_document(document, template):
    """
    Extract all fields from a document based on a template.

    Args:
        document: Document instance with OCR data
        template: DocumentTemplate instance defining the fields

    Returns:
        dict: Dictionary mapping field codes to extracted values
    """
    result = {}
    fields = template.fields.all()

    for field in fields:
        value = extract_field_from_document(document, field)
        if value:
            # Use the extracted code without prefixes
            field_code = field.code
            result[field_code] = value

    return result


def extract_field_from_document(document, field):
    """
    Extract a single field from a document based on field definition.

    Args:
        document: Document instance with OCR data
        field: TemplateField instance defining the field

    Returns:
        str: Extracted field value or None if not found
    """
    if not document.ocr_data or 'pages' not in document.ocr_data:
        return None

    # Determine extraction method
    if field.extraction_method == 'exact':
        return extract_field_by_position(document, field)
    elif field.extraction_method == 'label_based':
        return extract_field_by_label(document, field)
    elif field.extraction_method == 'relative':
        return extract_field_by_relative_position(document, field)
    elif field.extraction_method == 'regex':
        return extract_field_by_regex(document, field)
    elif field.extraction_method == 'table_cell':
        return extract_field_from_table(document, field)
    else:
        return None


def extract_field_by_position(document, field):
    """
    Extract field value based on exact position coordinates.

    Args:
        document: Document instance with OCR data
        field: TemplateField instance with position information

    Returns:
        str: Extracted text from the field area
    """
    pages = document.ocr_data.get('pages', [])
    extracted_text = []

    for page in pages:
        page_number = page.get('page', 1)
        words = page.get('words', [])

        # Filter words that fall within the field's bounding box
        field_words = []
        for word in words:
            word_x = word.get('x', 0)
            word_y = word.get('y', 0)
            word_w = word.get('w', 0)
            word_h = word.get('h', 0)

            # Check if word center is within field bounding box
            word_center_x = word_x + word_w / 2
            word_center_y = word_y + word_h / 2

            if (field.x1 <= word_center_x <= field.x2 and
                    field.y1 <= word_center_y <= field.y2):
                field_words.append((word, word_center_y))  # Store word and y-position for sorting

        # Sort words by y-position and then by x-position for reading order
        field_words.sort(key=lambda w: (w[1], w[0].get('x', 0)))

        # Extract text from sorted words
        if field_words:
            text = ' '.join(word[0].get('text', '') for word in field_words)
            extracted_text.append(text)

    # Join text from all pages
    result = ' '.join(extracted_text).strip()

    # Apply formatting if needed
    if field.format_pattern and result:
        result = format_field_value(result, field)

    return result if result else None


# def extract_field_by_label(document, field):
#     """
#     Extract field value by finding text that follows a label pattern.
#     """
#     if not field.search_pattern:
#         return None
#
#     # Log für Debugging
#     logger.debug(f"Extracting field {field.code} with pattern '{field.search_pattern}'")
#
#     # Get label patterns
#     label_patterns = [pattern.strip() for pattern in field.search_pattern.split('|')]
#
#     # Get OCR text (einfacher Ansatz für Debugging)
#     ocr_text = document.ocr_text
#
#     # Für jedes Muster überprüfen
#     for pattern in label_patterns:
#         # Muster in Zeilen suchen
#         for line in ocr_text.split('\n'):
#             if pattern.lower() in line.lower():
#                 logger.debug(f"Found pattern '{pattern}' in line: '{line}'")
#
#                 # Extrahiere den Text nach dem Muster
#                 start_idx = line.lower().find(pattern.lower()) + len(pattern)
#                 value = line[start_idx:].strip()
#
#                 # Entferne Doppelpunkt und führende/nachfolgende Leerzeichen
#                 if value.startswith(':'):
#                     value = value[1:].strip()
#
#                 # Bereinige den Wert (entferne "Ihre Bestellnummer:" etc.)
#                 if ":" in value:
#                     # Versuche, nur den Teil nach dem letzten Doppelpunkt zu nehmen
#                     parts = value.split(':', 1)
#                     if len(parts) > 1:
#                         value = parts[1].strip()
#
#                 if value:
#                     logger.debug(f"Extracted value for {field.code}: '{value}'")
#                     return value
#
#                 # Wenn auf dieser Zeile kein Wert gefunden wurde, nächste Zeile prüfen
#                 lines = ocr_text.split('\n')
#                 for i, current_line in enumerate(lines):
#                     if pattern.lower() in current_line.lower():
#                         if i + 1 < len(lines):
#                             next_line = lines[i + 1].strip()
#                             if next_line and ":" not in next_line:
#                                 logger.debug(f"Extracted value from next line for {field.code}: '{next_line}'")
#                                 return next_line
#
#     logger.debug(f"No value found for field {field.code}")
#     return None

def extract_field_by_label(document, field):
    """
    Extract field value by finding text that follows a label pattern.

    Args:
        document: Document instance with OCR data
        field: TemplateField instance with search pattern

    Returns:
        str: Extracted text that follows the label
    """
    if not field.search_pattern:
        return None

    # Behandle das Suchmuster als einen einzelnen regulären Ausdruck
    pattern = field.search_pattern.strip()

    try:
        # Kompiliere den regulären Ausdruck mit IGNORECASE-Flag
        regex = re.compile(pattern, re.IGNORECASE)

        # Suche in jeder Zeile des OCR-Textes
        lines = document.ocr_text.split('\n')
        for i, line in enumerate(lines):
            match = regex.search(line)
            if match:
                # Extrahiere Text nach dem gefundenen Muster
                value = line[match.end():].strip()

                # Entferne Doppelpunkt am Anfang
                if value.startswith(':'):
                    value = value[1:].strip()

                # Wenn Wert gefunden, gib ihn zurück
                if value:
                    return value

                # Wenn kein Wert auf dieser Zeile, prüfe die nächste Zeile
                if i + 1 < len(lines):
                    next_line = lines[i + 1].strip()
                    if next_line and not regex.search(next_line):
                        return next_line

    except re.error as e:
        # Bei einem Regex-Fehler loggen und auf fallback-Methode zurückgreifen
        logger.warning(f"Invalid regex pattern for field {field.name}: {pattern} - {str(e)}")

        # Fallback: Behandle als Liste von Teilstrings
        patterns = [p.strip() for p in pattern.split('|')]
        for i, line in enumerate(lines):
            for p in patterns:
                if p.lower() in line.lower():
                    start_idx = line.lower().find(p.lower()) + len(p)
                    value = line[start_idx:].strip()
                    if value.startswith(':'):
                        value = value[1:].strip()
                    if value:
                        return value

                    # Prüfe nächste Zeile
                    if i + 1 < len(lines):
                        return lines[i + 1].strip()

    return None


def extract_field_by_relative_position(document, field):
    """
    Extract field value based on position relative to another field.

    Args:
        document: Document instance with OCR data
        field: TemplateField instance with reference field and offset

    Returns:
        str: Extracted text from the relative position
    """
    if not field.reference_field:
        return None

    # Get reference field value and position
    ref_value = extract_field_from_document(document, field.reference_field)
    if not ref_value:
        return None

    # Calculate target position based on reference field position and offset
    target_x1 = field.reference_field.x1 + field.x_offset
    target_y1 = field.reference_field.y1 + field.y_offset
    target_x2 = target_x1 + (field.x2 - field.x1)
    target_y2 = target_y1 + (field.y2 - field.y1)

    # Create a temporary field with the calculated position
    from .models import TemplateField
    temp_field = TemplateField(
        x1=target_x1,
        y1=target_y1,
        x2=target_x2,
        y2=target_y2,
        extraction_method='exact',
        format_pattern=field.format_pattern
    )

    # Extract using the temporary field
    return extract_field_by_position(document, temp_field)


def extract_field_by_regex(document, field):
    """
    Extract field value using a regular expression pattern.

    Args:
        document: Document instance with OCR data
        field: TemplateField instance with regex pattern

    Returns:
        str: Extracted text that matches the regex pattern
    """
    if not field.search_pattern:
        return None

    try:
        pattern = re.compile(field.search_pattern, re.IGNORECASE)
        match = pattern.search(document.ocr_text)

        if match:
            value = match.group(1) if match.groups() else match.group(0)

            # Apply formatting if needed
            if field.format_pattern and value:
                value = format_field_value(value, field)

            return value
    except re.error:
        # Log error if regex is invalid
        log_processing_event(
            document, 'error',
            f"Invalid regex pattern for field {field.name}: {field.search_pattern}"
        )

    return None


def extract_field_from_table(document, field):
    """
    Extract field value from a table cell.

    Args:
        document: Document instance with OCR data
        field: TemplateField instance with table information

    Returns:
        str: Extracted text from the table cell
    """
    if field.table_parent is None or field.table_column_index is None or field.table_row_index is None:
        return None

    # Extract the table area using the parent field
    table_text = extract_field_by_position(document, field.table_parent)
    if not table_text:
        return None

    # Split table into rows and cells (simple approach)
    rows = table_text.strip().split('\n')
    if field.table_row_index >= len(rows):
        return None

    row = rows[field.table_row_index]
    cells = row.split()

    if field.table_column_index >= len(cells):
        return None

    value = cells[field.table_column_index]

    # Apply formatting if needed
    if field.format_pattern and value:
        value = format_field_value(value, field)

    return value


def format_field_value(value, field):
    """
    Format a field value based on field type and format pattern.

    Args:
        value: The extracted text value
        field: TemplateField instance with format information

    Returns:
        str: Formatted value
    """
    try:
        # Format based on field type
        if field.field_type == 'date' and field.format_pattern:
            # Try various date formats
            from datetime import datetime
            date_formats = [
                field.format_pattern,
                '%d.%m.%Y',
                '%Y-%m-%d',
                '%d/%m/%Y',
                '%m/%d/%Y',
            ]

            for fmt in date_formats:
                try:
                    date_obj = datetime.strptime(value, fmt)
                    # Return in standard format or specified format
                    return date_obj.strftime(field.format_pattern or '%Y-%m-%d')
                except ValueError:
                    continue

        elif field.field_type == 'number':
            # Clean and format number
            clean_value = re.sub(r'[^\d.,]', '', value)
            # Replace comma with dot for decimal
            clean_value = clean_value.replace(',', '.')
            try:
                num_value = float(clean_value)
                if field.format_pattern:
                    return field.format_pattern.format(num_value)
                return str(num_value)
            except ValueError:
                return clean_value

        elif field.field_type == 'currency':
            # Extract just the number part
            match = re.search(r'[\d.,]+', value)
            if match:
                number_str = match.group(0).replace(',', '.')
                try:
                    amount = float(number_str)
                    if field.format_pattern:
                        return field.format_pattern.format(amount)
                    return f"{amount:.2f}"
                except ValueError:
                    return value

        # For all other types, just return the value
        return value

    except Exception as e:
        # Log the error but return the original value
        logger.error(f"Error formatting field value '{value}': {e}")
        return value