from django.contrib import admin
from django.utils.html import format_html

from .models import (
    DocumentType, Document, DocumentTemplate, TemplateField,
    DocumentMatch, DocumentProcessingLog, StandardField
)


@admin.register(DocumentType)
class DocumentTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'description')
    search_fields = ('name', 'code', 'description')
    list_filter = ('is_active',)


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'document_type', 'supplier', 'matched_order', 'upload_date', 'processing_status',
                    'document_preview')
    list_filter = ('document_type', 'processing_status', 'upload_date')
    search_fields = ('title', 'notes', 'supplier__name', 'matched_order__order_number')
    readonly_fields = ('upload_date', 'document_preview')
    date_hierarchy = 'upload_date'

    fieldsets = (
        (None, {
            'fields': ('title', 'document_type', 'file', 'document_preview')
        }),
        ('Relations', {
            'fields': ('supplier', 'matched_order')
        }),
        ('Details', {
            'fields': ('notes', 'processing_status', 'ocr_data')
        }),
        ('System Information', {
            'classes': ('collapse',),
            'fields': ('upload_date', 'uploaded_by')
        }),
    )

    def document_preview(self, obj):
        if obj.file:
            file_url = obj.file.url
            if file_url.lower().endswith(('.png', '.jpg', '.jpeg', '.gif')):
                return format_html('<a href="{}" target="_blank"><img src="{}" width="100" /></a>', file_url, file_url)
            else:
                return format_html('<a href="{}" target="_blank">View Document</a>', file_url)
        return "No document"

    document_preview.short_description = "Preview"

    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(DocumentTemplate)
class DocumentTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'document_type', 'is_active', 'created_at')
    list_filter = ('document_type', 'is_active', 'created_at')
    search_fields = ('name', 'description')
    readonly_fields = ('created_at', 'updated_at')


class TemplateFieldInline(admin.TabularInline):
    model = TemplateField
    extra = 1
    fields = ('name', 'field_type', 'x_position', 'y_position', 'width', 'height', 'is_required')


@admin.register(TemplateField)
class TemplateFieldAdmin(admin.ModelAdmin):
    list_display = ('name', 'template', 'field_type', 'is_required')
    list_filter = ('template', 'field_type', 'is_required')
    search_fields = ('name', 'description', 'template__name')


@admin.register(DocumentMatch)
class DocumentMatchAdmin(admin.ModelAdmin):
    list_display = ('document', 'template', 'confidence_score', 'match_date')
    list_filter = ('template', 'match_date')
    search_fields = ('document__title', 'template__name')
    readonly_fields = ('match_date',)


@admin.register(DocumentProcessingLog)
class DocumentProcessingLogAdmin(admin.ModelAdmin):
    list_display = ('document', 'level', 'timestamp')
    list_filter = ('level', 'timestamp')
    search_fields = ('document__title', 'message')
    readonly_fields = ('timestamp', 'document', 'level', 'message', 'details')


@admin.register(StandardField)
class StandardFieldAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'field_type', 'document_type')
    list_filter = ('field_type', 'document_type')
    search_fields = ('name', 'code', 'description')

    def has_delete_permission(self, request, obj=None):
        # Always allow deletion for now
        return super().has_delete_permission(request, obj)
