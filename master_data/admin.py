from django.contrib import admin
from django.utils.html import format_html

from master_data.models.addresses_models import CompanyAddress
from master_data.models.currency_models import Currency
from master_data.models.organisations_models import Organization, Department
from master_data.models.systemsettings_models import WorkflowSettings, SystemSettings
from master_data.models.tax_models import Tax


# Organization and Department admin
class DepartmentInline(admin.TabularInline):
    model = Department
    extra = 1
    fields = ('name', 'code', 'manager', 'description')


@admin.register(Organization)
class OrganizationAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'subdomain', 'subscription_status', 'is_active', 'created_at')
    list_filter = ('is_active', 'subscription_active', 'subscription_package', 'created_at')
    search_fields = ('name', 'code', 'subdomain', 'email', 'phone')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('admin_users',)
    inlines = [DepartmentInline]

    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'is_active')
        }),
        ('Contact Information', {
            'fields': ('address', 'phone', 'email', 'website', 'tax_id')
        }),
        ('Multi-Tenant Settings', {
            'fields': ('subdomain', 'subscription_active', 'subscription_package')
        }),
        ('Administration', {
            'fields': ('admin_users',)
        }),
        ('System Information', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )

    def subscription_status(self, obj):
        if obj.subscription_active:
            package_name = obj.subscription_package.name if obj.subscription_package else "No Package"
            return format_html('<span style="color: green;">Active</span> - {}', package_name)
        else:
            return format_html('<span style="color: red;">Inactive</span>')

    subscription_status.short_description = 'Subscription'


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'organization', 'manager', 'created_at')
    list_filter = ('organization', 'created_at')
    search_fields = ('name', 'code', 'description', 'organization__name')
    readonly_fields = ('created_at', 'updated_at')
    filter_horizontal = ('members',)

    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'organization', 'description')
        }),
        ('Management', {
            'fields': ('manager', 'members')
        }),
        ('System Information', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )


# CompanyAddress admin
@admin.register(CompanyAddress)
class CompanyAddressAdmin(admin.ModelAdmin):
    list_display = ('name', 'address_type', 'is_default', 'city', 'country', 'created_at')
    list_filter = ('address_type', 'is_default', 'country', 'created_at')
    search_fields = ('name', 'street', 'city', 'country', 'contact_person')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('name', 'address_type', 'is_default')
        }),
        ('Address', {
            'fields': ('street', 'zip_code', 'city', 'country')
        }),
        ('Contact', {
            'fields': ('contact_person', 'phone', 'email', 'notes')
        }),
        ('System Information', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )


# Currency admin
@admin.register(Currency)
class CurrencyAdmin(admin.ModelAdmin):
    list_display = ('code', 'name', 'symbol', 'exchange_rate', 'is_default', 'is_active')
    list_filter = ('is_default', 'is_active', 'created_at')
    search_fields = ('code', 'name')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('code', 'name', 'symbol', 'decimal_places')
        }),
        ('Settings', {
            'fields': ('exchange_rate', 'is_default', 'is_active')
        }),
        ('System Information', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )


# SystemSettings admin
@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    list_display = ('company_name', 'default_warehouse', 'email_notifications_enabled')

    fieldsets = (
        (None, {
            'fields': ('company_name', 'company_logo')
        }),
        ('Inventory Settings', {
            'fields': ('default_warehouse', 'default_stock_min', 'default_lead_time', 'track_inventory_history')
        }),
        ('Order Settings', {
            'fields': ('next_order_number', 'order_number_prefix')
        }),
        ('Notification Settings', {
            'fields': ('email_notifications_enabled', 'email_from_address')
        }),
        ('User Settings', {
            'fields': ('auto_create_user_profile',)
        }),
    )

    def has_add_permission(self, request):
        # Only allow one instance of SystemSettings
        return not SystemSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of SystemSettings
        return False


@admin.register(WorkflowSettings)
class WorkflowSettingsAdmin(admin.ModelAdmin):
    list_display = ('order_approval_required', 'order_approval_threshold', 'auto_approve_preferred_suppliers')

    fieldsets = (
        ('Order Approval', {
            'fields': ('order_approval_required', 'order_approval_threshold', 'require_separate_approver')
        }),
        ('Small Orders', {
            'fields': ('skip_draft_for_small_orders', 'small_order_threshold')
        }),
        ('Automation', {
            'fields': ('auto_approve_preferred_suppliers', 'send_order_emails')
        }),
    )

    def has_add_permission(self, request):
        # Only allow one instance of WorkflowSettings
        return not WorkflowSettings.objects.exists()

    def has_delete_permission(self, request, obj=None):
        # Prevent deletion of WorkflowSettings
        return False


# Tax admin
@admin.register(Tax)
class TaxAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'rate', 'is_default', 'is_active')
    list_filter = ('is_default', 'is_active', 'created_at')
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('created_at', 'updated_at')

    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'rate', 'description')
        }),
        ('Settings', {
            'fields': ('is_default', 'is_active')
        }),
        ('System Information', {
            'classes': ('collapse',),
            'fields': ('created_at', 'updated_at')
        }),
    )
