from django import forms

from master_data.models.tax import Tax
from product_management.models.products import Product, ProductVariantType, ProductAttachment, ProductVariant, \
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
