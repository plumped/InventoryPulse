import os
import json
import csv
import logging
import smtplib
import ftplib
import requests
import paramiko
from io import StringIO
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from datetime import datetime
from django.conf import settings
from django.template import Template, Context
from django.utils import timezone
from django.core.mail import EmailMultiAlternatives
from django.db import transaction

from order.models import PurchaseOrder
from .models import SupplierInterface, InterfaceLog


logger = logging.getLogger(__name__)


class InterfaceError(Exception):
    """Basisklasse für alle Interface-bezogenen Fehler"""
    pass


class InterfaceService:
    """Basisklasse für alle Interface-Services"""
    
    def __init__(self, interface):
        self.interface = interface
        self.supplier = interface.supplier
    
    def send_order(self, order):
        """Sendet eine Bestellung über die Schnittstelle"""
        raise NotImplementedError("Subklassen müssen diese Methode implementieren")
    
    def log_transmission(self, order, status, message="", request_data="", response_data="", user=None):
        """Protokolliert eine Übertragung"""
        log = InterfaceLog.objects.create(
            interface=self.interface,
            order=order,
            status=status,
            message=message,
            request_data=request_data,
            response_data=response_data,
            initiated_by=user
        )
        
        # Aktualisiere den Zeitpunkt der letzten Verwendung der Schnittstelle
        self.interface.last_used = timezone.now()
        self.interface.save(update_fields=['last_used'])
        
        return log
    
    def format_order_data(self, order):
        """Formatiert die Bestelldaten gemäß dem konfigurierten Format"""
        format_method = getattr(self, f"format_as_{self.interface.order_format}", None)
        if format_method:
            return format_method(order)
        else:
            raise InterfaceError(f"Nicht unterstütztes Format: {self.interface.order_format}")
    
    def format_as_csv(self, order):
        """Formatiert die Bestellung als CSV"""
        output = StringIO()
        writer = csv.writer(output)
        
        # Header
        writer.writerow([
            'Order Number', 'Supplier', 'Order Date', 'Product SKU', 
            'Product Name', 'Supplier SKU', 'Quantity', 'Unit Price', 'Total'
        ])
        
        # Bestellpositionen
        for item in order.items.all():
            writer.writerow([
                order.order_number,
                order.supplier.name,
                order.order_date.strftime('%Y-%m-%d'),
                item.product.sku,
                item.product.name,
                item.supplier_sku,
                item.quantity_ordered,
                item.unit_price,
                item.line_total
            ])
        
        return output.getvalue()
    
    def format_as_xml(self, order):
        """Formatiert die Bestellung als XML"""
        # Wenn eine benutzerdefinierte Vorlage existiert, diese verwenden
        if self.interface.template:
            template = Template(self.interface.template)
            context = Context({
                'order': order,
                'supplier': self.supplier,
                'items': order.items.all(),
            })
            return template.render(context)
        
        # Ansonsten Standard-XML-Format erstellen
        xml = '<?xml version="1.0" encoding="UTF-8"?>\n'
        xml += '<Order>\n'
        xml += f'  <OrderNumber>{order.order_number}</OrderNumber>\n'
        xml += f'  <OrderDate>{order.order_date.strftime("%Y-%m-%d")}</OrderDate>\n'
        xml += f'  <Supplier>{order.supplier.name}</Supplier>\n'
        xml += '  <Items>\n'
        
        for item in order.items.all():
            xml += '    <Item>\n'
            xml += f'      <ProductSKU>{item.product.sku}</ProductSKU>\n'
            xml += f'      <ProductName>{item.product.name}</ProductName>\n'
            xml += f'      <SupplierSKU>{item.supplier_sku}</SupplierSKU>\n'
            xml += f'      <Quantity>{item.quantity_ordered}</Quantity>\n'
            xml += f'      <UnitPrice>{item.unit_price}</UnitPrice>\n'
            xml += f'      <Total>{item.line_total}</Total>\n'
            xml += '    </Item>\n'
        
        xml += '  </Items>\n'
        xml += f'  <Subtotal>{order.subtotal}</Subtotal>\n'
        xml += f'  <Tax>{order.tax}</Tax>\n'
        xml += f'  <ShippingCost>{order.shipping_cost}</ShippingCost>\n'
        xml += f'  <Total>{order.total}</Total>\n'
        xml += '</Order>'
        
        return xml
    
    def format_as_json(self, order):
        """Formatiert die Bestellung als JSON"""
        data = {
            'order_number': order.order_number,
            'order_date': order.order_date.strftime('%Y-%m-%d'),
            'supplier': order.supplier.name,
            'items': []
        }
        
        for item in order.items.all():
            data['items'].append({
                'product_sku': item.product.sku,
                'product_name': item.product.name,
                'supplier_sku': item.supplier_sku,
                'quantity': float(item.quantity_ordered),
                'unit_price': float(item.unit_price),
                'total': float(item.line_total)
            })
        
        data['subtotal'] = float(order.subtotal)
        data['tax'] = float(order.tax)
        data['shipping_cost'] = float(order.shipping_cost)
        data['total'] = float(order.total)
        
        return json.dumps(data, indent=2)


