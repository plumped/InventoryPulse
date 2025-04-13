from django import forms

from product_management.models.categories_models import Category


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
