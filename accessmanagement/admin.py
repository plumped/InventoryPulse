from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DefaultUserAdmin, GroupAdmin as DefaultGroupAdmin
from django.contrib.auth.models import Permission, Group, User
from django.contrib.contenttypes.models import ContentType

from .models import UserProfile, WarehouseAccess, ObjectPermission, RoleHierarchy
from .security import SecurityEvent

# Register the original models
admin.site.register(UserProfile)
admin.site.register(WarehouseAccess)
admin.site.register(ObjectPermission)
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