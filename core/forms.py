from django import forms

from inventory.models import Warehouse
from .models import Product, Category, ProductVariant, SerialNumber, BatchNumber, ProductVariantType, ProductAttachment, \
    ProductPhoto


class ProductForm(forms.ModelForm):
    """Form for creating and updating products."""
    initial_stock = forms.DecimalField(
        label="Anfangsbestand",
        required=False,
        initial=0,
        min_value=0,
        help_text="Nur bei Neuanlage: Anfänglicher Lagerbestand"
    )

    class Meta:
        model = Product
        fields = ['name', 'sku', 'barcode', 'description', 'category',
                  'minimum_stock', 'unit',
                  'has_variants', 'has_serial_numbers', 'has_batch_tracking', 'has_expiry_tracking']

        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'has_variants': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'has_serial_numbers': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'has_batch_tracking': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'has_expiry_tracking': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_sku(self):
        """Ensure SKU is unique."""
        sku = self.cleaned_data.get('sku')
        instance = getattr(self, 'instance', None)

        # Bei Update: Prüfen, ob die SKU bereits verwendet wird (außer bei diesem Produkt)
        if instance and instance.pk:
            qs = Product.objects.filter(sku=sku).exclude(pk=instance.pk)
        # Bei Create: Prüfen, ob die SKU bereits verwendet wird
        else:
            qs = Product.objects.filter(sku=sku)

        if qs.exists():
            raise forms.ValidationError('Diese Artikelnummer wird bereits verwendet.')

        return sku

    def clean_barcode(self):
        """Ensure barcode is unique if provided."""
        barcode = self.cleaned_data.get('barcode')

        # Wenn kein Barcode angegeben wurde, ist das OK
        if not barcode:
            return barcode

        instance = getattr(self, 'instance', None)

        # Bei Update: Prüfen, ob der Barcode bereits verwendet wird (außer bei diesem Produkt)
        if instance and instance.pk:
            qs = Product.objects.filter(barcode=barcode).exclude(pk=instance.pk)
        # Bei Create: Prüfen, ob der Barcode bereits verwendet wird
        else:
            qs = Product.objects.filter(barcode=barcode)

        if qs.exists():
            raise forms.ValidationError('Dieser Barcode wird bereits verwendet.')

        return barcode


class CategoryForm(forms.ModelForm):
    """Form for creating and updating categories."""

    class Meta:
        model = Category
        fields = ['name', 'description']

    def clean_name(self):
        """Ensure category name is unique."""
        name = self.cleaned_data.get('name')
        instance = getattr(self, 'instance', None)

        # Bei Update: Prüfen, ob der Name bereits verwendet wird (außer bei dieser Kategorie)
        if instance and instance.pk:
            qs = Category.objects.filter(name=name).exclude(pk=instance.pk)
        # Bei Create: Prüfen, ob der Name bereits verwendet wird
        else:
            qs = Category.objects.filter(name=name)

        if qs.exists():
            raise forms.ValidationError('Diese Kategorie existiert bereits.')

        return name


class ImportForm(forms.Form):
    """Base form for import operations."""

    file = forms.FileField(label="CSV-Datei",
                           help_text="Wählen Sie eine CSV-Datei zum Import aus.")
    delimiter = forms.ChoiceField(
        label="Trennzeichen",
        choices=[
            (',', 'Komma (,)'),
            (';', 'Semikolon (;)'),
            ('\t', 'Tab'),
            ('|', 'Pipe (|)'),
        ],
        initial=';',
        help_text="Wählen Sie das Trennzeichen der CSV-Datei."
    )
    encoding = forms.ChoiceField(
        label="Zeichenkodierung",
        choices=[
            ('utf-8', 'UTF-8'),
            ('latin1', 'ISO-8859-1 (Latin-1)'),
            ('cp1252', 'Windows-1252'),
        ],
        initial='utf-8',
        help_text="Wählen Sie die Zeichenkodierung der CSV-Datei."
    )
    skip_header = forms.BooleanField(
        label="Kopfzeile überspringen",
        required=False,
        initial=True,
        help_text="Aktivieren Sie diese Option, wenn die erste Zeile Spaltenüberschriften enthält."
    )


class ProductImportForm(ImportForm):
    """Form for importing products."""

    update_existing = forms.BooleanField(
        label="Bestehende Produkte aktualisieren",
        required=False,
        initial=True,
        help_text="Aktivieren Sie diese Option, um bestehende Produkte zu aktualisieren (basierend auf der Artikelnummer)."
    )
    default_category = forms.ModelChoiceField(
        label="Standardkategorie",
        queryset=Category.objects.all(),
        required=False,
        help_text="Wählen Sie eine Standardkategorie für Produkte, bei denen keine Kategorie angegeben ist."
    )


class SupplierImportForm(ImportForm):
    """Form for importing suppliers."""

    update_existing = forms.BooleanField(
        label="Bestehende Lieferanten aktualisieren",
        required=False,
        initial=True,
        help_text="Aktivieren Sie diese Option, um bestehende Lieferanten zu aktualisieren (basierend auf dem Namen)."
    )


