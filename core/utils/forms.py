from django.contrib import messages
from django.shortcuts import render, redirect

def handle_form_view(request, form_class, template, redirect_url, instance=None, context_extra=None,
                     success_message=None, post_save_hook=None):
    if request.method == 'POST':
        form = form_class(request.POST, request.FILES, instance=instance)
        if form.is_valid():
            try:
                # Transaktion verwenden, um teilweise Aktualisierungen zu vermeiden
                from django.db import transaction

                with transaction.atomic():
                    obj = form.save()

                    # Post-save Hook mit Fehlerbehandlung
                    if post_save_hook:
                        hook_result = post_save_hook(obj, form.cleaned_data)
                        # Wenn der Hook False zurückgibt, ist ein Fehler aufgetreten
                        if hook_result is False:
                            raise Exception("Der post_save_hook ist fehlgeschlagen.")

                    # Nur bei Erfolg Bestätigungsmeldung anzeigen
                    if success_message:
                        messages.success(request, success_message)

                    return redirect(redirect_url)

            except Exception as e:
                # Bei Fehler: Fehlermeldung anzeigen und Form mit Fehlern zurückgeben
                error_message = f"Beim Speichern ist ein Fehler aufgetreten: {str(e)}"
                messages.error(request, error_message)
                # Optional: Fehler protokollieren
                import logging
                logger = logging.getLogger(__name__)
                logger.error(error_message)
        else:
            # Formular ist nicht gültig, Fehlermeldung anzeigen
            messages.error(request, "Bitte korrigieren Sie die Fehler im Formular.")
    else:
        form = form_class(instance=instance)

    context = {'form': form}
    if context_extra:
        context.update(context_extra)
    return render(request, template, context)
