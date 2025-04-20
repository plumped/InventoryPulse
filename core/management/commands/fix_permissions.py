from django.contrib.auth.models import Permission
from django.core.management.base import BaseCommand
from django.db import connection


class Command(BaseCommand):
    help = 'Führt einen tieferen Check der Berechtigungen durch'

    def handle(self, *args, **options):
        self.stdout.write('Führe tiefere Prüfung der Berechtigungen durch...')

        # Direkte SQL-Abfrage für Permissions ohne gültigen ContentType
        with connection.cursor() as cursor:
            cursor.execute("""
                           SELECT ap.id, ap.codename, ap.name, ap.content_type_id
                           FROM auth_permission ap
                                    LEFT JOIN django_content_type dct ON ap.content_type_id = dct.id
                           WHERE dct.id IS NULL
                              OR ap.content_type_id IS NULL
                           """)
            rows = cursor.fetchall()

        if not rows:
            self.stdout.write(self.style.SUCCESS('Keine Probleme gefunden!'))
            return

        self.stdout.write(self.style.WARNING(f'Gefunden: {len(rows)} problematische Berechtigungen:'))
        for row in rows:
            self.stdout.write(f"ID: {row[0]}, Codename: {row[1]}, Name: {row[2]}, ContentType-ID: {row[3]}")

        self.stdout.write(self.style.WARNING('Möchtest du diese Berechtigungen löschen? (j/n)'))
        confirm = input()

        if confirm.lower() != 'j':
            self.stdout.write(self.style.WARNING('Abbruch - keine Änderungen vorgenommen.'))
            return

        # Lösche die problematischen Berechtigungen
        ids_to_delete = [row[0] for row in rows]
        Permission.objects.filter(id__in=ids_to_delete).delete()

        self.stdout.write(self.style.SUCCESS(f'{len(ids_to_delete)} problematische Berechtigungen wurden gelöscht.'))
        self.stdout.write(self.style.SUCCESS(
            'Führe nun "python manage.py migrate --fake-initial" aus, um die Berechtigungen neu zu erstellen.'))