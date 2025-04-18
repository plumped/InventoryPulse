from django.contrib.auth.models import User
from django.db import models


def get_default_organization():
    """
    Returns the ID of the first Organization or creates a default one if none exists.
    Used as the default value for the organization field in Department model.
    """
    from master_data.models.organisations_models import Organization
    org = Organization.objects.first()
    if not org:
        org = Organization.objects.create(
            name="Default Organization",
            code="DEFAULT"
        )
    return org.id


class Organization(models.Model):
    """
    Represents a company or organization in the system.
    Organizations can have multiple departments and users.
    In a multi-tenant setup, each organization is a tenant with its own data.
    """
    name = models.CharField(max_length=200, help_text="Name of the organization")
    code = models.CharField(max_length=20, unique=True, help_text="Unique code identifier for the organization")
    address = models.TextField(blank=True, help_text="Physical address of the organization")
    phone = models.CharField(max_length=50, blank=True, help_text="Contact phone number")
    email = models.EmailField(blank=True, help_text="Contact email address")
    website = models.URLField(blank=True, help_text="Organization website")
    tax_id = models.CharField(max_length=50, blank=True, help_text="Tax identification number")
    is_active = models.BooleanField(default=True, help_text="Whether this organization is currently active")
    admin_users = models.ManyToManyField(
        User,
        related_name='administered_organizations',
        blank=True,
        help_text="Users who have administrative privileges for this organization"
    )

    # Multi-tenant specific fields
    subdomain = models.CharField(
        max_length=100,
        unique=True,
        null=True,
        blank=True,
        help_text="Subdomain for this organization (e.g., 'acme' for acme.example.com)"
    )
    subscription_active = models.BooleanField(
        default=True,
        help_text="Whether this organization's subscription is active"
    )
    subscription_package = models.ForeignKey(
        'module_management.SubscriptionPackage',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='organizations',
        help_text="The subscription package this organization is subscribed to"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Organization'
        verbose_name_plural = 'Organizations'

    def __str__(self):
        return self.name

    def get_all_users(self):
        """Returns all users associated with this organization through departments"""
        from django.db.models import Q

        # Get all departments in this organization
        departments = self.departments.all()

        # Get all users who are members of these departments or managers
        users = User.objects.filter(
            Q(departments__in=departments) |
            Q(managed_departments__in=departments) |
            Q(administered_organizations=self)
        ).distinct()

        return users


class Department(models.Model):
    """
    Represents a department within an organization.
    Departments have members and a manager.
    """
    name = models.CharField(max_length=100, help_text="Name of the department")
    code = models.CharField(max_length=10, unique=True, help_text="Unique code identifier for the department")
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name='departments',
        default=get_default_organization,
        help_text="The organization this department belongs to"
    )
    manager = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='managed_departments',
        help_text="User who manages this department"
    )
    members = models.ManyToManyField(
        User,
        related_name='departments',
        blank=True,
        help_text="Users who are members of this department"
    )
    description = models.TextField(blank=True, help_text="Description of the department's function")
    created_at = models.DateTimeField(default=models.functions.Now())
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['organization', 'name']
        verbose_name = 'Department'
        verbose_name_plural = 'Departments'
        unique_together = ['organization', 'name']

    def __str__(self):
        return f"{self.organization.name} - {self.name}"
