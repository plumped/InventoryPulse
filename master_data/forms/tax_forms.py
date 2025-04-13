from django import forms

from master_data.models.tax import Tax


class TaxForm(forms.ModelForm):
    """Form for creating and updating tax rates."""

    class Meta:
        model = Tax
        fields = ['name', 'code', 'rate', 'description', 'is_default', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'rate': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_default': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean_code(self):
        """Steuerkürzel überprüfen."""
        code = self.cleaned_data.get('code')
        instance = getattr(self, 'instance', None)

        # Bei Update: Prüfen, ob der Code bereits verwendet wird (außer bei diesem Steuersatz)
        if instance and instance.pk:
            qs = Tax.objects.filter(code=code).exclude(pk=instance.pk)
        # Bei Create: Prüfen, ob der Code bereits verwendet wird
        else:
            qs = Tax.objects.filter(code=code)

        if qs.exists():
            raise forms.ValidationError('Dieser Steuerkürzel wird bereits verwendet.')

        return code
