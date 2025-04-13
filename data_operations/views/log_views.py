import csv
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.contrib.auth.models import User
from django.http.response import JsonResponse, HttpResponse
from django.shortcuts import redirect, get_object_or_404, render

from core.utils.pagination import paginate_queryset
from data_operations.models.importers_models import ImportError as ImportErrorModel
from data_operations.models.importers_models import ImportLog


@login_required
@permission_required('import', 'view')
def import_log_list(request):
    """List all import logs."""
    # Base queryset
    queryset = ImportLog.objects.all()

    # Apply filters
    if 'search' in request.GET and request.GET['search']:
        search = request.GET['search']
        queryset = queryset.filter(file_name__icontains=search)

    if 'status' in request.GET and request.GET['status']:
        status = request.GET['status']
        queryset = queryset.filter(status=status)

    if 'user' in request.GET and request.GET['user']:
        user_id = request.GET['user']
        queryset = queryset.filter(created_by_id=user_id)

    if 'type' in request.GET and request.GET['type']:
        import_type = request.GET['type']
        queryset = queryset.filter(import_type=import_type)

    # Apply sorting
    sort_param = request.GET.get('sort', '-created_at')
    if sort_param:
        queryset = queryset.order_by(sort_param)

    # Pagination
    queryset = ImportLog.objects.all()
    import_logs = paginate_queryset(queryset, request.GET.get('page'), per_page=20)

    context = {
        'import_logs': import_logs,
        'users': User.objects.all(),
    }

    return render(request, 'core/import/import_log_list.html', context)


@login_required
@permission_required('import', 'view')
def import_log_detail(request, pk):
    """Show details of an import log."""
    log = get_object_or_404(ImportLog, pk=pk)
    errors = log.errors.all() if hasattr(log, 'errors') else ImportError.objects.filter(import_log=log)

    context = {
        'log': log,
        'errors': errors,
    }

    return render(request, 'core/import/import_log_detail.html', context)


@login_required
@permission_required('import', 'view')
def download_error_file(request, log_id):
    """Download the error file for an import log."""
    log = get_object_or_404(ImportLog, pk=log_id)

    # Check if actual error file exists and return it if it does
    if log.error_file and log.error_file.name:
        response = HttpResponse(log.error_file.read(), content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename="{log.file_name}_errors.csv"'
        return response

    # Otherwise generate a CSV with errors
    errors = log.errors.all() if hasattr(log, 'errors') else ImportError.objects.filter(import_log=log)

    if not errors.exists():
        messages.warning(request, 'Keine Fehler zum Herunterladen vorhanden.')
        return redirect('import_log_detail', pk=log_id)

    # CSV-Datei erstellen
    response = HttpResponse(content_type='text/csv')
    response[
        'Content-Disposition'] = f'attachment; filename="import_fehler_{log.pk}_{datetime.now().strftime("%Y%m%d")}.csv"'

    # CSV-Writer einrichten
    writer = csv.writer(response)

    # Header schreiben
    writer.writerow(['Zeile', 'Feld', 'Fehler', 'Wert'])

    # Fehler schreiben
    for error in errors:
        writer.writerow([error.row_number, error.field_name, error.error_message, error.field_value])

    return response


@login_required
@permission_required('import', 'delete')
def delete_import_log(request, log_id):
    """Delete an import log."""
    if request.method == 'POST':
        log = get_object_or_404(ImportLog, pk=log_id)

        # Save name for confirmation message
        log_name = f"Import #{log.pk} ({log.import_type})"

        # Delete all errors associated with the log
        ImportErrorModel.objects.filter(import_log=log).delete()

        # Delete the log
        log.delete()

        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            # For AJAX requests
            return JsonResponse({'success': True, 'message': f'{log_name} wurde gelöscht.'})
        else:
            # For normal requests
            messages.success(request, f'{log_name} wurde gelöscht.')
            return redirect('import_log_list')

    # If not a POST request, 405 Method Not Allowed
    return JsonResponse({'success': False, 'message': 'Nur POST-Anfragen sind erlaubt.'}, status=405)


@login_required
@permission_required('import', 'delete')
def bulk_delete_import_logs(request):
    """Delete multiple import logs."""
    if request.method == 'POST':
        # Get IDs from the request (comma-separated list)
        ids_str = request.POST.get('ids', '')

        if not ids_str:
            return JsonResponse({'success': False, 'message': 'Keine IDs angegeben.'}, status=400)

        try:
            # Convert IDs to a list
            ids = [int(id_str.strip()) for id_str in ids_str.split(',') if id_str.strip()]

            # Delete errors associated with the logs
            ImportErrorModel.objects.filter(import_log_id__in=ids).delete()

            # Delete logs
            deleted_count = ImportLog.objects.filter(pk__in=ids).delete()[0]

            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                # For AJAX requests
                return JsonResponse({'success': True, 'message': f'{deleted_count} Import-Logs wurden gelöscht.'})
            else:
                # For normal requests
                messages.success(request, f'{deleted_count} Import-Logs wurden gelöscht.')
                return redirect('import_log_list')

        except Exception as e:
            return JsonResponse({'success': False, 'message': f'Fehler beim Löschen: {str(e)}'}, status=500)

    # If not a POST request, 405 Method Not Allowed
    return JsonResponse({'success': False, 'message': 'Nur POST-Anfragen sind erlaubt.'}, status=405)
