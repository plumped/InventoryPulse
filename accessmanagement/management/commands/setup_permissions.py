# accessmanagement/management/commands/setup_permissions.py
from django.core.management.base import BaseCommand
from accessmanagement.permissions import setup_permissions

class Command(BaseCommand):
    help = 'Sets up all permissions in the system'

    def handle(self, *args, **options):
        self.stdout.write('Setting up permissions...')
        setup_permissions()
        self.stdout.write(self.style.SUCCESS('Permissions set up successfully!'))