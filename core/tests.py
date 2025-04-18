from django.http import HttpResponse
from django.test import TestCase, RequestFactory

from master_data.models.organisations_models import Organization
from .middleware import TenantMiddleware


class TenantMiddlewareTestCase(TestCase):
    """Test cases for the TenantMiddleware"""
    
    def setUp(self):
        """Set up test data"""
        self.factory = RequestFactory()
        self.middleware = TenantMiddleware(get_response=lambda r: HttpResponse())
        
        # Create organizations with different subdomains
        self.org1 = Organization.objects.create(
            name="Test Company 1",
            code="TEST1",
            subdomain="test1",
            is_active=True
        )
        
        self.org2 = Organization.objects.create(
            name="Test Company 2",
            code="TEST2",
            subdomain="test2",
            is_active=True
        )
        
        # Create an inactive organization
        self.inactive_org = Organization.objects.create(
            name="Inactive Company",
            code="INACTIVE",
            subdomain="inactive",
            is_active=False
        )
    
    def test_tenant_identification_by_subdomain(self):
        """Test that the middleware correctly identifies tenants by subdomain"""
        # Test with org1 subdomain
        request = self.factory.get("/")
        request.META["HTTP_HOST"] = "test1.example.com"
        
        self.middleware.process_request(request)
        tenant = TenantMiddleware.get_current_tenant()
        
        self.assertEqual(tenant, self.org1)
        self.assertEqual(getattr(request, "organization", None), self.org1)
        
        # Test with org2 subdomain
        request = self.factory.get("/")
        request.META["HTTP_HOST"] = "test2.example.com"
        
        self.middleware.process_request(request)
        tenant = TenantMiddleware.get_current_tenant()
        
        self.assertEqual(tenant, self.org2)
        self.assertEqual(getattr(request, "organization", None), self.org2)
    
    def test_inactive_organization(self):
        """Test that inactive organizations are not set as tenants"""
        request = self.factory.get("/")
        request.META["HTTP_HOST"] = "inactive.example.com"
        
        self.middleware.process_request(request)
        tenant = TenantMiddleware.get_current_tenant()
        
        self.assertIsNone(tenant)
        self.assertFalse(hasattr(request, "organization"))
    
    def test_no_subdomain(self):
        """Test behavior when no subdomain is present"""
        request = self.factory.get("/")
        request.META["HTTP_HOST"] = "example.com"
        
        self.middleware.process_request(request)
        tenant = TenantMiddleware.get_current_tenant()
        
        self.assertIsNone(tenant)
        self.assertFalse(hasattr(request, "organization"))
    
    def test_www_subdomain(self):
        """Test that www subdomain is ignored"""
        request = self.factory.get("/")
        request.META["HTTP_HOST"] = "www.example.com"
        
        self.middleware.process_request(request)
        tenant = TenantMiddleware.get_current_tenant()
        
        self.assertIsNone(tenant)
        self.assertFalse(hasattr(request, "organization"))
    
    def test_admin_path_skipping(self):
        """Test that admin paths skip tenant identification"""
        request = self.factory.get("/admin/")
        request.META["HTTP_HOST"] = "test1.example.com"
        
        self.middleware.process_request(request)
        tenant = TenantMiddleware.get_current_tenant()
        
        self.assertIsNone(tenant)
        self.assertFalse(hasattr(request, "organization"))
    
    def test_static_path_skipping(self):
        """Test that static paths skip tenant identification"""
        request = self.factory.get("/static/css/style.css")
        request.META["HTTP_HOST"] = "test1.example.com"
        
        self.middleware.process_request(request)
        tenant = TenantMiddleware.get_current_tenant()
        
        self.assertIsNone(tenant)
        self.assertFalse(hasattr(request, "organization"))
    
    def test_tenant_clear(self):
        """Test that the tenant is cleared between requests"""
        # First request sets the tenant
        request1 = self.factory.get("/")
        request1.META["HTTP_HOST"] = "test1.example.com"
        
        self.middleware.process_request(request1)
        tenant1 = TenantMiddleware.get_current_tenant()
        
        self.assertEqual(tenant1, self.org1)
        
        # Second request should clear the previous tenant
        request2 = self.factory.get("/")
        request2.META["HTTP_HOST"] = "example.com"  # No subdomain
        
        self.middleware.process_request(request2)
        tenant2 = TenantMiddleware.get_current_tenant()
        
        self.assertIsNone(tenant2)
    
    def test_set_and_get_tenant(self):
        """Test the set_tenant and get_current_tenant methods"""
        # Initially no tenant
        self.assertIsNone(TenantMiddleware.get_current_tenant())
        
        # Set tenant
        TenantMiddleware.set_tenant(self.org1)
        self.assertEqual(TenantMiddleware.get_current_tenant(), self.org1)
        
        # Clear tenant
        TenantMiddleware.clear_tenant()
        self.assertIsNone(TenantMiddleware.get_current_tenant())