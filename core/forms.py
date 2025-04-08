from django import forms

from inventory.models import Warehouse
from .models import Product, Category, ProductVariant, SerialNumber, BatchNumber, ProductVariantType, ProductAttachment, \
    ProductPhoto, Tax, Currency

# Fix for the ProductForm class in core/forms.py

from django import forms
from inventory.models import Warehouse
from .models import Product, Category, ProductVariant, SerialNumber, BatchNumber, ProductVariantType, ProductAttachment, \
    ProductPhoto, Tax, Currency


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
        fields = ['name', 'sku', 'barcode', 'description', 'category', 'tax',
                  'minimum_stock', 'unit',
                  'has_variants', 'has_serial_numbers', 'has_batch_tracking', 'has_expiry_tracking']

        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'tax': forms.Select(attrs={'class': 'form-select'}),
            'has_variants': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'has_serial_numbers': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'has_batch_tracking': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'has_expiry_tracking': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Steuersätze nach Name sortieren
        self.fields['tax'].queryset = Tax.objects.filter(is_active=True).order_by('name')

        # Default-Steuersatz vorauswählen, wenn ein neues Produkt erstellt wird
        if not self.instance.pk:
            default_tax = Tax.get_default_tax()
            if default_tax:
                self.initial['tax'] = default_tax

        # Bei bestehendem Produkt überprüfen, ob Funktionen deaktivierbar sind
        if self.instance.pk:
            # Prüfen, ob Varianten existieren
            if hasattr(self.instance, 'variants') and self.instance.variants.exists():
                self.fields['has_variants'].disabled = True
                self.fields[
                    'has_variants'].help_text = "Diese Funktion kann nicht deaktiviert werden, da bereits Varianten existieren."

            # Prüfen, ob Seriennummern existieren
            if hasattr(self.instance, 'serial_numbers') and self.instance.serial_numbers.exists():
                self.fields['has_serial_numbers'].disabled = True
                self.fields[
                    'has_serial_numbers'].help_text = "Diese Funktion kann nicht deaktiviert werden, da bereits Seriennummern existieren."

            # Prüfen, ob Chargen existieren
            if hasattr(self.instance, 'batches') and self.instance.batches.exists():
                self.fields['has_batch_tracking'].disabled = True
                self.fields[
                    'has_batch_tracking'].help_text = "Diese Funktion kann nicht deaktiviert werden, da bereits Chargen existieren."

            # Überprüfen, ob Einträge mit Verfallsdaten existieren
            has_expiry_dates = False

            # Nur prüfen, ob tatsächlich Verfallsdaten eingetragen sind, nicht nur ob die Modelle existieren
            if hasattr(self.instance, 'serial_numbers'):
                has_expiry_dates = has_expiry_dates or self.instance.serial_numbers.filter(
                    expiry_date__isnull=False).exists()

            if hasattr(self.instance, 'batches'):
                has_expiry_dates = has_expiry_dates or self.instance.batches.filter(
                    expiry_date__isnull=False).exists()

            # Verfallsdatenverfolgung kann nur dann nicht deaktiviert werden, wenn tatsächlich Verfallsdaten existieren
            if has_expiry_dates:
                self.fields['has_expiry_tracking'].disabled = True
                self.fields[
                    'has_expiry_tracking'].help_text = "Diese Funktion kann nicht deaktiviert werden, da bereits Einträge mit Verfallsdaten existieren."

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

    def clean(self):
        """Zusätzliche Validierung für Tracking-Funktionen."""
        cleaned_data = super().clean()

        # Wenn das Produkt bereits existiert
        if self.instance.pk:
            # Nicht versuchen, deaktivierte Felder zu prüfen
            # (Diese Prüfung ist nur relevant, wenn jemand versucht, eine Deaktivierung zu erzwingen)

            # Prüfe, ob Tracking-Funktionen deaktiviert werden, wenn bereits Einträge existieren
            if not cleaned_data.get('has_variants') and not self.fields['has_variants'].disabled:
                if hasattr(self.instance, 'variants') and self.instance.variants.exists():
                    self.add_error('has_variants',
                                   "Diese Funktion kann nicht deaktiviert werden, da bereits Varianten existieren.")

            if not cleaned_data.get('has_serial_numbers') and not self.fields['has_serial_numbers'].disabled:
                if hasattr(self.instance, 'serial_numbers') and self.instance.serial_numbers.exists():
                    self.add_error('has_serial_numbers',
                                   "Diese Funktion kann nicht deaktiviert werden, da bereits Seriennummern existieren.")

            if not cleaned_data.get('has_batch_tracking') and not self.fields['has_batch_tracking'].disabled:
                if hasattr(self.instance, 'batches') and self.instance.batches.exists():
                    self.add_error('has_batch_tracking',
                                   "Diese Funktion kann nicht deaktiviert werden, da bereits Chargen existieren.")

            # FIX: Nur prüfen, ob tatsächlich Verfallsdaten eingetragen sind
            has_expiry_dates = False
            if hasattr(self.instance, 'serial_numbers'):
                has_expiry_dates = has_expiry_dates or self.instance.serial_numbers.filter(
                    expiry_date__isnull=False).exists()
            if hasattr(self.instance, 'batches'):
                has_expiry_dates = has_expiry_dates or self.instance.batches.filter(
                    expiry_date__isnull=False).exists()

            if not cleaned_data.get('has_expiry_tracking') and not self.fields['has_expiry_tracking'].disabled:
                if has_expiry_dates:
                    self.add_error('has_expiry_tracking',
                                   "Diese Funktion kann nicht deaktiviert werden, da bereits Einträge mit Verfallsdaten existieren.")

        # Wenn Verfallsdatenverfolgung aktiviert ist, muss entweder Chargen- oder Seriennummernverfolgung aktiviert sein
        if cleaned_data.get('has_expiry_tracking'):
            if not cleaned_data.get('has_batch_tracking') and not cleaned_data.get('has_serial_numbers'):
                self.add_error('has_expiry_tracking',
                               "Verfallsdatenverfolgung erfordert, dass entweder Chargenverfolgung oder Seriennummernverfolgung aktiviert ist.")

        return cleaned_data


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


