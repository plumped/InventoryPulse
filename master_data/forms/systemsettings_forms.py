from django import forms

from master_data.models.systemsettings_models import SystemSettings


class SystemSettingsForm(forms.ModelForm):
    """Form for system settings."""

    class Meta:
        model = SystemSettings
        fields = '__all__'
        widgets = {
            'company_name': forms.TextInput(attrs={'class': 'form-control'}),
            'company_logo': forms.FileInput(attrs={'class': 'form-control'}),
            'default_warehouse': forms.Select(attrs={'class': 'form-select'}),
            'default_stock_min': forms.NumberInput(attrs={'class': 'form-control'}),
            'default_lead_time': forms.NumberInput(attrs={'class': 'form-control'}),
            'email_notifications_enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'email_from_address': forms.EmailInput(attrs={'class': 'form-control'}),
            'next_order_number': forms.NumberInput(attrs={'class': 'form-control'}),
            'order_number_prefix': forms.TextInput(attrs={'class': 'form-control'}),
            'track_inventory_history': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_create_user_profile': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
