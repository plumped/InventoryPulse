import json
from decimal import Decimal

from django.db import models


class Module(models.Model):
    """
    Represents a functional module in the application that can be enabled or disabled per company.
    Modules can be part of subscription packages and have different pricing options.
    """
    name = models.CharField(max_length=100, help_text="Name of the module")
    code = models.CharField(max_length=50, unique=True, help_text="Unique code identifier for the module")
    description = models.TextField(blank=True, help_text="Detailed description of the module's functionality")
    is_active = models.BooleanField(default=True, help_text="Whether this module is currently available")
    price_monthly = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Monthly subscription price for this module"
    )
    price_yearly = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Yearly subscription price for this module"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Module'
        verbose_name_plural = 'Modules'

    def __str__(self):
        return self.name


class FeatureFlag(models.Model):
    """
    Represents a feature flag that can be enabled or disabled for specific subscription packages.
    Feature flags allow fine-grained control over access to specific features within modules.
    """
    name = models.CharField(max_length=100, help_text="Name of the feature flag")
    code = models.CharField(max_length=50, unique=True, help_text="Unique code identifier for the feature flag")
    description = models.TextField(blank=True, help_text="Detailed description of what this feature flag controls")
    module = models.ForeignKey(Module, on_delete=models.CASCADE, related_name='feature_flags')
    is_active = models.BooleanField(default=True, help_text="Whether this feature flag is currently available")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['module', 'name']
        verbose_name = 'Feature Flag'
        verbose_name_plural = 'Feature Flags'

    def __str__(self):
        return f"{self.module.name} - {self.name}"


class SubscriptionPackage(models.Model):
    """
    Represents a subscription package that includes a set of modules and feature flags.
    Companies can subscribe to different packages based on their needs.
    """
    name = models.CharField(max_length=100, help_text="Name of the subscription package")
    code = models.CharField(max_length=50, unique=True, help_text="Unique code identifier for the package")
    description = models.TextField(blank=True, help_text="Detailed description of what's included in this package")
    modules = models.ManyToManyField(Module, related_name='subscription_packages')
    feature_flags = models.ManyToManyField(FeatureFlag, related_name='subscription_packages', blank=True)
    price_monthly = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Monthly subscription price for this package"
    )
    price_yearly = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        help_text="Yearly subscription price for this package"
    )
    is_active = models.BooleanField(default=True, help_text="Whether this package is currently available")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['price_monthly']
        verbose_name = 'Subscription Package'
        verbose_name_plural = 'Subscription Packages'

    def __str__(self):
        return self.name


class Subscription(models.Model):
    """
    Represents a company's subscription to a specific package.
    Tracks subscription details including start/end dates and payment status.
    """
    SUBSCRIPTION_TYPE_CHOICES = [
        ('monthly', 'Monthly'),
        ('yearly', 'Yearly'),
        ('trial', 'Trial'),
    ]

    PAYMENT_STATUS_CHOICES = [
        ('pending', 'Pending'),
        ('paid', 'Paid'),
        ('failed', 'Failed'),
        ('cancelled', 'Cancelled'),
    ]

    organization = models.ForeignKey(
        'master_data.Organization',
        on_delete=models.CASCADE,
        related_name='subscriptions',
        null=True,  # Temporarily allow null until Organization model is implemented
    )
    package = models.ForeignKey(SubscriptionPackage, on_delete=models.PROTECT, related_name='subscriptions')
    subscription_type = models.CharField(max_length=10, choices=SUBSCRIPTION_TYPE_CHOICES, default='monthly')
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=True)
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='pending')
    custom_modules = models.ManyToManyField(Module, blank=True, related_name='custom_subscriptions',
                                            help_text="Additional modules not included in the package")
    custom_features = models.ManyToManyField(FeatureFlag, blank=True, related_name='custom_subscriptions',
                                             help_text="Additional features not included in the package")
    custom_settings = models.TextField(blank=True, help_text="JSON string with custom subscription settings")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-start_date']
        verbose_name = 'Subscription'
        verbose_name_plural = 'Subscriptions'

    def __str__(self):
        org_name = self.organization.name if self.organization else "No Organization"
        return f"{org_name} - {self.package.name} ({self.get_subscription_type_display()})"

    def get_custom_settings(self):
        """Returns the custom settings as a dictionary"""
        if not self.custom_settings:
            return {}
        try:
            return json.loads(self.custom_settings)
        except json.JSONDecodeError:
            return {}

    def set_custom_settings(self, settings_dict):
        """Sets the custom settings from a dictionary"""
        self.custom_settings = json.dumps(settings_dict)

    def has_module_access(self, module_code):
        """Check if this subscription has access to a specific module"""
        # Check if module is in the package
        if self.package.modules.filter(code=module_code, is_active=True).exists():
            return True

        # Check if module is in custom modules
        if self.custom_modules.filter(code=module_code, is_active=True).exists():
            return True

        return False

    def has_feature_access(self, feature_code):
        """Check if this subscription has access to a specific feature"""
        # Check if feature is in the package
        if self.package.feature_flags.filter(code=feature_code, is_active=True).exists():
            return True

        # Check if feature is in custom features
        if self.custom_features.filter(code=feature_code, is_active=True).exists():
            return True

        return False
