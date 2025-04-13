from datetime import timedelta

from django import forms
from django.forms.models import inlineformset_factory
from django.utils import timezone
from django_select2 import forms as s2forms

from master_data.models.currency import Currency
from product_management.models.products import Product
from .models import Supplier, SupplierProduct, SupplierPerformance, SupplierPerformanceMetric, SupplierContact, \
    SupplierAddress


class SupplierAddressForm(forms.ModelForm):
    """Form für Lieferantenadressen."""

    class Meta:
        model = SupplierAddress
        fields = ['address_type', 'is_default', 'name', 'street', 'street_number', 'postal_code',
                  'city', 'state', 'country', 'notes']
        widgets = {
            'address_type': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'street': forms.TextInput(attrs={'class': 'form-control'}),
            'street_number': forms.TextInput(attrs={'class': 'form-control'}),
            'postal_code': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'state': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('is_default'):
            # Prüfen, ob bereits eine Standardadresse für diesen Typ existiert
            supplier = self.instance.supplier if self.instance.pk else self.initial.get('supplier')
            address_type = cleaned_data.get('address_type')

            if supplier and address_type:
                existing_default = SupplierAddress.objects.filter(
                    supplier=supplier,
                    address_type=address_type,
                    is_default=True
                )

                if self.instance.pk:
                    existing_default = existing_default.exclude(pk=self.instance.pk)

                if existing_default.exists():
                    # Keine Validierung auslösen, später wird die alte Standardadresse aktualisiert
                    pass

        return cleaned_data


class SupplierContactForm(forms.ModelForm):
    """Form für Lieferantenkontakte."""

    class Meta:
        model = SupplierContact
        fields = ['contact_type', 'is_default', 'title', 'first_name', 'last_name',
                  'position', 'email', 'phone', 'mobile', 'notes']
        widgets = {
            'contact_type': forms.Select(attrs={'class': 'form-select'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'position': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'mobile': forms.TextInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('is_default'):
            # Prüfen, ob bereits ein Standardkontakt für diesen Typ existiert
            supplier = self.instance.supplier if self.instance.pk else self.initial.get('supplier')
            contact_type = cleaned_data.get('contact_type')

            if supplier and contact_type:
                existing_default = SupplierContact.objects.filter(
                    supplier=supplier,
                    contact_type=contact_type,
                    is_default=True
                )

                if self.instance.pk:
                    existing_default = existing_default.exclude(pk=self.instance.pk)

                if existing_default.exists():
                    # Keine Validierung auslösen, später wird der alte Standardkontakt aktualisiert
                    pass

        return cleaned_data

class SupplierForm(forms.ModelForm):
    """Form for creating and updating suppliers."""

    class Meta:
        model = Supplier
        fields = ['name', 'contact_person', 'email', 'phone', 'address',
                  'shipping_cost', 'minimum_order_value', 'default_currency']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'shipping_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'minimum_order_value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'default_currency': forms.Select(attrs={'class': 'form-select'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Währungen nach Code sortieren
        self.fields['default_currency'].queryset = Currency.objects.filter(is_active=True).order_by('code')

        # Wenn keine Standardwährung gesetzt ist (neue Instanz), setze die Systemstandardwährung
        if not self.instance.pk:
            default_currency = Currency.get_default_currency()
            if default_currency:
                self.initial['default_currency'] = default_currency

        # Hinweis für veraltete Felder hinzufügen
        self.fields[
            'contact_person'].help_text = "Veraltet - Bitte verwenden Sie stattdessen das Kontaktpersonen-Modell"
        self.fields['email'].help_text = "Veraltet - Bitte verwenden Sie stattdessen das Kontaktpersonen-Modell"
        self.fields['phone'].help_text = "Veraltet - Bitte verwenden Sie stattdessen das Kontaktpersonen-Modell"
        self.fields['address'].help_text = "Veraltet - Bitte verwenden Sie stattdessen das Adressen-Modell"

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


# Formset für Lieferantenadressen
SupplierAddressFormSet = inlineformset_factory(
    Supplier,
    SupplierAddress,
    form=SupplierAddressForm,
    extra=1,
    can_delete=True
)

# Formset für Lieferantenkontakte
SupplierContactFormSet = inlineformset_factory(
    Supplier,
    SupplierContact,
    form=SupplierContactForm,
    extra=1,
    can_delete=True
)


# Widget für die Produktsuche
class ProductWidget(s2forms.ModelSelect2Widget):
    search_fields = [
        'name__icontains',
        'sku__icontains',
    ]

    def get_queryset(self):
        return Product.objects.all().order_by('name')

    def label_from_instance(self, obj):
        return f"{obj.name} (SKU: {obj.sku})"


class SupplierProductForm(forms.ModelForm):
    """Form for linking products to suppliers."""

    class Meta:
        model = SupplierProduct
        fields = ['supplier', 'product', 'supplier_sku', 'purchase_price',
                  'currency', 'lead_time_days', 'is_preferred', 'notes']
        widgets = {
            'product': ProductWidget(attrs={
                'data-placeholder': 'Nach Produktname oder SKU suchen...',
                'data-minimum-input-length': 2,
                'class': 'form-select select2-widget',
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Sortierung der Dropdown-Listen
        self.fields['supplier'].queryset = Supplier.objects.all().order_by('name')
        self.fields['product'].queryset = Product.objects.all().order_by('name')

        # Currency field - abweichende Währung ist optional
        self.fields['currency'].queryset = Currency.objects.filter(is_active=True).order_by('code')
        self.fields[
            'currency'].required = False  # Wichtig: Nicht erforderlich, da die Lieferantenwährung verwendet wird

        # Wenn ein vorausgewählter Lieferant existiert oder ein bestehender Datensatz bearbeitet wird,
        # versuche die Standardwährung des Lieferanten zu ermitteln
        supplier = None
        if 'supplier' in self.initial:
            try:
                supplier = Supplier.objects.get(pk=self.initial['supplier'])
            except Supplier.DoesNotExist:
                pass
        elif self.instance.pk:
            supplier = self.instance.supplier

        # Standardwährung des Lieferanten ermitteln
        if supplier and supplier.default_currency:
            # Das Feld currency bleibt leer (None), damit die Standardwährung des Lieferanten verwendet wird
            # Das Formular zeigt aber eine Beschreibung an, welche Währung verwendet wird
            self.fields[
                'currency'].help_text = f"Optional. Standardmäßig wird die Währung des Lieferanten verwendet: {supplier.default_currency.name} ({supplier.default_currency.code})"

        # Labels und Hilfe-Texte
        self.fields['supplier_sku'].label = "Artikelnummer des Lieferanten"
        self.fields['supplier_sku'].help_text = "Die Artikelnummer, unter der der Lieferant das Produkt führt"
        self.fields['purchase_price'].label = "Einkaufspreis"
        self.fields['currency'].label = "Abweichende Währung"
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



class DateRangeForm(forms.Form):
    """Form for selecting a date range for performance analysis."""
    start_date = forms.DateField(
        label="Start Date",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=True,
        initial=lambda: (timezone.now().date() - timedelta(days=90))
    )

    end_date = forms.DateField(
        label="End Date",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=True,
        initial=timezone.now().date
    )

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')

        if start_date and end_date and start_date > end_date:
            self.add_error('start_date', "Start date cannot be after end date")

        return cleaned_data


class SupplierPerformanceForm(forms.ModelForm):
    """Form for manually entering supplier performance data."""

    class Meta:
        model = SupplierPerformance
        fields = ['metric', 'value', 'evaluation_date', 'notes',
                  'evaluation_period_start', 'evaluation_period_end']
        widgets = {
            'metric': forms.Select(attrs={'class': 'form-select'}),
            'value': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'evaluation_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'evaluation_period_start': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'evaluation_period_end': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Only show active metrics
        self.fields['metric'].queryset = SupplierPerformanceMetric.objects.filter(is_active=True)

        # Set initial values for dates
        if not self.instance.pk:
            self.fields['evaluation_date'].initial = timezone.now().date()

            # Set initial period as the last month
            today = timezone.now().date()
            self.fields['evaluation_period_end'].initial = today
            self.fields['evaluation_period_start'].initial = today.replace(day=1)

    def clean(self):
        cleaned_data = super().clean()
        period_start = cleaned_data.get('evaluation_period_start')
        period_end = cleaned_data.get('evaluation_period_end')

        if period_start and period_end and period_start > period_end:
            self.add_error('evaluation_period_start', "Period start date cannot be after end date")

        return cleaned_data


class SupplierPerformanceMetricForm(forms.ModelForm):
    """Form for creating and editing performance metrics."""

    class Meta:
        model = SupplierPerformanceMetric
        fields = ['name', 'code', 'description', 'metric_type', 'weight',
                  'target_value', 'minimum_value', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'metric_type': forms.Select(attrs={'class': 'form-select'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '10'}),
            'target_value': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'minimum_value': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_code(self):
        code = self.cleaned_data.get('code')
        if code:
            # Convert code to lowercase with underscores for consistency
            code = code.lower().replace(' ', '_')

            # Check if code is unique (excluding this instance for updates)
            instance = getattr(self, 'instance', None)
            if instance and instance.pk:
                if SupplierPerformanceMetric.objects.filter(code=code).exclude(pk=instance.pk).exists():
                    raise forms.ValidationError("This code is already in use")
            else:
                if SupplierPerformanceMetric.objects.filter(code=code).exists():
                    raise forms.ValidationError("This code is already in use")

        return code

    def clean(self):
        cleaned_data = super().clean()
        minimum = cleaned_data.get('minimum_value')
        target = cleaned_data.get('target_value')

        if minimum is not None and target is not None and minimum > target:
            self.add_error('minimum_value', "Minimum value cannot be greater than target value")

        return cleaned_data


# Create a formset for multiple performance metrics
SupplierPerformanceFormSet = inlineformset_factory(
    Supplier,  # Parent model
    SupplierPerformance,  # Child model
    form=SupplierPerformanceForm,
    extra=1,  # Number of empty forms to display
    can_delete=True,  # Allow deleting performances
    max_num=10  # Maximum number of forms
)


