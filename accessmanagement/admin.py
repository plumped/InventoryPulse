from datetime import timedelta

from django import forms
from django.contrib import admin
from django.contrib import messages
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin, GroupAdmin as DefaultGroupAdmin
from django.contrib.auth.models import Permission, Group, User
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

from .models import UserProfile, WarehouseAccess, ObjectPermission, RoleHierarchy
from .security import SecurityEvent


# Custom filter for validity status
class ValidityFilter(admin.SimpleListFilter):
    title = 'validity status'
    parameter_name = 'validity'

    def lookups(self, request, model_admin):
        return (
            ('valid', 'Currently Valid'),
            ('expired', 'Expired'),
            ('future', 'Future (Not Yet Valid)'),
            ('unlimited', 'Unlimited (No End Date)'),
        )

    def queryset(self, request, queryset):
        now = timezone.now()

        if self.value() == 'valid':
            # Currently valid: either no time constraints or within the valid period
            return queryset.filter(
                (models.Q(valid_from__isnull=True) | models.Q(valid_from__lte=now)) &
                (models.Q(valid_until__isnull=True) | models.Q(valid_until__gt=now))
            )

        if self.value() == 'expired':
            # Expired: valid_until is in the past
            return queryset.filter(valid_until__lt=now)

        if self.value() == 'future':
            # Future: valid_from is in the future
            return queryset.filter(valid_from__gt=now)

        if self.value() == 'unlimited':
            # Unlimited: no end date
            return queryset.filter(valid_until__isnull=True)

# Custom form for ObjectPermission
class ObjectPermissionForm(forms.ModelForm):
    class Meta:
        model = ObjectPermission
        fields = '__all__'

    def clean(self):
        cleaned_data = super().clean()
        user = cleaned_data.get('user')
        department = cleaned_data.get('department')

        # Check that either user or department is set, but not both
        if user and department:
            raise ValidationError("Please select either a user OR a department, not both.")
        if not user and not department:
            raise ValidationError("Please select either a user OR a department.")

        return cleaned_data

