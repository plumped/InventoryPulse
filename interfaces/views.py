from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
from django.db.models import Q
from django.http import JsonResponse
from django.urls import reverse
from django.views.decorators.http import require_POST

from accessmanagement.decorators import permission_required
from order.models import PurchaseOrder
from suppliers.models import Supplier

from .models import InterfaceType, SupplierInterface, InterfaceLog
from .services import send_order_via_interface, InterfaceError
from .forms import SupplierInterfaceForm, InterfaceTestForm


@login_required
@permission_required('supplier', 'view')
def interface_list(request):
    """Liste aller Schnittstellen."""
    interfaces = SupplierInterface.objects.select_related('supplier', 'interface_type')
    
    # Filter nach Lieferant
    supplier_id = request.GET.get('supplier')
    if supplier_id:
        interfaces = interfaces.filter(supplier_id=supplier_id)
    
    # Filter nach Schnittstellentyp
    interface_type_id = request.GET.get('type')
    if interface_type_id:
        interfaces = interfaces.filter(interface_type_id=interface_type_id)
    
    # Filter nach Status
    is_active = request.GET.get('active')
    if is_active == 'true':
        interfaces = interfaces.filter(is_active=True)
    elif is_active == 'false':
        interfaces = interfaces.filter(is_active=False)
    
    # Suche
    search_query = request.GET.get('search', '')
    if search_query:
        interfaces = interfaces.filter(
            Q(name__icontains=search_query) | 
            Q(supplier__name__icontains=search_query)
        )
    
    # Sortierung
    order_by = request.GET.get('order_by', 'supplier__name')
    if order_by not in ['name', 'supplier__name', 'interface_type__name', '-last_used']:
        order_by = 'supplier__name'
    
    interfaces = interfaces.order_by(order_by)
    
    # Paginierung
    paginator = Paginator(interfaces, 20)
    page = request.GET.get('page')
    try:
        interfaces_page = paginator.page(page)
    except PageNotAnInteger:
        interfaces_page = paginator.page(1)
    except EmptyPage:
        interfaces_page = paginator.page(paginator.num_pages)
    
    # Lieferanten und Schnittstellentypen für Filter
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')
    interface_types = InterfaceType.objects.filter(is_active=True).order_by('name')
    
    context = {
        'interfaces': interfaces_page,
        'suppliers': suppliers,
        'interface_types': interface_types,
        'supplier_id': supplier_id,
        'interface_type_id': interface_type_id,
        'is_active': is_active,
        'search_query': search_query,
        'order_by': order_by
    }
    
    return render(request, 'interfaces/interface_list.html', context)


@login_required
@permission_required('supplier', 'view')
def interface_detail(request, pk):
    """Detailansicht einer Schnittstelle."""
    interface = get_object_or_404(SupplierInterface.objects.select_related('supplier', 'interface_type'), pk=pk)
    
    # Übertragungsprotokolle dieser Schnittstelle
    logs = InterfaceLog.objects.filter(interface=interface).order_by('-timestamp')[:10]
    
    # Metriken für Dashboard
    success_count = InterfaceLog.objects.filter(interface=interface, status='success').count()
    failed_count = InterfaceLog.objects.filter(interface=interface, status='failed').count()
    total_count = InterfaceLog.objects.filter(interface=interface).count()
    success_rate = (success_count / total_count * 100) if total_count > 0 else 0
    
    # Testformular
    test_form = InterfaceTestForm()
    test_form.fields['order'].queryset = PurchaseOrder.objects.filter(
        supplier=interface.supplier,
        status__in=['approved', 'sent', 'partially_received']
    ).order_by('-order_date')
    
    context = {
        'interface': interface,
        'logs': logs,
        'success_count': success_count,
        'failed_count': failed_count,
        'total_count': total_count,
        'success_rate': success_rate,
        'test_form': test_form
    }
    
    return render(request, 'interfaces/interface_detail.html', context)


@login_required
@permission_required('supplier', 'create')
def interface_create(request):
    """Neue Schnittstelle erstellen."""
    if request.method == 'POST':
        form = SupplierInterfaceForm(request.POST)
        if form.is_valid():
            interface = form.save(commit=False)
            interface.created_by = request.user
            interface.save()
            
            messages.success(request, f'Schnittstelle "{interface.name}" für {interface.supplier.name} wurde erfolgreich erstellt.')
            return redirect('interface_detail', pk=interface.pk)
    else:
        # Vorauswahl des Lieferanten, falls aus Lieferantendetails aufgerufen
        supplier_id = request.GET.get('supplier')
        initial = {}
        if supplier_id:
            try:
                initial['supplier'] = Supplier.objects.get(pk=supplier_id)
            except Supplier.DoesNotExist:
                pass
        
        form = SupplierInterfaceForm(initial=initial)
    
    context = {
        'form': form,
        'title': 'Neue Schnittstelle erstellen'
    }
    
    return render(request, 'interfaces/interface_form.html', context)


