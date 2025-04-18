from datetime import date, timedelta

from django.contrib.auth.models import User
from django.http import HttpResponse
from django.test import TestCase, RequestFactory

from master_data.models.organisations_models import Organization, Department
from .middleware import ModuleAccessMiddleware
from .models import Module, FeatureFlag, SubscriptionPackage, Subscription


class ModuleModelTestCase(TestCase):
    """Test cases for the Module model"""

    def setUp(self):
        """Set up test data"""
        self.module = Module.objects.create(
            name="Inventory Management",
            code="inventory",
            description="Manage inventory and stock levels",
            is_active=True,
            price_monthly=10.00,
            price_yearly=100.00
        )

    def test_module_creation(self):
        """Test that a module can be created with the correct attributes"""
        self.assertEqual(self.module.name, "Inventory Management")
        self.assertEqual(self.module.code, "inventory")
        self.assertEqual(self.module.description, "Manage inventory and stock levels")
        self.assertTrue(self.module.is_active)
        self.assertEqual(self.module.price_monthly, 10.00)
        self.assertEqual(self.module.price_yearly, 100.00)

    def test_module_string_representation(self):
        """Test the string representation of a module"""
        self.assertEqual(str(self.module), "Inventory Management")


class FeatureFlagModelTestCase(TestCase):
    """Test cases for the FeatureFlag model"""

    def setUp(self):
        """Set up test data"""
        self.module = Module.objects.create(
            name="Inventory Management",
            code="inventory",
            description="Manage inventory and stock levels",
            is_active=True
        )

        self.feature_flag = FeatureFlag.objects.create(
            name="Barcode Scanning",
            code="barcode_scanning",
            description="Scan barcodes to quickly add items to inventory",
            module=self.module,
            is_active=True
        )

    def test_feature_flag_creation(self):
        """Test that a feature flag can be created with the correct attributes"""
        self.assertEqual(self.feature_flag.name, "Barcode Scanning")
        self.assertEqual(self.feature_flag.code, "barcode_scanning")
        self.assertEqual(self.feature_flag.description, "Scan barcodes to quickly add items to inventory")
        self.assertEqual(self.feature_flag.module, self.module)
        self.assertTrue(self.feature_flag.is_active)

    def test_feature_flag_string_representation(self):
        """Test the string representation of a feature flag"""
        self.assertEqual(str(self.feature_flag), "Inventory Management - Barcode Scanning")


class SubscriptionPackageModelTestCase(TestCase):
    """Test cases for the SubscriptionPackage model"""

    def setUp(self):
        """Set up test data"""
        self.module1 = Module.objects.create(
            name="Inventory Management",
            code="inventory",
            description="Manage inventory and stock levels",
            is_active=True
        )

        self.module2 = Module.objects.create(
            name="Order Management",
            code="order",
            description="Manage customer orders",
            is_active=True
        )

        self.feature_flag = FeatureFlag.objects.create(
            name="Barcode Scanning",
            code="barcode_scanning",
            description="Scan barcodes to quickly add items to inventory",
            module=self.module1,
            is_active=True
        )

        self.package = SubscriptionPackage.objects.create(
            name="Basic Package",
            code="basic",
            description="Basic package with essential modules",
            price_monthly=20.00,
            price_yearly=200.00,
            is_active=True
        )

        self.package.modules.add(self.module1, self.module2)
        self.package.feature_flags.add(self.feature_flag)

    def test_subscription_package_creation(self):
        """Test that a subscription package can be created with the correct attributes"""
        self.assertEqual(self.package.name, "Basic Package")
        self.assertEqual(self.package.code, "basic")
        self.assertEqual(self.package.description, "Basic package with essential modules")
        self.assertEqual(self.package.price_monthly, 20.00)
        self.assertEqual(self.package.price_yearly, 200.00)
        self.assertTrue(self.package.is_active)

    def test_subscription_package_modules(self):
        """Test that modules can be added to a subscription package"""
        self.assertEqual(self.package.modules.count(), 2)
        self.assertIn(self.module1, self.package.modules.all())
        self.assertIn(self.module2, self.package.modules.all())

    def test_subscription_package_feature_flags(self):
        """Test that feature flags can be added to a subscription package"""
        self.assertEqual(self.package.feature_flags.count(), 1)
        self.assertIn(self.feature_flag, self.package.feature_flags.all())

    def test_subscription_package_string_representation(self):
        """Test the string representation of a subscription package"""
        self.assertEqual(str(self.package), "Basic Package")


