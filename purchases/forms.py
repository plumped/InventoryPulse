from django import forms
from django.forms import inlineformset_factory
from suppliers.models import Supplier, SupplierProduct
from core.models import Product
from inventory.models import Warehouse

from .models import (
    PurchaseOrder,
    PurchaseOrderItem,
    GoodsReceipt,
    GoodsReceiptItem,
    PurchaseOrderTemplate,
    PurchaseOrderTemplateItem,
    PurchaseRecommendation
)


class PurchaseOrderForm(forms.ModelForm):
    """Form for creating and updating purchase orders."""

    class Meta:
        model = PurchaseOrder
        fields = [
            'supplier', 'order_date', 'expected_delivery_date',
            'shipping_address', 'notes', 'reference', 'internal_notes',
            'shipping_cost', 'tax'
        ]
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'order_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'expected_delivery_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'shipping_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'reference': forms.TextInput(attrs={'class': 'form-control'}),
            'internal_notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'shipping_cost': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'tax': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Add help text
        self.fields['supplier'].help_text = "Wählen Sie den Lieferanten für diese Bestellung."
        self.fields['order_date'].help_text = "Datum der Bestellung (leer lassen für Entwürfe)."
        self.fields['expected_delivery_date'].help_text = "Erwartetes Lieferdatum."
        self.fields['shipping_address'].help_text = "Lieferadresse für diese Bestellung."
        self.fields['reference'].help_text = "Externe Referenznummer (z.B. vom Lieferanten)."

        # If instance has a supplier, pre-fill shipping address
        if self.instance and self.instance.pk and self.instance.supplier:
            if not self.initial.get('shipping_address'):
                self.initial['shipping_address'] = self.instance.supplier.address


class PurchaseOrderItemForm(forms.ModelForm):
    """Form for creating and updating purchase order items."""

    class Meta:
        model = PurchaseOrderItem
        fields = [
            'product', 'supplier_product', 'quantity', 'unit_price',
            'discount_percentage', 'tax_percentage', 'supplier_sku',
            'description', 'notes', 'expected_delivery_date'
        ]
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'supplier_product': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'discount_percentage': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'tax_percentage': forms.NumberInput(
                attrs={'class': 'form-control', 'step': '0.01', 'min': '0', 'max': '100'}),
            'supplier_sku': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'expected_delivery_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        supplier = kwargs.pop('supplier', None)
        super().__init__(*args, **kwargs)

        if supplier:
            # Filter products that have a supplier_product link with this supplier
            self.fields['product'].queryset = Product.objects.filter(
                supplier_products__supplier=supplier
            ).distinct()

            # Filter supplier_products to only those from this supplier
            self.fields['supplier_product'].queryset = SupplierProduct.objects.filter(
                supplier=supplier
            )

        # If product is already selected, filter supplier_product accordingly
        if self.instance and self.instance.product_id:
            self.fields['supplier_product'].queryset = SupplierProduct.objects.filter(
                product=self.instance.product,
                supplier=supplier if supplier else self.instance.purchase_order.supplier
            )


# Create a formset for purchase order items
PurchaseOrderItemFormSet = inlineformset_factory(
    PurchaseOrder,
    PurchaseOrderItem,
    form=PurchaseOrderItemForm,
    extra=1,
    can_delete=True
)


class GoodsReceiptForm(forms.ModelForm):
    """Form for creating and updating goods receipts."""

    warehouse = forms.ModelChoiceField(
        queryset=Warehouse.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Lager, in das die Waren eingehen."
    )

    class Meta:
        model = GoodsReceipt
        fields = [
            'receipt_date', 'delivery_note_number', 'carrier',
            'package_count', 'notes'
        ]
        widgets = {
            'receipt_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'delivery_note_number': forms.TextInput(attrs={'class': 'form-control'}),
            'carrier': forms.TextInput(attrs={'class': 'form-control'}),
            'package_count': forms.NumberInput(attrs={'class': 'form-control', 'min': '1'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class GoodsReceiptItemForm(forms.ModelForm):
    """Form for recording received items."""

    class Meta:
        model = GoodsReceiptItem
        fields = ['purchase_order_item', 'received_quantity', 'is_defective', 'notes']
        widgets = {
            'purchase_order_item': forms.Select(attrs={'class': 'form-select'}),
            'received_quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0'}),
            'is_defective': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }

    def __init__(self, *args, **kwargs):
        purchase_order = kwargs.pop('purchase_order', None)
        super().__init__(*args, **kwargs)

        if purchase_order:
            # Only show items from this purchase order
            self.fields['purchase_order_item'].queryset = PurchaseOrderItem.objects.filter(
                purchase_order=purchase_order
            )

            # Show product info in the dropdown
            self.fields['purchase_order_item'].label_from_instance = lambda obj: (
                f"{obj.product.name} - Bestellt: {obj.quantity}, "
                f"Erhalten: {obj.received_quantity}"
            )


# Create a formset for goods receipt items
GoodsReceiptItemFormSet = inlineformset_factory(
    GoodsReceipt,
    GoodsReceiptItem,
    form=GoodsReceiptItemForm,
    extra=1,
    can_delete=True
)


class PurchaseOrderTemplateForm(forms.ModelForm):
    """Form for creating and updating purchase order templates."""

    class Meta:
        model = PurchaseOrderTemplate
        fields = ['name', 'supplier', 'notes']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class PurchaseOrderTemplateItemForm(forms.ModelForm):
    """Form for template items."""

    class Meta:
        model = PurchaseOrderTemplateItem
        fields = ['product', 'supplier_product', 'quantity']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'supplier_product': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
        }

    def __init__(self, *args, **kwargs):
        supplier = kwargs.pop('supplier', None)
        super().__init__(*args, **kwargs)

        if supplier:
            # Filter products that have a supplier_product link with this supplier
            self.fields['product'].queryset = Product.objects.filter(
                supplier_products__supplier=supplier
            ).distinct()

            # Filter supplier_products to only those from this supplier
            self.fields['supplier_product'].queryset = SupplierProduct.objects.filter(
                supplier=supplier
            )


# Create a formset for template items
PurchaseOrderTemplateItemFormSet = inlineformset_factory(
    PurchaseOrderTemplate,
    PurchaseOrderTemplateItem,
    form=PurchaseOrderTemplateItemForm,
    extra=1,
    can_delete=True
)


class RecommendationFilterForm(forms.Form):
    """Form for filtering purchase recommendations."""

    STATUS_CHOICES = (
                         ('', 'Alle Status'),
                     ) + PurchaseRecommendation.STATUS_CHOICES

    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.all(),
        required=False,
        empty_label="Alle Lieferanten",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Produkt suchen...'})
    )


class EmailPurchaseOrderForm(forms.Form):
    """Form for emailing purchase orders."""

    recipient = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        help_text="E-Mail-Adresse des Empfängers"
    )

    cc = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={'class': 'form-control'}),
        help_text="CC E-Mail-Adresse (optional)"
    )

    subject = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text="Betreff der E-Mail"
    )

    message = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5}),
        help_text="Text der E-Mail"
    )

    attach_pdf = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Bestellung als PDF anhängen"
    )