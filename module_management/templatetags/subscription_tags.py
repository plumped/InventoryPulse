from django import template

from module_management.utils import is_feature_available, get_subscription_level

register = template.Library()


@register.simple_tag(takes_context=True)
def has_feature(context, feature_code):
    """
    Prüft, ob der aktuelle Benutzer Zugriff auf ein bestimmtes Feature hat.
    """
    request = context['request']
    user = request.user

    # Admin-Benutzer haben immer Zugriff
    if user.is_superuser or user.is_staff:
        return True

    # Prüfen, ob Benutzer angemeldet ist
    if not user.is_authenticated:
        return False

    # Prüfen, ob der Benutzer ein Unternehmensprofil hat
    if not hasattr(user, 'company_profile'):
        return False

    # Prüfen, ob das Unternehmen das Feature hat
    company = user.company_profile.company
    return is_feature_available(company, feature_code)


@register.simple_tag(takes_context=True)
def get_subscription_name(context):
    """Gibt den Namen des aktuellen Subscription-Pakets zurück."""
    request = context['request']
    user = request.user

    if not user.is_authenticated or not hasattr(user, 'company_profile'):
        return "Kein Abonnement"

    company = user.company_profile.company
    if company.subscription_package:
        return company.subscription_package.name

    return "Basis-Abonnement"


@register.simple_tag(takes_context=True)
def subscription_level(context):
    """Gibt das aktuelle Subscription-Level zurück: basic, professional, enterprise."""
    request = context['request']
    user = request.user

    if not user.is_authenticated or not hasattr(user, 'company_profile'):
        return "basic"

    company = user.company_profile.company
    return get_subscription_level(company)


@register.inclusion_tag('module_management/tags/upgrade_notice.html', takes_context=True)
def show_upgrade_notice(context, feature_code, required_level='professional'):
    """
    Zeigt einen Upgrade-Hinweis an, wenn das erforderliche Feature nicht verfügbar ist.
    """
    request = context['request']
    user = request.user

    # Standardwerte setzen
    has_access = True
    current_level = 'basic'

    if user.is_authenticated and hasattr(user, 'company_profile'):
        company = user.company_profile.company
        has_access = is_feature_available(company, feature_code)
        current_level = get_subscription_level(company)

    return {
        'request': request,
        'has_access': has_access,
        'feature_code': feature_code,
        'required_level': required_level,
        'current_level': current_level
    }


@register.filter(name='replace')
def replace(value, arg):
    """
    Ersetzt ein Zeichen durch ein anderes.
    Syntax im Template: {{ text|replace:"_: " }}
    """
    try:
        old, new = arg.split(':')
        return value.replace(old, new)
    except Exception:
        return value
