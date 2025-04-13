from django.contrib import admin
from django.utils.html import format_html

from data_operations.models.performance_models import SupplierPerformance
from .models import (
    Supplier, SupplierProduct, SupplierAddress, SupplierContact,
)


class SupplierPerformanceInline(admin.TabularInline):
    model = SupplierPerformance
    extra = 0
    readonly_fields = ('metric', 'value', 'evaluation_date', 'evaluated_by')
    fields = ('metric', 'value', 'evaluation_date', 'evaluated_by')
    can_delete = False
    show_change_link = True


class SupplierAddressInline(admin.TabularInline):
    model = SupplierAddress
    extra = 1
    fields = ('address_type', 'is_default', 'name', 'street', 'street_number',
              'postal_code', 'city', 'country')


class SupplierContactInline(admin.TabularInline):
    model = SupplierContact
    extra = 1
    fields = ('contact_type', 'is_default', 'title', 'first_name', 'last_name',
              'position', 'email', 'phone')


class SupplierProductInline(admin.TabularInline):
    model = SupplierProduct
    extra = 1
    fields = ('product', 'supplier_sku', 'purchase_price', 'currency',
              'lead_time_days', 'is_preferred')


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'default_currency',
                    'total_products', 'website_link', 'created_at')
    list_filter = ('is_active', 'default_currency')
    search_fields = ('name', 'notes')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'is_active')
        }),
        ('Financial Details', {
            'fields': ('default_currency', 'shipping_cost', 'minimum_order_value')
        }),
        ('Additional Information', {
            'fields': ('website', 'notes', 'created_at', 'updated_at')
        }),
        ('Legacy Fields (Deprecated)', {
            'classes': ('collapse',),
            'fields': ('contact_person', 'email', 'phone', 'address')
        }),
    )
    inlines = [
        SupplierAddressInline,
        SupplierContactInline,
        SupplierProductInline,
        SupplierPerformanceInline,
    ]

    def website_link(self, obj):
        if obj.website:
            return format_html('<a href="{0}" target="_blank">{0}</a>', obj.website)
        return "-"

    website_link.short_description = "Website"

    def total_products(self, obj):
        return obj.supplier_products.count()

    total_products.short_description = "Products"


@admin.register(SupplierProduct)
class SupplierProductAdmin(admin.ModelAdmin):
    list_display = ('product', 'supplier', 'supplier_sku', 'purchase_price',
                    'currency_display', 'lead_time_days', 'is_preferred')
    list_filter = ('supplier', 'is_preferred', 'currency')
    search_fields = ('product__name', 'product__sku', 'supplier__name', 'supplier_sku')
    raw_id_fields = ['product', 'supplier']
    readonly_fields = ('created_at', 'updated_at')

    def currency_display(self, obj):
        if obj.currency:
            return obj.currency.code
        elif obj.supplier and obj.supplier.default_currency:
            return f"{obj.supplier.default_currency.code} (default)"
        return "-"

    currency_display.short_description = "Currency"


@admin.register(SupplierAddress)
class SupplierAddressAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'address_type', 'is_default', 'city', 'country')
    list_filter = ('address_type', 'is_default', 'country')
    search_fields = ('supplier__name', 'name', 'city', 'street')
    autocomplete_fields = ['supplier']
    readonly_fields = ('created_at', 'updated_at')


@admin.register(SupplierContact)
class SupplierContactAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'full_name', 'contact_type', 'is_default',
                    'position', 'email', 'phone')
    list_filter = ('contact_type', 'is_default')
    search_fields = ('supplier__name', 'first_name', 'last_name', 'email')
    autocomplete_fields = ['supplier']
    readonly_fields = ('created_at', 'updated_at')
