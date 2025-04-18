from django import template
from django.utils.safestring import mark_safe

from module_management.models import Module, Subscription

register = template.Library()


@register.simple_tag
def is_module_active(module_code):
    """
    Check if a module is active.
    Usage: {% is_module_active "module_code" %}
    """
    try:
        module = Module.objects.get(code=module_code)
        return module.is_active
    except Module.DoesNotExist:
        return False


@register.simple_tag
def get_module_info(module_code):
    """
    Get information about a module.
    Usage: {% get_module_info "module_code" as module_info %}
    """
    try:
        return Module.objects.get(code=module_code)
    except Module.DoesNotExist:
        return None


@register.simple_tag(takes_context=True)
def has_module_access(context, module_code):
    """
    Check if the current user has access to a module.
    Usage: {% has_module_access "module_code" %}
    """
    request = context.get('request')
    if not request or not request.user.is_authenticated:
        return False

    # For superusers, always return True
    if request.user.is_superuser:
        return True

    # Check if the user's organization has an active subscription with this module
    try:
        # Get user's organization through profile
        if hasattr(request.user, 'profile') and hasattr(request.user.profile, 'departments'):
            departments = request.user.profile.departments.all()
            if departments.exists():
                organization = departments.first().organization

                # Check if organization has an active subscription with this module
                active_subscriptions = Subscription.objects.filter(
                    organization=organization,
                    is_active=True
                )

                for subscription in active_subscriptions:
                    if subscription.has_module_access(module_code):
                        return True
    except Exception:
        pass

    return False


@register.filter
def module_badge(module, css_class=""):
    """
    Render a badge for a module with its status.
    Usage: {{ module|module_badge }}
    """
    if not module:
        return ""

    if module.is_active:
        badge_class = "bg-success"
        status = "Active"
    else:
        badge_class = "bg-secondary"
        status = "Inactive"

    return mark_safe(f'<span class="badge {badge_class} {css_class}">{status}</span>')


@register.inclusion_tag('module_management/tags/module_card.html')
def module_card(module):
    """
    Render a card for a module.
    Usage: {% module_card module %}
    """
    return {'module': module}


@register.inclusion_tag('module_management/tags/subscription_info.html', takes_context=True)
def subscription_info(context):
    """
    Render subscription information for the current user.
    Usage: {% subscription_info %}
    """
    request = context.get('request')
    subscription = None
    organization = None

    if request and request.user.is_authenticated:
        if hasattr(request.user, 'profile') and hasattr(request.user.profile, 'departments'):
            departments = request.user.profile.departments.all()
            if departments.exists():
                organization = departments.first().organization

                # Get active subscription
                subscription = Subscription.objects.filter(
                    organization=organization,
                    is_active=True
                ).first()

    return {
        'subscription': subscription,
        'organization': organization
    }
