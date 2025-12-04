from django.core.management.base import BaseCommand
from django.utils import timezone
from datetime import timedelta
from orders.models import Order, OrderWorkflowLog
from django.contrib.auth import get_user_model

User = get_user_model()

class Command(BaseCommand):
    help = 'Update pending orders to postponed status after 24 hours'

    def handle(self, *args, **options):
        # Get orders that have been pending for more than 24 hours
        cutoff_time = timezone.now() - timedelta(hours=24)
        pending_orders = Order.objects.filter(
            status='pending',
            date__lt=cutoff_time,
            workflow_status__in=['callcenter_review', 'callcenter_approved']
        )
        
        updated_count = 0
        for order in pending_orders:
            # Update status to postponed
            order.status = 'postponed'
            order.workflow_status = 'postponed'
            order.save()
            
            # Create workflow log
            OrderWorkflowLog.objects.create(
                order=order,
                from_status='callcenter_approved',
                to_status='postponed',
                user=None,  # System action
                notes='Order automatically postponed due to inactivity (24+ hours)'
            )
            updated_count += 1
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully updated {updated_count} orders to postponed status.')
        )
