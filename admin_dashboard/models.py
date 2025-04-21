from django.db import models

class AdminDashboardPermission(models.Model):
    """
    Dieses Modell existiert nur für Berechtigungszwecke.
    """
    class Meta:
        managed = False
        default_permissions = ()
        permissions = [
            ('view_admin_dashboard', 'Can view admin dashboard'),
            # Weitere benötigte Berechtigungen...
        ]
        app_label = 'admin_dashboard'