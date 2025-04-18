from django.core.management.base import BaseCommand

from module_management.models import FeatureFlag


class Command(BaseCommand):
    help = 'Lists all feature flags in the system'

    def handle(self, *args, **options):
        self.stdout.write(self.style.NOTICE('Listing all feature flags...'))
        
        feature_flags = FeatureFlag.objects.all()
        
        if not feature_flags.exists():
            self.stdout.write(self.style.WARNING('No feature flags found.'))
            return
        
        self.stdout.write(self.style.SUCCESS(f'Found {feature_flags.count()} feature flags:'))
        
        for flag in feature_flags:
            self.stdout.write(f"- {flag.code}: {flag.name} (Module: {flag.module.name}, Active: {flag.is_active})")