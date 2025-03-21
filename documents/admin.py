from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from .models import (
    DocumentType, Document, DocumentTemplate,
    TemplateField, DocumentMatch, DocumentProcessingLog
)


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active')
    search_fields = ('name', 'code')
    list_filter = ('is_active',)


class DocumentProcessingLogInline(admin.TabularInline):
    model = DocumentProcessingLog
    extra = 0
    readonly_fields = ('timestamp', 'level', 'message')
    fields = ('timestamp', 'level', 'message')
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'document_type', 'supplier', 'upload_date', 'status_badge', 'matching_info')
    list_filter = ('processing_status', 'document_type', 'supplier', 'upload_date')
    search_fields = ('title', 'document_number', 'ocr_text')
    readonly_fields = ('ocr_text', 'ocr_data', 'processing_status', 'confidence_score', 'extracted_data')
    fieldsets = (
        (None, {
            'fields': ('title', 'file', 'document_type', 'supplier')
        }),
        (_('Processing Information'), {
            'fields': ('processing_status', 'document_number', 'document_date')
        }),
        (_('Matching Information'), {
            'fields': ('matched_template', 'matched_order', 'confidence_score')
        }),
        (_('OCR Data'), {
            'classes': ('collapse',),
            'fields': ('ocr_text', 'extracted_data', 'ocr_data')
        }),
    )
    inlines = [DocumentProcessingLogInline]

    def status_badge(self, obj):
        status_colors = {
            'pending': 'secondary',
            'processing': 'info',
            'processed': 'primary',
            'error': 'danger',
            'matched': 'success',
        }
        color = status_colors.get(obj.processing_status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_processing_status_display()
        )

    status_badge.short_description = _('Status')

    def matching_info(self, obj):
        if obj.matched_order:
            return format_html(
                '<span class="badge bg-success">Matched to order: {}</span>',
                obj.matched_order.order_number
            )
        elif obj.matched_template:
            return format_html(
                '<span class="badge bg-info">Matched to template: {}</span>',
                obj.matched_template.name
            )
        return format_html('<span class="badge bg-secondary">Not matched</span>')

    matching_info.short_description = _('Matching')


class TemplateFieldInline(admin.TabularInline):
    model = TemplateField
    extra = 1
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'field_type', 'is_key_field', 'is_required')
        }),
        (_('Coordinates'), {
            'fields': ('x1', 'y1', 'x2', 'y2')
        }),
        (_('Extraction Configuration'), {
            'fields': ('extraction_method', 'search_pattern', 'reference_field', 'format_pattern')
        }),
    )


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'supplier', 'document_type', 'is_active', 'fields_count')
    list_filter = ('supplier', 'document_type', 'is_active')
    search_fields = ('name', 'description')
    fieldsets = (
        (None, {
            'fields': ('name', 'supplier', 'document_type', 'is_active', 'description')
        }),
        (_('Template Identification'), {
            'fields': ('header_pattern', 'footer_pattern', 'reference_document')
        }),
    )
    inlines = [TemplateFieldInline]

    def fields_count(self, obj):
        count = obj.fields.count()
        return format_html(
            '<span class="badge bg-info">{} fields</span>',
            count
        )

    fields_count.short_description = _('Fields')


@admin.register(TemplateField)
class TemplateFieldAdmin(admin.ModelAdmin):
    list_display = ('name', 'template', 'field_type', 'extraction_method', 'is_key_field')
    list_filter = ('template__supplier', 'field_type', 'extraction_method', 'is_key_field')
    search_fields = ('name', 'code', 'description')
    fieldsets = (
        (None, {
            'fields': ('template', 'name', 'code', 'field_type', 'description')
        }),
        (_('Coordinates'), {
            'fields': ('x1', 'y1', 'x2', 'y2')
        }),
        (_('Extraction Configuration'), {
            'fields': ('extraction_method', 'search_pattern', 'reference_field',
                       'x_offset', 'y_offset', 'format_pattern')
        }),
        (_('Table Configuration'), {
            'fields': ('is_table_header', 'table_column_index', 'table_row_index', 'table_parent')
        }),
        (_('Validation'), {
            'fields': ('is_required', 'is_key_field', 'validation_regex')
        }),
    )


@admin.register(DocumentMatch)
class DocumentMatchAdmin(admin.ModelAdmin):
    list_display = ('document', 'template', 'purchase_order', 'status', 'confidence_score', 'match_date')
    list_filter = ('status', 'match_date')
    search_fields = ('document__title', 'template__name', 'purchase_order__order_number')
    readonly_fields = ('document', 'template', 'confidence_score', 'match_date', 'matched_data')
    fieldsets = (
        (None, {
            'fields': ('document', 'template', 'purchase_order', 'status')
        }),
        (_('Match Details'), {
            'fields': ('confidence_score', 'match_date', 'matched_by', 'notes')
        }),
        (_('Matched Data'), {
            'classes': ('collapse',),
            'fields': ('matched_data',)
        }),
    )


@admin.register(DocumentProcessingLog)
class DocumentProcessingLogAdmin(admin.ModelAdmin):
    list_display = ('document', 'timestamp', 'level', 'message')
    list_filter = ('level', 'timestamp')
    search_fields = ('document__title', 'message')
    readonly_fields = ('document', 'timestamp', 'level', 'message', 'details')

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False