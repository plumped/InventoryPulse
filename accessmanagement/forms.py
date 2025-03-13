# accessmanagement/forms.py
from django import forms
from inventory.models import Warehouse
from organization.models import Department
from .models import WarehouseAccess


class WarehouseAccessForm(forms.ModelForm):
    """Form for managing warehouse access rights."""

    class Meta:
        model = WarehouseAccess
        fields = ['warehouse', 'department', 'can_view', 'can_edit', 'can_manage_stock']
        widgets = {
            'warehouse': forms.Select(attrs={'class': 'form-select'}),
            'department': forms.Select(attrs={'class': 'form-select'}),
            'can_view': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_edit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_manage_stock': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['warehouse'].queryset = Warehouse.objects.filter(is_active=True).order_by('name')
        self.fields['department'].queryset = Department.objects.all().order_by('name')

        # Check if this combination already has an access right
        if self.instance.pk is None:  # only for new entries
            self.fields['warehouse'].help_text = "Select a warehouse."
            self.fields['department'].help_text = ("Select a department. There can only be one access right entry "
                                                "for each warehouse-department combination.")


class UserPermissionForm(forms.Form):
    """Form for assigning permissions to users."""
    user = forms.ModelChoiceField(
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    permission = forms.ModelChoiceField(
        queryset=None,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        from django.contrib.auth.models import User, Permission
        self.fields['user'].queryset = User.objects.all().order_by('username')
        self.fields['permission'].queryset = Permission.objects.filter(
            content_type__app_label='accessmanagement'
        ).order_by('name')