@login_required
@permission_required('supplier', 'edit')
def interface_update(request, pk):
    """Schnittstelle bearbeiten."""
    interface = get_object_or_404(SupplierInterface, pk=pk)
    
    if request.method == 'POST':
        form = SupplierInterfaceForm(request.POST, instance=interface)
        if form.is_valid():
            interface = form.save()
            messages.success(request, f'Schnittstelle "{interface.name}" wurde erfolgreich aktualisiert.')
            return redirect('interface_detail', pk=interface.pk)
    else:
        form = SupplierInterfaceForm(instance=interface)
    
    context = {
        'form': form,
        'interface': interface,
        'title': f'Schnittstelle "{interface.name}" bearbeiten'
    }
    
    return render(request, 'interfaces/interface_form.html', context)


@login_required
@permission_required('supplier', 'delete')
def interface_delete(request, pk):
    """Schnittstelle löschen."""
    interface = get_object_or_404(SupplierInterface, pk=pk)
    
    if request.method == 'POST':
        supplier_name = interface.supplier.name
        interface_name = interface.name
        
        interface.delete()
        messages.success(request, f'Schnittstelle "{interface_name}" für {supplier_name} wurde erfolgreich gelöscht.')
        return redirect('interface_list')
    
    context = {
        'interface': interface
    }
    
    return render(request, 'interfaces/interface_confirm_delete.html', context)


@login_required
@permission_required('supplier', 'edit')
def interface_toggle_active(request, pk):
    """Aktivieren/Deaktivieren einer Schnittstelle."""
    interface = get_object_or_404(SupplierInterface, pk=pk)
    
    interface.is_active = not interface.is_active
    interface.save()
    
    status = "aktiviert" if interface.is_active else "deaktiviert"
    messages.success(request, f'Schnittstelle "{interface.name}" wurde {status}.')
    
    return redirect('interface_detail', pk=interface.pk)


@login_required
@permission_required('supplier', 'edit')
def interface_set_default(request, pk):
    """Schnittstelle als Standard setzen."""
    interface = get_object_or_404(SupplierInterface, pk=pk)
    
    # Alle anderen Schnittstellen dieses Lieferanten auf nicht-Standard setzen
    SupplierInterface.objects.filter(supplier=interface.supplier, is_default=True).exclude(pk=pk).update(is_default=False)
    
    interface.is_default = True
    interface.save()
    
    messages.success(request, f'Schnittstelle "{interface.name}" wurde als Standard für {interface.supplier.name} festgelegt.')
    
    return redirect('interface_detail', pk=interface.pk)


@login_required
@permission_required('order', 'edit')
@require_POST
def test_interface(request, pk):
    """Test einer Schnittstelle mit einer ausgewählten Bestellung."""
    interface = get_object_or_404(SupplierInterface, pk=pk)
    
    form = InterfaceTestForm(request.POST)
    if form.is_valid():
        order = form.cleaned_data['order']
        
        # Prüfen, ob die Bestellung zum Lieferanten der Schnittstelle passt
        if order.supplier != interface.supplier:
            messages.error(request, 'Die ausgewählte Bestellung gehört nicht zum Lieferanten dieser Schnittstelle.')
            return redirect('interface_detail', pk=interface.pk)
        
        try:
            from .services import get_interface_service
            
            service = get_interface_service(interface)
            result = service.send_order(order, user=request.user)
            
            if result:
                messages.success(request, f'Bestellung {order.order_number} wurde erfolgreich über die Schnittstelle "{interface.name}" gesendet.')
            else:
                messages.warning(request, f'Bestellung {order.order_number} konnte nicht gesendet werden.')
                
        except InterfaceError as e:
            messages.error(request, f'Fehler beim Testen der Schnittstelle: {str(e)}')
        except Exception as e:
            messages.error(request, f'Unerwarteter Fehler: {str(e)}')
    else:
        messages.error(request, 'Bitte wählen Sie eine gültige Bestellung aus.')
    
    return redirect('interface_detail', pk=interface.pk)


