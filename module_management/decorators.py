import logging
from functools import wraps

from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.urls import reverse

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
