from django.contrib import admin
from django.utils.html import format_html

from .models import (
    PurchaseOrder, PurchaseOrderItem, OrderSplit, OrderSplitItem,
    PurchaseOrderReceipt, PurchaseOrderReceiptItem, OrderSuggestion,
    OrderTemplate, OrderTemplateItem, PurchaseOrderComment
)


class PurchaseOrderItemInline(admin.TabularInline):
    model = PurchaseOrderItem
    extra = 1
    fields = ('product', 'quantity_ordered', 'unit_price', 'tax', 'line_total', 'receipt_status')
    readonly_fields = ('line_total', 'receipt_status')

    def line_total(self, obj):
        return obj.line_total() if obj.pk else "-"

    line_total.short_description = "Total"

    def receipt_status(self, obj):
        if not obj.pk:
            return "-"
        status = obj.receipt_status()
        colors = {
            'not_received': 'red',
            'partially_received': 'orange',
            'fully_received': 'green'
        }
        color = colors.get(status, 'black')
        return format_html('<span style="color: {};">{}</span>',
                           color, status.replace('_', ' ').title())

    receipt_status.short_description = "Receipt Status"


class PurchaseOrderCommentInline(admin.StackedInline):
    model = PurchaseOrderComment
    extra = 0
    fields = ('comment_type', 'comment', 'user', 'created_at')
    readonly_fields = ('user', 'created_at')

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PurchaseOrder)
class PurchaseOrderAdmin(admin.ModelAdmin):
    list_display = ('order_number', 'supplier', 'order_date', 'status', 'total', 'created_by')
    list_filter = ('status', 'order_date', 'supplier', 'created_by')
    search_fields = ('order_number', 'supplier__name', 'notes')
    readonly_fields = ('created_by', 'approved_by', 'subtotal', 'tax', 'total')
    date_hierarchy = 'order_date'
    inlines = [PurchaseOrderItemInline, PurchaseOrderCommentInline]

    fieldsets = (
        (None, {
            'fields': ('order_number', 'supplier', 'order_date', 'status')
        }),
        ('Shipping Information', {
            'fields': ('shipping_address', 'expected_delivery')
        }),
        ('Financial Details', {
            'fields': ('subtotal', 'tax', 'shipping_cost', 'total')
        }),
        ('Notes', {
            'fields': ('notes',)
        }),
        ('Approval Information', {
            'fields': ('created_by', 'approved_by')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def save_formset(self, request, form, formset, change):
        instances = formset.save(commit=False)
        for instance in instances:
            if isinstance(instance, PurchaseOrderComment) and not instance.pk:
                instance.user = request.user
            instance.save()
        formset.save_m2m()


@admin.register(PurchaseOrderItem)
class PurchaseOrderItemAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'product', 'quantity_ordered', 'unit_price', 'line_total_display',
                    'receipt_status_display')
    list_filter = ('purchase_order__status', 'purchase_order__supplier')
    search_fields = ('purchase_order__order_number', 'product__name', 'supplier_sku')
    readonly_fields = ('line_subtotal', 'line_tax', 'line_total', 'receipt_status_display')

    fieldsets = (
        (None, {
            'fields': ('purchase_order', 'product', 'supplier_sku')
        }),
        ('Pricing', {
            'fields': ('quantity_ordered', 'unit_price', 'tax', 'line_subtotal', 'line_tax', 'line_total')
        }),
        ('Details', {
            'fields': ('item_notes', 'receipt_status_display')
        }),
    )

    def line_total_display(self, obj):
        return obj.line_total()

    line_total_display.short_description = "Total"

    def receipt_status_display(self, obj):
        status = obj.receipt_status()
        colors = {
            'not_received': 'red',
            'partially_received': 'orange',
            'fully_received': 'green'
        }
        color = colors.get(status, 'black')
        return format_html('<span style="color: {};">{}</span>',
                           color, status.replace('_', ' ').title())

    receipt_status_display.short_description = "Receipt Status"


class OrderSplitItemInline(admin.TabularInline):
    model = OrderSplitItem
    extra = 1


@admin.register(OrderSplit)
class OrderSplitAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'created_at', 'notes', 'created_by')
    list_filter = ('created_at', 'created_by')
    search_fields = ('purchase_order__order_number', 'notes')
    readonly_fields = ('created_by', 'created_at')
    inlines = [OrderSplitItemInline]

    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class PurchaseOrderReceiptItemInline(admin.TabularInline):
    model = PurchaseOrderReceiptItem
    extra = 1


@admin.register(PurchaseOrderReceipt)
class PurchaseOrderReceiptAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'receipt_date', 'received_by')
    list_filter = ('receipt_date', 'received_by')
    search_fields = ('purchase_order__order_number', 'notes')
    inlines = [PurchaseOrderReceiptItemInline]


@admin.register(OrderSuggestion)
class OrderSuggestionAdmin(admin.ModelAdmin):
    list_display = ('product', 'suggested_order_quantity', 'preferred_supplier', 'last_calculated')
    list_filter = ('last_calculated', 'preferred_supplier')
    search_fields = ('product__name', 'preferred_supplier__name')
    readonly_fields = ('last_calculated',)

    actions = ['create_purchase_order']

    def create_purchase_order(self, request, queryset):
        # This would be implemented to create a purchase order from selected suggestions
        self.message_user(request, f"{queryset.count()} suggestions selected for order creation")

    create_purchase_order.short_description = "Create purchase order from selected suggestions"


class OrderTemplateItemInline(admin.TabularInline):
    model = OrderTemplateItem
    extra = 1


@admin.register(OrderTemplate)
class OrderTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'supplier', 'is_active', 'created_by', 'created_at')
    list_filter = ('is_active', 'supplier', 'created_by')
    search_fields = ('name', 'description', 'supplier__name')
    readonly_fields = ('created_by', 'created_at')
    inlines = [OrderTemplateItemInline]

    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PurchaseOrderComment)
class PurchaseOrderCommentAdmin(admin.ModelAdmin):
    list_display = ('purchase_order', 'comment_type', 'user', 'created_at', 'truncated_comment')
    list_filter = ('comment_type', 'user', 'created_at')
    search_fields = ('purchase_order__order_number', 'comment')
    readonly_fields = ('user', 'created_at')

    def truncated_comment(self, obj):
        if len(obj.comment) > 100:
            return obj.comment[:97] + '...'
        return obj.comment

    truncated_comment.short_description = 'Comment'

    def has_change_permission(self, request, obj=None):
        # Comments should not be editable after creation
        return False
