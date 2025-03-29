# order/management/commands/handle_recurring_orders.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from order.views import handle_recurring_orders


class Command(BaseCommand):
    help = 'Process recurring order templates and create new orders'

    def handle(self, *args, **options):
        self.stdout.write(self.style.SUCCESS('Starting to process recurring orders...'))
        start_time = timezone.now()

        orders_created = handle_recurring_orders()

        end_time = timezone.now()
        duration = (end_time - start_time).total_seconds()

        self.stdout.write(self.style.SUCCESS(
            f'Completed successfully in {duration:.2f} seconds. '
            f'Created {orders_created} orders from recurring templates.'
        ))