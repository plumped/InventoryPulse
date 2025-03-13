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

class CustomPermission(models.Model):
    """Dummy model for ContentType of the custom permissions."""

    class Meta:
        managed = False  # No database table creation
        default_permissions = ()
        permissions = (
            ('can_view_inventory', 'Kann Lagerverwaltung ansehen'),
            ('can_edit_inventory', 'Kann Lagerverwaltung bearbeiten'),
            ('can_create_inventory', 'Kann in Lagerverwaltung erstellen'),
            ('can_delete_inventory', 'Kann in Lagerverwaltung löschen'),
            ('can_admin_inventory', 'Kann Lagerverwaltung administrieren'),

            ('can_view_product', 'Kann Produktverwaltung ansehen'),
            ('can_edit_product', 'Kann Produktverwaltung bearbeiten'),
            ('can_create_product', 'Kann in Produktverwaltung erstellen'),
            ('can_delete_product', 'Kann in Produktverwaltung löschen'),
            ('can_admin_product', 'Kann Produktverwaltung administrieren'),

            ('can_view_supplier', 'Kann Lieferantenverwaltung ansehen'),
            ('can_edit_supplier', 'Kann Lieferantenverwaltung bearbeiten'),
            ('can_create_supplier', 'Kann in Lieferantenverwaltung erstellen'),
            ('can_delete_supplier', 'Kann in Lieferantenverwaltung löschen'),
            ('can_admin_supplier', 'Kann Lieferantenverwaltung administrieren'),

            ('can_view_report', 'Kann Berichtswesen ansehen'),
            ('can_edit_report', 'Kann Berichtswesen bearbeiten'),
            ('can_create_report', 'Kann in Berichtswesen erstellen'),
            ('can_delete_report', 'Kann in Berichtswesen löschen'),
            ('can_admin_report', 'Kann Berichtswesen administrieren'),

            ('can_view_import', 'Kann Datenimport ansehen'),
            ('can_edit_import', 'Kann Datenimport bearbeiten'),
            ('can_create_import', 'Kann in Datenimport erstellen'),
            ('can_delete_import', 'Kann in Datenimport löschen'),
            ('can_admin_import', 'Kann Datenimport administrieren'),

            ('can_view_order', 'Kann Bestellungen ansehen'),
            ('can_edit_order', 'Kann Bestellungen bearbeiten'),
            ('can_create_order', 'Kann Bestellungen erstellen'),
            ('can_delete_order', 'Kann Bestellungen löschen'),
            ('can_approve_order', 'Kann Bestellungen genehmigen'),
            ('can_admin_order', 'Kann Bestellverwaltung administrieren'),

            # Add permissions for the admin dashboard
            ('access_admin', 'Can access admin dashboard'),
        )


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
        
        Args:
            user: The user to check
            warehouse: The warehouse to check access for
            permission_type: Type of access ('view', 'edit', 'manage_stock')
            
        Returns:
            bool: True if access is granted, False otherwise
        """
        # Admin always has access
        if user.is_superuser:
            return True

        # Get departments from user profile
        try:
            user_departments = user.profile.departments.all()
        except:
            # Fallback to direct relationship if profile doesn't exist
            try:
                user_departments = user.departments.all()
            except:
                return False

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

        return False
