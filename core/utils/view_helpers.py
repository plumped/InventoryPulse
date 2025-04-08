from django.contrib import messages
from django.shortcuts import render, redirect

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
