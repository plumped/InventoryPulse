import datetime

from django.contrib.auth.models import User
from django.db import models
from django.utils import timezone

from inventory.models import Warehouse
from master_data.models.organisations_models import Department


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    organization = models.ForeignKey(
        'master_data.Organization',
        on_delete=models.CASCADE,
        related_name='user_profiles',
        null=True,
        blank=True,
        help_text="The organization this user belongs to"
    )
    departments = models.ManyToManyField(Department, related_name='user_profiles', blank=True)

    def __str__(self):
        return f"Profil von {self.user.username}"

    def save(self, *args, **kwargs):
        # If departments are set but organization is not, set organization from the first department
        if not self.organization_id and self.pk:  # Only for existing profiles
            departments = self.departments.all()
            if departments.exists():
                self.organization = departments.first().organization
        super().save(*args, **kwargs)

class WarehouseAccess(models.Model):
    """Model for warehouse access rights per department."""
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    # Access rights
    can_view = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)
    can_manage_stock = models.BooleanField(default=False)

    class Meta:
        unique_together = ('warehouse', 'department')
        verbose_name_plural = 'Warehouse Access Rights'

    def __str__(self):
        return f"{self.department} -> {self.warehouse}"

    @classmethod
    def has_access(cls, user, warehouse, permission_type='view'):
        """
        Check if a user has access to a specific warehouse.
        """
        # Admin always has access
        if user.is_superuser:
            return True

        # Get departments from user profile
        try:
            if not hasattr(user, 'profile'):
                # Fallback: Direkte Beziehung versuchen, falls Profil nicht existiert
                try:
                    user_departments = user.departments.all()
                except (AttributeError, ValueError) as e:
                    # Log the error
                    import logging
                    logger = logging.getLogger('accessmanagement')
                    logger.warning(f"Error getting departments for user {user.id}: {str(e)}")
                    return False
            else:
                user_departments = user.profile.departments.all()

            for department in user_departments:
                try:
                    access = cls.objects.get(warehouse=warehouse, department=department)
                    if permission_type == 'view' and access.can_view:
                        return True
                    elif permission_type == 'edit' and access.can_edit:
                        return True
                    elif permission_type == 'manage_stock' and access.can_manage_stock:
                        return True
                except cls.DoesNotExist:
                    continue
        except Exception:
            return False

        return False


