from django import forms
from django.utils import timezone

from suppliers.models import Supplier
from inventory.models import Warehouse

from .models import PurchaseOrder, PurchaseOrderReceipt


class PurchaseOrderForm(forms.ModelForm):
    """Formular für das Erstellen und Bearbeiten von Bestellungen."""

    class Meta:
        model = PurchaseOrder
        fields = ['supplier', 'expected_delivery', 'shipping_address', 'notes']
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'expected_delivery': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'shipping_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Nur aktive Lieferanten anzeigen
        self.fields['supplier'].queryset = Supplier.objects.filter(is_active=True).order_by('name')

        # Vorausgefüllter Wert für expected_delivery (1 Woche in der Zukunft)
        if not self.instance.pk and not self.initial.get('expected_delivery'):
            self.initial['expected_delivery'] = (timezone.now() + timezone.timedelta(days=7)).date()


class ReceiveOrderForm(forms.Form):
    """Formular für die Erfassung von Wareneingängen."""

    notes = forms.CharField(
        label="Anmerkungen",
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=False
    )

    def __init__(self, *args, **kwargs):
        self.order = kwargs.pop('order', None)
        super().__init__(*args, **kwargs)

        # Dynamisch Felder für jede Bestellposition hinzufügen
        if self.order:
            for item in self.order.items.all():
                # Restmenge berechnen
                remaining = item.quantity_ordered - item.quantity_received

                # Feld für empfangene Menge
                self.fields[f'receive_quantity_{item.id}'] = forms.DecimalField(
                    label=f"Empfangene Menge für {item.product.name}",
                    min_value=0,
                    max_value=remaining,
                    initial=remaining,  # Standardwert: Restmenge
                    widget=forms.NumberInput(attrs={
                        'class': 'form-control',
                        'step': '0.01',
                        'data-max': str(remaining)
                    })
                )

                # Feld für Ziel-Lager
                self.fields[f'warehouse_{item.id}'] = forms.ModelChoiceField(
                    label=f"Ziellager für {item.product.name}",
                    queryset=Warehouse.objects.filter(is_active=True),
                    widget=forms.Select(attrs={'class': 'form-select'})
                )

                # Chargen-Tracking, falls erforderlich
                if item.product.has_batch_tracking:
                    self.fields[f'batch_{item.id}'] = forms.CharField(
                        label=f"Chargennummer für {item.product.name}",
                        required=True,
                        widget=forms.TextInput(attrs={'class': 'form-control'})
                    )

                # Verfallsdatum, falls erforderlich
                if item.product.has_expiry_tracking:
                    self.fields[f'expiry_{item.id}'] = forms.DateField(
                        label=f"Verfallsdatum für {item.product.name}",
                        required=True,
                        widget=forms.DateInput(attrs={
                            'class': 'form-control',
                            'type': 'date',
                            'min': timezone.now().date().isoformat()
                        })
                    )


class OrderFilterForm(forms.Form):
    """Formular zum Filtern von Bestellungen."""

    status = forms.ChoiceField(
        label="Status",
        choices=[('', 'Alle Status')] + list(PurchaseOrder.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    supplier = forms.ModelChoiceField(
        label="Lieferant",
        queryset=Supplier.objects.filter(is_active=True),
        required=False,
        empty_label="Alle Lieferanten",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    date_from = forms.DateField(
        label="Von",
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

    date_to = forms.DateField(
        label="Bis",
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )

    search = forms.CharField(
        label="Suche",
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Bestellnummer, Lieferant...'})
    )