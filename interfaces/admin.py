from django.contrib import admin
from django.utils.html import format_html

from .models import InterfaceType, SupplierInterface, InterfaceLog, XMLStandardTemplate


@admin.register(InterfaceType)
class InterfaceTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'description', 'is_active')
    search_fields = ('name', 'code', 'description')
    list_filter = ('is_active',)


@admin.register(SupplierInterface)
class SupplierInterfaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'supplier', 'interface_type', 'is_active')
    list_filter = ('interface_type', 'is_active')
    search_fields = ('name', 'supplier__name', 'api_url', 'template')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('name', 'supplier', 'interface_type', 'is_active')
        }),
        ('Connection Details', {
            'fields': ('api_url', 'api_key', 'username', 'password', 'host', 'port', 'remote_path')
        }),
        ('Configuration', {
            'fields': ('config_json', 'template')
        }),
        ('Email Settings', {
            'fields': ('email_to', 'email_cc', 'email_subject_template')
        }),
        ('System Information', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )

    def get_readonly_fields(self, request, obj=None):
        # Make API credentials read-only after creation for security
        if obj:  # editing an existing object
            return self.readonly_fields + ('api_key', 'password')
        return self.readonly_fields


@admin.register(InterfaceLog)
class InterfaceLogAdmin(admin.ModelAdmin):
    list_display = ('interface', 'order', 'status_badge', 'timestamp', 'truncated_message')
    list_filter = ('interface', 'status', 'timestamp')
    search_fields = ('interface__name', 'message', 'request_data', 'response_data')
    readonly_fields = ('interface', 'order', 'status', 'message', 'request_data', 'response_data', 'timestamp',
                       'initiated_by')
    date_hierarchy = 'timestamp'

    fieldsets = (
        (None, {
            'fields': ('interface', 'order', 'status', 'timestamp')
        }),
        ('Message', {
            'fields': ('message', 'initiated_by')
        }),
        ('Data', {
            'classes': ('collapse',),
            'fields': ('request_data', 'response_data')
        }),
    )

    def truncated_message(self, obj):
        if len(obj.message) > 100:
            return obj.message[:97] + '...'
        return obj.message

    truncated_message.short_description = 'Message'

    def status_badge(self, obj):
        colors = {
            'success': 'green',
            'pending': 'blue',
            'in_progress': 'orange',
            'failed': 'red',
            'retry': 'purple'
        }
        color = colors.get(obj.status, 'gray')
        return format_html('<span style="background-color: {}; color: white; padding: 3px 7px; '
                           'border-radius: 10px;">{}</span>', color, obj.get_status_display())

    status_badge.short_description = 'Status'

    def has_add_permission(self, request):
        return False  # Logs should only be created by the system

    def has_change_permission(self, request, obj=None):
        return False  # Logs should not be editable


@admin.register(XMLStandardTemplate)
class XMLStandardTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'version', 'is_active')
    list_filter = ('is_active', 'industry')
    search_fields = ('name', 'description', 'code')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'description', 'is_active', 'industry', 'version')
        }),
        ('Template Content', {
            'fields': ('template',),
            'classes': ('wide',)
        }),
        ('System Information', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )
