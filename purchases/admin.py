from django.contrib import admin
from .models import (
    PurchaseOrder,
    PurchaseOrderItem,
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrderTemplate,
    PurchaseOrderTemplateItem,
    PurchaseRecommendation
)


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1
    fields = ('product', 'supplier_product', 'quantity', 'received_quantity', 'unit_price', 'line_total')
    readonly_fields = ('line_total',)
    autocomplete_fields = ['product', 'supplier_product']

    def line_total(self, obj):
        return obj.line_total if obj.pk else 0

    line_total.short_description = 'Gesamtpreis'


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'supplier', 'status', 'order_date', 'expected_delivery_date', 'total', 'created_by')
    list_filter = ('status', 'supplier', 'order_date')
    search_fields = ('order_number', 'supplier__name', 'notes')
    readonly_fields = ('subtotal', 'total', 'created_by', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('order_number', 'supplier', 'status')
        }),
        ('Termine', {
            'fields': ('order_date', 'expected_delivery_date', 'delivery_date')
        }),
        ('Finanzielles', {
            'fields': ('subtotal', 'tax', 'shipping_cost', 'total')
        }),
        ('Weitere Informationen', {
            'fields': ('shipping_address', 'notes', 'reference', 'internal_notes')
        }),
        ('Metadaten', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    inlines = [PurchaseOrderItemInline]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class GoodsReceiptItemInline(admin.TabularInline):
    model = GoodsReceiptItem
    extra = 1
    fields = ('purchase_order_item', 'received_quantity', 'is_defective', 'notes')


@admin.register(GoodsReceipt)
class GoodsReceiptAdmin(admin.ModelAdmin):
    list_display = ('receipt_number', 'purchase_order', 'status', 'receipt_date', 'created_by')
    list_filter = ('status', 'receipt_date')
    search_fields = ('receipt_number', 'purchase_order__order_number', 'notes')
    readonly_fields = ('created_by', 'created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('receipt_number', 'purchase_order', 'status', 'receipt_date')
        }),
        ('Lieferdetails', {
            'fields': ('delivery_note_number', 'carrier', 'package_count', 'notes')
        }),
        ('Metadaten', {
            'fields': ('created_by', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    inlines = [GoodsReceiptItemInline]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class PurchaseOrderTemplateItemInline(admin.TabularInline):
    model = PurchaseOrderTemplateItem
    extra = 1
    fields = ('product', 'supplier_product', 'quantity')
    autocomplete_fields = ['product', 'supplier_product']


@admin.register(PurchaseOrderTemplate)
class PurchaseOrderTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'supplier', 'created_by', 'created_at')
    search_fields = ('name', 'supplier__name', 'notes')
    readonly_fields = ('created_by', 'created_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'supplier', 'notes')
        }),
        ('Metadaten', {
            'fields': ('created_by', 'created_at'),
            'classes': ('collapse',)
        }),
    )
    inlines = [PurchaseOrderTemplateItemInline]

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PurchaseRecommendation)
class PurchaseRecommendationAdmin(admin.ModelAdmin):
    list_display = ('product', 'current_stock', 'min_stock', 'recommended_quantity', 'status', 'recommended_date')
    list_filter = ('status', 'recommended_date')
    search_fields = ('product__name', 'product__sku')
    list_editable = ('status',)
    readonly_fields = ('recommended_date', 'last_updated')