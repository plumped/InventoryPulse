from django.contrib import admin
from django.urls import reverse
from django.utils.html import format_html

from .models import (
    RMA, RMAItem, RMAPhoto, RMAHistory, RMAComment, RMADocument
)


class RMAItemInline(admin.TabularInline):
    model = RMAItem
    extra = 1
    fields = ('product', 'quantity', 'unit_price', 'issue_type', 'issue_description', 'is_resolved')
    readonly_fields = ('value',)


class RMAHistoryInline(admin.TabularInline):
    model = RMAHistory
    extra = 0
    fields = ('timestamp', 'status_from', 'status_to', 'changed_by', 'note')
    readonly_fields = ('timestamp', 'status_from', 'status_to', 'changed_by', 'note')
    can_delete = False
    max_num = 0
    ordering = ('-timestamp',)


class RMACommentInline(admin.StackedInline):
    model = RMAComment
    extra = 0
    fields = ('user', 'comment', 'attachment', 'is_public', 'created_at')
    readonly_fields = ('user', 'created_at')


@admin.register(RMA)
class RMAAdmin(admin.ModelAdmin):
    list_display = ('rma_number', 'supplier', 'status_badge', 'total_value', 'created_by', 'created_at')
    list_filter = ('status', 'supplier', 'created_by', 'created_at')
    search_fields = ('rma_number', 'supplier__name', 'notes', 'contact_person')
    readonly_fields = ('created_at', 'updated_at', 'created_by', 'approved_by', 'submission_date', 'resolution_date')
    date_hierarchy = 'created_at'
    inlines = [RMAItemInline, RMAHistoryInline, RMACommentInline]

    fieldsets = (
        (None, {
            'fields': ('rma_number', 'supplier', 'related_order', 'status')
        }),
        ('Resolution', {
            'fields': ('resolution_type', 'resolution_notes', 'rma_warehouse')
        }),
        ('Contact Information', {
            'fields': ('contact_person', 'contact_email', 'contact_phone')
        }),
        ('Shipping Information', {
            'fields': ('shipping_address', 'tracking_number', 'shipping_date')
        }),
        ('Financial Information', {
            'fields': ('total_value',)
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('System Information', {
            'classes': ('collapse',),
            'fields': ('created_by', 'created_at', 'updated_at', 'approved_by', 'submission_date', 'resolution_date')
        }),
    )

    def status_badge(self, obj):
        colors = {
            'draft': 'gray',
            'pending': 'blue',
            'approved': 'green',
            'sent': 'purple',
            'resolved': 'green',
            'rejected': 'red',
            'cancelled': 'red'
        }
        color = colors.get(obj.status, 'black')
        return format_html('<span style="background-color: {}; color: white; padding: 3px 7px; '
                           'border-radius: 10px;">{}</span>', color, obj.get_status_display())

    status_badge.short_description = 'Status'

    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(RMAItem)
class RMAItemAdmin(admin.ModelAdmin):
    list_display = ('rma_link', 'product', 'quantity', 'unit_price', 'value', 'issue_type', 'is_resolved')
    list_filter = ('issue_type', 'is_resolved', 'rma__status')
    search_fields = ('product__name', 'issue_description', 'batch_number', 'serial_number')
    readonly_fields = ('value',)

    fieldsets = (
        (None, {
            'fields': ('rma', 'product', 'receipt_item')
        }),
        ('Quantity and Price', {
            'fields': ('quantity', 'unit_price', 'value')
        }),
        ('Issue Details', {
            'fields': ('issue_type', 'issue_description', 'is_resolved', 'resolution_notes')
        }),
        ('Tracking Information', {
            'fields': ('batch_number', 'serial_number', 'expiry_date')
        }),
    )

    def rma_link(self, obj):
        url = reverse('admin:rma_rma_change', args=[obj.rma.id])
        return format_html('<a href="{}">{}</a>', url, obj.rma.rma_number)

    rma_link.short_description = 'RMA'


@admin.register(RMAPhoto)
class RMAPhotoAdmin(admin.ModelAdmin):
    list_display = ('rma_item', 'caption', 'uploaded_at', 'image_preview')
    list_filter = ('uploaded_at',)
    search_fields = ('caption', 'rma_item__product__name')
    readonly_fields = ('uploaded_at', 'image_preview')

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" />', obj.image.url)
        return "No Image"

    image_preview.short_description = "Preview"


@admin.register(RMAHistory)
class RMAHistoryAdmin(admin.ModelAdmin):
    list_display = ('rma', 'timestamp', 'status_change', 'changed_by')
    list_filter = ('timestamp', 'status_from', 'status_to')
    search_fields = ('rma__rma_number', 'note')
    readonly_fields = ('rma', 'timestamp', 'status_from', 'status_to', 'changed_by', 'note')

    def status_change(self, obj):
        if obj.status_from and obj.status_to:
            from_display = dict(obj._meta.model.status_from.field.choices).get(obj.status_from, obj.status_from)
            to_display = dict(obj._meta.model.status_to.field.choices).get(obj.status_to, obj.status_to)
            return f"{from_display} → {to_display}"
        return obj.note

    status_change.short_description = "Status Change"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(RMAComment)
class RMACommentAdmin(admin.ModelAdmin):
    list_display = ('rma', 'user', 'created_at', 'is_public', 'has_attachment')
    list_filter = ('created_at', 'is_public', 'user')
    search_fields = ('rma__rma_number', 'comment', 'user__username')
    readonly_fields = ('created_at',)

    def has_attachment(self, obj):
        return bool(obj.attachment)

    has_attachment.boolean = True
    has_attachment.short_description = "Has Attachment"


@admin.register(RMADocument)
class RMADocumentAdmin(admin.ModelAdmin):
    list_display = ('title', 'rma', 'document_type', 'uploaded_by', 'uploaded_at', 'file_link')
    list_filter = ('document_type', 'uploaded_at')
    search_fields = ('title', 'rma__rma_number', 'notes')
    readonly_fields = ('uploaded_at', 'uploaded_by', 'file_link')

    def file_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">View File</a>', obj.file.url)
        return "No File"

    file_link.short_description = "File"

    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)
