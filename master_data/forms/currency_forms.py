from django import forms

from master_data.models.currency_models import Currency


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
