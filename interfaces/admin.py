from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from django.conf import settings

from .models import InterfaceType, SupplierInterface, InterfaceLog, XMLStandardTemplate


@admin.register(InterfaceType)
class InterfaceTypeAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'interface_count')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'description')
    readonly_fields = ('interface_count',)
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'is_active')
        }),
        (_('Beschreibung'), {
            'fields': ('description',),
            'classes': ('collapse',)
        }),
        (_('Statistik'), {
            'fields': ('interface_count',),
            'classes': ('collapse',)
        }),
    )
    
    def interface_count(self, obj):
        if not obj.pk:
            return '0'
        count = SupplierInterface.objects.filter(interface_type=obj).count()
        return str(count)
    interface_count.short_description = _('Anzahl Schnittstellen')


class InterfaceLogInline(admin.TabularInline):
    model = InterfaceLog
    extra = 0
    fields = ('timestamp', 'status', 'order_link', 'message')
    readonly_fields = ('timestamp', 'status', 'order_link', 'message')
    can_delete = False
    show_change_link = True
    verbose_name = _('Übertragungsprotokoll')
    verbose_name_plural = _('Übertragungsprotokolle')
    
    def has_add_permission(self, request, obj=None):
        return False
    
    def order_link(self, obj):
        url = reverse('admin:order_purchaseorder_change', args=[obj.order.id])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = _('Bestellung')


@admin.register(SupplierInterface)
class SupplierInterfaceAdmin(admin.ModelAdmin):
    list_display = ('name', 'supplier_link', 'interface_type', 'is_active', 'is_default', 'last_used')
    list_filter = ('is_active', 'is_default', 'interface_type')
    search_fields = ('name', 'supplier__name')
    readonly_fields = ('created_by', 'created_at', 'updated_at', 'last_used')
    fieldsets = (
        (None, {
            'fields': ('supplier', 'name', 'interface_type', 'is_active', 'is_default')
        }),
        (_('API/Web-Konfiguration'), {
            'fields': ('api_url', 'username', 'password', 'api_key'),
            'classes': ('collapse',),
            'description': _('Konfiguration für API- und Webservice-Schnittstellen.')
        }),
        (_('FTP/SFTP-Konfiguration'), {
            'fields': ('host', 'port', 'remote_path'),
            'classes': ('collapse',),
            'description': _('Konfiguration für FTP- und SFTP-Schnittstellen.')
        }),
        (_('E-Mail-Konfiguration'), {
            'fields': ('email_to', 'email_cc', 'email_subject_template'),
            'classes': ('collapse',),
            'description': _('Konfiguration für E-Mail-Schnittstellen.')
        }),
        (_('Format-Konfiguration'), {
            'fields': ('order_format', 'template'),
            'classes': ('collapse',),
            'description': _('Hier können Sie das Format der Bestellungen konfigurieren.')
        }),
        (_('Erweiterte Konfiguration'), {
            'fields': ('config_json',),
            'classes': ('collapse',),
            'description': _('Zusätzliche Konfigurationsparameter im JSON-Format.')
        }),
        (_('System-Informationen'), {
            'fields': ('created_by', 'created_at', 'updated_at', 'last_used'),
            'classes': ('collapse',),
        }),
    )
    inlines = [InterfaceLogInline]
    
    def save_model(self, request, obj, form, change):
        if not obj.pk:  # Nur bei Neuanlage
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
    
    def supplier_link(self, obj):
        url = reverse('admin:suppliers_supplier_change', args=[obj.supplier.id])
        return format_html('<a href="{}">{}</a>', url, obj.supplier.name)
    supplier_link.short_description = _('Lieferant')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('supplier', 'interface_type')


@admin.register(InterfaceLog)
class InterfaceLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'interface_link', 'order_link', 'timestamp', 'status_colored', 'message_short', 'attempt_count')
    list_filter = ('status', 'timestamp', 'interface__supplier', 'interface__interface_type')
    search_fields = ('message', 'interface__name', 'order__order_number')
    readonly_fields = ('interface', 'order', 'timestamp', 'status', 'message', 'request_data', 
                      'response_data', 'initiated_by', 'attempt_count')
    date_hierarchy = 'timestamp'
    fieldsets = (
        (None, {
            'fields': ('interface', 'order', 'timestamp', 'status', 'initiated_by', 'attempt_count')
        }),
        (_('Nachricht'), {
            'fields': ('message',),
        }),
        (_('Datenübertragung'), {
            'fields': ('request_data', 'response_data'),
            'classes': ('collapse',),
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def interface_link(self, obj):
        url = reverse('admin:interfaces_supplierinterface_change', args=[obj.interface.id])
        return format_html('<a href="{}">{}</a>', url, obj.interface.name)
    interface_link.short_description = _('Schnittstelle')
    
    def order_link(self, obj):
        url = reverse('admin:order_purchaseorder_change', args=[obj.order.id])
        return format_html('<a href="{}">{}</a>', url, obj.order.order_number)
    order_link.short_description = _('Bestellung')
    
    def message_short(self, obj):
        if not obj.message:
            return "-"
        return obj.message[:50] + "..." if len(obj.message) > 50 else obj.message
    message_short.short_description = _('Nachricht')
    
    def status_colored(self, obj):
        colors = {
            'pending': '#FFA500',      # Orange
            'in_progress': '#1E90FF',  # Blue
            'success': '#32CD32',      # Green
            'failed': '#FF0000',       # Red
            'retry': '#9370DB'         # Purple
        }
        return format_html(
            '<span style="color: {};">{}</span>',
            colors.get(obj.status, 'black'),
            obj.get_status_display()
        )
    status_colored.short_description = _('Status')
    
    def get_queryset(self, request):
        return super().get_queryset(request).select_related('interface', 'order', 'initiated_by')


@admin.register(XMLStandardTemplate)
class XMLStandardTemplateAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'industry', 'version', 'is_active')
    list_filter = ('is_active', 'industry')
    search_fields = ('name', 'code', 'description', 'industry')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('name', 'code', 'is_active')
        }),
        (_('Metadaten'), {
            'fields': ('industry', 'version', 'description')
        }),
        (_('XML-Vorlage'), {
            'fields': ('template',),
            'classes': ('wide',)
        }),
        (_('System-Informationen'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )

    def save_model(self, request, obj, form, change):
        """Stellt sicher, dass die Vorlage wohlgeformtes XML ist"""
        import xml.dom.minidom
        from django.core.exceptions import ValidationError

        try:
            # Versuchen, das XML zu parsen
            xml_template = obj.template.strip()
            if xml_template:
                xml.dom.minidom.parseString(xml_template)
        except Exception as e:
            # Fehlermeldung für ungültiges XML
            raise ValidationError(f"Die XML-Vorlage ist nicht wohlgeformt: {str(e)}")

        super().save_model(request, obj, form, change)