@login_required
@permission_required('order', 'edit')
def interface_logs(request, interface_id=None):
    """Liste der Übertragungsprotokolle, optional gefiltert nach Schnittstelle."""
    logs = InterfaceLog.objects.select_related('interface', 'order', 'initiated_by')
    
    # Filter nach Schnittstelle
    if interface_id:
        logs = logs.filter(interface_id=interface_id)
    
    # Filter nach Lieferant
    supplier_id = request.GET.get('supplier')
    if supplier_id:
        logs = logs.filter(interface__supplier_id=supplier_id)
    
    # Filter nach Status
    status = request.GET.get('status')
    if status:
        logs = logs.filter(status=status)
    
    # Filter nach Zeitraum
    date_from = request.GET.get('date_from')
    if date_from:
        logs = logs.filter(timestamp__gte=date_from)
    
    date_to = request.GET.get('date_to')
    if date_to:
        logs = logs.filter(timestamp__lte=date_to)
    
    # Suche
    search_query = request.GET.get('search', '')
    if search_query:
        logs = logs.filter(
            Q(message__icontains=search_query) | 
            Q(interface__name__icontains=search_query) |
            Q(order__order_number__icontains=search_query)
        )
    
    # Sortierung
    logs = logs.order_by('-timestamp')
    
    # Paginierung
    paginator = Paginator(logs, 20)
    page = request.GET.get('page')
    try:
        logs_page = paginator.page(page)
    except PageNotAnInteger:
        logs_page = paginator.page(1)
    except EmptyPage:
        logs_page = paginator.page(paginator.num_pages)
    
    # Filter-Optionen
    suppliers = Supplier.objects.filter(is_active=True).order_by('name')
    interfaces = SupplierInterface.objects.filter(is_active=True).order_by('name')
    
    context = {
        'logs': logs_page,
        'suppliers': suppliers,
        'interfaces': interfaces,
        'status_choices': InterfaceLog.STATUS_CHOICES,
        'interface_id': interface_id,
        'supplier_id': supplier_id,
        'status': status,
        'date_from': date_from,
        'date_to': date_to,
        'search_query': search_query
    }
    
    return render(request, 'interfaces/interface_logs.html', context)


@login_required
@permission_required('order', 'view')
def interface_log_detail(request, pk):
    """Detailansicht eines Übertragungsprotokolls."""
    log = get_object_or_404(
        InterfaceLog.objects.select_related('interface', 'order', 'initiated_by'),
        pk=pk
    )
    
    context = {
        'log': log
    }
    
    return render(request, 'interfaces/interface_log_detail.html', context)


@login_required
@permission_required('order', 'edit')
def send_order(request, order_id):
    """Bestellung über die Standard-Schnittstelle des Lieferanten senden."""
    order = get_object_or_404(PurchaseOrder, pk=order_id)
    
    # Nur genehmigte oder bereits gesendete Bestellungen können gesendet werden
    if order.status not in ['approved', 'sent', 'partially_received']:
        messages.error(request, f'Bestellung {order.order_number} kann nicht gesendet werden, da sie nicht genehmigt oder bereits gesendet ist.')
        return redirect('purchase_order_detail', pk=order_id)
    
    try:
        # Standard-Schnittstelle des Lieferanten ermitteln
        interface = SupplierInterface.objects.filter(
            supplier=order.supplier,
            is_default=True,
            is_active=True
        ).first()
        
        if not interface:
            messages.error(request, f'Keine aktive Standard-Schnittstelle für Lieferant {order.supplier.name} gefunden.')
            return redirect('purchase_order_detail', pk=order_id)
        
        # Bestellung senden
        result = send_order_via_interface(order_id, interface.id, request.user)
        
        if result:
            messages.success(request, f'Bestellung {order.order_number} wurde erfolgreich über die Schnittstelle "{interface.name}" gesendet.')
            
            # Bestellung als gesendet markieren, falls noch nicht geschehen
            if order.status == 'approved':
                order.status = 'sent'
                order.save()
                messages.info(request, f'Bestellung {order.order_number} wurde als gesendet markiert.')
        else:
            messages.warning(request, f'Bestellung {order.order_number} konnte nicht gesendet werden.')
            
    except InterfaceError as e:
        messages.error(request, f'Fehler beim Senden der Bestellung: {str(e)}')
    except Exception as e:
        messages.error(request, f'Unerwarteter Fehler: {str(e)}')
    
    return redirect('purchase_order_detail', pk=order_id)


