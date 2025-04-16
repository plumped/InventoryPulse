import logging

from django import template

register = template.Library()
logger = logging.getLogger(__name__)


@register.filter(name='has_module_access')
def has_module_access_filter(company, module_code):
    """
    Prüft, ob ein Unternehmen Zugriff auf das angegebene Modul hat

    Beispiel:
    {% load module_tags %}
    {% if company|has_module_access:module.code %}
        <!-- Content here -->
    {% endif %}
    """
    # Prüfen, ob das Unternehmensabonnement aktiv ist
    if not company.subscription_active:
        return False

    # Prüfen, ob das Unternehmen Zugriff auf das Modul hat
    return company.has_module_access(module_code)


@register.simple_tag(takes_context=True, name='check_module_access')
def check_module_access(context, module_code):
    """
    Prüft, ob der aktuelle Benutzer Zugriff auf das angegebene Modul hat

    Beispiel:
    {% load module_tags %}
    {% if check_module_access module.code %}
        <a href="{% url 'inventory:dashboard' %}">Lagerverwaltung</a>
    {% endif %}
    """
    request = context['request']
    user = request.user

    # Admin-Benutzer haben immer Zugriff
    if user.is_superuser or user.is_staff:
        return True

    # Prüfen, ob der Benutzer angemeldet ist
    if not user.is_authenticated:
        return False

    # Prüfen, ob der Benutzer ein Unternehmensprofil hat
    if not hasattr(user, 'company_profile'):
        return False

    # Prüfen, ob das Unternehmen Zugriff auf das Modul hat
    company = user.company_profile.company

    # Prüfen, ob das Unternehmensabonnement aktiv ist
    if not company.subscription_active:
        return False

    # Prüfen, ob das Unternehmen Zugriff auf das Modul hat
    return company.has_module_access(module_code)



@register.simple_tag(takes_context=True)
def is_company_admin(context):
    """
    Prüft, ob der aktuelle Benutzer ein Unternehmensadministrator ist

    Beispiel:
    {% load module_tags %}

    {% if is_company_admin %}
        <a href="{% url 'module_management:manage_modules' %}">Module verwalten</a>
    {% endif %}
    """
    request = context['request']
    user = request.user

    # Admin-Benutzer haben immer Zugriff
    if user.is_superuser or user.is_staff:
        return True

    # Prüfen, ob der Benutzer angemeldet ist
    if not user.is_authenticated:
        return False

    # Prüfen, ob der Benutzer ein Unternehmensprofil hat
    if not hasattr(user, 'company_profile'):
        return False

    # Prüfen, ob der Benutzer ein Unternehmensadministrator ist
    return user.company_profile.is_admin


@register.inclusion_tag('module_management/tags/module_menu.html', takes_context=True)
def render_module_menu(context):
    """
    Rendert das Modulmenü basierend auf den verfügbaren Modulen und Berechtigungen

    Beispiel:
    {% load module_tags %}

    {% render_module_menu %}
    """
    request = context['request']
    user = request.user

    modules = []

    # Nur für angemeldete Benutzer
    if user.is_authenticated:
        from module_management.models import Module

        # Für Admins alle aktiven Module anzeigen
        if user.is_superuser or user.is_staff:
            modules = Module.objects.filter(is_active=True).order_by('order', 'name')
        # Für normale Benutzer nur abonnierte Module anzeigen
        elif hasattr(user, 'company_profile'):
            company = user.company_profile.company
            if company.subscription_active:
                modules = company.modules.filter(
                    is_active=True,
                    companymodulesubscription__is_active=True
                ).order_by('order', 'name')

    return {
        'modules': modules,
        'request': request
    }


@register.filter
def get_module_status(company, module_code):
    """
    Gibt den Status eines Moduls für ein Unternehmen zurück

    Rückgabewerte:
    - 'active': Das Modul ist aktiv und nicht abgelaufen
    - 'expired': Das Abonnement ist abgelaufen
    - 'inactive': Das Modul ist inaktiv
    - 'unsubscribed': Das Unternehmen hat das Modul nicht abonniert

    Beispiel:
    {% load module_tags %}

    {% with status=company|get_module_status:'inventory' %}
        {% if status == 'active' %}
            <span class="badge bg-success">Aktiv</span>
        {% elif status == 'expired' %}
            <span class="badge bg-warning">Abgelaufen</span>
        {% elif status == 'inactive' %}
            <span class="badge bg-danger">Inaktiv</span>
        {% else %}
            <span class="badge bg-secondary">Nicht abonniert</span>
        {% endif %}
    {% endwith %}
    """
    from module_management.models import Module
    from django.utils import timezone

    try:
        module = Module.objects.get(code=module_code)

        # Prüfen, ob das Unternehmen das Modul abonniert hat
        if not company.modules.filter(id=module.id).exists():
            return 'unsubscribed'

        subscription = company.module_subscriptions.get(module=module)

        if not subscription.is_active:
            return 'inactive'

        if subscription.expiry_date and subscription.expiry_date < timezone.now().date():
            return 'expired'

        return 'active'
    except (Module.DoesNotExist, Exception) as e:
        logger.error(f"Error in get_module_status for company {company.id} and module {module_code}: {str(e)}")
        return 'unsubscribed'


@register.filter
def multiply(value, arg):
    """Multiplies the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return value


@register.filter
def subtract(value, arg):
    """Subtracts the argument from the value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return value
