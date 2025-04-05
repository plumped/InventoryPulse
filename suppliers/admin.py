# In suppliers/admin.py
from django.contrib import admin
from .models import Supplier, SupplierProduct, SupplierPerformance, SupplierPerformanceMetric, SupplierAddress, \
    SupplierContact


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



class SupplierAddressInline(admin.TabularInline):
    model = SupplierAddress
    extra = 1
    classes = ['collapse']


class SupplierContactInline(admin.TabularInline):
    model = SupplierContact
    extra = 1
    classes = ['collapse']


@admin.register(SupplierAddress)
class SupplierAddressAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'address_type', 'name', 'city', 'is_default')
    list_filter = ('address_type', 'is_default', 'country', 'city')
    search_fields = ('supplier__name', 'name', 'street', 'city', 'postal_code')
    autocomplete_fields = ['supplier']

    fieldsets = (
        (None, {
            'fields': ('supplier', 'address_type', 'is_default', 'name')
        }),
        ('Adressdetails', {
            'fields': ('street', 'street_number', 'postal_code', 'city', 'state', 'country')
        }),
        ('Zusätzliche Informationen', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


@admin.register(SupplierContact)
class SupplierContactAdmin(admin.ModelAdmin):
    list_display = ('supplier', 'contact_type', 'full_name', 'position', 'email', 'phone', 'is_default')
    list_filter = ('contact_type', 'is_default')
    search_fields = ('supplier__name', 'first_name', 'last_name', 'email', 'position')
    autocomplete_fields = ['supplier']

    fieldsets = (
        (None, {
            'fields': ('supplier', 'contact_type', 'is_default')
        }),
        ('Personendaten', {
            'fields': ('title', 'first_name', 'last_name', 'position')
        }),
        ('Kontaktdaten', {
            'fields': ('email', 'phone', 'mobile')
        }),
        ('Zusätzliche Informationen', {
            'fields': ('notes',),
            'classes': ('collapse',)
        }),
    )


# Aktualisieren Sie den bestehenden SupplierAdmin
@admin.register(Supplier)
class SupplierAdmin(admin.ModelAdmin):
    list_display = ('name', 'get_primary_contact', 'get_primary_email', 'get_primary_phone')
    search_fields = ('name', 'contacts__first_name', 'contacts__last_name', 'contacts__email')
    inlines = [SupplierAddressInline, SupplierContactInline, SupplierPerformanceInline]

    fieldsets = (
        (None, {
            'fields': ('name', 'is_active')
        }),
        ('Veraltete Kontaktdaten', {
            'fields': ('contact_person', 'email', 'phone', 'address'),
            'classes': ('collapse',),
        }),
        ('Finanzinformationen', {
            'fields': ('shipping_cost', 'minimum_order_value', 'default_currency'),
        }),
    )

    def get_primary_contact(self, obj):
        contact = obj.get_default_contact()
        return contact.full_name() if contact else "-"

    get_primary_contact.short_description = "Hauptkontakt"

    def get_primary_email(self, obj):
        contact = obj.get_default_contact()
        return contact.email if contact and contact.email else "-"

    get_primary_email.short_description = "E-Mail"

    def get_primary_phone(self, obj):
        contact = obj.get_default_contact()
        return contact.phone if contact and contact.phone else "-"

    get_primary_phone.short_description = "Telefon"



