from django.contrib.auth.models import User, Permission
from django.test import TestCase, Client
from django.urls import reverse


class PredefinedRolesViewTest(TestCase):
    """Test case for the predefined_roles view."""

    def setUp(self):
        """Set up test data."""
        # Create a test user
        self.user = User.objects.create_user(
            username='testuser',
            password='testpassword'
        )
        # Add required permission
        permission = Permission.objects.get(codename='view_group')
        self.user.user_permissions.add(permission)

        # Create a client
        self.client = Client()

    def test_predefined_roles_view_with_permission(self):
        """Test that a user with the right permission can access the view."""
        # Log in the user
        self.client.login(username='testuser', password='testpassword')

        # Access the view
        response = self.client.get(reverse('admin_dashboard:predefined_roles'))

        # Check that the response is successful
        self.assertEqual(response.status_code, 200)

        # Check that the correct template is used
        self.assertTemplateUsed(response, 'admin_dashboard/permissions/predefined_roles.html')

    def test_predefined_roles_view_without_login(self):
        """Test that an unauthenticated user is redirected to login."""
        # Access the view without logging in
        response = self.client.get(reverse('admin_dashboard:predefined_roles'))

        # Check that the response is a redirect to the login page
        self.assertEqual(response.status_code, 302)
