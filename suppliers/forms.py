from django import forms
from .models import Supplier, SupplierProduct
from core.models import Product


class SupplierForm(forms.ModelForm):
    """Form for creating and updating suppliers."""

    class Meta:
        model = Supplier
        fields = ['name', 'contact_person', 'email', 'phone', 'address',
                  'shipping_cost', 'minimum_order_value']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'shipping_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'minimum_order_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
        }

    def clean_name(self):
        """Ensure supplier name is unique."""
        name = self.cleaned_data.get('name')
        instance = getattr(self, 'instance', None)

        # Bei Update: Prüfen, ob der Name bereits verwendet wird (außer bei diesem Lieferanten)
        if instance and instance.pk:
            qs = Supplier.objects.filter(name=name).exclude(pk=instance.pk)
        # Bei Create: Prüfen, ob der Name bereits verwendet wird
        else:
            qs = Supplier.objects.filter(name=name)

        if qs.exists():
            raise forms.ValidationError('Ein Lieferant mit diesem Namen existiert bereits.')

        return name


class SupplierProductForm(forms.ModelForm):
    """Form for linking products to suppliers."""

    class Meta:
        model = SupplierProduct
        fields = ['supplier', 'product', 'supplier_sku', 'purchase_price',
                  'lead_time_days', 'is_preferred', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Sortierung der Dropdown-Listen
        self.fields['supplier'].queryset = Supplier.objects.all().order_by('name')
        self.fields['product'].queryset = Product.objects.all().order_by('name')

        # Labels und Hilfe-Texte
        self.fields['supplier_sku'].label = "Artikelnummer des Lieferanten"
        self.fields['supplier_sku'].help_text = "Die Artikelnummer, unter der der Lieferant das Produkt führt"
        self.fields['purchase_price'].label = "Einkaufspreis"
        self.fields['lead_time_days'].label = "Lieferzeit (Tage)"
        self.fields['is_preferred'].label = "Bevorzugter Lieferant"
        self.fields[
            'is_preferred'].help_text = "Markieren Sie diese Option, wenn dies der bevorzugte Lieferant für dieses Produkt ist"

    def clean(self):
        """Ensure the supplier-product combination is unique."""
        cleaned_data = super().clean()
        supplier = cleaned_data.get('supplier')
        product = cleaned_data.get('product')

        if supplier and product:
            instance = getattr(self, 'instance', None)

            # Bei Update: Prüfen, ob die Kombination bereits existiert (außer bei dieser Zuordnung)
            if instance and instance.pk:
                qs = SupplierProduct.objects.filter(supplier=supplier, product=product).exclude(pk=instance.pk)
            # Bei Create: Prüfen, ob die Kombination bereits existiert
            else:
                qs = SupplierProduct.objects.filter(supplier=supplier, product=product)

            if qs.exists():
                raise forms.ValidationError(
                    'Dieser Lieferant bietet dieses Produkt bereits an. Bitte aktualisieren Sie den bestehenden Eintrag.'
                )

        return cleaned_data