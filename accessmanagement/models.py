from django.db import models

from inventory.models import Warehouse
from organization.models import Department


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
                except:
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