class SubscriptionModelTestCase(TestCase):
    """Test cases for the Subscription model"""

    def setUp(self):
        """Set up test data"""
        self.organization = Organization.objects.create(
            name="Test Company",
            code="TEST",
            subscription_active=True
        )

        self.module1 = Module.objects.create(
            name="Inventory Management",
            code="inventory",
            description="Manage inventory and stock levels",
            is_active=True
        )

        self.module2 = Module.objects.create(
            name="Order Management",
            code="order",
            description="Manage customer orders",
            is_active=True
        )

        self.feature_flag = FeatureFlag.objects.create(
            name="Barcode Scanning",
            code="barcode_scanning",
            description="Scan barcodes to quickly add items to inventory",
            module=self.module1,
            is_active=True
        )

        self.package = SubscriptionPackage.objects.create(
            name="Basic Package",
            code="basic",
            description="Basic package with essential modules",
            price_monthly=20.00,
            price_yearly=200.00,
            is_active=True
        )

        self.package.modules.add(self.module1)
        self.package.feature_flags.add(self.feature_flag)

        self.subscription = Subscription.objects.create(
            organization=self.organization,
            package=self.package,
            subscription_type="monthly",
            start_date=date.today(),
            end_date=date.today() + timedelta(days=30),
            is_active=True,
            payment_status="paid"
        )

        self.subscription.custom_modules.add(self.module2)

    def test_subscription_creation(self):
        """Test that a subscription can be created with the correct attributes"""
        self.assertEqual(self.subscription.organization, self.organization)
        self.assertEqual(self.subscription.package, self.package)
        self.assertEqual(self.subscription.subscription_type, "monthly")
        self.assertEqual(self.subscription.start_date, date.today())
        self.assertEqual(self.subscription.end_date, date.today() + timedelta(days=30))
        self.assertTrue(self.subscription.is_active)
        self.assertEqual(self.subscription.payment_status, "paid")

    def test_subscription_custom_modules(self):
        """Test that custom modules can be added to a subscription"""
        self.assertEqual(self.subscription.custom_modules.count(), 1)
        self.assertIn(self.module2, self.subscription.custom_modules.all())

    def test_subscription_has_module_access(self):
        """Test the has_module_access method"""
        # Module from package
        self.assertTrue(self.subscription.has_module_access("inventory"))
        # Custom module
        self.assertTrue(self.subscription.has_module_access("order"))
        # Non-existent module
        self.assertFalse(self.subscription.has_module_access("nonexistent"))

    def test_subscription_has_feature_access(self):
        """Test the has_feature_access method"""
        # Feature from package
        self.assertTrue(self.subscription.has_feature_access("barcode_scanning"))
        # Non-existent feature
        self.assertFalse(self.subscription.has_feature_access("nonexistent"))

    def test_subscription_custom_settings(self):
        """Test the custom settings methods"""
        # Set custom settings
        settings = {"max_users": 5, "storage_limit": "10GB"}
        self.subscription.set_custom_settings(settings)

        # Get custom settings
        retrieved_settings = self.subscription.get_custom_settings()
        self.assertEqual(retrieved_settings, settings)

        # Test with invalid JSON
        self.subscription.custom_settings = "invalid json"
        self.assertEqual(self.subscription.get_custom_settings(), {})


class ModuleAccessMiddlewareTestCase(TestCase):
    """Test cases for the ModuleAccessMiddleware"""

    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.middleware = ModuleAccessMiddleware(lambda r: HttpResponse())

        # Create a superuser
        self.superuser = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="password"
        )

        # Create a regular user
        self.user = User.objects.create_user(
            username="user",
            email="user@example.com",
            password="password"
        )

        # Create an organization
        self.organization = Organization.objects.create(
            name="Test Company",
            code="TEST",
            subscription_active=True
        )

        # Create a department and add the user to it
        self.department = Department.objects.create(
            name="Test Department",
            code="TEST-DEPT",
            organization=self.organization
        )
        self.department.members.add(self.user)

        # Create modules
        self.inventory_module = Module.objects.create(
            name="Inventory Management",
            code="inventory",
            description="Manage inventory and stock levels",
            is_active=True
        )

        self.order_module = Module.objects.create(
            name="Order Management",
            code="order",
            description="Manage customer orders",
            is_active=True
        )

        # Create a subscription package
        self.package = SubscriptionPackage.objects.create(
            name="Basic Package",
            code="basic",
            description="Basic package with essential modules",
            is_active=True
        )
        self.package.modules.add(self.inventory_module)

        # Assign the package to the organization
        self.organization.subscription_package = self.package
        self.organization.save()

    def test_superuser_access(self):
        """Test that superusers have access to all modules"""
        request = self.factory.get("/inventory/")
        request.user = self.superuser

        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

        request = self.factory.get("/order/")
        request.user = self.superuser

        response = self.middleware(request)
        self.assertEqual(response.status_code, 200)

    def test_user_with_access(self):
        """Test that users with access can access the module"""
        # Mock the TenantMiddleware.get_current_tenant method
        from core.middleware import TenantMiddleware
        original_get_current_tenant = TenantMiddleware.get_current_tenant
        TenantMiddleware.get_current_tenant = lambda: self.organization

        try:
            request = self.factory.get("/inventory/")
            request.user = self.user

            response = self.middleware(request)
            self.assertEqual(response.status_code, 200)
        finally:
            # Restore the original method
            TenantMiddleware.get_current_tenant = original_get_current_tenant

    def test_user_without_access(self):
        """Test that users without access cannot access the module"""
        # Mock the TenantMiddleware.get_current_tenant method
        from core.middleware import TenantMiddleware
        original_get_current_tenant = TenantMiddleware.get_current_tenant
        TenantMiddleware.get_current_tenant = lambda: self.organization

        try:
            request = self.factory.get("/order/")
            request.user = self.user
            request.headers = {}

            response = self.middleware(request)
            self.assertEqual(response.status_code, 302)  # Redirect to dashboard
        finally:
            # Restore the original method
            TenantMiddleware.get_current_tenant = original_get_current_tenant
