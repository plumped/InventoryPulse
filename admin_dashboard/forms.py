from django import forms
from django.contrib.auth.models import User, Group, Permission
from django.contrib.contenttypes.models import ContentType

from accessmanagement.models import WarehouseAccess, ObjectPermission, RoleHierarchy
from documents.models import DocumentType
from interfaces.models import InterfaceType
from master_data.models.organisations_models import Department


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

    def clean(self):
        cleaned_data = super().clean()
        can_view = cleaned_data.get('can_view')
        can_edit = cleaned_data.get('can_edit')
        can_manage_stock = cleaned_data.get('can_manage_stock')

        # Ensure at least one permission type is granted
        if not (can_view or can_edit or can_manage_stock):
            raise forms.ValidationError("At least one permission type (view, edit, or manage stock) must be granted.")

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


class DocumentTypeForm(forms.ModelForm):
    class Meta:
        model = DocumentType
        fields = ['name', 'code', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }


class ObjectPermissionForm(forms.ModelForm):
    """Form for creating or editing object permissions."""
    content_type = forms.ModelChoiceField(
        queryset=ContentType.objects.all().order_by('app_label', 'model'),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    object_id = forms.IntegerField(
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
    )
    user = forms.ModelChoiceField(
        queryset=User.objects.all().order_by('username'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
    )
    department = forms.ModelChoiceField(
        queryset=Department.objects.all().order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
    )
    valid_from = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        required=False,
    )
    valid_until = forms.DateTimeField(
        widget=forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
        required=False,
    )

    class Meta:
        model = ObjectPermission
        fields = [
            'content_type', 'object_id', 'user', 'department',
            'can_view', 'can_edit', 'can_delete', 'valid_from', 'valid_until'
        ]
        widgets = {
            'can_view': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_edit': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'can_delete': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get('user')
        department = cleaned_data.get('department')

        if not user and not department:
            raise forms.ValidationError("Either a user or a department must be specified.")

        if user and department:
            raise forms.ValidationError("You cannot specify both a user and a department.")

        return cleaned_data


class RoleHierarchyForm(forms.ModelForm):
    """Form for creating or editing role hierarchies."""
    parent_role = forms.ModelChoiceField(
        queryset=Group.objects.all().order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )
    child_role = forms.ModelChoiceField(
        queryset=Group.objects.all().order_by('name'),
        widget=forms.Select(attrs={'class': 'form-select'}),
    )

    class Meta:
        model = RoleHierarchy
        fields = ['parent_role', 'child_role']

    def clean(self):
        cleaned_data = super().clean()
        parent_role = cleaned_data.get('parent_role')
        child_role = cleaned_data.get('child_role')

        if parent_role and child_role and parent_role == child_role:
            raise forms.ValidationError("Parent role and child role cannot be the same.")

        # Check for circular references
        if parent_role and child_role:
            # Check if child is already a parent of parent (direct or indirect)
            parent_roles = RoleHierarchy.get_all_parent_roles(parent_role)
            if child_role in parent_roles:
                raise forms.ValidationError("This would create a circular reference in the role hierarchy.")

        return cleaned_data


class TimeBasedPermissionForm(ObjectPermissionForm):
    """Form specifically for time-based permissions."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Time fields are optional but at least one should be provided
        self.fields['valid_from'].required = False
        self.fields['valid_until'].required = False

    def clean(self):
        cleaned_data = super().clean()
        valid_from = cleaned_data.get('valid_from')
        valid_until = cleaned_data.get('valid_until')

        # Check if at least one time constraint is provided
        if not valid_from and not valid_until:
            raise forms.ValidationError("At least one time constraint (valid from or valid until) must be specified for a time-based permission.")

        # Check if date range is logical
        if valid_from and valid_until and valid_from >= valid_until:
            raise forms.ValidationError("The 'valid from' date must be before the 'valid until' date.")

        # Check if at least one permission type is granted
        can_view = cleaned_data.get('can_view')
        can_edit = cleaned_data.get('can_edit')
        can_delete = cleaned_data.get('can_delete')

        if not (can_view or can_edit or can_delete):
            raise forms.ValidationError("At least one permission type (view, edit, or delete) must be granted.")