class EmailInterfaceService(InterfaceService):
    """Service für E-Mail-Schnittstellen"""
    
    def send_order(self, order, user=None):
        """Sendet eine Bestellung per E-Mail"""
        try:
            # Formatieren der Bestelldaten
            order_data = self.format_order_data(order)
            
            # E-Mail-Betreff erstellen
            subject = self.interface.email_subject_template or f"Bestellung {order.order_number}"
            subject = subject.replace("{order_number}", order.order_number)
            
            # Empfänger festlegen
            to_emails = [email.strip() for email in self.interface.email_to.split(",") if email.strip()]
            if not to_emails:
                raise InterfaceError("Keine E-Mail-Empfänger konfiguriert")
            
            # CC-Empfänger festlegen
            cc_emails = [email.strip() for email in self.interface.email_cc.split(",") if email.strip()]
            
            # Nachrichtentext erstellen
            text_content = f"""
            Sehr geehrte Damen und Herren,
            
            anbei erhalten Sie unsere Bestellung mit der Nummer {order.order_number}.
            
            Mit freundlichen Grüßen
            Ihr Team von {settings.COMPANY_NAME if hasattr(settings, 'COMPANY_NAME') else 'InventoryPulse'}
            """
            
            # E-Mail erstellen
            email = EmailMultiAlternatives(
                subject=subject,
                body=text_content,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=to_emails,
                cc=cc_emails
            )
            
            # Bestimme den Dateinamen und MIME-Typ basierend auf dem Format
            format_to_extension = {
                'csv': ('csv', 'text/csv'),
                'xml': ('xml', 'application/xml'),
                'json': ('json', 'application/json'),
                'pdf': ('pdf', 'application/pdf'),
                'excel': ('xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
            }
            
            ext, mime_type = format_to_extension.get(
                self.interface.order_format, ('txt', 'text/plain')
            )
            
            # Anhang hinzufügen
            attachment = MIMEApplication(order_data.encode('utf-8'))
            attachment['Content-Disposition'] = f'attachment; filename="order_{order.order_number}.{ext}"'
            email.attach(attachment)
            
            # E-Mail senden
            email.send()
            
            # Erfolgreich protokollieren
            self.log_transmission(
                order=order,
                status='success',
                message="Bestellung erfolgreich per E-Mail gesendet",
                request_data=order_data,
                user=user
            )
            
            return True
            
        except Exception as e:
            # Fehler protokollieren
            error_message = f"Fehler beim Senden der Bestellung per E-Mail: {str(e)}"
            logger.error(error_message)
            
            self.log_transmission(
                order=order,
                status='failed',
                message=error_message,
                request_data=order_data if 'order_data' in locals() else "",
                user=user
            )
            
            raise InterfaceError(error_message)


class APIInterfaceService(InterfaceService):
    """Service für API-Schnittstellen"""
    
    def send_order(self, order, user=None):
        """Sendet eine Bestellung über eine API"""
        try:
            # URL überprüfen
            if not self.interface.api_url:
                raise InterfaceError("Keine API-URL konfiguriert")
            
            # Formatieren der Bestelldaten
            order_data = self.format_order_data(order)
            
            # Headers vorbereiten
            headers = {'Content-Type': 'application/json'}
            
            # API-Key hinzufügen, falls vorhanden
            if self.interface.api_key:
                headers['Authorization'] = f"Bearer {self.interface.api_key}"
            
            # Basic Auth hinzufügen, falls Benutzername und Passwort vorhanden
            auth = None
            if self.interface.username and self.interface.password:
                auth = (self.interface.username, self.interface.password)
            
            # Zusätzliche Konfiguration aus JSON laden
            config = self.interface.config_json or {}
            
            # Methode ermitteln (Standard: POST)
            method = config.get('http_method', 'POST').upper()
            
            # Endpunkt aufrufen
            response = None
            if method == 'POST':
                response = requests.post(
                    self.interface.api_url,
                    data=order_data,
                    headers=headers,
                    auth=auth,
                    timeout=30
                )
            elif method == 'PUT':
                response = requests.put(
                    self.interface.api_url,
                    data=order_data,
                    headers=headers,
                    auth=auth,
                    timeout=30
                )
            else:
                raise InterfaceError(f"Nicht unterstützte HTTP-Methode: {method}")
            
            # Antwort überprüfen
            response.raise_for_status()
            
            # Erfolgreich protokollieren
            self.log_transmission(
                order=order,
                status='success',
                message=f"Bestellung erfolgreich über API gesendet. Status: {response.status_code}",
                request_data=order_data,
                response_data=response.text,
                user=user
            )
            
            return True
            
        except requests.RequestException as e:
            # Fehler protokollieren
            error_message = f"API-Fehler: {str(e)}"
            response_text = getattr(e.response, 'text', '') if hasattr(e, 'response') else ''
            
            self.log_transmission(
                order=order,
                status='failed',
                message=error_message,
                request_data=order_data if 'order_data' in locals() else "",
                response_data=response_text,
                user=user
            )
            
            logger.error(error_message)
            raise InterfaceError(error_message)
            
        except Exception as e:
            # Allgemeiner Fehler
            error_message = f"Fehler beim Senden der Bestellung über API: {str(e)}"
            logger.error(error_message)
            
            self.log_transmission(
                order=order,
                status='failed',
                message=error_message,
                request_data=order_data if 'order_data' in locals() else "",
                user=user
            )
            
            raise InterfaceError(error_message)


class FTPInterfaceService(InterfaceService):
    """Service für FTP-Schnittstellen"""

    def send_order(self, order, user=None):
        """Sendet eine Bestellung über FTP"""
        try:
            # Host überprüfen
            if not self.interface.host:
                raise InterfaceError("Kein FTP-Host konfiguriert")

            # Formatieren der Bestelldaten
            order_data = self.format_order_data(order)

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

            # Port festlegen (Standard: 21)
            port = self.interface.port or 21

            # FTP-Verbindung herstellen
            ftp = ftplib.FTP()
            ftp.timeout = 30  # Increase timeout to 30 seconds
            ftp.connect(self.interface.host, port)
            ftp.login(self.interface.username, self.interface.password)
            ftp.set_pasv(True)  # Use passive mode which works better with firewalls

            # Properly encode and prepare the data
            from io import BytesIO
            file_data = order_data.encode('utf-8')
            data_stream = BytesIO(file_data)

            # Datei hochladen
            ftp.storbinary(f'STOR {remote_filename}', data_stream)
            ftp.quit()

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


class SFTPInterfaceService(InterfaceService):
    """Service für SFTP-Schnittstellen"""
    
    def send_order(self, order, user=None):
        """Sendet eine Bestellung über SFTP"""
        try:
            # Host überprüfen
            if not self.interface.host:
                raise InterfaceError("Kein SFTP-Host konfiguriert")
            
            # Formatieren der Bestelldaten
            order_data = self.format_order_data(order)
            
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
            
            # Port festlegen (Standard: 22)
            port = self.interface.port or 22
            
            # SFTP-Verbindung herstellen
            transport = paramiko.Transport((self.interface.host, port))
            transport.connect(username=self.interface.username, password=self.interface.password)
            
            sftp = paramiko.SFTPClient.from_transport(transport)
            
            # Temporäre Datei erstellen
            with StringIO(order_data) as file_obj:
                sftp.putfo(file_obj, full_remote_path)
            
            sftp.close()
            transport.close()
            
            # Erfolgreich protokollieren
            self.log_transmission(
                order=order,
                status='success',
                message=f"Bestellung erfolgreich per SFTP gesendet. Datei: {full_remote_path}",
                request_data=order_data,
                user=user
            )
            
            return True
            
        except Exception as e:
            # Fehler protokollieren
            error_message = f"Fehler beim Senden der Bestellung per SFTP: {str(e)}"
            logger.error(error_message)
            
            self.log_transmission(
                order=order,
                status='failed',
                message=error_message,
                request_data=order_data if 'order_data' in locals() else "",
                user=user
            )
            
            raise InterfaceError(error_message)


def get_interface_service(interface):
    """Factory-Methode für Interface-Services"""
    interface_type_code = interface.interface_type.code.lower()
    
    if interface_type_code == 'email':
        return EmailInterfaceService(interface)
    elif interface_type_code == 'api':
        return APIInterfaceService(interface)
    elif interface_type_code == 'ftp':
        return FTPInterfaceService(interface)
    elif interface_type_code == 'sftp':
        return SFTPInterfaceService(interface)
    else:
        raise InterfaceError(f"Nicht unterstützter Schnittstellentyp: {interface_type_code}")


def send_order_via_interface(order_id, interface_id=None, user=None):
    """
    Sendet eine Bestellung über eine Schnittstelle.
    Wenn interface_id nicht angegeben ist, wird die Standard-Schnittstelle des Lieferanten verwendet.
    """
    try:
        with transaction.atomic():
            # Bestellung abrufen
            order = PurchaseOrder.objects.get(pk=order_id)
            
            # Schnittstelle ermitteln
            interface = None
            if interface_id:
                interface = SupplierInterface.objects.get(pk=interface_id, supplier=order.supplier)
            else:
                # Standard-Schnittstelle des Lieferanten verwenden
                interface = SupplierInterface.objects.filter(
                    supplier=order.supplier,
                    is_default=True,
                    is_active=True
                ).first()
            
            if not interface:
                raise InterfaceError(f"Keine aktive Schnittstelle für Lieferant {order.supplier.name} gefunden")
            
            # Service abrufen und Bestellung senden
            service = get_interface_service(interface)
            result = service.send_order(order, user)
            
            return result
            
    except PurchaseOrder.DoesNotExist:
        raise InterfaceError(f"Bestellung mit ID {order_id} nicht gefunden")
        
    except SupplierInterface.DoesNotExist:
        raise InterfaceError(f"Schnittstelle mit ID {interface_id} nicht gefunden")
        
    except Exception as e:
        logger.error(f"Fehler beim Senden der Bestellung: {str(e)}")
        raise