# Custom admin for ObjectPermission
class ObjectPermissionAdmin(admin.ModelAdmin):
    form = ObjectPermissionForm
    list_display = ('get_target', 'get_object_info', 'content_type', 'object_id', 'can_view', 'can_edit', 'can_delete', 'is_currently_valid', 'valid_until')
    list_filter = (ValidityFilter, 'content_type', 'can_view', 'can_edit', 'can_delete', 'user', 'department')
    search_fields = ('user__username', 'department__name', 'content_type__model', 'object_id')
    raw_id_fields = ('user',)
    date_hierarchy = 'valid_from'
    readonly_fields = ('content_object', 'get_object_info')
    actions = ['extend_validity_30_days', 'extend_validity_90_days', 'extend_validity_1_year']

    def get_fieldsets(self, request, obj=None):
        """
        Override to provide different fieldsets for add and change forms.
        For the add form, exclude get_object_info and content_object.
        For the change form, include them.
        """
        if obj is None:
            # Add form - exclude get_object_info and content_object
            return (
                ('Target', {
                    'fields': ('user', 'department'),
                    'description': 'Select either a user OR a department (not both)'
                }),
                ('Object', {
                    'fields': ('content_type', 'object_id'),
                    'description': 'Select the object type and ID.'
                }),
                ('Permissions', {
                    'fields': ('can_view', 'can_edit', 'can_delete'),
                    'description': 'Select the permissions to grant'
                }),
                ('Time Constraints', {
                    'fields': ('valid_from', 'valid_until'),
                    'description': 'Optionally set time constraints for when this permission is valid',
                    'classes': ('collapse',),
                }),
            )
        else:
            # Change form - include get_object_info and content_object
            return (
                ('Target', {
                    'fields': ('user', 'department'),
                    'description': 'Select either a user OR a department (not both)'
                }),
                ('Object', {
                    'fields': ('content_type', 'object_id', 'get_object_info', 'content_object'),
                    'description': 'Select the object type and ID. The object name will be displayed automatically.'
                }),
                ('Permissions', {
                    'fields': ('can_view', 'can_edit', 'can_delete'),
                    'description': 'Select the permissions to grant'
                }),
                ('Time Constraints', {
                    'fields': ('valid_from', 'valid_until'),
                    'description': 'Optionally set time constraints for when this permission is valid',
                    'classes': ('collapse',),
                }),
            )

    def get_target(self, obj):
        """Return the user or department that has the permission."""
        if obj.user:
            return f"User: {obj.user.username}"
        elif obj.department:
            return f"Department: {obj.department.name}"
        return "Unknown target"
    get_target.short_description = 'Target'

    def get_object_info(self, obj):
        """Return identifying information about the object."""
        try:
            # Get the actual object
            content_object = obj.content_object

            # If the object has a name attribute, use that
            if hasattr(content_object, 'name'):
                return content_object.name

            # If the object has a title attribute, use that
            if hasattr(content_object, 'title'):
                return content_object.title

            # If the object has a username attribute (for User objects), use that
            if hasattr(content_object, 'username'):
                return content_object.username

            # If the object has a __str__ method, use that
            return str(content_object)
        except Exception as e:
            return f"Error retrieving object: {str(e)}"
    get_object_info.short_description = 'Object Name'

    def get_readonly_fields(self, request, obj=None):
        """
        Override to make get_object_info only readonly when the object exists.
        This prevents it from showing up in the add form before an object is selected.
        """
        if obj is None:
            # When adding a new object, don't include get_object_info in readonly_fields
            return ('content_object',)
        # When editing an existing object, include get_object_info in readonly_fields
        return self.readonly_fields

    def is_currently_valid(self, obj):
        """Check if the permission is currently valid based on time constraints."""
        return obj.is_valid()
    is_currently_valid.short_description = 'Is Valid'
    is_currently_valid.boolean = True

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Customize the form fields for foreign keys."""
        if db_field.name == "content_type":
            # Filter content types to only include models that are likely to need permissions
            excluded_apps = ['admin', 'contenttypes', 'sessions', 'messages', 'staticfiles']
            excluded_models = ['permission', 'contenttype', 'logentry']

            kwargs["queryset"] = ContentType.objects.exclude(
                app_label__in=excluded_apps
            ).exclude(
                model__in=excluded_models
            ).order_by('app_label', 'model')

        elif db_field.name == "department":
            # Order departments by name
            from master_data.models.organisations_models import Department
            kwargs["queryset"] = Department.objects.all().order_by('name')

        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def extend_validity_30_days(self, request, queryset):
        """Extend the validity of selected permissions by 30 days."""
        self._extend_validity(request, queryset, days=30)
    extend_validity_30_days.short_description = "Extend validity by 30 days"

    def extend_validity_90_days(self, request, queryset):
        """Extend the validity of selected permissions by 90 days."""
        self._extend_validity(request, queryset, days=90)
    extend_validity_90_days.short_description = "Extend validity by 90 days"

    def extend_validity_1_year(self, request, queryset):
        """Extend the validity of selected permissions by 1 year."""
        self._extend_validity(request, queryset, days=365)
    extend_validity_1_year.short_description = "Extend validity by 1 year"

    def _extend_validity(self, request, queryset, days):
        """Helper method to extend the validity of permissions."""
        count = 0
        now = timezone.now()

        for permission in queryset:
            # If valid_until is in the past or not set, extend from now
            if not permission.valid_until or permission.valid_until < now:
                permission.valid_until = now + timedelta(days=days)
            else:
                # Otherwise, extend from the current valid_until date
                permission.valid_until = permission.valid_until + timedelta(days=days)

            permission.save()
            count += 1

        messages.success(request, f"Extended validity for {count} permissions by {days} days.")

# Register the original models
admin.site.register(UserProfile)
admin.site.register(WarehouseAccess)
admin.site.register(ObjectPermission, ObjectPermissionAdmin)
admin.site.register(RoleHierarchy)
admin.site.register(SecurityEvent)


# Permission Admin with better display and filtering
class PermissionAdmin(admin.ModelAdmin):
    list_display = ('codename', 'name', 'get_content_type', 'get_app_label', 'get_model')
    list_filter = ('content_type__app_label',)
    search_fields = ('name', 'codename')
    ordering = ('content_type__app_label', 'codename')

    def get_content_type(self, obj):
        try:
            return obj.content_type if obj.content_type else "-"
        except:
            return "-"
    get_content_type.short_description = 'Content Type'

    def get_app_label(self, obj):
        try:
            return obj.content_type.app_label if obj.content_type else "-"
        except:
            return "-"
    get_app_label.short_description = 'Application'

    def get_model(self, obj):
        try:
            return obj.content_type.model if obj.content_type else "-"
        except:
            return "-"
    get_model.short_description = 'Model'
admin.site.register(Permission, PermissionAdmin)


# Enhanced User Admin that shows more permissions info
class EnhancedUserAdmin(DefaultUserAdmin):
    list_display = DefaultUserAdmin.list_display + ('get_groups', 'get_permissions_count')

    def get_groups(self, obj):
        return ", ".join([g.name for g in obj.groups.all()])

    get_groups.short_description = 'Groups'

    def get_permissions_count(self, obj):
        return obj.user_permissions.count()

    get_permissions_count.short_description = 'Direct Permissions'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('groups', 'user_permissions')


# Enhanced Group Admin that shows more info
class EnhancedGroupAdmin(DefaultGroupAdmin):
    list_display = ('name', 'get_permissions_count', 'get_users_count')

    def get_permissions_count(self, obj):
        return obj.permissions.count()

    get_permissions_count.short_description = 'Permissions'

    def get_users_count(self, obj):
        return User.objects.filter(groups=obj).count()

    get_users_count.short_description = 'Users'

    def get_queryset(self, request):
        return super().get_queryset(request).prefetch_related('permissions')


# Unregister the default User and Group admins
try:
    admin.site.unregister(User)
except admin.sites.NotRegistered:
    pass

try:
    admin.site.unregister(Group)
except admin.sites.NotRegistered:
    pass

# Register our enhanced User and Group admins
admin.site.register(User, EnhancedUserAdmin)
admin.site.register(Group, EnhancedGroupAdmin)


# Content Type Admin for deeper introspection
class ContentTypeAdmin(admin.ModelAdmin):
    list_display = ('app_label', 'model', 'get_permissions_count')
    list_filter = ('app_label',)
    search_fields = ('app_label', 'model')
    ordering = ('app_label', 'model')

    def get_permissions_count(self, obj):
        return Permission.objects.filter(content_type=obj).count()

    get_permissions_count.short_description = 'Permissions'


# Unregister the default ContentType admin if registered
try:
    admin.site.unregister(ContentType)
except admin.sites.NotRegistered:
    pass

# Register our enhanced ContentType admin
admin.site.register(ContentType, ContentTypeAdmin)
