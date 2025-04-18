from django.contrib import admin
from django.utils.html import format_html

from .models import Warehouse, StockMovement, StockTake, StockTakeItem, VariantWarehouse


@admin.register(Warehouse)
class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'is_active')
    search_fields = ('name', 'location', 'description')
    list_filter = ('is_active',)


@admin.register(StockMovement)
class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'warehouse', 'movement_type', 'quantity', 'created_at', 'created_by')
    list_filter = ('movement_type', 'warehouse', 'created_at')
    search_fields = ('product__name', 'warehouse__name', 'reference', 'notes')
    readonly_fields = ('created_at', 'created_by')
    date_hierarchy = 'created_at'

    fieldsets = (
        (None, {
            'fields': ('product', 'warehouse', 'movement_type', 'quantity')
        }),
        ('Details', {
            'fields': ('reference', 'notes')
        }),
        ('System Information', {
            'classes': ('collapse',),
            'fields': ('created_at', 'created_by')
        }),
    )

    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


class StockTakeItemInline(admin.TabularInline):
    model = StockTakeItem
    extra = 0
    fields = ('product', 'expected_quantity', 'counted_quantity', 'get_discrepancy', 'get_discrepancy_status')
    readonly_fields = ('get_discrepancy', 'get_discrepancy_status')

    def get_discrepancy(self, obj):
        return obj.get_discrepancy()

    get_discrepancy.short_description = 'Discrepancy'

    def get_discrepancy_status(self, obj):
        status = obj.get_discrepancy_status()
        colors = {
            'match': 'green',
            'minor': 'orange',
            'major': 'red',
            'uncounted': 'gray'
        }
        color = colors.get(status, 'black')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, status.title())

    get_discrepancy_status.short_description = 'Status'


@admin.register(StockTake)
class StockTakeAdmin(admin.ModelAdmin):
    list_display = ('name', 'warehouse', 'status', 'start_date', 'completion_percentage', 'discrepancy_count')
    list_filter = ('status', 'warehouse', 'inventory_type', 'start_date')
    search_fields = ('name', 'description', 'notes')
    readonly_fields = ('start_date', 'created_by', 'completion_percentage', 'total_discrepancy', 'discrepancy_count')
    date_hierarchy = 'start_date'
    inlines = [StockTakeItemInline]

    fieldsets = (
        (None, {
            'fields': ('name', 'warehouse', 'status', 'inventory_type')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date')
        }),
        ('Details', {
            'fields': ('description', 'notes')
        }),
        ('Results', {
            'fields': ('completion_percentage', 'total_discrepancy', 'discrepancy_count')
        }),
        ('System Information', {
            'classes': ('collapse',),
            'fields': ('created_by',)
        }),
    )

    def completion_percentage(self, obj):
        percentage = obj.get_completion_percentage()
        return format_html('<div style="width:100px; background-color:#f8f8f8; border:1px solid #ddd;">'
                           '<div style="width:{}px; background-color:{}; height:20px;"></div>'
                           '</div> {}%',
                           percentage,
                           'green' if percentage == 100 else 'orange',
                           percentage)

    completion_percentage.short_description = 'Completion'

    def total_discrepancy(self, obj):
        return obj.get_total_discrepancy()

    total_discrepancy.short_description = 'Total Discrepancy'

    def discrepancy_count(self, obj):
        return obj.get_discrepancy_count()

    discrepancy_count.short_description = 'Discrepancies'

    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(StockTakeItem)
class StockTakeItemAdmin(admin.ModelAdmin):
    list_display = ('stock_take', 'product', 'expected_quantity', 'counted_quantity', 'discrepancy',
                    'discrepancy_status')
    list_filter = ('stock_take', 'stock_take__warehouse')
    search_fields = ('product__name', 'stock_take__name')
    readonly_fields = ('discrepancy', 'discrepancy_value', 'discrepancy_status')

    def discrepancy(self, obj):
        return obj.get_discrepancy()

    discrepancy.short_description = 'Discrepancy'

    def discrepancy_value(self, obj):
        return obj.get_discrepancy_value()

    discrepancy_value.short_description = 'Discrepancy Value'

    def discrepancy_status(self, obj):
        status = obj.get_discrepancy_status()
        colors = {
            'match': 'green',
            'minor': 'orange',
            'major': 'red',
            'uncounted': 'gray'
        }
        color = colors.get(status, 'black')
        return format_html('<span style="color: {}; font-weight: bold;">{}</span>', color, status.title())

    discrepancy_status.short_description = 'Status'


@admin.register(VariantWarehouse)
class VariantWarehouseAdmin(admin.ModelAdmin):
    list_display = ('variant', 'warehouse', 'quantity', 'stock_status')
    list_filter = ('warehouse', 'variant__parent_product')
    search_fields = ('variant__name', 'variant__parent_product__name', 'warehouse__name')

    def stock_status(self, obj):
        if obj.is_below_min_stock():
            return format_html('<span style="color: red; font-weight: bold;">Low Stock</span>')
        elif obj.is_above_max_stock():
            return format_html('<span style="color: blue; font-weight: bold;">Overstocked</span>')
        else:
            return format_html('<span style="color: green; font-weight: bold;">Normal</span>')

    stock_status.short_description = 'Stock Status'
