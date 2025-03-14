from django.core.management.base import BaseCommand
from interfaces.models import InterfaceType


class Command(BaseCommand):
    help = 'Initialisiert die Standard-Schnittstellentypen'

    def handle(self, *args, **options):
        # Standard-Schnittstellentypen
        interface_types = [
            {
                'name': 'E-Mail',
                'code': 'email',
                'description': 'Bestellungen per E-Mail an Lieferanten senden.',
                'is_active': True
            },
            {
                'name': 'API',
                'code': 'api',
                'description': 'Bestellungen über eine REST-API an Lieferanten senden.',
                'is_active': True
            },
            {
                'name': 'FTP',
                'code': 'ftp',
                'description': 'Bestellungen auf einem FTP-Server ablegen.',
                'is_active': True
            },
            {
                'name': 'SFTP',
                'code': 'sftp',
                'description': 'Bestellungen sicher auf einem SFTP-Server ablegen.',
                'is_active': True
            },
            {
                'name': 'Webservice',
                'code': 'webservice',
                'description': 'Bestellungen über einen SOAP- oder anderen Webservice senden.',
                'is_active': True
            }
        ]

        # Zähler für die Statistik
        created_count = 0
        updated_count = 0

        for type_data in interface_types:
            # Versuchen, den Typ anhand des Codes zu finden
            interface_type, created = InterfaceType.objects.update_or_create(
                code=type_data['code'],
                defaults={
                    'name': type_data['name'],
                    'description': type_data['description'],
                    'is_active': type_data['is_active']
                }
            )

            if created:
                created_count += 1
                self.stdout.write(self.style.SUCCESS(f"Schnittstellentyp '{type_data['name']}' erstellt."))
            else:
                updated_count += 1
                self.stdout.write(self.style.WARNING(f"Schnittstellentyp '{type_data['name']}' aktualisiert."))

        self.stdout.write(self.style.SUCCESS(
            f"Initialisierung abgeschlossen. {created_count} Typen erstellt, {updated_count} Typen aktualisiert."
        ))