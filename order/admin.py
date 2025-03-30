from django.contrib import admin
from .models import (
    PurchaseOrder, PurchaseOrderItem, PurchaseOrderReceipt,
    PurchaseOrderReceiptItem, OrderSuggestion, OrderTemplate, OrderTemplateItem, OrderSplitItem, OrderSplit
)


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 0
    fields = ('product', 'supplier_sku', 'quantity_ordered', 'canceled_quantity', 'quantity_received', 'unit_price', 'get_line_total', 'status')
    readonly_fields = ('get_line_total', 'status', 'canceled_quantity')
    autocomplete_fields = ['product']

    def get_line_total(self, obj):
        """Sichere Methode zum Abrufen des Zeilenwerts"""
        if obj and obj.line_total is not None:
            return f"{obj.line_total:.2f}"
        return "0.00"
    get_line_total.short_description = "Zeilensumme"


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
    list_display = (
    'purchase_order', 'product', 'supplier_sku', 'get_quantity_info', 'status', 'unit_price', 'get_line_total')
    list_filter = ('purchase_order__supplier', 'product__category', 'status')
    search_fields = ('product__name', 'product__sku', 'supplier_sku')
    readonly_fields = (
    'get_line_total', 'get_quantity_info', 'canceled_quantity', 'canceled_at', 'canceled_by', 'cancellation_reason')
    autocomplete_fields = ['purchase_order', 'product']

    def get_quantity_info(self, obj):
        """Zeigt die Bestellmenge und ggf. stornierte Menge an"""
        if obj.is_canceled:
            return f"{obj.quantity_ordered} (storniert)"
        elif obj.is_partially_canceled:
            return f"{obj.effective_quantity} (von {obj.quantity_ordered}, {obj.canceled_quantity} storniert)"
        return f"{obj.quantity_ordered}"

    get_quantity_info.short_description = "Menge"

    def get_line_total(self, obj):
        """Sichere Methode zum Abrufen des Zeilenwerts"""
        if obj and obj.display_line_total is not None:
            return f"{obj.display_line_total:.2f}"
        return "0.00"

    get_line_total.short_description = "Zeilensumme"

    fieldsets = (
        (None, {
            'fields': ('purchase_order', 'product', 'supplier_sku', 'quantity_ordered', 'unit_price')
        }),
        ('Stornierung', {
            'fields': ('status', 'canceled_quantity', 'cancellation_reason', 'canceled_at', 'canceled_by'),
            'classes': ('collapse',),
            'description': 'Informationen zu Stornierungen dieser Position'
        }),
    )

    def get_queryset(self, request):
        """
        Optimize the queryset to reduce database queries
        """
        return super().get_queryset(request).select_related('purchase_order', 'product', 'canceled_by')


class OrderTemplateItemInline(admin.TabularInline):
    model = OrderTemplateItem
    extra = 0
    fields = ('product', 'supplier_sku', 'quantity')
    autocomplete_fields = ['product']


class OrderTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'supplier', 'created_by', 'is_recurring', 'recurrence_frequency', 'is_active')
    list_filter = ('is_active', 'is_recurring', 'supplier', 'created_by')
    search_fields = ('name', 'description', 'supplier__name')
    inlines = [OrderTemplateItemInline]
    autocomplete_fields = ['supplier']

    fieldsets = (
        (None, {
            'fields': ('name', 'description', 'supplier', 'is_active')
        }),
        ('Wiederkehrende Bestellung', {
            'fields': ('is_recurring', 'recurrence_frequency', 'next_order_date')
        }),
        ('Zusatzinformationen', {
            'fields': ('shipping_address', 'notes', 'created_by')
        })
    )

    def save_model(self, request, obj, form, change):
        if not change:  # If creating a new object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class OrderSplitItemInline(admin.TabularInline):
    model = OrderSplitItem
    extra = 0
    fields = ('order_item', 'quantity')
    autocomplete_fields = ['order_item']


class OrderSplitAdmin(admin.ModelAdmin):
    list_display = ('name', 'purchase_order', 'status', 'expected_delivery', 'carrier', 'created_by')
    list_filter = ('status', 'expected_delivery', 'created_at')
    search_fields = ('name', 'purchase_order__order_number', 'carrier', 'tracking_number')
    date_hierarchy = 'expected_delivery'
    inlines = [OrderSplitItemInline]
    autocomplete_fields = ['purchase_order', 'created_by']

    fieldsets = (
        (None, {
            'fields': ('purchase_order', 'name', 'status', 'created_by')
        }),
        ('Lieferinformationen', {
            'fields': ('expected_delivery', 'carrier', 'tracking_number')
        }),
        ('Zusatzinformationen', {
            'fields': ('notes',)
        })
    )


# Register the models
admin.site.register(OrderTemplate, OrderTemplateAdmin)


admin.site.register(PurchaseOrder, PurchaseOrderAdmin)
admin.site.register(PurchaseOrderReceipt, PurchaseOrderReceiptAdmin)
admin.site.register(OrderSuggestion, OrderSuggestionAdmin)
admin.site.register(PurchaseOrderItem, PurchaseOrderItemAdmin)
admin.site.register(OrderSplit, OrderSplitAdmin)

