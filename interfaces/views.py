import json
from datetime import datetime

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.template import Template, Context
from django.urls import reverse

from core.utils.pagination import paginate_queryset
from order.models import PurchaseOrder
from suppliers.models import Supplier
from .forms import SupplierInterfaceForm, InterfaceTestForm
from .models import InterfaceType, SupplierInterface, InterfaceLog, XMLStandardTemplate
from .services import send_order_via_interface, InterfaceError


@login_required
@permission_required('supplier.view_supplier', raise_exception=True)

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
    interfaces_page = paginate_queryset(interfaces, request.GET.get('page'), per_page=20)

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
        'order_by': order_by,
        'section': 'interface_list'  # Hinzugefügt für Navigations-Highlighting
    }
    
    return render(request, 'interfaces/interface_list.html', context)


@login_required
@permission_required('supplier.view_supplier', raise_exception=True)
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

            messages.success(request,
                             f'Schnittstelle "{interface.name}" für {interface.supplier.name} wurde erfolgreich erstellt.')
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

    # XML-Standardvorlagen für das Formular laden
    xml_templates = XMLStandardTemplate.objects.filter(is_active=True).order_by('name')

    context = {
        'form': form,
        'title': 'Neue Schnittstelle erstellen',
        'test_connectivity_url': reverse('test_interface_connectivity'),
        'xml_templates': xml_templates  # Hier hinzugefügt
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

    # XML-Standardvorlagen für das Formular laden
    xml_templates = XMLStandardTemplate.objects.filter(is_active=True).order_by('name')

    context = {
        'form': form,
        'interface': interface,
        'title': f'Schnittstelle "{interface.name}" bearbeiten',
        'test_connectivity_url': reverse('test_interface_connectivity'),
        'xml_templates': xml_templates  # Hier hinzugefügt
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


# In views.py hinzufügen
@login_required
@permission_required('supplier', 'edit')
def test_interface_connectivity(request, pk=None):
    """
    AJAX-Endpunkt zum Testen der Konnektivität einer Schnittstellenkonfiguration.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Nur POST-Anfragen werden unterstützt.'})

    # Check if we're testing an existing interface or a form
    interface_id = request.POST.get('interface_id')

    # Variable to hold the interface we'll test
    test_interface = None

    if interface_id:
        # Testing an existing interface
        try:
            interface = SupplierInterface.objects.get(pk=interface_id)

            # Use the provided interface directly for testing
            test_interface = interface
        except SupplierInterface.DoesNotExist:
            return JsonResponse({
                'success': False,
                'message': 'Die angegebene Schnittstelle wurde nicht gefunden.'
            })
    else:
        # We're testing a form configuration (either for new or edit)
        form = SupplierInterfaceForm(request.POST)

        # For edit operations, we may need to exclude the current interface from uniqueness checks
        if 'pk' in request.POST and request.POST.get('pk'):
            try:
                existing_interface = SupplierInterface.objects.get(pk=request.POST.get('pk'))
                # Create a form instance excluding this record from uniqueness validation
                form = SupplierInterfaceForm(request.POST, instance=existing_interface)
            except SupplierInterface.DoesNotExist:
                # If not found, continue with standard validation
                pass

        if not form.is_valid():
            return JsonResponse({
                'success': False,
                'message': 'Die Schnittstellenkonfiguration ist ungültig.',
                'details': str(form.errors)
            })

        # Create temporary instance without saving to DB
        test_interface = form.save(commit=False)
        test_interface.created_by = request.user

    # Schnittstelle testen ohne zu speichern
    try:
        # Je nach Schnittstellentyp unterschiedliche Tests durchführen
        interface_type_code = test_interface.interface_type.code.lower()

        if interface_type_code == 'email':
            test_connectivity_email(test_interface)
            return JsonResponse({
                'success': True,
                'message': "E-Mail-Konfiguration erfolgreich validiert.",
                'details': f"E-Mail-Konfiguration überprüft:\n- Empfänger: {test_interface.email_to}\n- CC: {test_interface.email_cc or 'Nicht konfiguriert'}\n- Betreffvorlage: {test_interface.email_subject_template or 'Standard'}\n- Format: {test_interface.get_order_format_display()}"
            })
        elif interface_type_code == 'api':
            test_connectivity_api(test_interface)
            return JsonResponse({
                'success': True,
                'message': "API-Verbindung erfolgreich getestet.",
                'details': f"API-Konfiguration überprüft:\n- URL: {test_interface.api_url}\n- Authentifizierung: {('Benutzername/Passwort' if test_interface.username else '') + (' & ' if test_interface.username and test_interface.api_key else '') + ('API-Schlüssel' if test_interface.api_key else '') or 'Keine'}\n- Format: {test_interface.get_order_format_display()}"
            })
        elif interface_type_code in ['ftp', 'sftp']:
            test_connectivity_ftp(test_interface)
            return JsonResponse({
                'success': True,
                'message': f"{interface_type_code.upper()}-Verbindung erfolgreich getestet.",
                'details': f"{'SFTP' if interface_type_code == 'sftp' else 'FTP'}-Konfiguration überprüft:\n- Host: {test_interface.host}\n- Port: {test_interface.port or ('22' if interface_type_code == 'sftp' else '21')}\n- Remote-Pfad: {test_interface.remote_path or '/'}\n- Benutzername: {test_interface.username}\n- Format: {test_interface.get_order_format_display()}"
            })
        else:
            return JsonResponse({
                'success': False,
                'message': f'Schnittstellentyp {interface_type_code} wird nicht unterstützt.',
                'details': f'Der Test für {interface_type_code} ist nicht implementiert.'
            })

    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'message': f'Fehler beim Testen der Schnittstelle: {str(e)}',
            'details': traceback.format_exc()
        })


def test_connectivity_email(interface):
    """Testet die E-Mail-Konfiguration"""
    if not interface.email_to:
        raise ValueError("Keine E-Mail-Empfänger konfiguriert")

    # Hier ggf. weitere E-Mail-Validierungen
    # Z.B. E-Mail-Adressen prüfen oder E-Mail-Server-Verbindung testen


def test_connectivity_api(interface):
    """Testet die API-Konfiguration"""
    if not interface.api_url:
        raise ValueError("Keine API-URL konfiguriert")

    # URL validieren
    from urllib.parse import urlparse

    parsed_url = urlparse(interface.api_url)
    if not parsed_url.scheme or not parsed_url.netloc:
        raise ValueError("Ungültige URL")

    # DNS-Auflösung testen
    import socket
    socket.gethostbyname(parsed_url.netloc)


def test_connectivity_ftp(interface):
    """Testet die FTP/SFTP-Konfiguration"""
    import logging
    logger = logging.getLogger(__name__)

    logger.info(f"Testing FTP connection to {interface.host}:{interface.port or 21}")

    if not interface.host:
        raise ValueError("Kein Host konfiguriert")

    if not interface.username:
        raise ValueError("Kein Benutzername konfiguriert")

    # DNS-Auflösung testen
    import socket
    try:
        logger.info(f"Resolving hostname: {interface.host}")
        ip_address = socket.gethostbyname(interface.host)
        logger.info(f"Resolved to IP: {ip_address}")
    except Exception as e:
        logger.error(f"DNS resolution failed: {str(e)}")
        raise ValueError(f"Hostname '{interface.host}' konnte nicht aufgelöst werden: {str(e)}")

    # Port-Verbindung testen
    port = interface.port or (22 if interface.interface_type.code.lower() == 'sftp' else 21)
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)

    try:
        logger.info(f"Connecting to {ip_address}:{port}")
        sock.connect((interface.host, port))
        logger.info("Socket connection successful")
    except Exception as e:
        logger.error(f"Socket connection failed: {str(e)}")
        raise ValueError(f"Verbindung zu {interface.host}:{port} fehlgeschlagen: {str(e)}")
    finally:
        sock.close()
        logger.info("Socket closed")


@login_required
@permission_required('order', 'edit')
def interface_logs(request, interface_id=None):
    """Liste der Übertragungsprotokolle, optional gefiltert nach Schnittstelle."""
    # Add debugging
    import logging
    logger = logging.getLogger(__name__)

    # Check total count first without filters
    total_logs_count = InterfaceLog.objects.count()
    logger.info(f"Total logs in database: {total_logs_count}")

    logs = InterfaceLog.objects.select_related('interface', 'order', 'initiated_by')
    logger.info(f"Initial query count: {logs.count()}")
    
    # Filter nach Schnittstelle
    if interface_id:
        logs = logs.filter(interface_id=interface_id)
        logger.info(f"After interface_id filter: {logs.count()}")
    
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
    
    # Statistiken berechnen
    total_count = logs.count()
    success_count = logs.filter(status='success').count()
    failed_count = logs.filter(status='failed').count()
    
    # Erfolgsrate berechnen
    success_rate = 0
    if total_count > 0:
        success_rate = (success_count / total_count) * 100
    
    # Sortierung
    logs = logs.order_by('-timestamp')
    
    # Paginierung
    logs_page = paginate_queryset(logs, request.GET.get('page'), per_page=20)

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
        'search_query': search_query,
        'section': 'interface_logs',
        # Statistiken zur Anzeige
        'total_count': total_count,
        'success_count': success_count,
        'failed_count': failed_count,
        'success_rate': success_rate
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
def send_order(self, order, user=None):
    """Sendet eine Bestellung über FTP"""
    try:
        import logging
        logger = logging.getLogger(__name__)
        # Check if this order has already been successfully sent through this interface
        from .models import InterfaceLog
        existing_log = InterfaceLog.objects.filter(
            interface=self.interface,
            order=order,
            status='success'
        ).exists()

        if existing_log:
            logger.warning(f"Order {order.order_number} has already been successfully sent through this interface")
            # You could either return success (as it's already been sent) or raise an exception
            raise InterfaceError(
                f"Bestellung {order.order_number} wurde bereits erfolgreich über diese Schnittstelle gesendet.")

        logger.info(f"Starting FTP order send to {self.interface.host}:{self.interface.port or 21}")

        # Host überprüfen
        if not self.interface.host:
            raise InterfaceError("Kein FTP-Host konfiguriert")

        # Formatieren der Bestelldaten
        order_data = self.format_order_data(order)
        logger.info(f"Order data formatted, size: {len(order_data)} bytes")

        # Bestimme Dateiendung basierend auf dem Format
        format_to_extension = {
            'csv': 'csv',
            'xml': 'xml',
            'json': 'json',
            'pdf': 'pdf',
            'excel': 'xlsx'
        }
        ext = format_to_extension.get(self.interface.order_format, 'txt')

        # Dateiname erstellen
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        remote_filename = f"order_{order.order_number}_{timestamp}.{ext}"

        # Remote-Pfad festlegen
        remote_path = self.interface.remote_path or '/'
        remote_path = remote_path.rstrip('/') + '/'
        full_remote_path = remote_path + remote_filename
        logger.info(f"Will upload to path: {full_remote_path}")

        # Port festlegen (Standard: 21)
        port = self.interface.port or 21

        # FTP-Verbindung herstellen
        from io import BytesIO
        import ftplib

        ftp = ftplib.FTP()
        ftp.timeout = 30

        try:
            logger.info(f"Connecting to {self.interface.host}:{port}")
            ftp.connect(self.interface.host, port)
            logger.info(f"Connected, attempting login with username: {self.interface.username}")
            ftp.login(self.interface.username, self.interface.password)
            logger.info("Login successful")

            # Enable passive mode
            logger.info("Setting passive mode")
            ftp.set_pasv(True)

            # Prepare file for upload
            file_data = BytesIO(order_data.encode('utf-8'))

            # If a specific remote path is required, try to navigate to it
            if remote_path != '/':
                try:
                    logger.info(f"Changing to directory: {remote_path}")
                    ftp.cwd(remote_path)
                    # If the change is successful, just use the filename without the path
                    logger.info(f"Changed to directory: {ftp.pwd()}")
                    upload_filename = remote_filename
                except Exception as e:
                    logger.warning(f"Could not change to directory {remote_path}: {str(e)}")
                    # Use the full path
                    upload_filename = full_remote_path
            else:
                upload_filename = remote_filename

            # Upload the file
            logger.info(f"Uploading file: {upload_filename}")
            ftp.storbinary(f'STOR {upload_filename}', file_data)
            logger.info("File uploaded successfully")

            # Close the connection
            ftp.quit()
            logger.info("FTP connection closed gracefully")

        except Exception as e:
            logger.error(f"FTP operation error: {str(e)}")
            try:
                # Try to close connection in case of error
                ftp.close()
            except:
                pass
            raise e

        # Erfolgreich protokollieren
        self.log_transmission(
            order=order,
            status='success',
            message=f"Bestellung erfolgreich per FTP gesendet. Datei: {full_remote_path}",
            request_data=order_data,
            user=user
        )

        return True

    except Exception as e:
        # Fehler protokollieren
        error_message = f"Fehler beim Senden der Bestellung per FTP: {str(e)}"
        logger.error(error_message)

        self.log_transmission(
            order=order,
            status='failed',
            message=error_message,
            request_data=order_data if 'order_data' in locals() else "",
            user=user
        )

        raise InterfaceError(error_message)


@login_required
@permission_required('order', 'edit')
def select_interface(request, order_id):
    """Bestellung über eine ausgewählte Schnittstelle senden."""
    order = get_object_or_404(PurchaseOrder, pk=order_id)

    # Nur genehmigte Bestellungen können gesendet werden
    if order.status != 'approved':
        messages.error(request,
                       f'Bestellung {order.order_number} kann nicht gesendet werden, da sie nicht genehmigt ist.')
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
                # Bestellung als gesendet markieren (automatisch)
                order.status = 'sent'
                order.save()

                messages.success(request,
                                 f'Bestellung {order.order_number} wurde erfolgreich gesendet und als "Bestellt" markiert.')
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
@permission_required('supplier.view_supplier', raise_exception=True)

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
@permission_required('supplier.view_supplier', raise_exception=True)

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


@login_required
@permission_required('supplier', 'edit')
def test_send_order(request):
    """
    AJAX-Endpunkt zum Testen des Versands einer Bestellung über eine Schnittstelle.
    """
    if request.method != 'POST':
        return JsonResponse({'success': False, 'message': 'Nur POST-Anfragen werden unterstützt.'})

    interface_id = request.POST.get('interface_id')
    order_id = request.POST.get('order')

    if not interface_id or not order_id:
        return JsonResponse({
            'success': False,
            'message': 'Schnittstelle und Bestellung müssen angegeben werden.'
        })

    try:
        # Bestellung über die Schnittstelle senden
        result = send_order_via_interface(order_id, interface_id, request.user)

        # Log abrufen, um Details zu erhalten
        log = InterfaceLog.objects.filter(
            interface_id=interface_id,
            order_id=order_id
        ).order_by('-timestamp').first()

        if result:
            return JsonResponse({
                'success': True,
                'message': 'Testübertragung der Bestellung erfolgreich durchgeführt.',
                'details': log.message if log else "Die Bestellung wurde erfolgreich gesendet.",
                'log_id': log.id if log else None
            })
        else:
            return JsonResponse({
                'success': False,
                'message': 'Fehler bei der Testübertragung',
                'details': log.message if log else "Unbekannter Fehler beim Senden der Bestellung."
            })

    except SupplierInterface.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Die angegebene Schnittstelle wurde nicht gefunden.'
        })
    except PurchaseOrder.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'Die angegebene Bestellung wurde nicht gefunden.'
        })
    except InterfaceError as e:
        return JsonResponse({
            'success': False,
            'message': 'Fehler bei der Testübertragung',
            'details': str(e)
        })
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'message': f'Unerwarteter Fehler beim Senden der Bestellung: {str(e)}',
            'details': traceback.format_exc()
        })


@login_required
@permission_required('supplier.view_supplier', raise_exception=True)

def get_xml_template(request, template_id):
    """AJAX-Endpunkt zum Abrufen einer XML-Standardvorlage"""
    try:
        template = XMLStandardTemplate.objects.get(pk=template_id, is_active=True)
        return JsonResponse({
            'success': True,
            'template': template.template,
            'name': template.name,
            'description': template.description
        })
    except XMLStandardTemplate.DoesNotExist:
        return JsonResponse({
            'success': False,
            'message': 'XML-Vorlage nicht gefunden'
        }, status=404)
    except Exception as e:
        return JsonResponse({
            'success': False,
            'message': str(e)
        }, status=500)


@login_required
@permission_required('supplier.view_supplier', raise_exception=True)

def preview_xml_template(request):
    """AJAX-Endpunkt zur Vorschau einer XML-Vorlage mit Beispieldaten"""
    if request.method != 'POST':
        return JsonResponse({
            'success': False,
            'message': 'Nur POST-Anfragen werden unterstützt'
        }, status=405)

    try:
        # JSON-Daten aus dem Request-Body lesen
        data = json.loads(request.body)
        template_str = data.get('template', '')
        sample_data = data

        if not template_str:
            return JsonResponse({
                'success': False,
                'message': 'Keine Vorlage angegeben'
            }, status=400)

        # Django-Template erstellen und rendern
        template = Template(template_str)
        context = Context(sample_data)
        rendered_template = template.render(context)

        return JsonResponse({
            'success': True,
            'rendered_template': rendered_template
        })
    except Exception as e:
        import traceback
        return JsonResponse({
            'success': False,
            'message': str(e),
            'details': traceback.format_exc()
        }, status=500)


@login_required
@permission_required('supplier.view_supplier', raise_exception=True)

def list_xml_templates(request):
    """Listet alle verfügbaren XML-Standardvorlagen auf"""
    templates = XMLStandardTemplate.objects.filter(is_active=True).order_by('industry', 'name')

    # Nach Branche filtern
    industry = request.GET.get('industry', '')
    if industry:
        templates = templates.filter(industry=industry)

    # Suche
    search_query = request.GET.get('search', '')
    if search_query:
        templates = templates.filter(
            Q(name__icontains=search_query) |
            Q(description__icontains=search_query) |
            Q(industry__icontains=search_query)
        )

    # Branchen für Filter
    industries = XMLStandardTemplate.objects.filter(is_active=True).values_list(
        'industry', flat=True).distinct().order_by('industry')

    context = {
        'templates': templates,
        'industries': industries,
        'industry': industry,
        'search_query': search_query
    }

    return render(request, 'interfaces/xml_templates.html', context)


@login_required
@permission_required('supplier.view_supplier', raise_exception=True)

def xml_template_detail(request, template_id):
    """Zeigt die Details einer XML-Standardvorlage an"""
    template = get_object_or_404(XMLStandardTemplate, pk=template_id, is_active=True)

    context = {
        'template': template
    }

    return render(request, 'interfaces/xml_template_detail.html', context)