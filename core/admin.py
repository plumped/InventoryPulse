from django.contrib import admin
from .models import (
    Product,
    Category,
    ProductWarehouse,
    ProductPhoto,
    ProductAttachment,
    ProductVariantType,
    ProductVariant,
    SerialNumber,
    BatchNumber,
    ImportLog,
    ImportError,
    UserProfile, Tax, Currency
)


class ProductWarehouseInline(admin.TabularInline):
    model = ProductWarehouse
    extra = 0


class ProductPhotoInline(admin.TabularInline):
    model = ProductPhoto
    extra = 0


class ProductAttachmentInline(admin.TabularInline):
    model = ProductAttachment
    extra = 0


class ProductVariantInline(admin.TabularInline):
    model = ProductVariant
    extra = 0


class SerialNumberInline(admin.TabularInline):
    model = SerialNumber
    extra = 0


class BatchNumberInline(admin.TabularInline):
    model = BatchNumber
    extra = 0


class ProductAdmin(admin.ModelAdmin):
    list_display = ('name', 'sku', 'category', 'minimum_stock', 'total_stock', 'tax', 'has_variants', 'has_serial_numbers', 'has_batch_tracking')
    list_filter = ('category', 'tax', 'has_variants', 'has_serial_numbers', 'has_batch_tracking')
    search_fields = ('name', 'sku', 'barcode', 'description')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [ProductWarehouseInline, ProductPhotoInline, ProductAttachmentInline, ProductVariantInline, SerialNumberInline, BatchNumberInline]
    fieldsets = (
        (None, {
            'fields': ('name', 'sku', 'barcode', 'description', 'category', 'tax')
        }),
        ('Bestand', {
            'fields': ('minimum_stock', 'unit')
        }),
        ('Eigenschaften', {
            'fields': ('has_variants', 'has_serial_numbers', 'has_batch_tracking', 'has_expiry_tracking')
        }),
        ('Zeitstempel', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    autocomplete_fields = ['category', 'tax']


class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')


class ProductWarehouseAdmin(admin.ModelAdmin):
    list_display = ('product', 'warehouse', 'quantity')
    list_filter = ('warehouse',)
    search_fields = ('product__name', 'warehouse__name')
    autocomplete_fields = ['product', 'warehouse']


class ProductPhotoAdmin(admin.ModelAdmin):
    list_display = ('product', 'is_primary', 'caption', 'upload_date')
    list_filter = ('is_primary', 'upload_date')
    search_fields = ('product__name', 'caption')
    autocomplete_fields = ['product']


class ProductAttachmentAdmin(admin.ModelAdmin):
    list_display = ('product', 'title', 'file_type', 'upload_date')
    list_filter = ('file_type', 'upload_date')
    search_fields = ('product__name', 'title', 'description')
    autocomplete_fields = ['product']


class ProductVariantTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    search_fields = ('name', 'description')


class ProductVariantAdmin(admin.ModelAdmin):
    list_display = ('name', 'parent_product', 'sku', 'variant_type', 'value', 'is_active')
    list_filter = ('variant_type', 'is_active')
    search_fields = ('name', 'sku', 'parent_product__name', 'value')
    autocomplete_fields = ['parent_product', 'variant_type']


class SerialNumberAdmin(admin.ModelAdmin):
    list_display = ('serial_number', 'product', 'variant', 'status', 'warehouse', 'purchase_date', 'expiry_date')
    list_filter = ('status', 'warehouse', 'purchase_date', 'expiry_date')
    search_fields = ('serial_number', 'product__name', 'variant__name', 'notes')
    date_hierarchy = 'created_at'
    autocomplete_fields = ['product', 'variant', 'warehouse']


class BatchNumberAdmin(admin.ModelAdmin):
    list_display = ('batch_number', 'product', 'variant', 'quantity', 'production_date', 'expiry_date', 'warehouse')
    list_filter = ('warehouse', 'production_date', 'expiry_date', 'supplier')
    search_fields = ('batch_number', 'product__name', 'variant__name', 'notes')
    date_hierarchy = 'created_at'
    autocomplete_fields = ['product', 'variant', 'warehouse', 'supplier']


class ImportErrorInline(admin.TabularInline):
    model = ImportError
    extra = 0


class ImportLogAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'import_type', 'status', 'rows_processed', 'rows_created', 'rows_updated', 'rows_error', 'created_at', 'created_by')
    list_filter = ('import_type', 'status', 'created_at')
    search_fields = ('file_name', 'notes', 'created_by__username')
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    inlines = [ImportErrorInline]


class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user',)
    filter_horizontal = ('departments',)
    autocomplete_fields = ['user']


admin.site.register(Product, ProductAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(ProductWarehouse, ProductWarehouseAdmin)
admin.site.register(ProductPhoto, ProductPhotoAdmin)
admin.site.register(ProductAttachment, ProductAttachmentAdmin)
admin.site.register(ProductVariantType, ProductVariantTypeAdmin)
admin.site.register(ProductVariant, ProductVariantAdmin)
admin.site.register(SerialNumber, SerialNumberAdmin)
admin.site.register(BatchNumber, BatchNumberAdmin)
admin.site.register(ImportLog, ImportLogAdmin)
admin.site.register(UserProfile, UserProfileAdmin)

# Ermöglicht Suche für bestimmte Modelle im Admin-Interface
admin.site.add_action(lambda modeladmin, request, queryset: None, 'custom_search_fields')

# Registrieren Sie ProductVariantType mit Autocomplete-Unterstützung
class ProductVariantTypeAdminAutocomplete(ProductVariantTypeAdmin):
    search_fields = ['name']

admin.site.unregister(ProductVariantType)
admin.site.register(ProductVariantType, ProductVariantTypeAdminAutocomplete)

# Registrieren Sie Category mit Autocomplete-Unterstützung
class CategoryAdminAutocomplete(CategoryAdmin):
    search_fields = ['name']

admin.site.unregister(Category)
admin.site.register(Category, CategoryAdminAutocomplete)

class TaxAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'rate', 'is_default', 'is_active', 'updated_at')
    list_filter = ('is_active', 'is_default')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'rate', 'description')
        }),
        ('Status', {
            'fields': ('is_default', 'is_active')
        }),
        ('Zeitstempel', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

admin.site.register(Tax, TaxAdmin)

class TaxAdminAutocomplete(TaxAdmin):
    search_fields = ['name', 'code']

admin.site.unregister(Tax)
admin.site.register(Tax, TaxAdminAutocomplete)


class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'symbol', 'exchange_rate', 'is_default', 'is_active', 'updated_at')
    list_filter = ('is_active', 'is_default')
    search_fields = ('code', 'name')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('code', 'name', 'symbol', 'decimal_places')
        }),
        ('Exchange Rate', {
            'fields': ('exchange_rate',)
        }),
        ('Status', {
            'fields': ('is_default', 'is_active')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

admin.site.register(Currency, CurrencyAdmin)

# For autocomplete support
class CurrencyAdminAutocomplete(CurrencyAdmin):
    search_fields = ['code', 'name']

admin.site.unregister(Currency)
admin.site.register(Currency, CurrencyAdminAutocomplete)
