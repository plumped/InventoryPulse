from django.core.management.base import BaseCommand
from core.permissions import setup_permissions

class Command(BaseCommand):
    help = 'Richtet alle Berechtigungen im System ein'

    def handle(self, *args, **options):
        self.stdout.write('Berechtigung einrichten...')
        setup_permissions()
        self.stdout.write(self.style.SUCCESS('Berechtigungen erfolgreich eingerichtet!'))