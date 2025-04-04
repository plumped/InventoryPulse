from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal

from core.models import Product
from inventory.models import Warehouse
from order.models import PurchaseOrderReceiptItem, PurchaseOrder
from suppliers.models import Supplier

from .models import RMA, RMAItem, RMAComment, RMAIssueType, RMAStatus, RMAResolutionType


class RMAForm(forms.ModelForm):
    """Form for creating and editing an RMA."""

    class Meta:
        model = RMA
        fields = ['supplier', 'related_order', 'rma_warehouse', 'contact_person',
                  'contact_email', 'contact_phone', 'shipping_address', 'notes']
        widgets = {
            'supplier': forms.Select(attrs={'class': 'form-select'}),
            'related_order': forms.Select(attrs={'class': 'form-select'}),
            'rma_warehouse': forms.Select(attrs={'class': 'form-select'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'contact_phone': forms.TextInput(attrs={'class': 'form-control'}),
            'shipping_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        # Get the user from kwargs if available
        user = kwargs.pop('user', None)

        # Get optional receipt_item_id to pre-fill the form
        receipt_item_id = kwargs.pop('receipt_item_id', None)
        purchase_order = kwargs.pop('purchase_order', None)

        super().__init__(*args, **kwargs)

        # Only show active warehouses and set default RMA warehouse if any is marked as such
        self.fields['rma_warehouse'].queryset = Warehouse.objects.filter(is_active=True)

        # Try to set a default RMA warehouse if one is available
        try:
            rma_warehouses = Warehouse.objects.filter(is_active=True, name__icontains='RMA')
            if rma_warehouses.exists():
                self.fields['rma_warehouse'].initial = rma_warehouses.first().pk
        except:
            pass

        # Pre-fill form if receipt_item_id is provided
        if receipt_item_id and not self.instance.pk:
            try:
                receipt_item = PurchaseOrderReceiptItem.objects.get(pk=receipt_item_id)
                self.fields['supplier'].initial = receipt_item.order_item.purchase_order.supplier.pk
                self.fields['related_order'].initial = receipt_item.order_item.purchase_order.pk

                # Filter related_order queryset to only show orders from the selected supplier
                self.fields['related_order'].queryset = PurchaseOrder.objects.filter(
                    supplier=receipt_item.order_item.purchase_order.supplier
                )

            except PurchaseOrderReceiptItem.DoesNotExist:
                pass

        # If purchase order is provided, pre-fill the supplier and order
        elif purchase_order and not self.instance.pk:
            self.fields['supplier'].initial = purchase_order.supplier.pk
            self.fields['related_order'].initial = purchase_order.pk

            # Filter related_order queryset to only show orders from the selected supplier
            self.fields['related_order'].queryset = PurchaseOrder.objects.filter(
                supplier=purchase_order.supplier
            )

        else:
            # By default limit to orders from the past year
            from datetime import timedelta
            one_year_ago = timezone.now().date() - timedelta(days=365)
            self.fields['related_order'].queryset = PurchaseOrder.objects.filter(
                order_date__gte=one_year_ago
            ).order_by('-order_date')



class RMAItemForm(forms.ModelForm):
    """Form for adding items to an RMA."""

    class Meta:
        model = RMAItem
        fields = ['product', 'quantity', 'unit_price', 'issue_type', 'issue_description',
                  'batch_number', 'serial_number', 'expiry_date']
        widgets = {
            'product': forms.Select(attrs={'class': 'form-select'}),
            'quantity': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01'}),
            'unit_price': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.00'}),
            'issue_type': forms.Select(attrs={'class': 'form-select'}),
            'issue_description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'batch_number': forms.TextInput(attrs={'class': 'form-control'}),
            'serial_number': forms.TextInput(attrs={'class': 'form-control'}),
            'expiry_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        }

    receipt_item = forms.ModelChoiceField(
        queryset=PurchaseOrderReceiptItem.objects.none(),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    def __init__(self, *args, **kwargs):
        rma = kwargs.pop('rma', None)
        receipt_item_id = kwargs.pop('receipt_item_id', None)

        super().__init__(*args, **kwargs)

        # If this is for a particular RMA, only show items from related orders
        if rma and rma.related_order:
            # Narrow down products to those in the related order
            order_products = rma.related_order.items.values_list('product_id', flat=True)
            self.fields['product'].queryset = Product.objects.filter(id__in=order_products)

            # Narrow down receipt items to those from the related order
            self.fields['receipt_item'].queryset = PurchaseOrderReceiptItem.objects.filter(
                order_item__purchase_order=rma.related_order
            )

        # If a specific receipt item is provided, pre-fill the form
        if receipt_item_id and not self.instance.pk:
            try:
                receipt_item = PurchaseOrderReceiptItem.objects.get(pk=receipt_item_id)

                # Set the fields based on the receipt item
                self.fields['product'].initial = receipt_item.order_item.product.pk
                self.fields['quantity'].initial = receipt_item.quantity_received
                self.fields['unit_price'].initial = receipt_item.order_item.unit_price
                self.fields['batch_number'].initial = receipt_item.batch_number
                self.fields['expiry_date'].initial = receipt_item.expiry_date

                # Set this receipt item as selected
                self.fields['receipt_item'].initial = receipt_item.pk
                self.fields['receipt_item'].queryset = PurchaseOrderReceiptItem.objects.filter(pk=receipt_item.pk)

            except PurchaseOrderReceiptItem.DoesNotExist:
                pass

    def save(self, commit=True):
        instance = super().save(commit=False)

        # Set the receipt_item if provided
        receipt_item = self.cleaned_data.get('receipt_item')
        if receipt_item:
            instance.receipt_item = receipt_item

        if commit:
            instance.save()

        return instance


class RMAItemFormSet(forms.BaseModelFormSet):
    """Formset for managing multiple RMA items."""

    def __init__(self, *args, **kwargs):
        self.rma = kwargs.pop('rma', None)
        super().__init__(*args, **kwargs)

    def _construct_form(self, i, **kwargs):
        kwargs['rma'] = self.rma
        return super()._construct_form(i, **kwargs)


class RMAStatusUpdateForm(forms.Form):
    """Form for updating the status of an RMA."""
    status = forms.ChoiceField(
        choices=RMAStatus.choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        help_text="Nur erforderlich bei Ablehnungen oder Stornierungen."
    )

    def __init__(self, *args, **kwargs):
        current_status = kwargs.pop('current_status', None)
        super().__init__(*args, **kwargs)

        # Limit status choices based on the current status
        if current_status:
            allowed_transitions = {
                RMAStatus.DRAFT: [RMAStatus.PENDING, RMAStatus.CANCELLED],
                RMAStatus.PENDING: [RMAStatus.APPROVED, RMAStatus.REJECTED, RMAStatus.CANCELLED],
                RMAStatus.APPROVED: [RMAStatus.SENT, RMAStatus.CANCELLED],
                RMAStatus.SENT: [RMAStatus.RESOLVED, RMAStatus.CANCELLED],
                RMAStatus.RESOLVED: [],  # No transitions from resolved
                RMAStatus.REJECTED: [RMAStatus.DRAFT, RMAStatus.CANCELLED],
                RMAStatus.CANCELLED: [],  # No transitions from cancelled
            }

            allowed_statuses = allowed_transitions.get(current_status, [])

            if allowed_statuses:
                # Add the current status and allowed transitions only
                choices = [(current_status, dict(RMAStatus.choices)[current_status])]
                for status in allowed_statuses:
                    choices.append((status, dict(RMAStatus.choices)[status]))

                self.fields['status'].choices = choices
            else:
                # If no transitions are allowed, only show current status
                self.fields['status'].choices = [(current_status, dict(RMAStatus.choices)[current_status])]
                self.fields['status'].disabled = True

    def clean(self):
        cleaned_data = super().clean()
        new_status = cleaned_data.get('status')
        reason = cleaned_data.get('reason')

        # Validate that reason is provided for rejection or cancellation
        if new_status in [RMAStatus.REJECTED, RMAStatus.CANCELLED] and not reason:
            self.add_error('reason', "Ein Grund ist erforderlich für Ablehnungen oder Stornierungen.")

        return cleaned_data


class RMAResolutionForm(forms.Form):
    """Form for resolving an RMA."""
    resolution_type = forms.ChoiceField(
        choices=RMAResolutionType.choices,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    resolution_notes = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=True,
        help_text="Fügen Sie Details zur Lösung hinzu"
    )

    # Fields for tracking shipping back from supplier
    received_replacement = forms.BooleanField(
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label="Ersatz erhalten"
    )
    replacement_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Ersatz erhalten am"
    )

    # Fields for refund
    refund_amount = forms.DecimalField(
        required=False,
        widget=forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
        label="Rückerstattungsbetrag"
    )
    refund_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Rückerstattung erhalten am"
    )

    def clean(self):
        cleaned_data = super().clean()
        resolution_type = cleaned_data.get('resolution_type')

        # Validate fields based on resolution type
        if resolution_type == RMAResolutionType.REPLACEMENT:
            if cleaned_data.get('received_replacement') and not cleaned_data.get('replacement_date'):
                self.add_error('replacement_date', "Bitte geben Sie das Datum an, an dem der Ersatz eingegangen ist.")

        elif resolution_type == RMAResolutionType.REFUND:
            if not cleaned_data.get('refund_amount'):
                self.add_error('refund_amount', "Bitte geben Sie den Rückerstattungsbetrag ein.")
            if not cleaned_data.get('refund_date'):
                self.add_error('refund_date', "Bitte geben Sie das Datum der Rückerstattung ein.")

        return cleaned_data


class RMACommentForm(forms.ModelForm):
    """Form for adding comments to an RMA."""

    class Meta:
        model = RMAComment
        fields = ['comment', 'attachment', 'is_public']
        widgets = {
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Ihr Kommentar...'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class RMAFilterForm(forms.Form):
    """Form for filtering RMAs in list view."""
    status = forms.ChoiceField(
        choices=[('', 'Alle Status')] + list(RMAStatus.choices),
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    supplier = forms.ModelChoiceField(
        queryset=Supplier.objects.filter(is_active=True),
        required=False,
        empty_label="Alle Lieferanten",
        widget=forms.Select(attrs={'class': 'form-select'})
    )

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Von"
    )

    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
        label="Bis"
    )

    search = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'RMA-Nummer, Produkt...'}),
        label="Suche"
    )