from django.shortcuts import render, redirect

def handle_form_view(request, form_class, template, redirect_url, instance=None, context_extra=None):
    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            obj = form.save()
            return redirect(redirect_url)
    else:
        form = form_class(instance=instance)

    context = {'form': form}
    if context_extra:
        context.update(context_extra)
    return render(request, template, context)