class PasswordHistory(models.Model):
    """
    Stores a history of user password hashes to enforce password history policy.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='password_history')
    password = models.CharField(max_length=255)  # Stores the hashed password
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = 'Password Histories'
        ordering = ['-created_at']

    def __str__(self):
        return f"Password history for {self.user.username} ({self.created_at})"


class Role(models.Model):
    """
    Represents a role in the system with a set of permissions.
    Roles are used for role-based access control.
    """
    name = models.CharField(max_length=100, unique=True, help_text="Name of the role")
    description = models.TextField(blank=True, help_text="Description of the role and its permissions")
    permissions = models.ManyToManyField(
        'auth.Permission',
        blank=True,
        related_name='roles',
        help_text="Permissions granted to users with this role"
    )
    is_system_role = models.BooleanField(
        default=False,
        help_text="Whether this is a system-defined role that cannot be modified"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Role'
        verbose_name_plural = 'Roles'

    def __str__(self):
        return self.name

    def has_permission(self, permission_codename):
        """
        Check if this role has a specific permission.

        Args:
            permission_codename: The codename of the permission to check

        Returns:
            bool: True if the role has the permission, False otherwise
        """
        if '.' in permission_codename:
            app_label, codename = permission_codename.split('.')
            return self.permissions.filter(
                content_type__app_label=app_label,
                codename=codename
            ).exists()
        else:
            return self.permissions.filter(codename=permission_codename).exists()


class UserRole(models.Model):
    """
    Associates a user with a role in the system.
    Users can have multiple roles, and roles can be scoped to specific organizations or departments.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='user_roles')
    role = models.ForeignKey(Role, on_delete=models.CASCADE, related_name='user_roles')
    organization = models.ForeignKey(
        'master_data.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='user_roles',
        help_text="If set, the role is only applicable within this organization"
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='user_roles',
        help_text="If set, the role is only applicable within this department"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Role'
        verbose_name_plural = 'User Roles'
        unique_together = [
            ('user', 'role', 'organization', 'department')
        ]

    def __str__(self):
        scope = ""
        if self.organization:
            scope = f" in {self.organization.name}"
            if self.department:
                scope += f" / {self.department.name}"
        elif self.department:
            scope = f" in {self.department.name}"

        return f"{self.user.username} as {self.role.name}{scope}"


class ObjectPermission(models.Model):
    """
    Represents a permission for a specific object.
    This allows for fine-grained control over who can access specific objects.
    """
    PERMISSION_TYPES = [
        ('view', 'View'),
        ('change', 'Change'),
        ('delete', 'Delete'),
        ('full', 'Full Access'),
    ]

    content_type = models.ForeignKey('contenttypes.ContentType', on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    permission_type = models.CharField(max_length=10, choices=PERMISSION_TYPES)

    # The permission can be granted to a user, a role, or a department
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='object_permissions'
    )
    role = models.ForeignKey(
        Role,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='object_permissions'
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='object_permissions'
    )

    # The organization that owns the object
    organization = models.ForeignKey(
        'master_data.Organization',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='object_permissions'
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Object Permission'
        verbose_name_plural = 'Object Permissions'
        unique_together = [
            ('content_type', 'object_id', 'permission_type', 'user', 'role', 'department')
        ]

    def __str__(self):
        obj_str = f"{self.content_type.model} #{self.object_id}"
        perm_str = self.get_permission_type_display()

        if self.user:
            return f"{self.user.username} has {perm_str} permission on {obj_str}"
        elif self.role:
            return f"Role '{self.role.name}' has {perm_str} permission on {obj_str}"
        elif self.department:
            return f"Department '{self.department.name}' has {perm_str} permission on {obj_str}"
        else:
            return f"{perm_str} permission on {obj_str}"


class UserSecuritySettings(models.Model):
    """
    Stores security settings for a user, such as password expiration date.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='security_settings')
    password_last_changed = models.DateTimeField(default=timezone.now)
    password_expiry_date = models.DateTimeField(null=True, blank=True)
    failed_login_attempts = models.PositiveIntegerField(default=0)
    last_failed_login = models.DateTimeField(null=True, blank=True)
    account_locked_until = models.DateTimeField(null=True, blank=True)
    require_password_change = models.BooleanField(default=False)

    def __str__(self):
        return f"Security settings for {self.user.username}"

    def save(self, *args, **kwargs):
        # Calculate password expiry date if not set
        if not self.password_expiry_date:
            from django.conf import settings
            expiry_days = getattr(settings, 'PASSWORD_EXPIRY_DAYS', 90)
            self.password_expiry_date = self.password_last_changed + datetime.timedelta(days=expiry_days)
        super().save(*args, **kwargs)

    def is_password_expired(self):
        """Check if the user's password has expired"""
        return timezone.now() >= self.password_expiry_date if self.password_expiry_date else False

    def is_account_locked(self):
        """Check if the user's account is locked due to failed login attempts"""
        if self.account_locked_until:
            return timezone.now() < self.account_locked_until
        return False

    def record_failed_login(self):
        """Record a failed login attempt and lock account if threshold is reached"""
        self.failed_login_attempts += 1
        self.last_failed_login = timezone.now()

        # Lock account after 5 failed attempts
        if self.failed_login_attempts >= 5:
            # Lock for 30 minutes
            self.account_locked_until = timezone.now() + datetime.timedelta(minutes=30)

        self.save()

    def reset_failed_login_attempts(self):
        """Reset failed login attempts counter after successful login"""
        self.failed_login_attempts = 0
        self.account_locked_until = None
        self.save()