@login_required
@permission_required('order', 'edit')
def select_interface(request, order_id):
    """Bestellung über eine ausgewählte Schnittstelle senden."""
    order = get_object_or_404(PurchaseOrder, pk=order_id)
    
    # Nur genehmigte oder bereits gesendete Bestellungen können gesendet werden
    if order.status not in ['approved', 'sent', 'partially_received']:
        messages.error(request, f'Bestellung {order.order_number} kann nicht gesendet werden, da sie nicht genehmigt oder bereits gesendet ist.')
        return redirect('purchase_order_detail', pk=order_id)
    
    # Verfügbare Schnittstellen für diesen Lieferanten
    interfaces = SupplierInterface.objects.filter(
        supplier=order.supplier,
        is_active=True
    ).select_related('interface_type')
    
    if not interfaces:
        messages.error(request, f'Keine aktiven Schnittstellen für Lieferant {order.supplier.name} gefunden.')
        return redirect('purchase_order_detail', pk=order_id)
    
    if request.method == 'POST':
        interface_id = request.POST.get('interface')
        
        try:
            # Bestellung senden
            result = send_order_via_interface(order_id, interface_id, request.user)
            
            if result:
                messages.success(request, f'Bestellung {order.order_number} wurde erfolgreich gesendet.')
                
                # Bestellung als gesendet markieren, falls noch nicht geschehen
                if order.status == 'approved':
                    order.status = 'sent'
                    order.save()
                    messages.info(request, f'Bestellung {order.order_number} wurde als gesendet markiert.')
            else:
                messages.warning(request, f'Bestellung {order.order_number} konnte nicht gesendet werden.')
                
        except InterfaceError as e:
            messages.error(request, f'Fehler beim Senden der Bestellung: {str(e)}')
        except Exception as e:
            messages.error(request, f'Unerwarteter Fehler: {str(e)}')
        
        return redirect('purchase_order_detail', pk=order_id)
    
    context = {
        'order': order,
        'interfaces': interfaces
    }
    
    return render(request, 'interfaces/select_interface.html', context)


@login_required
@permission_required('order', 'edit')
def retry_failed_transmission(request, log_id):
    """Erneuter Versuch, eine fehlgeschlagene Übertragung zu senden."""
    log = get_object_or_404(InterfaceLog, pk=log_id)
    
    # Nur fehlgeschlagene Übertragungen können wiederholt werden
    if log.status != 'failed':
        messages.error(request, 'Nur fehlgeschlagene Übertragungen können wiederholt werden.')
        return redirect('interface_log_detail', pk=log_id)
    
    try:
        # Bestellung erneut senden
        from .services import get_interface_service
        
        service = get_interface_service(log.interface)
        result = service.send_order(log.order, user=request.user)
        
        if result:
            # Versuchszähler des alten Logs erhöhen
            log.attempt_count += 1
            log.save()
            
            messages.success(request, f'Bestellung {log.order.order_number} wurde erfolgreich erneut gesendet.')
        else:
            messages.warning(request, f'Bestellung {log.order.order_number} konnte nicht erneut gesendet werden.')
            
    except InterfaceError as e:
        messages.error(request, f'Fehler beim erneuten Senden der Bestellung: {str(e)}')
    except Exception as e:
        messages.error(request, f'Unerwarteter Fehler: {str(e)}')
    
    return redirect('interface_log_detail', pk=log_id)


# AJAX-Endpunkte

@login_required
@permission_required('supplier', 'view')
def get_supplier_interfaces(request):
    """AJAX-Endpunkt, um die Schnittstellen eines Lieferanten abzurufen."""
    supplier_id = request.GET.get('supplier_id')
    
    if not supplier_id:
        return JsonResponse({'success': False, 'message': 'Lieferanten-ID erforderlich'})
    
    try:
        interfaces = SupplierInterface.objects.filter(
            supplier_id=supplier_id,
            is_active=True
        ).values('id', 'name', 'interface_type__name')
        
        return JsonResponse({
            'success': True,
            'interfaces': list(interfaces)
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })


@login_required
@permission_required('supplier', 'view')
def get_interface_fields(request):
    """AJAX-Endpunkt, um die relevanten Felder für einen Schnittstellentyp abzurufen."""
    interface_type_id = request.GET.get('interface_type_id')
    
    if not interface_type_id:
        return JsonResponse({'success': False, 'message': 'Schnittstellentyp-ID erforderlich'})
    
    try:
        interface_type = InterfaceType.objects.get(pk=interface_type_id)
        
        field_groups = {
            'email': ['email_to', 'email_cc', 'email_subject_template'],
            'api': ['api_url', 'username', 'password', 'api_key'],
            'ftp': ['host', 'port', 'remote_path', 'username', 'password'],
            'sftp': ['host', 'port', 'remote_path', 'username', 'password'],
            'webservice': ['api_url', 'username', 'password', 'api_key'],
        }
        
        code = interface_type.code.lower()
        relevant_fields = field_groups.get(code, [])
        
        return JsonResponse({
            'success': True,
            'relevant_fields': relevant_fields,
            'type_name': interface_type.name
        })
    except InterfaceType.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Schnittstellentyp nicht gefunden'
        })
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        })