from django import forms
from django.utils.translation import gettext_lazy as _
from .models import Document, DocumentTemplate, TemplateField, DocumentType


class DocumentUploadForm(forms.ModelForm):
    """Form for uploading new documents."""

    class Meta:
        model = Document
        fields = ['title', 'file', 'document_type', 'supplier', 'notes']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make fields required
        self.fields['document_type'].required = True
        self.fields['document_type'].empty_label = _("-- Select Document Type --")

        # Only show active document types
        self.fields['document_type'].queryset = DocumentType.objects.filter(is_active=True)

        # Apply Bootstrap classes
        for field_name, field in self.fields.items():
            if field_name != 'file':
                field.widget.attrs.update({'class': 'form-control'})
            else:
                field.widget.attrs.update({'class': 'form-control-file'})


class DocumentTemplateForm(forms.ModelForm):
    """Form for creating and updating document templates."""

    reference_document = forms.ModelChoiceField(
        queryset=Document.objects.filter(is_processed=True),
        required=False,
        label=_("Reference Document"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )

    class Meta:
        model = DocumentTemplate
        fields = ['name', 'document_type', 'supplier', 'description', 'header_pattern', 'footer_pattern', 'is_active',
                  'reference_document']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make fields required
        self.fields['document_type'].required = True
        self.fields['supplier'].required = True

        # Apply Bootstrap classes
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})

        # Set text areas for patterns
        self.fields['header_pattern'].widget = forms.Textarea(attrs={'rows': 3, 'class': 'form-control'})
        self.fields['footer_pattern'].widget = forms.Textarea(attrs={'rows': 3, 'class': 'form-control'})
        self.fields['description'].widget = forms.Textarea(attrs={'rows': 3, 'class': 'form-control'})


class TemplateFieldForm(forms.ModelForm):
    """Form for creating and updating template fields."""

    class Meta:
        model = TemplateField
        fields = [
            'name', 'code', 'field_type', 'description',
            'x1', 'y1', 'x2', 'y2',
            'extraction_method', 'search_pattern', 'reference_field',
            'x_offset', 'y_offset', 'format_pattern',
            'is_table_header', 'table_column_index', 'table_row_index', 'table_parent',
            'is_required', 'is_key_field', 'validation_regex'
        ]

    def __init__(self, *args, **kwargs):
        template_id = kwargs.pop('template_id', None)
        super().__init__(*args, **kwargs)

        # Apply Bootstrap classes
        for field_name, field in self.fields.items():
            field.widget.attrs.update({'class': 'form-control'})

        # Set checkboxes
        for field_name in ['is_table_header', 'is_required', 'is_key_field']:
            self.fields[field_name].widget = forms.CheckboxInput(attrs={'class': 'form-check-input'})

        # Set coordinate fields as number inputs
        for field_name in ['x1', 'y1', 'x2', 'y2', 'x_offset', 'y_offset']:
            self.fields[field_name].widget = forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'})

        # Set table index fields as number inputs
        for field_name in ['table_column_index', 'table_row_index']:
            self.fields[field_name].widget = forms.NumberInput(attrs={'class': 'form-control'})

        # Filter reference field choices to only include fields from the same template
        if template_id:
            self.fields['reference_field'].queryset = TemplateField.objects.filter(template_id=template_id)
            self.fields['table_parent'].queryset = TemplateField.objects.filter(template_id=template_id)
        else:
            self.fields['reference_field'].queryset = TemplateField.objects.none()
            self.fields['table_parent'].queryset = TemplateField.objects.none()


class DocumentMatchForm(forms.Form):
    """Form for manually matching a document to a purchase order."""
    purchase_order = forms.ModelChoiceField(
        queryset=None,
        label=_("Purchase Order"),
        empty_label=_("-- Select Purchase Order --"),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3})
    )

    def __init__(self, *args, **kwargs):
        supplier_id = kwargs.pop('supplier_id', None)
        super().__init__(*args, **kwargs)

        # Filter purchase orders by supplier if provided
        from order.models import PurchaseOrder
        if supplier_id:
            self.fields['purchase_order'].queryset = PurchaseOrder.objects.filter(
                supplier_id=supplier_id,
                status__in=['approved', 'sent', 'partially_received']
            )
        else:
            self.fields['purchase_order'].queryset = PurchaseOrder.objects.filter(
                status__in=['approved', 'sent', 'partially_received']
            )