class CurrencyForm(forms.ModelForm):
    """Form for creating and updating currencies."""

    class Meta:
        model = Currency
        fields = ['code', 'name', 'symbol', 'decimal_places', 'exchange_rate', 'is_default', 'is_active']
        widgets = {
            'code': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 3}),
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'symbol': forms.TextInput(attrs={'class': 'form-control', 'maxlength': 5}),
            'decimal_places': forms.NumberInput(attrs={'class': 'form-control', 'min': 0, 'max': 10}),
            'exchange_rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.000001', 'min': '0.000001'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_code(self):
        """Ensure currency code follows ISO 4217 format (3 uppercase letters)."""
        code = self.cleaned_data.get('code')
        if code:
            code = code.upper()  # Convert to uppercase
            if not (len(code) == 3 and code.isalpha()):
                raise forms.ValidationError('Der Währungscode muss aus 3 Buchstaben bestehen (ISO 4217).')
        return code

    def clean(self):
        """Additional validation for default currency."""
        cleaned_data = super().clean()
        is_default = cleaned_data.get('is_default')
        is_active = cleaned_data.get('is_active')

        # If this is the default currency, it must be active
        if is_default and not is_active:
            self.add_error('is_active', 'Die Standardwährung muss aktiv sein.')

        return cleaned_data


class SerialNumberImportForm(forms.Form):
    file = forms.FileField(label='CSV-Datei', help_text='Bitte laden Sie eine CSV-Datei hoch.')

class BatchNumberImportForm(forms.Form):
    """Form für den Import von Chargen."""
    file = forms.FileField(label='CSV-Datei', help_text='Bitte laden Sie eine CSV-Datei hoch.')
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
    update_existing = forms.BooleanField(
        label="Bestehende Chargen aktualisieren",
        required=False,
        initial=True,
        help_text="Wenn aktiviert, werden bereits existierende Chargen (gleiche Kombination aus Produkt und Chargennummer) "
                  "mit den Daten aus der CSV-Datei aktualisiert. Wenn deaktiviert, werden diese Zeilen übersprungen."
    )