import os
import json
import base64
from io import BytesIO
from PIL import Image
from pdf2image import convert_from_path

from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse, HttpResponse
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.views.decorators.csrf import csrf_exempt
from django.core.exceptions import PermissionDenied
from django.db.models import Q

from .models import Document, DocumentTemplate, TemplateField, DocumentType, DocumentMatch
from .forms import DocumentUploadForm, DocumentTemplateForm, TemplateFieldForm, DocumentMatchForm
from .utils import process_document_with_ocr, extract_field_from_document, log_processing_event, \
    extract_fields_from_document
from .tasks import process_document_ocr


@login_required
def document_list(request):
    """View for listing uploaded documents with filtering options."""
    # Get filter parameters
    document_type_id = request.GET.get('document_type')
    supplier_id = request.GET.get('supplier')
    status = request.GET.get('status')
    search_query = request.GET.get('search')

    # Base queryset
    queryset = Document.objects.all()

    # Apply filters
    if document_type_id:
        queryset = queryset.filter(document_type_id=document_type_id)
    if supplier_id:
        queryset = queryset.filter(supplier_id=supplier_id)
    if status:
        queryset = queryset.filter(processing_status=status)
    if search_query:
        queryset = queryset.filter(
            Q(title__icontains=search_query) |
            Q(document_number__icontains=search_query) |
            Q(ocr_text__icontains=search_query)
        )

    # Order by upload date descending
    queryset = queryset.order_by('-upload_date')

    # Pagination
    paginator = Paginator(queryset, 25)  # Show 25 documents per page
    page_number = request.GET.get('page')
    documents = paginator.get_page(page_number)

    # Get document types and suppliers for filtering
    from core.models import Category
    from suppliers.models import Supplier
    document_types = DocumentType.objects.filter(is_active=True)
    suppliers = Supplier.objects.filter(is_active=True)

    context = {
        'documents': documents,
        'document_types': document_types,
        'suppliers': suppliers,
        'selected_document_type': document_type_id,
        'selected_supplier': supplier_id,
        'selected_status': status,
        'search_query': search_query,
        'status_choices': Document.PROCESSING_STATUS,
    }

    return render(request, 'documents/document_list.html', context)


@login_required
def document_upload(request):
    """View for uploading new documents."""
    if request.method == 'POST':
        form = DocumentUploadForm(request.POST, request.FILES)
        if form.is_valid():
            document = form.save(commit=False)
            document.uploaded_by = request.user
            document.save()

            messages.success(request, _('Document uploaded successfully.'))
            return redirect('document_detail', pk=document.pk)
    else:
        form = DocumentUploadForm()

    context = {
        'form': form,
        'title': _('Upload Document'),
    }

    return render(request, 'documents/document_upload.html', context)


@login_required
def document_detail(request, pk):
    """View for viewing document details and OCR results."""
    document = get_object_or_404(Document, pk=pk)

    # Get processing logs
    processing_logs = document.processing_logs.all().order_by('-timestamp')

    # Get possible matching templates
    if document.supplier and document.document_type:
        matching_templates = DocumentTemplate.objects.filter(
            supplier=document.supplier,
            document_type=document.document_type,
            is_active=True
        )
    else:
        matching_templates = DocumentTemplate.objects.none()

    # If document is processed and has a supplier, create a match form
    match_form = None
    if document.is_processed and document.supplier:
        match_form = DocumentMatchForm(supplier_id=document.supplier.id)

    context = {
        'document': document,
        'processing_logs': processing_logs,
        'matching_templates': matching_templates,
        'match_form': match_form,
    }

    return render(request, 'documents/document_detail.html', context)


@login_required
def document_delete(request, pk):
    """View for deleting a document."""
    document = get_object_or_404(Document, pk=pk)

    if request.method == 'POST':
        document.delete()
        messages.success(request, _('Document deleted successfully.'))
        return redirect('document_list')

    context = {
        'document': document,
    }

    return render(request, 'documents/document_delete.html', context)


@login_required
def document_process(request, pk):
    """View for manually triggering document processing."""
    document = get_object_or_404(Document, pk=pk)

    # Process the document with OCR
    document.processing_status = 'processing'
    document.save(update_fields=['processing_status'])

    # In a real application, this would be a Celery task
    # process_document_ocr.delay(document.id)
    # For demonstration, we'll process it synchronously
    success = process_document_with_ocr(document)

    if success:
        messages.success(request, _('Document processed successfully.'))
    else:
        messages.error(request, _('Failed to process document.'))

    return redirect('document_detail', pk=document.pk)


