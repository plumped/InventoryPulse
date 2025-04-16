import logging
from functools import wraps

from django.contrib import messages
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse

from module_management.utils import is_feature_available

logger = logging.getLogger(__name__)


def module_required(module_code):
    """
    Dekorator zur Prüfung des Modulzugriffs

    Beispiel:
    @module_required('inventory')
    def inventory_view(request):
        # Diese View ist nur zugänglich, wenn der Benutzer das Inventar-Modul abonniert hat
        ...
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Admin-Benutzer dürfen immer passieren
            if request.user.is_superuser or request.user.is_staff:
                return view_func(request, *args, **kwargs)

            if hasattr(request.user, 'company_profile'):
                company = request.user.company_profile.company

                # Prüfen, ob das Unternehmensabonnement aktiv ist
                if not company.subscription_active:
                    logger.warning(
                        f"User {request.user.username} attempted to access {request.path}, but company subscription is inactive")
                    return HttpResponseForbidden("Ihr Unternehmensabonnement ist inaktiv.")

                # Prüfen, ob der Benutzer Zugriff auf das Modul hat
                if company.has_module_access(module_code):
                    return view_func(request, *args, **kwargs)
                else:
                    logger.warning(
                        f"User {request.user.username} attempted to access {request.path}, but lacks access to module {module_code}")
                    return HttpResponseForbidden(
                        f"Kein Zugriff auf dieses Modul ({module_code}). "
                        f"Bitte kontaktieren Sie Ihren Administrator, um dieses Modul zu abonnieren."
                    )
            else:
                # Benutzer ohne Unternehmensprofil zum Profil umleiten
                logger.warning(f"User {request.user.username} has no company_profile, redirecting to profile")
                return redirect(reverse('profile'))

        return _wrapped_view

    return decorator


def company_admin_required(view_func):
    """
    Dekorator, der prüft, ob der Benutzer ein Unternehmensadministrator ist

    Beispiel:
    @company_admin_required
    def manage_company_modules(request):
        # Diese View ist nur für Unternehmensadministratoren zugänglich
        ...
    """

    @wraps(view_func)
    def _wrapped_view(request, *args, **kwargs):
        # Admin-Benutzer dürfen immer passieren
        if request.user.is_superuser or request.user.is_staff:
            return view_func(request, *args, **kwargs)

        if hasattr(request.user, 'company_profile'):
            if request.user.company_profile.is_admin:
                return view_func(request, *args, **kwargs)
            else:
                logger.warning(
                    f"User {request.user.username} attempted to access admin view {request.path}, but is not a company admin")
                return HttpResponseForbidden("Sie benötigen Administratorrechte für diese Aktion.")
        else:
            # Benutzer ohne Unternehmensprofil zum Profil umleiten
            return redirect(reverse('profile'))

    return _wrapped_view


def feature_required(feature_code, fallback_url=None):
    """
    Prüft, ob ein Benutzer Zugriff auf ein bestimmtes Feature hat.

    Beispiel:
    @feature_required('inventory_multi_warehouse')
    def warehouse_list(request):
        # Diese View wird nur ausgeführt, wenn der Benutzer Zugriff auf multi_warehouse hat
    """

    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            # Admin-Benutzer dürfen immer passieren
            if request.user.is_superuser or request.user.is_staff:
                return view_func(request, *args, **kwargs)

            # Unternehmen des Benutzers abrufen
            if not request.user.is_authenticated or not hasattr(request.user, 'company_profile'):
                if fallback_url:
                    return redirect(fallback_url)
                return redirect('module_management:subscription_plans')

            company = request.user.company_profile.company

            # Feature-Zugriff prüfen
            if is_feature_available(company, feature_code):
                return view_func(request, *args, **kwargs)
            else:
                # Fehlermeldung und Umleitung zur Subscription-Seite
                messages.warning(
                    request,
                    f"Für diese Funktion ist ein Upgrade auf einen höheren Plan erforderlich."
                )
                return redirect(reverse('module_management:subscription_plans') + f'?required_feature={feature_code}')

        return _wrapped_view

    return decorator
