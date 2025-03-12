from django.apps import AppConfig


class AdminDashboardConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'admin_dashboard'
    verbose_name = 'Admin-Dashboard'

    def ready(self):
        """
        Import signals when the app is ready.
        """
        import admin_dashboard.signals  # noqa