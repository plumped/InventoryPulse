from django.contrib import admin
from .models import (
    RMA, RMAItem, RMAPhoto, RMAHistory,
    RMAComment, RMADocument
)


class RMAItemInline(admin.TabularInline):
    model = RMAItem
    extra = 0
    readonly_fields = ('value',)
    autocomplete_fields = ('product', 'receipt_item')


class RMAPhotoInline(admin.TabularInline):
    model = RMAPhoto
    extra = 0


class RMAHistoryInline(admin.TabularInline):
    model = RMAHistory
    extra = 0
    readonly_fields = ('timestamp', 'status_from', 'status_to', 'changed_by', 'note')
    can_delete = False


class RMACommentInline(admin.StackedInline):
    model = RMAComment
    extra = 0
    readonly_fields = ('created_at',)
    autocomplete_fields = ('user',)


class RMADocumentInline(admin.StackedInline):
    model = RMADocument
    extra = 0
    readonly_fields = ('uploaded_at',)
    autocomplete_fields = ('uploaded_by',)


@admin.register(RMA)
class RMAAdmin(admin.ModelAdmin):
    list_display = ('rma_number', 'supplier', 'status', 'created_at', 'submission_date', 'resolution_date', 'total_value')
    list_filter = ('status', 'resolution_type', 'created_at')
    search_fields = ('rma_number', 'supplier__name', 'contact_person', 'contact_email')
    date_hierarchy = 'created_at'
    inlines = [RMAItemInline, RMAHistoryInline, RMACommentInline, RMADocumentInline]
    autocomplete_fields = ('supplier', 'related_order', 'rma_warehouse', 'created_by', 'approved_by')

    readonly_fields = ('created_at', 'updated_at', 'total_value')


@admin.register(RMAItem)
class RMAItemAdmin(admin.ModelAdmin):
    list_display = ('rma', 'product', 'quantity', 'unit_price', 'issue_type', 'is_resolved')
    search_fields = ('product__name', 'batch_number', 'serial_number')
    list_filter = ('issue_type', 'is_resolved')
    autocomplete_fields = ('rma', 'product', 'receipt_item')


@admin.register(RMAPhoto)
class RMAPhotoAdmin(admin.ModelAdmin):
    list_display = ('rma_item', 'caption', 'uploaded_at')
    autocomplete_fields = ('rma_item',)


@admin.register(RMAHistory)
class RMAHistoryAdmin(admin.ModelAdmin):
    list_display = ('rma', 'status_from', 'status_to', 'changed_by', 'timestamp')
    list_filter = ('status_from', 'status_to')
    search_fields = ('rma__rma_number', 'note')
    autocomplete_fields = ('rma', 'changed_by')


@admin.register(RMAComment)
class RMACommentAdmin(admin.ModelAdmin):
    list_display = ('rma', 'user', 'created_at', 'is_public')
    search_fields = ('comment',)
    list_filter = ('is_public',)
    autocomplete_fields = ('rma', 'user')


@admin.register(RMADocument)
class RMADocumentAdmin(admin.ModelAdmin):
    list_display = ('rma', 'title', 'document_type', 'uploaded_by', 'uploaded_at')
    list_filter = ('document_type',)
    search_fields = ('title', 'notes')
    autocomplete_fields = ('rma', 'uploaded_by')
