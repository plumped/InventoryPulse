from datetime import date, timedelta

from django.contrib import admin

from .models import SerialNumber, BatchNumber


@admin.register(SerialNumber)
class SerialNumberAdmin(admin.ModelAdmin):
    list_display = (
        'serial_number', 'product', 'variant', 'status', 'warehouse', 'purchase_date', 'expiry_date', 'is_expired')
    list_filter = ('status', 'warehouse', 'purchase_date', 'expiry_date')
    search_fields = ('serial_number', 'product__name', 'variant__name', 'notes')
    readonly_fields = ('created_at', 'updated_at', 'is_expired', 'days_until_expiry')
    raw_id_fields = ('product', 'variant', 'warehouse')  # Ersetzt autocomplete_fields
    fieldsets = (
        ('Allgemeine Informationen', {
            'fields': ('serial_number', 'product', 'variant', 'status')
        }),
        ('Lager & Zeitdaten', {
            'fields': ('warehouse', 'purchase_date', 'expiry_date', 'is_expired', 'days_until_expiry')
        }),
        ('Zusätzliche Informationen', {
            'fields': ('notes', 'created_at', 'updated_at')
        }),
    )


@admin.register(BatchNumber)
class BatchNumberAdmin(admin.ModelAdmin):
    list_display = (
        'batch_number', 'product', 'variant', 'quantity', 'warehouse', 'supplier', 'production_date', 'expiry_date',
        'is_expired')
    list_filter = ('warehouse', 'supplier', 'production_date', 'expiry_date')
    search_fields = ('batch_number', 'product__name', 'variant__name', 'notes')
    readonly_fields = ('created_at', 'is_expired', 'days_until_expiry')
    raw_id_fields = ('product', 'variant', 'warehouse', 'supplier')  # Ersetzt autocomplete_fields
    fieldsets = (
        ('Allgemeine Informationen', {
            'fields': ('batch_number', 'product', 'variant', 'quantity')
        }),
        ('Lager & Lieferanten', {
            'fields': ('warehouse', 'supplier')
        }),
        ('Zeitdaten', {
            'fields': ('production_date', 'expiry_date', 'is_expired', 'days_until_expiry')
        }),
        ('Zusätzliche Informationen', {
            'fields': ('notes', 'created_at')
        }),
    )


# Benutzerdefinierter Filter für abgelaufene Artikel
class ExpiredFilter(admin.SimpleListFilter):
    title = 'Ablaufstatus'
    parameter_name = 'expiry_status'

    def lookups(self, request, model_admin):
        return (
            ('expired', 'Abgelaufen'),
            ('not_expired', 'Nicht abgelaufen'),
            ('expiring_soon', 'Läuft bald ab (30 Tage)'),
        )

    def queryset(self, request, queryset):
        today = date.today()

        if self.value() == 'expired':
            return queryset.filter(expiry_date__lt=today)
        elif self.value() == 'not_expired':
            return queryset.filter(expiry_date__gte=today)
        elif self.value() == 'expiring_soon':
            thirty_days_later = today + timedelta(days=30)
            return queryset.filter(expiry_date__gte=today, expiry_date__lte=thirty_days_later)
        return queryset