@login_required
def document_match(request, pk):
    """View for manually matching a document to a purchase order."""
    document = get_object_or_404(Document, pk=pk)

    if request.method == 'POST':
        form = DocumentMatchForm(request.POST, supplier_id=document.supplier_id if document.supplier else None)
        if form.is_valid():
            purchase_order = form.cleaned_data['purchase_order']
            notes = form.cleaned_data['notes']

            # Create a document match
            document_match = DocumentMatch.objects.create(
                document=document,
                template=document.matched_template,
                purchase_order=purchase_order,
                status='matched',
                confidence_score=1.0,  # Manual match = 100% confidence
                matched_by=request.user,
                notes=notes,
                matched_data=document.extracted_data
            )

            # Update the document
            document.matched_order = purchase_order
            document.processing_status = 'matched'
            document.save(update_fields=['matched_order', 'processing_status'])

            # Log the match
            log_processing_event(
                document, 'info',
                f"Document manually matched to purchase order {purchase_order.order_number} by {request.user.username}"
            )

            messages.success(request, _('Document matched successfully.'))
            return redirect('document_detail', pk=document.pk)
    else:
        form = DocumentMatchForm(supplier_id=document.supplier_id if document.supplier else None)

    context = {
        'document': document,
        'form': form,
    }

    return render(request, 'documents/document_match.html', context)


@login_required
def template_list(request):
    """View for listing document templates."""
    # Get filter parameters
    document_type_id = request.GET.get('document_type')
    supplier_id = request.GET.get('supplier')
    search_query = request.GET.get('search')

    # Base queryset
    queryset = DocumentTemplate.objects.all()

    # Apply filters
    if document_type_id:
        queryset = queryset.filter(document_type_id=document_type_id)
    if supplier_id:
        queryset = queryset.filter(supplier_id=supplier_id)
    if search_query:
        queryset = queryset.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query)
        )

    # Order by supplier and name
    queryset = queryset.order_by('supplier__name', 'name')

    # Pagination
    paginator = Paginator(queryset, 25)  # Show 25 templates per page
    page_number = request.GET.get('page')
    templates = paginator.get_page(page_number)

    # Get document types and suppliers for filtering
    from suppliers.models import Supplier
    document_types = DocumentType.objects.filter(is_active=True)
    suppliers = Supplier.objects.filter(is_active=True)

    context = {
        'templates': templates,
        'document_types': document_types,
        'suppliers': suppliers,
        'selected_document_type': document_type_id,
        'selected_supplier': supplier_id,
        'search_query': search_query,
    }

    return render(request, 'documents/template_list.html', context)


@login_required
def template_create(request):
    """View for creating a new document template."""
    if request.method == 'POST':
        form = DocumentTemplateForm(request.POST)
        if form.is_valid():
            template = form.save(commit=False)
            template.created_by = request.user

            # Make sure reference document is set
            reference_doc_id = request.POST.get('reference_document')
            if reference_doc_id:
                try:
                    template.reference_document = Document.objects.get(pk=reference_doc_id)
                except Document.DoesNotExist:
                    pass

            template.save()

            messages.success(request, _('Template created successfully.'))

            # If reference document is provided, redirect to field mapping editor
            if request.POST.get('reference_document'):
                return redirect('field_mapping_editor', template_id=template.pk)

            return redirect('template_detail', pk=template.pk)
    else:
        # Pre-select reference document if provided
        reference_doc_id = request.GET.get('reference_document')
        initial = {}

        if reference_doc_id:
            try:
                reference_doc = Document.objects.get(pk=reference_doc_id)
                initial = {
                    'supplier': reference_doc.supplier,
                    'document_type': reference_doc.document_type,
                    'reference_document': reference_doc,
                }
            except Document.DoesNotExist:
                pass

        form = DocumentTemplateForm(initial=initial)

    context = {
        'form': form,
        'title': _('Create Document Template'),
    }

    return render(request, 'documents/template_create.html', context)


@login_required
def template_detail(request, pk):
    """View for viewing template details and fields."""
    template = get_object_or_404(DocumentTemplate, pk=pk)

    # Get template fields
    fields = template.fields.all().order_by('name')

    # Get matched documents
    matched_documents = Document.objects.filter(matched_template=template).order_by('-upload_date')

    context = {
        'template': template,
        'fields': fields,
        'matched_documents': matched_documents,
    }

    return render(request, 'documents/template_detail.html', context)


@login_required
def template_edit(request, pk):
    """View for editing a document template."""
    template = get_object_or_404(DocumentTemplate, pk=pk)

    if request.method == 'POST':
        form = DocumentTemplateForm(request.POST, instance=template)
        if form.is_valid():
            form.save()
            messages.success(request, _('Template updated successfully.'))
            return redirect('template_detail', pk=template.pk)
    else:
        form = DocumentTemplateForm(instance=template)

    context = {
        'form': form,
        'template': template,
        'title': _('Edit Document Template'),
    }

    return render(request, 'documents/template_edit.html', context)


