from django.contrib import admin

from .models import Module, FeatureFlag, SubscriptionPackage, Subscription


class FeatureFlagInline(admin.TabularInline):
    model = FeatureFlag
    extra = 1


@admin.register(Module)
class ModuleAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'price_monthly', 'price_yearly')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'description')
    inlines = [FeatureFlagInline]


@admin.register(FeatureFlag)
class FeatureFlagAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'module', 'is_active')
    list_filter = ('is_active', 'module')
    search_fields = ('name', 'code', 'description')


class ModuleInline(admin.TabularInline):
    model = SubscriptionPackage.modules.through
    extra = 1
    verbose_name = "Module"
    verbose_name_plural = "Modules"


class FeatureFlagPackageInline(admin.TabularInline):
    model = SubscriptionPackage.feature_flags.through
    extra = 1
    verbose_name = "Feature Flag"
    verbose_name_plural = "Feature Flags"


@admin.register(SubscriptionPackage)
class SubscriptionPackageAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'price_monthly', 'price_yearly')
    list_filter = ('is_active',)
    search_fields = ('name', 'code', 'description')
    filter_horizontal = ('modules', 'feature_flags')
    inlines = [ModuleInline, FeatureFlagPackageInline]
    exclude = ('modules', 'feature_flags')


class CustomModuleInline(admin.TabularInline):
    model = Subscription.custom_modules.through
    extra = 1
    verbose_name = "Custom Module"
    verbose_name_plural = "Custom Modules"


class CustomFeatureInline(admin.TabularInline):
    model = Subscription.custom_features.through
    extra = 1
    verbose_name = "Custom Feature"
    verbose_name_plural = "Custom Features"


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ('__str__', 'organization', 'package', 'subscription_type', 'start_date', 'end_date', 'is_active',
                    'payment_status')
    list_filter = ('is_active', 'subscription_type', 'payment_status', 'package')
    search_fields = ('organization__name', 'package__name')
    filter_horizontal = ('custom_modules', 'custom_features')
    inlines = [CustomModuleInline, CustomFeatureInline]
    exclude = ('custom_modules', 'custom_features')
    readonly_fields = ('created_at', 'updated_at')
    fieldsets = (
        (None, {
            'fields': ('organization', 'package', 'subscription_type')
        }),
        ('Dates', {
            'fields': ('start_date', 'end_date', 'created_at', 'updated_at')
        }),
        ('Status', {
            'fields': ('is_active', 'payment_status')
        }),
        ('Custom Settings', {
            'fields': ('custom_settings',),
            'classes': ('collapse',)
        }),
    )
