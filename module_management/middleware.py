import logging
import re

from django.conf import settings
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import resolve
from django.urls import reverse

from module_management.utils import is_feature_available

logger = logging.getLogger(__name__)


class ModuleAccessMiddleware:
    """Middleware zur Überprüfung des Modulzugriffs"""

    # Mapping von URL-Namespaces zu Modulcodes
    MODULE_MAPPING = {
        'inventory': 'inventory',
        'suppliers': 'supplier_management',
        'order': 'order_management',
        'rma': 'rma_management',
        'product_management': 'product_management',
        'tracking': 'tracking',
        'documents': 'document_management',
        'interfaces': 'interfaces',
        'data_operations': 'data_operations',
        'analytics': 'analytics',
        'api': 'api_access',
    }

    # URLs, die immer zugänglich sind
    EXEMPT_URLS = [
        '/admin/',
        '/login/',
        '/logout/',
        '/profile/',
        '/module_management/',
        '/static/',
        '/media/',
    ]

    def __init__(self, get_response):
        self.get_response = get_response

        # Feature-Code zu URL-Mapping
        self.FEATURE_URL_MAPPING = {
            # Inventory Features
            'inventory_multi_warehouse': ['/dashboard/inventory/warehouses/'],
            'inventory_stock_take': ['/dashboard/inventory/stocktake/'],

            # Order Features
            'order_templates': ['/dashboard/order/templates/'],
            'order_split_delivery': ['/dashboard/order/.*/splits/'],
            'order_suggestions': ['/dashboard/order/suggestions/'],

            # Dokumenten-Features
            'document_ocr': ['/dashboard/documents/ocr/'],

            # API-Features
            'api_access': ['/api/'],
        }

    def __call__(self, request):
        # Zuerst prüfen, ob Middleware aktiv sein soll
        if not getattr(settings, 'ENABLE_MODULE_ACCESS_CHECK', True):
            return self.get_response(request)

        # Nicht authentifizierte Benutzer dürfen passieren (Login-Seite etc.)
        if not request.user.is_authenticated:
            return self.get_response(request)

        # Admin-Benutzer dürfen immer passieren
        if request.user.is_superuser or request.user.is_staff:
            return self.get_response(request)

        # Prüfen, ob die URL von der Zugriffsüberprüfung ausgenommen ist
        path = request.path_info
        if request.user.is_authenticated and hasattr(request.user, 'company_profile'):
            company = request.user.company_profile.company

            # Feature-Flags prüfen
            for feature_code, url_patterns in self.FEATURE_URL_MAPPING.items():
                if any(re.match(pattern, path) for pattern in url_patterns):
                    if not is_feature_available(company, feature_code):
                        logger.warning(
                            f"User {request.user.username} attempted to access {path}, but lacks access to feature {feature_code}"
                        )

                        # Upgrade-Seite anzeigen statt Zugriff verweigern
                        return redirect(
                            reverse('module_management:subscription_plans') + f'?required_feature={feature_code}')

        if any(path.startswith(exempt_url) for exempt_url in self.EXEMPT_URLS):
            return self.get_response(request)

        try:
            # URL-Namespace ermitteln
            resolver_match = resolve(path)
            app_name = resolver_match.app_name or getattr(resolver_match, 'namespace', '')

            # Wenn die URL keinem Namespace zugeordnet ist, Anfrage durchlassen
            if not app_name:
                return self.get_response(request)

            # Prüfen, ob URL einem Modul zugeordnet ist
            if app_name in self.MODULE_MAPPING:
                module_code = self.MODULE_MAPPING[app_name]

                # Prüfen, ob der Benutzer Zugriff auf das Modul hat
                try:
                    if hasattr(request.user, 'company_profile'):
                        company = request.user.company_profile.company
                        if not company.subscription_active:
                            logger.warning(
                                f"User {request.user.username} attempted to access {path}, but company subscription is inactive")
                            return HttpResponseForbidden("Ihr Unternehmensabonnement ist inaktiv.")

                        if not company.has_module_access(module_code):
                            logger.warning(
                                f"User {request.user.username} attempted to access {path}, but lacks access to module {module_code}")

                            # Umleitung zur Abonnementseite, wenn verfügbar
                            if 'module_management:subscription' in [url.name for url in resolver_match.app.urls]:
                                return redirect(reverse('module_management:subscription'))

                            return HttpResponseForbidden(
                                f"Kein Zugriff auf dieses Modul ({module_code}). "
                                f"Bitte kontaktieren Sie Ihren Administrator, um dieses Modul zu abonnieren."
                            )
                    else:
                        logger.warning(f"User {request.user.username} has no company_profile, redirecting to profile")
                        return redirect(reverse('profile'))

                except Exception as e:
                    logger.exception(f"Error checking module access: {str(e)}")
                    # Bei Fehlern durchlassen, um die Benutzererfahrung nicht zu beeinträchtigen
                    return self.get_response(request)

        except Exception as e:
            logger.exception(f"Error in ModuleAccessMiddleware: {str(e)}")
            # Bei Fehlern durchlassen
            return self.get_response(request)

        # Alles in Ordnung, Anfrage durchlassen
        return self.get_response(request)