@login_required
def template_delete(request, pk):
    """View for deleting a document template."""
    template = get_object_or_404(DocumentTemplate, pk=pk)

    if request.method == 'POST':
        template.delete()
        messages.success(request, _('Template deleted successfully.'))
        return redirect('template_list')

    context = {
        'template': template,
    }

    return render(request, 'documents/template_delete.html', context)


@login_required
def field_create(request, template_id):
    """View for creating a new template field."""
    template = get_object_or_404(DocumentTemplate, pk=template_id)

    if request.method == 'POST':
        form = TemplateFieldForm(request.POST, template_id=template_id)
        if form.is_valid():
            field = form.save(commit=False)
            field.template = template
            field.save()

            messages.success(request, _('Field created successfully.'))
            return redirect('template_detail', pk=template_id)
    else:
        form = TemplateFieldForm(template_id=template_id)

    context = {
        'form': form,
        'template': template,
        'title': _('Create Template Field'),
    }

    return render(request, 'documents/field_create.html', context)


@login_required
def field_edit(request, template_id, pk):
    """View for editing a template field."""
    template = get_object_or_404(DocumentTemplate, pk=template_id)
    field = get_object_or_404(TemplateField, pk=pk, template=template)

    if request.method == 'POST':
        form = TemplateFieldForm(request.POST, instance=field, template_id=template_id)
        if form.is_valid():
            form.save()
            messages.success(request, _('Field updated successfully.'))
            return redirect('template_detail', pk=template_id)
    else:
        form = TemplateFieldForm(instance=field, template_id=template_id)

    context = {
        'form': form,
        'template': template,
        'field': field,
        'title': _('Edit Template Field'),
    }

    return render(request, 'documents/field_edit.html', context)


@login_required
def field_delete(request, template_id, pk):
    """View for deleting a template field."""
    template = get_object_or_404(DocumentTemplate, pk=template_id)
    field = get_object_or_404(TemplateField, pk=pk, template=template)

    if request.method == 'POST':
        field.delete()
        messages.success(request, _('Field deleted successfully.'))
        return redirect('template_detail', pk=template_id)

    context = {
        'template': template,
        'field': field,
    }

    return render(request, 'documents/field_delete.html', context)


@login_required
def field_mapping_editor(request, template_id):
    """View for visually mapping fields on a document."""
    template = get_object_or_404(DocumentTemplate, pk=template_id)

    # Get reference document
    reference_document = template.reference_document

    if not reference_document:
        messages.error(request, _('No reference document found for this template.'))
        return redirect('template_detail', pk=template_id)

    # Get existing fields
    fields = template.fields.all().order_by('name')

    context = {
        'template': template,
        'reference_document': reference_document,
        'fields': fields,
    }

    return render(request, 'documents/field_mapping_editor.html', context)


