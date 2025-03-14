from django.apps import AppConfig
from django.utils.translation import gettext_lazy as _


class InterfacesConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'interfaces'
    verbose_name = _('Lieferanten-Schnittstellen')

    def ready(self):
        """Import signals when the app is ready."""
        import interfaces.signals  # noqa