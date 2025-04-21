import logging

from django.contrib import messages
from django.shortcuts import redirect

from core.utils.access import has_object_permission

logger = logging.getLogger('permissions')

def handle_model_add(request, form_class, model_name_singular, success_redirect, context_extra=None, instance=None):
    if request.method == 'POST':
        form = form_class(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            if instance:
                for field in instance._meta.fields:
                    if hasattr(instance, field.name) and not hasattr(obj, field.name):
                        setattr(obj, field.name, getattr(instance, field.name))
            obj.save()
            messages.success(request, f'{model_name_singular} wurde erfolgreich hinzugefügt.')
            return redirect(success_redirect)
    else:
        form = form_class()

    context = {'form': form}
    if context_extra:
        context.update(context_extra)
    return context

def handle_model_update(request, instance, form_class, model_name_singular, success_redirect, context_extra=None):
    if request.method == 'POST':
        form = form_class(request.POST, instance=instance)
        if form.is_valid():
            form.save()
            messages.success(request, f'{model_name_singular} wurde erfolgreich aktualisiert.')
            return redirect(success_redirect)
    else:
        form = form_class(instance=instance)

    context = {'form': form, model_name_singular.lower(): instance}
    if context_extra:
        context.update(context_extra)
    return context

def handle_model_delete(request, instance, model_name_singular, success_redirect, context_extra=None):
    if request.method == 'POST':
        instance.delete()
        messages.success(request, f'{model_name_singular} wurde erfolgreich gelöscht.')
        return redirect(success_redirect)

    context = {model_name_singular.lower(): instance}
    if context_extra:
        context.update(context_extra)
    return context


def check_permission(user, obj=None, permission_type='view', django_permission=None, valid_status=None):
    """
    Centralized function to check if a user has permission to perform an action.

    Args:
        user: The user to check permissions for
        obj: The object to check permissions for (optional)
        permission_type: The type of permission to check ('view', 'edit', or 'delete')
        django_permission: The Django permission string to check (e.g., 'app_label.change_model')
        valid_status: A status or list of statuses that the object must have (optional)

    Returns:
        Boolean: True if the user has permission, False otherwise
    """
    # Superuser always has access
    if user.is_superuser:
        logger.debug(f"Superuser {user.username} granted {permission_type} permission")
        return True

    # Check Django permission if specified
    if django_permission and not user.has_perm(django_permission):
        logger.debug(f"User {user.username} denied {permission_type} permission - missing Django permission {django_permission}")
        return False

    # Check object-level permission if an object is provided
    if obj and not has_object_permission(user, obj, permission_type):
        logger.debug(f"User {user.username} denied {permission_type} permission for {obj.__class__.__name__}:{getattr(obj, 'id', 'N/A')}")
        return False

    # Check status if specified
    if valid_status and hasattr(obj, 'status'):
        if isinstance(valid_status, (list, tuple)):
            if obj.status not in valid_status:
                logger.debug(f"User {user.username} denied {permission_type} permission - invalid status {obj.status}, expected one of {valid_status}")
                return False
        elif obj.status != valid_status:
            logger.debug(f"User {user.username} denied {permission_type} permission - invalid status {obj.status}, expected {valid_status}")
            return False

    # All checks passed
    logger.debug(f"User {user.username} granted {permission_type} permission")
    return True
