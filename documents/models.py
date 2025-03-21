from django.db import models
from django.contrib.auth.models import User
from django.utils.translation import gettext_lazy as _
from suppliers.models import Supplier
from order.models import PurchaseOrder


class DocumentType(models.Model):
    """Defines types of documents like delivery notes, invoices, etc."""
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = _("Document Type")
        verbose_name_plural = _("Document Types")
        ordering = ['name']


class Document(models.Model):
    """Stores uploaded documents and their OCR content."""
    PROCESSING_STATUS = [
        ('pending', _('Awaiting Processing')),
        ('processing', _('Processing')),
        ('processed', _('Processed')),
        ('error', _('Error')),
        ('matched', _('Matched to Order')),
    ]

    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/%Y/%m/%d/')
    document_type = models.ForeignKey(DocumentType, on_delete=models.SET_NULL, null=True, related_name='documents')
    supplier = models.ForeignKey(Supplier, on_delete=models.SET_NULL, null=True, blank=True, related_name='documents')
    upload_date = models.DateTimeField(auto_now_add=True)
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='uploaded_documents')

    # OCR and processing fields
    processing_status = models.CharField(max_length=20, choices=PROCESSING_STATUS, default='pending')
    ocr_text = models.TextField(blank=True)
    ocr_data = models.JSONField(null=True, blank=True, help_text=_("Complete OCR data including word coordinates"))

    # Document identification and matching
    document_number = models.CharField(max_length=100, blank=True, help_text=_("Extracted document number"))
    document_date = models.DateField(null=True, blank=True)
    matched_template = models.ForeignKey('DocumentTemplate', on_delete=models.SET_NULL, null=True, blank=True,
                                         related_name='matched_documents')
    matched_order = models.ForeignKey(PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True,
                                      related_name='delivery_documents')
    extracted_data = models.JSONField(null=True, blank=True, help_text=_("Extracted field data based on template"))
    confidence_score = models.FloatField(default=0.0, help_text=_("Confidence score of the document matching"))

    # Additional fields for document analysis
    notes = models.TextField(blank=True)
    is_processed = models.BooleanField(default=False)

    def __str__(self):
        return self.title

    class Meta:
        verbose_name = _("Document")
        verbose_name_plural = _("Documents")
        ordering = ['-upload_date']

    def get_field_value(self, field_code):
        """Return the extracted value for a given field code"""
        if not self.extracted_data:
            return None
        return self.extracted_data.get(field_code)


class DocumentTemplate(models.Model):
    """Template for document recognition and field mapping."""
    name = models.CharField(max_length=100)
    document_type = models.ForeignKey(DocumentType, on_delete=models.CASCADE, related_name='templates')
    supplier = models.ForeignKey(Supplier, on_delete=models.CASCADE, related_name='document_templates')
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    # Template identification
    header_pattern = models.TextField(blank=True, help_text=_("Text pattern to identify document header"))
    footer_pattern = models.TextField(blank=True, help_text=_("Text pattern to identify document footer"))

    # Reference document used to create the template
    reference_document = models.ForeignKey(Document, on_delete=models.SET_NULL, null=True, blank=True,
                                           related_name='derived_templates')

    # Metadata
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_templates')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.supplier.name} - {self.name}"

    class Meta:
        verbose_name = _("Document Template")
        verbose_name_plural = _("Document Templates")
        unique_together = ('name', 'supplier', 'document_type')
        ordering = ['supplier__name', 'name']


