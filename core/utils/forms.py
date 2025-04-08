from django.contrib import messages
from django.shortcuts import render, redirect

def handle_form_view(request, form_class, template, redirect_url, instance=None, context_extra=None,
                     success_message=None, post_save_hook=None):
    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            obj = form.save()
            if post_save_hook:
                post_save_hook(obj, form.cleaned_data)
            if success_message:
                messages.success(request, success_message)
            return redirect(redirect_url)
    else:
        form = form_class(instance=instance)

    context = {'form': form}
    if context_extra:
        context.update(context_extra)
    return render(request, template, context)
