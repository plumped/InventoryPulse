from django import template
from core.permissions import has_permission

register = template.Library()


@register.filter
def has_perm(user, permission_string):
    """
    Prüft in Templates, ob ein Benutzer eine Berechtigung hat.

    Verwendung:
    {% if user|has_perm:'inventory:view' %}
        <!-- Inhalt anzeigen -->
    {% endif %}
    """
    try:
        area, action = permission_string.split(':')
        return has_permission(user, area, action)
    except (ValueError, TypeError):
        return False