from django import forms
from django.contrib.auth.models import User

from .models import StockMovement, StockTake, StockTakeItem, Department, Warehouse, WarehouseAccess
from core.models import Product
from .utils import user_has_warehouse_access


class StockMovementForm(forms.ModelForm):
    """Form for creating stock movements."""

    class Meta:
        model = StockMovement
        fields = ['product', 'quantity', 'movement_type', 'reference', 'notes', 'warehouse']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Dropdown für die Produktauswahl mit aktuellen Beständen
        self.fields['product'].queryset = Product.objects.all().order_by('name')
        self.fields['product'].label_from_instance = lambda obj: f"{obj.name} (Bestand: {obj.current_stock} {obj.unit})"

        # Tooltips für die Felder
        self.fields['quantity'].help_text = "Anzahl der Einheiten für diese Bewegung"
        self.fields['reference'].help_text = "Optionale Referenz (z.B. Lieferschein-Nr., Rechnung-Nr.)"
        self.fields['notes'].help_text = "Weitere Informationen zu dieser Bewegung"


class StockTakeForm(forms.ModelForm):
    """Form for creating and updating stock takes."""

    class Meta:
        model = StockTake
        fields = [
            'name', 'description', 'notes', 'warehouse',
            'inventory_type', 'display_expected_quantity',
            'cycle_count_category', 'count_frequency'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['name'].widget.attrs.update({'class': 'form-control'})
        self.fields['description'].widget.attrs.update({'class': 'form-control', 'rows': 3})
        self.fields['notes'].widget.attrs.update({'class': 'form-control', 'rows': 3})
        self.fields['inventory_type'].widget.attrs.update({'class': 'form-select'})
        self.fields['display_expected_quantity'].widget.attrs.update({'class': 'form-check-input'})
        self.fields['cycle_count_category'].widget.attrs.update({'class': 'form-select'})
        self.fields['count_frequency'].widget.attrs.update({'class': 'form-control'})

        # Dynamisches Anzeigen der Felder je nach Inventurtyp mit JavaScript
        self.fields['cycle_count_category'].widget.attrs['data-inventory-type'] = 'rolling'
        self.fields['count_frequency'].widget.attrs['data-inventory-type'] = 'rolling'


class StockTakeItemForm(forms.ModelForm):
    """Form for updating stock take items."""

    class Meta:
        model = StockTakeItem
        fields = ['counted_quantity', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['counted_quantity'].widget.attrs.update({'class': 'form-control counted-qty'})
        self.fields['notes'].widget.attrs.update(
            {'class': 'form-control', 'rows': 2, 'placeholder': 'Optionale Anmerkungen'})

    def clean_counted_quantity(self):
        counted_quantity = self.cleaned_data.get('counted_quantity')
        if counted_quantity is not None and counted_quantity < 0:
            raise forms.ValidationError("Die gezählte Menge kann nicht negativ sein.")
        return counted_quantity


class StockTakeFilterForm(forms.Form):
    """Form for filtering stock takes."""
    status = forms.ChoiceField(
        choices=[('', 'Alle Status')] + list(StockTake.STATUS_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    inventory_type = forms.ChoiceField(  # Neues Feld
        choices=[('', 'Alle Typen')] + [
            ('full', 'Komplettinventur'),
            ('rolling', 'Rollierende Inventur'),
            ('blind', 'Blindzählung'),
            ('sample', 'Stichprobeninventur'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.filter(is_active=True),
        required=False,
        empty_label="Alle Lager",
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
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Suchen...'})
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        # Lagerauswahl basierend auf Benutzerberechtigungen einschränken
        if user and not user.is_superuser:
            accessible_warehouses = [w.id for w in Warehouse.objects.filter(is_active=True)
                                   if user_has_warehouse_access(user, w, 'view')]
            self.fields['warehouse'].queryset = Warehouse.objects.filter(id__in=accessible_warehouses)


class StockTakeItemBulkUpdateForm(forms.Form):
    """Form for bulk updating multiple stock take items at once."""
    product_ids = forms.CharField(widget=forms.HiddenInput())
    stock_take_id = forms.IntegerField(widget=forms.HiddenInput())

    def clean_product_ids(self):
        product_ids_str = self.cleaned_data.get('product_ids')
        try:
            product_ids = [int(id) for id in product_ids_str.split(',') if id.strip()]
            if not product_ids:
                raise forms.ValidationError("Keine Produkte ausgewählt.")
            return product_ids
        except ValueError:
            raise forms.ValidationError("Ungültige Produkt-IDs.")


# In inventory/forms.py

class DepartmentForm(forms.ModelForm):
    """Form für die Erstellung und Bearbeitung von Abteilungen."""
    class Meta:
        model = Department
        fields = ['name', 'code', 'manager', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'manager': forms.Select(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class WarehouseForm(forms.ModelForm):
    class Meta:
        model = Warehouse
        fields = ['name', 'location', 'description', 'is_active']


class WarehouseAccessForm(forms.ModelForm):
    class Meta:
        model = WarehouseAccess
        fields = ['warehouse', 'department', 'can_view', 'can_edit', 'can_manage_stock']