class TemplateField(models.Model):
    """Field definition in a document template with its position and extraction rules."""
    FIELD_TYPES = [
        ('text', _('Text')),
        ('number', _('Number')),
        ('date', _('Date')),
        ('currency', _('Currency')),
        ('boolean', _('Boolean')),
        ('list', _('List of Items')),
        ('table', _('Table')),
    ]

    EXTRACTION_METHODS = [
        ('exact', _('Exact Position')),
        ('label_based', _('Based on Label')),
        ('relative', _('Relative to Another Field')),
        ('regex', _('Regular Expression')),
        ('table_cell', _('Table Cell')),
    ]

    template = models.ForeignKey(DocumentTemplate, on_delete=models.CASCADE, related_name='fields')
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, help_text=_("Unique code for this field in the template"))
    field_type = models.CharField(max_length=20, choices=FIELD_TYPES, default='text')
    description = models.TextField(blank=True)

    # Visual mapping on document
    x1 = models.FloatField(help_text=_("Left coordinate"))
    y1 = models.FloatField(help_text=_("Top coordinate"))
    x2 = models.FloatField(help_text=_("Right coordinate"))
    y2 = models.FloatField(help_text=_("Bottom coordinate"))

    # Extraction configuration
    extraction_method = models.CharField(max_length=20, choices=EXTRACTION_METHODS, default='exact')
    search_pattern = models.CharField(max_length=255, blank=True,
                                      help_text=_("Label or regex pattern to find the field"))
    reference_field = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                        related_name='dependent_fields')
    x_offset = models.IntegerField(default=0, help_text=_("X offset from reference field"))
    y_offset = models.IntegerField(default=0, help_text=_("Y offset from reference field"))

    # Value formatting
    format_pattern = models.CharField(max_length=255, blank=True, help_text=_("Format pattern for the extracted value"))

    # For table fields
    is_table_header = models.BooleanField(default=False)
    table_column_index = models.IntegerField(null=True, blank=True)
    table_row_index = models.IntegerField(null=True, blank=True)
    table_parent = models.ForeignKey('self', on_delete=models.SET_NULL, null=True, blank=True,
                                     related_name='table_fields')

    # Field priority and validation
    is_required = models.BooleanField(default=False, help_text=_("Is this field required for document validation"))
    is_key_field = models.BooleanField(default=False, help_text=_("Is this a key field for document matching"))
    validation_regex = models.CharField(max_length=255, blank=True, help_text=_("Regex pattern for field validation"))

    def __str__(self):
        return f"{self.template} - {self.name}"

    class Meta:
        verbose_name = _("Template Field")
        verbose_name_plural = _("Template Fields")
        unique_together = ('template', 'code')
        ordering = ['template', 'name']


class DocumentMatch(models.Model):
    """Record of document matching attempts and results."""
    STATUS_CHOICES = [
        ('pending', _('Pending')),
        ('matched', _('Matched')),
        ('manual_review', _('Requires Manual Review')),
        ('rejected', _('Rejected')),
    ]

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='match_attempts')
    template = models.ForeignKey(DocumentTemplate, on_delete=models.CASCADE, related_name='document_matches')
    purchase_order = models.ForeignKey(PurchaseOrder, on_delete=models.SET_NULL, null=True, blank=True,
                                       related_name='document_matches')

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending')
    confidence_score = models.FloatField(default=0.0)
    matched_data = models.JSONField(null=True, blank=True)

    match_date = models.DateTimeField(auto_now_add=True)
    matched_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True,
                                   related_name='document_matches')
    notes = models.TextField(blank=True)

    def __str__(self):
        return f"Match: {self.document.title} - {self.template.name} ({self.confidence_score:.2f})"

    class Meta:
        verbose_name = _("Document Match")
        verbose_name_plural = _("Document Matches")
        ordering = ['-match_date']


class DocumentProcessingLog(models.Model):
    """Log for document processing and OCR operations."""
    LOG_LEVELS = [
        ('info', _('Information')),
        ('warning', _('Warning')),
        ('error', _('Error')),
        ('debug', _('Debug')),
    ]

    document = models.ForeignKey(Document, on_delete=models.CASCADE, related_name='processing_logs')
    timestamp = models.DateTimeField(auto_now_add=True)
    level = models.CharField(max_length=10, choices=LOG_LEVELS, default='info')
    message = models.TextField()
    details = models.JSONField(null=True, blank=True)

    def __str__(self):
        return f"{self.timestamp} - {self.level}: {self.document.title}"

    class Meta:
        verbose_name = _("Document Processing Log")
        verbose_name_plural = _("Document Processing Logs")
        ordering = ['-timestamp']