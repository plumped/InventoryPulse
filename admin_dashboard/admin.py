# admin_dashboard/admin.py
from django.contrib import admin
from .models import CompanyAddress, CompanyAddressType, WorkflowSettings, SystemSettings


@admin.register(CompanyAddress)
class CompanyAddressAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'address_type',
        'city',
        'country',
        'is_default',
        'contact_person',
        'email',
    )
    list_filter = ('address_type', 'is_default', 'country')
    search_fields = ('name', 'city', 'zip_code', 'street', 'contact_person', 'email')
    ordering = ('address_type', 'name')
    fieldsets = (
        (None, {
            'fields': (
                'name',
                'address_type',
                'is_default',
                ('street', 'zip_code', 'city'),
                'country',
                ('contact_person', 'phone', 'email'),
                'notes',
            )
        }),
    )


@admin.register(WorkflowSettings)
class WorkflowSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'order_approval_required',
        'order_approval_threshold',
        'skip_draft_for_small_orders',
        'small_order_threshold',
        'auto_approve_preferred_suppliers',
        'require_separate_approver',
        'send_order_emails',
    )


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = (
        'company_name',
        'default_warehouse',
        'default_stock_min',
        'default_lead_time',
        'next_order_number',
        'order_number_prefix',
        'track_inventory_history',
        'auto_create_user_profile',
    )
    fieldsets = (
        ('Allgemein', {
            'fields': (
                'company_name',
                'company_logo',
                'default_warehouse',
                ('default_stock_min', 'default_lead_time'),
            )
        }),
        ('Nummerierung & System', {
            'fields': ('next_order_number', 'order_number_prefix', 'track_inventory_history')
        }),
        ('E-Mail', {
            'fields': ('email_notifications_enabled', 'email_from_address')
        }),
        ('Benutzerprofile', {
            'fields': ('auto_create_user_profile',)
        }),
    )
