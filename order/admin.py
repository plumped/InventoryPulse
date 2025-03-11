from django.contrib import admin
from .models import (
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderReceipt,
    PurchaseOrderReceiptItem, OrderSuggestion
)


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 0
    fields = ('product', 'supplier_sku', 'quantity_ordered', 'quantity_received', 'unit_price', 'line_total')
    readonly_fields = ('line_total',)
    autocomplete_fields = ['product']


class PurchaseOrderReceiptItemInline(admin.TabularInline):
    model = PurchaseOrderReceiptItem
    extra = 0
    fields = ('order_item', 'quantity_received', 'warehouse', 'batch_number', 'expiry_date')
    autocomplete_fields = ['order_item', 'warehouse']


class PurchaseOrderReceiptInline(admin.TabularInline):
    model = PurchaseOrderReceipt
    extra = 0
    fields = ('receipt_date', 'received_by', 'notes')
    readonly_fields = ('receipt_date', 'received_by')


class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'supplier', 'order_date', 'status', 'total', 'created_by')
    list_filter = ('status', 'order_date', 'supplier')
    search_fields = ('order_number', 'supplier__name', 'notes')
    readonly_fields = ('order_date', 'created_by', 'approved_by', 'subtotal', 'total')
    date_hierarchy = 'order_date'
    inlines = [PurchaseOrderItemInline, PurchaseOrderReceiptInline]
    autocomplete_fields = ['supplier']

    fieldsets = (
        (None, {
            'fields': ('order_number', 'supplier', 'status')
        }),
        ('Termine und Lieferung', {
            'fields': ('order_date', 'expected_delivery', 'shipping_address')
        }),
        ('Finanzen', {
            'fields': ('subtotal', 'tax', 'shipping_cost', 'total')
        }),
        ('Zusatzinformationen', {
            'fields': ('notes', 'created_by', 'approved_by')
        })
    )


class PurchaseOrderReceiptAdmin(admin.ModelAdmin):
    list_display = ('id', 'purchase_order', 'receipt_date', 'received_by')
    list_filter = ('receipt_date', 'received_by')
    search_fields = ('purchase_order__order_number', 'notes')
    readonly_fields = ('receipt_date', 'received_by')
    inlines = [PurchaseOrderReceiptItemInline]
    autocomplete_fields = ['purchase_order']


class OrderSuggestionAdmin(admin.ModelAdmin):
    list_display = (
    'product', 'current_stock', 'minimum_stock', 'suggested_order_quantity', 'preferred_supplier', 'last_calculated')
    list_filter = ('last_calculated', 'preferred_supplier')
    search_fields = ('product__name', 'product__sku')
    readonly_fields = ('last_calculated',)
    autocomplete_fields = ['product', 'preferred_supplier']

class PurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'product', 'supplier_sku', 'quantity_ordered', 'quantity_received', 'unit_price', 'line_total')
    list_filter = ('purchase_order__supplier', 'product__category')
    search_fields = ('product__name', 'product__sku', 'supplier_sku')
    readonly_fields = ('line_total',)
    autocomplete_fields = ['purchase_order', 'product']

    def get_queryset(self, request):
        """
        Optimize the queryset to reduce database queries
        """
        return super().get_queryset(request).select_related('purchase_order', 'product')


admin.site.register(PurchaseOrder, PurchaseOrderAdmin)
admin.site.register(PurchaseOrderReceipt, PurchaseOrderReceiptAdmin)
admin.site.register(OrderSuggestion, OrderSuggestionAdmin)
admin.site.register(PurchaseOrderItem, PurchaseOrderItemAdmin)