class CategoryImportForm(ImportForm):
    """Form for importing categories."""

    update_existing = forms.BooleanField(
        label="Bestehende Kategorien aktualisieren",
        required=False,
        initial=True,
        help_text="Aktivieren Sie diese Option, um bestehende Kategorien zu aktualisieren (basierend auf dem Namen)."
    )


class SupplierProductImportForm(ImportForm):
    """Form for importing supplier-product relationships."""

    update_existing = forms.BooleanField(
        label="Bestehende Zuordnungen aktualisieren",
        required=False,
        initial=True,
        help_text="Aktivieren Sie diese Option, um bestehende Produkt-Lieferanten-Zuordnungen zu aktualisieren."
    )


class WarehouseImportForm(ImportForm):
    """Form für den Import von Lagern."""

    update_existing = forms.BooleanField(
        label="Bestehende Lager aktualisieren",
        required=False,
        initial=True,
        help_text="Aktivieren Sie diese Option, um bestehende Lager zu aktualisieren (basierend auf dem Namen)."
    )


class DepartmentImportForm(ImportForm):
    """Form für den Import von Abteilungen."""

    update_existing = forms.BooleanField(
        label="Bestehende Abteilungen aktualisieren",
        required=False,
        initial=True,
        help_text="Aktivieren Sie diese Option, um bestehende Abteilungen zu aktualisieren (basierend auf dem Code)."
    )


class WarehouseProductImportForm(ImportForm):
    """Form für den Import von Produkt-Lager-Beständen."""

    update_existing = forms.BooleanField(
        label="Bestehende Bestände aktualisieren",
        required=False,
        initial=True,
        help_text="Aktivieren Sie diese Option, um bestehende Lagerbestände zu aktualisieren."
    )


class ProductPhotoForm(forms.ModelForm):
    """Form for adding photos to products."""

    class Meta:
        model = ProductPhoto
        fields = ['image', 'is_primary', 'caption']
        widgets = {
            'is_primary': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'caption': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optionale Beschreibung'}),
        }


class ProductAttachmentForm(forms.ModelForm):
    """Form for adding attachments to products."""

    class Meta:
        model = ProductAttachment
        fields = ['file', 'title', 'description']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ProductVariantTypeForm(forms.ModelForm):
    """Form for creating and updating variant types."""

    class Meta:
        model = ProductVariantType
        fields = ['name', 'description']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }


class ProductVariantForm(forms.ModelForm):
    """Form for creating and updating product variants."""
    initial_stock = forms.DecimalField(
        label="Anfangsbestand",
        required=False,
        initial=0,
        min_value=0,
        help_text="Nur bei Neuanlage: Anfänglicher Lagerbestand"
    )

    class Meta:
        model = ProductVariant
        fields = ['sku', 'name', 'variant_type', 'value', 'price_adjustment',
                  'barcode', 'is_active']
        widgets = {
            'sku': forms.TextInput(attrs={'class': 'form-control'}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'variant_type': forms.Select(attrs={'class': 'form-select'}),
            'value': forms.TextInput(attrs={'class': 'form-control'}),
            'price_adjustment': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'barcode': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean_sku(self):
        """Ensure SKU is unique."""
        sku = self.cleaned_data.get('sku')
        instance = getattr(self, 'instance', None)

        if instance and instance.pk:
            # Bei Update: Prüfen, ob die SKU bereits verwendet wird (außer bei dieser Variante)
            exists = ProductVariant.objects.filter(sku=sku).exclude(pk=instance.pk).exists()
            # Auch prüfen, ob die SKU bereits bei einem Produkt verwendet wird
            exists_in_product = Product.objects.filter(sku=sku).exists()
        else:
            # Bei Create: Prüfen, ob die SKU bereits verwendet wird
            exists = ProductVariant.objects.filter(sku=sku).exists()
            # Auch prüfen, ob die SKU bereits bei einem Produkt verwendet wird
            exists_in_product = Product.objects.filter(sku=sku).exists()

        if exists or exists_in_product:
            raise forms.ValidationError('Diese Artikelnummer wird bereits verwendet.')

        return sku

    def clean_barcode(self):
        """Ensure barcode is unique if provided."""
        barcode = self.cleaned_data.get('barcode')

        # Wenn kein Barcode angegeben wurde, ist das OK
        if not barcode:
            return barcode

        instance = getattr(self, 'instance', None)

        if instance and instance.pk:
            # Bei Update: Prüfen, ob der Barcode bereits verwendet wird (außer bei dieser Variante)
            exists = ProductVariant.objects.filter(barcode=barcode).exclude(pk=instance.pk).exists()
            # Auch prüfen, ob der Barcode bereits bei einem Produkt verwendet wird
            exists_in_product = Product.objects.filter(barcode=barcode).exists()
        else:
            # Bei Create: Prüfen, ob der Barcode bereits verwendet wird
            exists = ProductVariant.objects.filter(barcode=barcode).exists()
            # Auch prüfen, ob der Barcode bereits bei einem Produkt verwendet wird
            exists_in_product = Product.objects.filter(barcode=barcode).exists()

        if exists or exists_in_product:
            raise forms.ValidationError('Dieser Barcode wird bereits verwendet.')

        return barcode


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