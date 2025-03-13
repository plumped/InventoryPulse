from django.db import models
from inventory.models import Warehouse
from organization.models import Department

# Custom Permission Model
class AdminDashboardPermission(models.Model):
    """Model for admin dashboard permissions."""

    class Meta:
        managed = False  # No database table creation
        default_permissions = ()
        permissions = (
            ('access_admin', 'Can access admin dashboard'),
        )

class WarehouseAccess(models.Model):
    warehouse = models.ForeignKey(Warehouse, on_delete=models.CASCADE)
    department = models.ForeignKey(Department, on_delete=models.CASCADE)
    # Zugriffsrechte definieren
    can_view = models.BooleanField(default=True)
    can_edit = models.BooleanField(default=False)
    can_manage_stock = models.BooleanField(default=False)

    class Meta:
        unique_together = ('warehouse', 'department')
        verbose_name_plural = 'Warehouse Access Rights'

    def __str__(self):
        return f"{self.department} -> {self.warehouse}"
