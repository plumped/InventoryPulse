from django.contrib import admin
from django.utils.html import format_html

from .models.categories_models import Category
from .models.products_models import (
    Product, ProductWarehouse, ProductPhoto, ProductAttachment,
    ProductVariantType, ProductVariant
)


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name',)
    search_fields = ('name', 'description')


class ProductPhotoInline(admin.TabularInline):
    model = ProductPhoto
    extra = 1
    fields = ('image', 'is_primary', 'caption')


class ProductAttachmentInline(admin.TabularInline):
    model = ProductAttachment
    extra = 1
    fields = ('file', 'title', 'description', 'file_type')


class ProductWarehouseInline(admin.TabularInline):
    model = ProductWarehouse
    extra = 1
    fields = ('warehouse', 'quantity')


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 1
    fields = ('name', 'sku', 'variant_type', 'value', 'price_adjustment', 'barcode', 'is_active')


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'total_stock_display', 'minimum_stock', 'has_variants',
                    'has_serial_numbers', 'has_batch_tracking')
    list_filter = ('category', 'has_variants', 'has_serial_numbers', 'has_batch_tracking', 'has_expiry_tracking')
    search_fields = ('name', 'sku', 'barcode', 'description')
    readonly_fields = ('created_at', 'updated_at', 'total_stock_display')
    inlines = [ProductPhotoInline, ProductAttachmentInline, ProductWarehouseInline, ProductVariantInline]

    fieldsets = (
        (None, {
            'fields': ('name', 'sku', 'barcode', 'category', 'description')
        }),
        ('Inventory Settings', {
            'fields': ('minimum_stock', 'unit', 'tax')
        }),
        ('Tracking Options', {
            'fields': ('has_variants', 'has_serial_numbers', 'has_batch_tracking', 'has_expiry_tracking')
        }),
        ('System Information', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at', 'total_stock_display')
        }),
    )

    def total_stock_display(self, obj):
        stock = obj.total_stock
        color = 'red' if stock < obj.minimum_stock else 'green'
        return format_html('<span style="color: {}; font-weight: bold;">{} {}</span>',
                           color, stock, obj.unit)

    total_stock_display.short_description = "Total Stock"


@admin.register(ProductWarehouse)
class ProductWarehouseAdmin(admin.ModelAdmin):
    list_display = ('product', 'warehouse', 'quantity')
    list_filter = ('warehouse',)
    search_fields = ('product__name', 'product__sku', 'warehouse__name')


@admin.register(ProductPhoto)
class ProductPhotoAdmin(admin.ModelAdmin):
    list_display = ('product', 'is_primary', 'caption', 'upload_date', 'image_preview')
    list_filter = ('is_primary', 'upload_date')
    search_fields = ('product__name', 'caption')
    readonly_fields = ('upload_date', 'image_preview')

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" width="100" />', obj.image.url)
        return "No Image"

    image_preview.short_description = "Preview"


@admin.register(ProductAttachment)
class ProductAttachmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'product', 'file_type', 'upload_date', 'file_link')
    list_filter = ('file_type', 'upload_date')
    search_fields = ('title', 'description', 'product__name')
    readonly_fields = ('upload_date', 'file_link')

    def file_link(self, obj):
        if obj.file:
            return format_html('<a href="{}" target="_blank">View File</a>', obj.file.url)
        return "No File"

    file_link.short_description = "File"


@admin.register(ProductVariantType)
class ProductVariantTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')


@admin.register(ProductVariant)
class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_product', 'sku', 'variant_type', 'value', 'price_adjustment', 'is_active',
                    'total_stock_display')
    list_filter = ('variant_type', 'is_active', 'parent_product')
    search_fields = ('name', 'sku', 'barcode', 'value', 'parent_product__name')
    readonly_fields = ('created_at', 'updated_at', 'total_stock_display')

    fieldsets = (
        (None, {
            'fields': ('parent_product', 'name', 'sku', 'barcode')
        }),
        ('Variant Details', {
            'fields': ('variant_type', 'value', 'price_adjustment', 'is_active')
        }),
        ('System Information', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at', 'total_stock_display')
        }),
    )

    def total_stock_display(self, obj):
        stock = obj.total_stock
        parent_min_stock = obj.parent_product.minimum_stock
        color = 'red' if stock < parent_min_stock else 'green'
        return format_html('<span style="color: {}; font-weight: bold;">{} {}</span>',
                           color, stock, obj.parent_product.unit)

    total_stock_display.short_description = "Total Stock"
