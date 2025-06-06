from decimal import Decimal

from django import forms
from django.core.exceptions import ValidationError
from django.forms.formsets import formset_factory
from django.utils import timezone

from suppliers.models import Supplier
from inventory.models import Warehouse

from .models import PurchaseOrder, PurchaseOrderReceipt, OrderSplit


class PurchaseOrderForm(forms.ModelForm):
    class Meta:
        model = PurchaseOrder
        fields = ['supplier', 'expected_delivery', 'shipping_address', 'billing_address', 'notes']
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select', 'required': True}),
            'expected_delivery': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'shipping_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'billing_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
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


class OrderSplitForm(forms.ModelForm):
    """Form for creating and editing order splits."""

    class Meta:
        model = OrderSplit
        fields = ['name', 'expected_delivery', 'carrier', 'tracking_number', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'expected_delivery': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'carrier': forms.TextInput(attrs={'class': 'form-control'}),
            'tracking_number': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Set default expected delivery date to one week in the future if it's a new instance
        if not self.instance.pk and not self.initial.get('expected_delivery'):
            self.initial['expected_delivery'] = (timezone.now() + timezone.timedelta(days=7)).date()


class OrderSplitItemForm(forms.Form):
    """Form for managing individual items in an order split."""

    item_id = forms.IntegerField(widget=forms.HiddenInput())
    product_name = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True}))
    product_sku = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True}))
    total_quantity = forms.DecimalField(widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True}))
    remaining_quantity = forms.DecimalField(widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True}))
    unit = forms.CharField(widget=forms.TextInput(attrs={'class': 'form-control', 'readonly': True}))
    split_quantity = forms.DecimalField(
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        required=False
    )

    def clean_split_quantity(self):
        """Validate that split quantity is not more than remaining quantity."""
        split_quantity = self.cleaned_data.get('split_quantity') or Decimal('0')
        remaining_quantity = self.cleaned_data.get('remaining_quantity')

        if split_quantity > remaining_quantity:
            raise ValidationError(
                f"Die Menge kann nicht größer sein als die verbleibende Menge ({remaining_quantity}).")

        if split_quantity < 0:
            raise ValidationError("Die Menge kann nicht negativ sein.")

        return split_quantity


OrderSplitItemFormSet = formset_factory(OrderSplitItemForm, extra=0)