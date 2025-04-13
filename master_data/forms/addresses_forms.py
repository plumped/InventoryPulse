from django import forms

from master_data.models.addresses_models import CompanyAddress


class CompanyAddressForm(forms.ModelForm):
    """Form für Unternehmensadressen"""

    class Meta:
        model = CompanyAddress
        fields = [
            'name', 'address_type', 'is_default',
            'street', 'zip_code', 'city', 'country',
            'contact_person', 'phone', 'email', 'notes'
        ]
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'address_type': forms.Select(attrs={'class': 'form-select'}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'street': forms.TextInput(attrs={'class': 'form-control'}),
            'zip_code': forms.TextInput(attrs={'class': 'form-control'}),
            'city': forms.TextInput(attrs={'class': 'form-control'}),
            'country': forms.TextInput(attrs={'class': 'form-control'}),
            'contact_person': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
