from django import forms

from inventory.models import Warehouse
from product_management.models.products import ProductVariant, \
    Product
from tracking.models import SerialNumber, BatchNumber


class SerialNumberForm(forms.ModelForm):
    """Form for adding and updating serial numbers."""

    class Meta:
        model = SerialNumber
        fields = ['serial_number', 'status', 'warehouse', 'purchase_date',
                  'expiry_date', 'notes', 'variant']
        widgets = {
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'warehouse': forms.Select(attrs={'class': 'form-select'}),
            'purchase_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'variant': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        product = kwargs.pop('product', None)
        super().__init__(*args, **kwargs)

        if product:
            self.fields['variant'].queryset = ProductVariant.objects.filter(parent_product=product)


class BatchNumberForm(forms.ModelForm):
    """Form for adding and updating batch numbers."""
    product = forms.ModelChoiceField(
        queryset=Product.objects.all(),
        label="Produkt",
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    class Meta:
        model = BatchNumber
        fields = ['batch_number', 'quantity', 'production_date', 'expiry_date',
                  'supplier', 'warehouse', 'notes', 'variant']
        widgets = {
            'batch_number': forms.TextInput(attrs={'class': 'form-control'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'production_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'warehouse': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'variant': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        product = kwargs.pop('product', None)
        super().__init__(*args, **kwargs)

        if product:
            self.fields['variant'].queryset = ProductVariant.objects.filter(parent_product=product)


class BulkSerialNumberForm(forms.Form):
    """Form for adding multiple serial numbers at once."""

    prefix = forms.CharField(
        required=False,
        max_length=50,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optionales Präfix'})
    )
    start_number = forms.IntegerField(
        min_value=1,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    count = forms.IntegerField(
        min_value=1,
        max_value=1000,
        initial=10,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    digits = forms.IntegerField(
        min_value=1,
        max_value=10,
        initial=6,
        help_text="Anzahl der Stellen für die Nummerierung (mit führenden Nullen)",
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    status = forms.ChoiceField(
        choices=SerialNumber.status_choices,
        initial='in_stock',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.filter(is_active=True),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    purchase_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    expiry_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    variant = forms.ModelChoiceField(
        queryset=ProductVariant.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        product = kwargs.pop('product', None)
        super().__init__(*args, **kwargs)

        if product:
            self.fields['variant'].queryset = ProductVariant.objects.filter(parent_product=product)


