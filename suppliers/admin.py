# In suppliers/admin.py
from django.contrib import admin
from .models import Supplier, SupplierProduct, SupplierPerformance, SupplierPerformanceMetric


class SupplierPerformanceInline(admin.TabularInline):
    model = SupplierPerformance
    extra = 0
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['metric', 'evaluated_by', 'supplier']

    def get_queryset(self, request):
        # Get only the most recent records to avoid too many entries
        qs = super().get_queryset(request)
        return qs.order_by('-evaluation_date')[:10]

@admin.register(SupplierPerformanceMetric)
class SupplierPerformanceMetricAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'metric_type', 'target_value', 'weight', 'is_active', 'is_system')
    list_filter = ('metric_type', 'is_active', 'is_system')
    search_fields = ('name', 'code', 'description')
    ordering = ('name',)
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'description', 'metric_type')
        }),
        ('Configuration', {
            'fields': ('target_value', 'minimum_value', 'weight', 'is_active', 'is_system')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

@admin.register(SupplierPerformance)
class SupplierPerformanceAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'metric', 'value', 'evaluation_date', 'evaluated_by')
    list_filter = ('metric', 'evaluation_date', 'supplier')
    search_fields = ('supplier__name', 'metric__name', 'notes')
    ordering = ('-evaluation_date', 'supplier')
    readonly_fields = ('created_at', 'updated_at')
    autocomplete_fields = ['supplier', 'metric', 'evaluated_by', 'reference_orders']

    fieldsets = (
        (None, {
            'fields': ('supplier', 'metric', 'value', 'evaluation_date')
        }),
        ('Evaluation Period', {
            'fields': ('evaluation_period_start', 'evaluation_period_end')
        }),
        ('Details', {
            'fields': ('notes', 'evaluated_by', 'reference_orders')
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )


@admin.register(SupplierProduct)
class SupplierProductAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'product', 'purchase_price', 'is_preferred')
    list_filter = ('supplier', 'is_preferred')
    search_fields = ('supplier__name', 'product__name')


@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'contact_person', 'email', 'phone')
    search_fields = ('name', 'contact_person', 'email')



