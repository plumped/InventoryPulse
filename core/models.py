from django.contrib.auth.models import User
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

from .utils.encryption import EncryptedTextField


class TenantModel(models.Model):
    """
    Abstract base model for all tenant-specific models.
    All models that should be scoped to a tenant (organization) should inherit from this class.
    """
    organization = models.ForeignKey(
        'master_data.Organization',
        on_delete=models.CASCADE,
        related_name='%(class)ss',
        help_text="The organization (tenant) this record belongs to"
    )

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        # If organization is not set and there's a current tenant in thread local storage,
        # set the organization from the current tenant
        if not self.organization_id and hasattr(self, '_current_tenant'):
            self.organization = self._current_tenant
        super().save(*args, **kwargs)


class SensitiveData(models.Model):
    """
    Example model demonstrating how to use encrypted fields for sensitive data.
    This model stores sensitive information in encrypted form.
    """
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sensitive_data')

    # Encrypted fields
    _credit_card_number = models.TextField(blank=True, null=True, db_column='credit_card_number')
    _tax_id = models.TextField(blank=True, null=True, db_column='tax_id')
    _personal_notes = models.TextField(blank=True, null=True, db_column='personal_notes')

    # Descriptors for encrypted fields
    credit_card_number = EncryptedTextField('_credit_card_number')
    tax_id = EncryptedTextField('_tax_id')
    personal_notes = EncryptedTextField('_personal_notes')

    # Non-encrypted fields
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Sensitive Data'
        verbose_name_plural = 'Sensitive Data'

    def __str__(self):
        return f"Sensitive data for {self.user.username}"

    def save(self, *args, **kwargs):
        # Encrypt the data before saving
        # This is handled automatically by the EncryptedTextField descriptors
        super().save(*args, **kwargs)


class AuditLog(models.Model):
    """
    Model for storing audit logs of sensitive operations.
    """
    ACTION_TYPES = [
        ('create', 'Create'),
        ('update', 'Update'),
        ('delete', 'Delete'),
        ('view', 'View'),
        ('export', 'Export'),
        ('login', 'Login'),
        ('logout', 'Logout'),
        ('password_change', 'Password Change'),
        ('permission_change', 'Permission Change'),
        ('other', 'Other'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(max_length=20, choices=ACTION_TYPES)
    timestamp = models.DateTimeField(default=timezone.now)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True, null=True)

    # For linking to the affected object
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')

    # Additional data about the action
    data = models.JSONField(blank=True, null=True)

    # For tracking changes to objects
    before_state = models.JSONField(blank=True, null=True)
    after_state = models.JSONField(blank=True, null=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['user']),
            models.Index(fields=['action']),
            models.Index(fields=['timestamp']),
            models.Index(fields=['content_type', 'object_id']),
        ]

    def __str__(self):
        user_str = self.user.username if self.user else 'Anonymous'
        action_str = self.get_action_display()
        obj_str = f"{self.content_type.model} #{self.object_id}" if self.content_type else "N/A"
        return f"{user_str} {action_str} {obj_str} at {self.timestamp}"
