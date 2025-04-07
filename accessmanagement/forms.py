# accessmanagement/forms.py
from django import forms
from django.contrib.auth.models import User, Permission
from inventory.models import Warehouse
from organization.models import Department
from .models import WarehouseAccess


class SelectFormMixin:
    """Mixin for standardized select styling."""
    select_class = 'form-select'

    def _apply_select_class(self, field_names):
        for name in field_names:
            if name in self.fields:
                self.fields[name].widget.attrs.update({'class': self.select_class})


class WarehouseAccessForm(forms.ModelForm):
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
        self._was_created = False

    def save(self, commit=True):
        self.instance, self._was_created = WarehouseAccess.objects.update_or_create(
            warehouse=self.cleaned_data['warehouse'],
            department=self.cleaned_data['department'],
            defaults={
                'can_view': self.cleaned_data['can_view'],
                'can_edit': self.cleaned_data['can_edit'],
                'can_manage_stock': self.cleaned_data['can_manage_stock'],
            }
        )
        return self.instance

    def was_created(self):
        return self._was_created


class UserPermissionForm(SelectFormMixin, forms.Form):
    """Form for assigning permissions to users."""
    user = forms.ModelChoiceField(queryset=User.objects.none())
    permission = forms.ModelChoiceField(queryset=Permission.objects.none())

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['user'].queryset = User.objects.all().order_by('username')
        self.fields['permission'].queryset = Permission.objects.filter(
            content_type__app_label='accessmanagement'
        ).order_by('name')
        self._apply_select_class(['user', 'permission'])
