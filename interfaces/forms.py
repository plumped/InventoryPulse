from django import forms
from django.utils.translation import gettext_lazy as _

from order.models import PurchaseOrder
from suppliers.models import Supplier
from .models import InterfaceLog, InterfaceType, SupplierInterface


from django import forms
from django.utils.translation import gettext_lazy as _
from suppliers.models import Supplier
from interfaces.models import InterfaceType
from .models import SupplierInterface

class SupplierInterfaceForm(forms.ModelForm):
    """Formular für Lieferantenschnittstellen."""
    
    class Meta:
        model = SupplierInterface
        fields = [
            'supplier', 'name', 'interface_type', 'is_active', 'is_default',
            'api_url', 'username', 'password', 'api_key',
            'host', 'port', 'remote_path',
            'email_to', 'email_cc', 'email_subject_template',
            'order_format', 'template', 'config_json'
        ]
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select', 'id': 'id_supplier'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'interface_type': forms.Select(attrs={'class': 'form-select', 'id': 'id_interface_type'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'api_url': forms.URLInput(attrs={'class': 'form-control', 'id': 'id_api_url'}),
            'username': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_username_dynamic'}),
            'password': forms.PasswordInput(attrs={'class': 'form-control', 'id': 'id_password_dynamic', 'autocomplete': 'new-password'}),
            'api_key': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_api_key'}),
            'host': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_host'}),
            'port': forms.NumberInput(attrs={'class': 'form-control', 'id': 'id_port'}),
            'remote_path': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_remote_path'}),
            'email_to': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_email_to'}),
            'email_cc': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_email_cc'}),
            'email_subject_template': forms.TextInput(attrs={'class': 'form-control', 'id': 'id_email_subject_template'}),
            'order_format': forms.Select(attrs={'class': 'form-select', 'id': 'id_order_format'}),
            'template': forms.Textarea(attrs={'class': 'form-control', 'rows': 10, 'id': 'id_template'}),
            'config_json': forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'id': 'id_config_json'}),
        }
        help_texts = {
            'api_url': _('Die URL der API, z.B. https://api.lieferant.de/orders'),
            'username': _('Benutzername für die API/FTP-Authentifizierung'),
            'password': _('Passwort für die API/FTP-Authentifizierung'),
            'api_key': _('API-Schlüssel für die Authentifizierung'),
            'host': _('Hostname des FTP/SFTP-Servers'),
            'port': _('Port des FTP/SFTP-Servers (Standard: 21 für FTP, 22 für SFTP)'),
            'remote_path': _('Pfad auf dem Remote-Server, z.B. /orders'),
            'email_to': _('Empfänger-E-Mail-Adressen, durch Kommas getrennt'),
            'email_cc': _('CC-E-Mail-Adressen, durch Kommas getrennt'),
            'email_subject_template': _('Betreff der E-Mail, {order_number} wird durch die Bestellnummer ersetzt'),
            'order_format': _('Format der Bestelldaten'),
            'template': _('Vorlage für die Formatierung der Bestelldaten (z.B. XML-Template)'),
            'config_json': _('Zusätzliche Konfigurationsdaten im JSON-Format'),
            'is_default': _('Diese Schnittstelle als Standard für diesen Lieferanten verwenden'),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Sortieren der Dropdown-Felder
        self.fields['supplier'].queryset = Supplier.objects.all().order_by('name')
        self.fields['interface_type'].queryset = InterfaceType.objects.filter(is_active=True).order_by('name')
        
        # Alle Felder optional machen, Validierung erfolgt später je nach Schnittstellentyp
        for field_name in self.fields:
            if field_name not in ['supplier', 'name', 'interface_type']:
                self.fields[field_name].required = False
        
        # Initial-Port basierend auf Schnittstellentyp
        instance = kwargs.get('instance')
        if instance and instance.interface_type:
            if instance.interface_type.code.lower() == 'ftp' and not instance.port:
                self.initial['port'] = 21
            elif instance.interface_type.code.lower() == 'sftp' and not instance.port:
                self.initial['port'] = 22
    
    def clean_config_json(self):
        """Validiert das JSON-Format."""
        config_json = self.cleaned_data.get('config_json')
        if config_json:
            try:
                import json
                json.loads(config_json)
            except ValueError:
                raise forms.ValidationError(_('Ungültiges JSON-Format'))
        return config_json
    
    def clean(self):
        """Validiert, dass die erforderlichen Felder je nach Schnittstellentyp ausgefüllt sind."""
        cleaned_data = super().clean()
        interface_type = cleaned_data.get('interface_type')
        
        if interface_type:
            type_code = interface_type.code.lower()
            
            # E-Mail-Schnittstelle validieren
            if type_code == 'email':
                email_to = cleaned_data.get('email_to')
                if not email_to:
                    self.add_error('email_to', _('Für E-Mail-Schnittstellen ist mindestens ein Empfänger erforderlich'))
            
            # API-Schnittstelle validieren
            elif type_code == 'api':
                api_url = cleaned_data.get('api_url')
                if not api_url:
                    self.add_error('api_url', _('Für API-Schnittstellen ist eine URL erforderlich'))
            
            # FTP-Schnittstelle validieren
            elif type_code in ['ftp', 'sftp']:
                host = cleaned_data.get('host')
                username = cleaned_data.get('username')
                password = cleaned_data.get('password')
                
                if not host:
                    self.add_error('host', _('Für FTP/SFTP-Schnittstellen ist ein Host erforderlich'))
                
                if not username:
                    self.add_error('username', _('Für FTP/SFTP-Schnittstellen ist ein Benutzername erforderlich'))
                
                # Nur beim Neuanlegen prüfen, ob ein Passwort angegeben ist
                instance = getattr(self, 'instance', None)
                is_new = not instance or not instance.pk
                
                if is_new and not password:
                    self.add_error('password', _('Für neue FTP/SFTP-Schnittstellen ist ein Passwort erforderlich'))
        
        return cleaned_data


class InterfaceTestForm(forms.Form):
    """Formular zum Testen einer Schnittstelle."""
    
    order = forms.ModelChoiceField(
        queryset=PurchaseOrder.objects.none(),
        label=_('Bestellung'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        supplier_id = kwargs.pop('supplier_id', None)
        super().__init__(*args, **kwargs)
        
        # Bestellungen für diesen Lieferanten
        if supplier_id:
            self.fields['order'].queryset = PurchaseOrder.objects.filter(
                supplier_id=supplier_id,
                status__in=['approved', 'sent', 'partially_received']
            ).order_by('-order_date')


class InterfaceFilterForm(forms.Form):
    """Formular zum Filtern von Schnittstellen."""
    
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_active=True),
        required=False,
        empty_label=_('Alle Lieferanten'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    interface_type = forms.ModelChoiceField(
        queryset=InterfaceType.objects.filter(is_active=True),
        required=False,
        empty_label=_('Alle Typen'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    status = forms.ChoiceField(
        choices=[
            ('', _('Alle')),
            ('active', _('Aktiv')),
            ('inactive', _('Inaktiv')),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Suchen...')})
    )


class InterfaceLogFilterForm(forms.Form):
    """Formular zum Filtern von Übertragungsprotokollen."""
    
    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_active=True),
        required=False,
        empty_label=_('Alle Lieferanten'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    interface = forms.ModelChoiceField(
        queryset=SupplierInterface.objects.filter(is_active=True),
        required=False,
        empty_label=_('Alle Schnittstellen'),
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    status = forms.ChoiceField(
        choices=[
            ('', _('Alle Status')),
        ] + list(InterfaceLog.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': _('Suchen...')})
    )
    
    def __init__(self, *args, **kwargs):
        supplier_id = kwargs.pop('supplier_id', None)
        super().__init__(*args, **kwargs)
        
        # Wenn ein Lieferant ausgewählt ist, nur Schnittstellen dieses Lieferanten anzeigen
        if supplier_id:
            self.fields['interface'].queryset = SupplierInterface.objects.filter(
                supplier_id=supplier_id,
                is_active=True
            ).order_by('name')