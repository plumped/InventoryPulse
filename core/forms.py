from django import forms
from .models import Product, Category


class ProductForm(forms.ModelForm):
    """Form for creating and updating products."""

    class Meta:
        model = Product
        fields = ['name', 'sku', 'barcode', 'description', 'category',
                  'current_stock', 'minimum_stock', 'unit']

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