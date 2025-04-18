from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User

from .models import (
    UserProfile, WarehouseAccess, PasswordHistory, Role,
    UserRole, ObjectPermission, UserSecuritySettings
)


# Register your models here.

class UserProfileInline(admin.StackedInline):
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'User Profile'
    fk_name = 'user'


class UserAdmin(BaseUserAdmin):
    inlines = (UserProfileInline,)
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'get_organization')

    def get_organization(self, obj):
        try:
            return obj.profile.organization
        except UserProfile.DoesNotExist:
            return None

    get_organization.short_description = 'Organization'
    get_organization.admin_order_field = 'profile__organization'


# Re-register UserAdmin
admin.site.unregister(User)
admin.site.register(User, UserAdmin)


@admin.register(WarehouseAccess)
class WarehouseAccessAdmin(admin.ModelAdmin):
    list_display = ('warehouse', 'department', 'can_view', 'can_edit', 'can_manage_stock')
    list_filter = ('can_view', 'can_edit', 'can_manage_stock', 'warehouse', 'department')
    search_fields = ('warehouse__name', 'department__name')


@admin.register(PasswordHistory)
class PasswordHistoryAdmin(admin.ModelAdmin):
    list_display = ('user', 'created_at')
    list_filter = ('created_at',)
    search_fields = ('user__username',)
    readonly_fields = ('user', 'password', 'created_at')


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_system_role', 'created_at', 'updated_at')
    list_filter = ('is_system_role', 'created_at', 'updated_at')
    search_fields = ('name', 'description')
    filter_horizontal = ('permissions',)
    readonly_fields = ('created_at', 'updated_at')


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ('user', 'role', 'organization', 'department', 'created_at')
    list_filter = ('role', 'organization', 'department', 'created_at')
    search_fields = ('user__username', 'role__name', 'organization__name', 'department__name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(ObjectPermission)
class ObjectPermissionAdmin(admin.ModelAdmin):
    list_display = ('content_type', 'object_id', 'permission_type', 'user', 'role', 'department', 'organization')
    list_filter = ('permission_type', 'content_type', 'organization', 'created_at')
    search_fields = ('content_type__model', 'object_id', 'user__username', 'role__name')
    readonly_fields = ('created_at', 'updated_at')


@admin.register(UserSecuritySettings)
class UserSecuritySettingsAdmin(admin.ModelAdmin):
    list_display = ('user', 'password_last_changed', 'password_expiry_date', 'failed_login_attempts',
                    'is_account_locked')
    list_filter = ('password_last_changed', 'password_expiry_date', 'account_locked_until', 'require_password_change')
    search_fields = ('user__username',)
    readonly_fields = ('password_last_changed',)

    def is_account_locked(self, obj):
        return obj.is_account_locked()

    is_account_locked.boolean = True
    is_account_locked.short_description = 'Account Locked'