@login_required
def get_document_image(request, pk):
    """AJAX view for getting a document page image."""
    document = get_object_or_404(Document, pk=pk)
    page = request.GET.get('page', 1)
    try:
        page = int(page)
    except ValueError:
        page = 1

    try:
        # Convert PDF to image
        images = convert_from_path(document.file.path, dpi=200)

        if page <= 0 or page > len(images):
            page = 1

        # Get the requested page
        img = images[page - 1]

        # Convert image to base64
        buffer = BytesIO()
        img.save(buffer, format='JPEG')
        image_base64 = base64.b64encode(buffer.getvalue()).decode('utf-8')

        # Return as JSON
        return JsonResponse({
            'image': f'data:image/jpeg;base64,{image_base64}',
            'page': page,
            'total_pages': len(images),
            'width': img.width,
            'height': img.height,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_document_ocr_data(request, pk):
    """AJAX view for getting document OCR data."""
    document = get_object_or_404(Document, pk=pk)
    page = request.GET.get('page', 1)
    try:
        page = int(page)
    except ValueError:
        page = 1

    if not document.ocr_data or 'pages' not in document.ocr_data:
        return JsonResponse({'error': 'No OCR data available'}, status=404)

    pages = document.ocr_data.get('pages', [])

    if page <= 0 or page > len(pages):
        page = 1

    # Get data for the requested page
    page_data = next((p for p in pages if p.get('page') == page), None)

    if not page_data:
        return JsonResponse({'error': 'Page not found in OCR data'}, status=404)

    return JsonResponse({
        'page': page,
        'width': page_data.get('width', 0),
        'height': page_data.get('height', 0),
        'words': page_data.get('words', []),
    })


@csrf_exempt
@login_required
def save_field_coordinates(request):
    """AJAX view for saving field coordinates."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)

    try:
        data = json.loads(request.body)
        template_id = data.get('template_id')
        field_id = data.get('field_id')
        coordinates = data.get('coordinates', {})

        if not template_id or not coordinates:
            return JsonResponse({'error': 'Missing required data'}, status=400)

        template = get_object_or_404(DocumentTemplate, pk=template_id)

        if field_id:
            # Update existing field
            field = get_object_or_404(TemplateField, pk=field_id, template=template)
        else:
            # Create new field
            field_name = data.get('field_name', 'New Field')
            field_code = data.get('field_code', f'field_{template.fields.count() + 1}')
            field_type = data.get('field_type', 'text')

            field = TemplateField(
                template=template,
                name=field_name,
                code=field_code,
                field_type=field_type,
                extraction_method='exact'
            )

        # Update coordinates
        field.x1 = float(coordinates.get('x1', 0))
        field.y1 = float(coordinates.get('y1', 0))
        field.x2 = float(coordinates.get('x2', 0))
        field.y2 = float(coordinates.get('y2', 0))

        field.save()

        return JsonResponse({
            'success': True,
            'field_id': field.id,
            'field_name': field.name,
            'field_code': field.code,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
def extract_field_value(request):
    """AJAX view for extracting field value from a document."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)

    try:
        data = json.loads(request.body)
        document_id = data.get('document_id')
        field_id = data.get('field_id')

        document = get_object_or_404(Document, pk=document_id)
        field = get_object_or_404(TemplateField, pk=field_id)

        value = extract_field_from_document(document, field)

        return JsonResponse({
            'success': True,
            'value': value,
            'field_id': field.id,
            'field_name': field.name,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@csrf_exempt
@login_required
def match_document_to_order(request, pk):
    """AJAX view for matching a document to a purchase order."""
    if request.method != 'POST':
        return JsonResponse({'error': 'Only POST requests are allowed'}, status=405)

    try:
        document = get_object_or_404(Document, pk=pk)
        data = json.loads(request.body)
        purchase_order_id = data.get('purchase_order_id')

        if not purchase_order_id:
            return JsonResponse({'error': 'Missing purchase order ID'}, status=400)

        from order.models import PurchaseOrder
        purchase_order = get_object_or_404(PurchaseOrder, pk=purchase_order_id)

        # Create document match
        match = DocumentMatch.objects.create(
            document=document,
            template=document.matched_template,
            purchase_order=purchase_order,
            status='matched',
            confidence_score=1.0,  # Manual match = 100% confidence
            matched_by=request.user,
            notes=data.get('notes', ''),
            matched_data=document.extracted_data
        )

        # Update document
        document.matched_order = purchase_order
        document.processing_status = 'matched'
        document.save(update_fields=['matched_order', 'processing_status'])

        # Log the match
        log_processing_event(
            document, 'info',
            f"Document matched to purchase order {purchase_order.order_number} by {request.user.username}"
        )

        return JsonResponse({
            'success': True,
            'match_id': match.id,
            'purchase_order': purchase_order.order_number,
        })
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)


@login_required
def get_field_suggestions(request):
    """AJAX view for getting field suggestions for a document type."""
    document_type_code = request.GET.get('document_type_code')

    if not document_type_code:
        return JsonResponse({'error': 'Document type code is required'}, status=400)

    from .field_suggestions import get_field_suggestions

    suggestions = get_field_suggestions(document_type_code)

    return JsonResponse({
        'success': True,
        'document_type_code': document_type_code,
        'suggestions': suggestions
    })


@login_required
def match_document_to_template(request, pk, template_id):
    """View für manuelles Zuordnen eines Dokuments zu einem Template."""
    document = get_object_or_404(Document, pk=pk)
    template = get_object_or_404(DocumentTemplate, pk=template_id)

    if request.method == 'POST':
        # Dokument mit Template verknüpfen
        document.matched_template = template

        # Daten aus dem Template extrahieren
        extracted_data = extract_fields_from_document(document, template)
        document.extracted_data = extracted_data

        # Konfidenz auf 100% setzen (manuelle Zuordnung)
        document.confidence_score = 1.0

        # Status aktualisieren
        document.processing_status = 'processed'
        document.save(update_fields=['matched_template', 'extracted_data', 'confidence_score', 'processing_status'])

        # Ereignis protokollieren
        log_processing_event(
            document, 'info',
            f"Dokument manuell mit Template '{template.name}' verknüpft durch {request.user.username}"
        )

        messages.success(request, _('Dokument erfolgreich mit Template verknüpft.'))

    return redirect('document_detail', pk=document.pk)