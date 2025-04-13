from django.contrib import admin
from django.utils.html import format_html

from data_operations.models.importers_models import ImportLog, ImportError
from data_operations.models.performance_models import SupplierPerformance, SupplierPerformanceMetric


# ===== Import Log Admin =====

class ImportErrorInline(admin.TabularInline):
    model = ImportError
    extra = 0
    fields = ('row_number', 'field_name', 'field_value', 'error_message')
    readonly_fields = ('row_number', 'field_name', 'field_value', 'error_message')
    can_delete = False
    max_num = 0  # Don't allow adding new errors manually
    show_change_link = False
    verbose_name = "Import Error"
    verbose_name_plural = "Import Errors"


@admin.register(ImportLog)
class ImportLogAdmin(admin.ModelAdmin):
    list_display = ('file_name', 'import_type', 'status_badge', 'created_at',
                    'created_by', 'rows_processed', 'success_rate')
    list_filter = ('status', 'import_type', 'created_by', 'created_at')
    search_fields = ('file_name', 'notes')
    readonly_fields = ('created_at', 'created_by', 'success_rate_display',
                       'total_records', 'success_count', 'error_count',
                       'rows_processed', 'rows_created', 'rows_updated', 'rows_error')
    date_hierarchy = 'created_at'

    fieldsets = (
        (None, {
            'fields': ('file_name', 'import_type', 'status')
        }),
        ('Results', {
            'fields': (
                ('rows_processed', 'rows_created', 'rows_updated', 'rows_error'),
                'success_rate_display'
            )
        }),
        ('Legacy Fields', {
            'classes': ('collapse',),
            'fields': ('total_records', 'success_count', 'error_count')
        }),
        ('Additional Information', {
            'fields': ('notes', 'error_details', 'error_file', 'created_at', 'created_by')
        }),
    )

    inlines = [ImportErrorInline]

    def success_rate_display(self, obj):
        """Display success rate with color-coded indication"""
        rate = obj.success_rate()
        if rate >= 95:
            color = 'green'
        elif rate >= 75:
            color = 'orange'
        else:
            color = 'red'

        # Use str.format() instead of f-strings in format_html
        return format_html('<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
                           color, rate)

    success_rate_display.short_description = "Success Rate"

    # For the list display, use a simple method that returns a value, not HTML
    def success_rate(self, obj):
        return f"{obj.success_rate():.1f}%"

    success_rate.short_description = "Success Rate (%)"

    def status_badge(self, obj):
        """Display status as a colored badge"""
        colors = {
            'completed': 'green',
            'completed_with_errors': 'orange',
            'processing': 'blue',
            'failed': 'red'
        }
        color = colors.get(obj.status, 'gray')
        return format_html('<span style="background-color: {}; color: white; padding: 3px 7px; '
                           'border-radius: 10px;">{}</span>',
                           color, obj.get_status_display())

    status_badge.short_description = "Status"

    def has_change_permission(self, request, obj=None):
        # Only allow changing notes and error_details
        if obj and obj.status in ['completed', 'completed_with_errors', 'failed']:
            # Could implement custom permission here if needed
            return True
        return super().has_change_permission(request, obj)

    def get_readonly_fields(self, request, obj=None):
        # Make all fields readonly if the import is completed
        if obj and obj.status in ['completed', 'completed_with_errors', 'failed']:
            return [f.name for f in self.model._meta.fields if f.name not in ['notes', 'error_details']]
        return self.readonly_fields

    def save_model(self, request, obj, form, change):
        if not change:  # New object
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(ImportError)
class ImportErrorAdmin(admin.ModelAdmin):
    list_display = ('import_log', 'row_number', 'field_name', 'truncated_error_message')
    list_filter = ('import_log__status', 'import_log__import_type')
    search_fields = ('row_data', 'error_message', 'field_name', 'field_value')
    readonly_fields = ('import_log', 'row_number', 'error_message', 'row_data', 'field_name', 'field_value')

    def truncated_error_message(self, obj):
        """Display truncated error message"""
        if len(obj.error_message) > 100:
            return obj.error_message[:97] + '...'
        return obj.error_message

    truncated_error_message.short_description = "Error Message"

    def has_add_permission(self, request):
        return False  # Don't allow adding errors manually


# ===== Supplier Performance Admin =====

class SupplierPerformanceInline(admin.TabularInline):
    model = SupplierPerformance
    extra = 0
    fields = ('metric', 'value', 'evaluation_date', 'evaluated_by')
    readonly_fields = ('evaluation_date', 'evaluated_by')
    can_delete = True
    max_num = 10  # Limit the number of metrics shown inline
    verbose_name = "Performance Metric"
    verbose_name_plural = "Performance Metrics"


@admin.register(SupplierPerformanceMetric)
class SupplierPerformanceMetricAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'metric_type', 'target_value', 'is_active', 'is_system')
    list_filter = ('metric_type', 'is_active', 'is_system')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'description', 'metric_type')
        }),
        ('Configuration', {
            'fields': ('target_value', 'minimum_value', 'weight', 'is_active', 'is_system')
        }),
        ('System Information', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of system metrics
        if obj and obj.is_system:
            return False
        return super().has_delete_permission(request, obj)


@admin.register(SupplierPerformance)
class SupplierPerformanceAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'metric', 'value_display', 'evaluation_date', 'evaluated_by')
    list_filter = ('metric', 'evaluation_date', 'evaluated_by', 'supplier')
    search_fields = ('supplier__name', 'metric__name', 'notes')
    raw_id_fields = ['supplier', 'evaluated_by', 'reference_orders']
    readonly_fields = ('created_at', 'updated_at')
    date_hierarchy = 'evaluation_date'

    fieldsets = (
        (None, {
            'fields': ('supplier', 'metric', 'value')
        }),
        ('Evaluation Details', {
            'fields': ('evaluation_date', 'evaluation_period_start', 'evaluation_period_end', 'evaluated_by')
        }),
        ('References', {
            'fields': ('reference_orders', 'notes')
        }),
        ('System Information', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )

    def value_display(self, obj):
        """Display value with color-coded indication"""
        value = obj.value
        target = obj.metric.target_value if obj.metric else 100
        minimum = obj.metric.minimum_value if obj.metric else 0

        # Calculate percentage of target achieved
        range_size = target - minimum
        if range_size <= 0:
            percentage = 100  # Avoid division by zero
        else:
            percentage = ((value - minimum) / range_size) * 100

        # Color based on percentage of target
        if percentage >= 90:
            color = 'green'
        elif percentage >= 70:
            color = 'orange'
        else:
            color = 'red'

        return format_html('<span style="color: {}; font-weight: bold;">{:.1f}%</span>',
                           color, value)

    value_display.short_description = "Value"

    def save_model(self, request, obj, form, change):
        if not obj.evaluated_by:
            obj.evaluated_by = request.user
        super().save_model(request, obj, form, change)
