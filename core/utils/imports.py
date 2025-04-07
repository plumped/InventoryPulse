from django.contrib import messages
from django.shortcuts import render, redirect

def handle_csv_import(form_class, importer_class, request, template_name, success_redirect, extra_context=None):
    if request.method == 'POST':
        form = form_class(request.POST, request.FILES)
        if form.is_valid():
            try:
                importer = importer_class(user=request.user, **form.cleaned_data)
                import_log = importer.run_import()

                messages.success(request, f"{import_log.successful_rows} von {import_log.total_rows} Zeilen erfolgreich importiert.")
                if import_log.failed_rows:
                    messages.warning(request, f"{import_log.failed_rows} Zeilen konnten nicht importiert werden.")
                return redirect(success_redirect, pk=import_log.pk)

            except Exception as e:
                messages.error(request, f"Fehler beim Import: {str(e)}")
    else:
        form = form_class()

    context = {'form': form}
    if extra_context:
        context.update(extra_context)
    return render(request, template_name, context)
