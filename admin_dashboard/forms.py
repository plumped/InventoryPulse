# admin_dashboard/forms.py
from django import forms
from django.contrib.auth.models import User, Group, Permission

from accessmanagement.models import WarehouseAccess
from interfaces.models import InterfaceType
from organization.models import Department
from .models import SystemSettings, WorkflowSettings, CompanyAddress


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


class WorkflowSettingsForm(forms.ModelForm):
    """Form for workflow settings."""

    class Meta:
        model = WorkflowSettings
        fields = '__all__'
        widgets = {
            'order_approval_required': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'order_approval_threshold': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'skip_draft_for_small_orders': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'small_order_threshold': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01'}),
            'auto_approve_preferred_suppliers': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'send_order_emails': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'require_separate_approver': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class UserCreateForm(forms.ModelForm):
    """Form for creating a new user."""
    password = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    password_confirm = forms.CharField(widget=forms.PasswordInput(attrs={'class': 'form-control'}))
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        required=False
    )
    departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_superuser': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        password = cleaned_data.get("password")
        password_confirm = cleaned_data.get("password_confirm")

        if password and password_confirm and password != password_confirm:
            self.add_error('password_confirm', "Die Passwörter stimmen nicht überein.")

        return cleaned_data


class UserEditForm(forms.ModelForm):
    """Form for editing an existing user."""
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        required=False,
        help_text="Lassen Sie dieses Feld leer, um das Passwort unverändert zu lassen."
    )
    groups = forms.ModelMultipleChoiceField(
        queryset=Group.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        required=False
    )
    departments = forms.ModelMultipleChoiceField(
        queryset=Department.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        required=False
    )

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'is_active', 'is_staff', 'is_superuser']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_staff': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_superuser': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.get('instance')
        super().__init__(*args, **kwargs)

        if user:
            self.initial['groups'] = user.groups.all()
            try:
                self.initial['departments'] = user.profile.departments.all()
            except:
                self.initial['departments'] = []

class GroupForm(forms.ModelForm):
    """Form for creating or editing a group."""

    permissions = forms.ModelMultipleChoiceField(
        queryset=Permission.objects.all().order_by('content_type__app_label', 'content_type__model', 'name'),
        widget=forms.CheckboxSelectMultiple,
        required=False
    )

    class Meta:
        model = Group
        fields = ['name', 'permissions']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance.pk:
            # Vorauswahl der aktuellen Berechtigungen, falls eine existierende Gruppe bearbeitet wird
            self.initial['permissions'] = self.instance.permissions.all()


class DepartmentForm(forms.ModelForm):
    """Form for creating or editing a department."""
    manager = forms.ModelChoiceField(
        queryset=User.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False
    )
    members = forms.ModelMultipleChoiceField(
        queryset=User.objects.all(),
        widget=forms.SelectMultiple(attrs={'class': 'form-select'}),
        required=False
    )
    description = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        required=False
    )

    class Meta:
        model = Department
        fields = ['name', 'code']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
        }


class WarehouseAccessForm(forms.ModelForm):
    """Form for creating or editing warehouse access."""

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

class InterfaceTypeForm(forms.ModelForm):
    class Meta:
        model = InterfaceType
        fields = ['name', 'code', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }