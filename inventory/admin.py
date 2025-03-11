from django.contrib import admin
from .models import (
    Warehouse,
    StockMovement,
    StockTake,
    StockTakeItem,
    Department,
    WarehouseAccess
)

class WarehouseAdmin(admin.ModelAdmin):
    list_display = ('name', 'location', 'is_active')
    list_filter = ('is_active',)
    search_fields = ('name', 'location')


class StockMovementAdmin(admin.ModelAdmin):
    list_display = ('product', 'warehouse', 'quantity', 'movement_type', 'created_at', 'created_by')
    list_filter = ('movement_type', 'warehouse', 'created_at')
    search_fields = ('product__name', 'reference', 'notes')
    date_hierarchy = 'created_at'
    autocomplete_fields = ['product']


class StockTakeItemInline(admin.TabularInline):
    model = StockTakeItem
    extra = 0
    autocomplete_fields = ['product']


class StockTakeAdmin(admin.ModelAdmin):
    list_display = ('name', 'warehouse', 'status', 'start_date', 'end_date', 'get_completion_percentage')
    list_filter = ('status', 'warehouse', 'start_date')
    search_fields = ('name', 'description')
    readonly_fields = ('start_date',)
    inlines = [StockTakeItemInline]
    date_hierarchy = 'start_date'


class StockTakeItemAdmin(admin.ModelAdmin):
    list_display = ('stock_take', 'product', 'expected_quantity', 'counted_quantity', 'is_counted', 'get_discrepancy')
    list_filter = ('is_counted', 'stock_take')
    search_fields = ('product__name', 'stock_take__name')
    readonly_fields = ('stock_take', 'product', 'expected_quantity')
    autocomplete_fields = ['product']


class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'manager')
    search_fields = ('name', 'code', 'manager__username')
    filter_horizontal = ('members',)


class WarehouseAccessAdmin(admin.ModelAdmin):
    list_display = ('warehouse', 'department', 'can_view', 'can_edit', 'can_manage_stock')
    list_filter = ('warehouse', 'department', 'can_view', 'can_edit', 'can_manage_stock')
    search_fields = ('warehouse__name', 'department__name')


admin.site.register(Warehouse, WarehouseAdmin)
admin.site.register(StockMovement, StockMovementAdmin)
admin.site.register(StockTake, StockTakeAdmin)
admin.site.register(StockTakeItem, StockTakeItemAdmin)
admin.site.register(Department, DepartmentAdmin)
admin.site.register(WarehouseAccess, WarehouseAccessAdmin)