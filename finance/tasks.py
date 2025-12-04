"""
Celery tasks for Finance module
"""
from celery import shared_task
from django.utils import timezone
from django.db.models import Sum, Count, Q, F
from datetime import timedelta
from decimal import Decimal
import logging

logger = logging.getLogger('atlas_crm')


@shared_task
def generate_daily_report():
    """
    Generate daily finance report
    Runs at 11:30 PM daily
    """
    from .models import Transaction, Invoice, Payout
    from notifications.models import Notification
    from users.models import User

    try:
        today = timezone.now().date()

        # Get today's financial statistics
        stats = Transaction.objects.filter(
            created_at__date=today
        ).aggregate(
            total_revenue=Sum('amount', filter=Q(transaction_type='credit')),
            total_expenses=Sum('amount', filter=Q(transaction_type='debit')),
            transaction_count=Count('id'),
        )

        # Get invoice statistics
        invoice_stats = Invoice.objects.filter(
            created_at__date=today
        ).aggregate(
            invoices_created=Count('id'),
            invoices_paid=Count('id', filter=Q(status='paid')),
            total_invoiced=Sum('total_amount'),
        )

        # Get payout statistics
        payout_stats = Payout.objects.filter(
            created_at__date=today
        ).aggregate(
            payouts_count=Count('id'),
            total_payouts=Sum('amount'),
        )

        report = {
            'date': today.strftime('%Y-%m-%d'),
            'revenue': float(stats['total_revenue'] or 0),
            'expenses': float(stats['total_expenses'] or 0),
            'net_profit': float((stats['total_revenue'] or 0) - (stats['total_expenses'] or 0)),
            'transactions': stats['transaction_count'] or 0,
            'invoices_created': invoice_stats['invoices_created'] or 0,
            'invoices_paid': invoice_stats['invoices_paid'] or 0,
            'total_invoiced': float(invoice_stats['total_invoiced'] or 0),
            'payouts': payout_stats['payouts_count'] or 0,
            'total_payouts': float(payout_stats['total_payouts'] or 0),
        }

        # Notify finance managers
        finance_users = User.objects.filter(
            is_active=True,
            userrole__role__role_type__in=['admin', 'finance_manager', 'accountant']
        ).distinct()

        for user in finance_users:
            Notification.objects.create(
                user=user,
                title=f"Daily Finance Report - {today.strftime('%B %d, %Y')}",
                message=f"Revenue: ${report['revenue']:,.2f}, "
                       f"Expenses: ${report['expenses']:,.2f}, "
                       f"Net: ${report['net_profit']:,.2f}, "
                       f"Transactions: {report['transactions']}",
                notification_type='report',
                priority='normal'
            )

        logger.info(f"Daily finance report generated: {report}")
        return {'status': 'success', 'report': report}

    except Exception as e:
        logger.error(f"Daily finance report failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def process_pending_payouts():
    """
    Process pending seller payouts
    """
    from .models import Payout, Transaction

    try:
        processed = 0
        failed = 0

        # Get approved payouts ready for processing
        pending_payouts = Payout.objects.filter(
            status='approved',
            scheduled_date__lte=timezone.now().date()
        ).select_related('seller')

        for payout in pending_payouts:
            try:
                # Mark as processing
                payout.status = 'processing'
                payout.save(update_fields=['status'])

                # Create transaction record
                Transaction.objects.create(
                    transaction_type='debit',
                    amount=payout.amount,
                    description=f"Payout to seller: {payout.seller.business_name}",
                    reference_type='payout',
                    reference_id=str(payout.id),
                    status='completed'
                )

                # Mark payout as completed
                payout.status = 'completed'
                payout.processed_at = timezone.now()
                payout.save(update_fields=['status', 'processed_at'])
                processed += 1

            except Exception as e:
                payout.status = 'failed'
                payout.notes = f"Processing failed: {str(e)}"
                payout.save(update_fields=['status', 'notes'])
                failed += 1
                logger.error(f"Payout {payout.id} failed: {str(e)}")

        logger.info(f"Payout processing completed. Processed: {processed}, Failed: {failed}")
        return {'status': 'success', 'processed': processed, 'failed': failed}

    except Exception as e:
        logger.error(f"Payout processing task failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def check_overdue_invoices():
    """
    Check for overdue invoices and send reminders
    """
    from .models import Invoice
    from notifications.models import Notification
    from users.models import User

    try:
        today = timezone.now().date()

        # Get overdue invoices
        overdue_invoices = Invoice.objects.filter(
            status='sent',
            due_date__lt=today
        ).select_related('customer')

        overdue_count = overdue_invoices.count()
        total_overdue_amount = overdue_invoices.aggregate(
            total=Sum('total_amount')
        )['total'] or Decimal('0')

        if overdue_count > 0:
            # Mark invoices as overdue
            overdue_invoices.update(status='overdue')

            # Notify finance team
            finance_users = User.objects.filter(
                is_active=True,
                userrole__role__role_type__in=['admin', 'finance_manager', 'accountant']
            ).distinct()

            for user in finance_users:
                Notification.objects.create(
                    user=user,
                    title="Overdue Invoices Alert",
                    message=f"There are {overdue_count} overdue invoices "
                           f"totaling ${float(total_overdue_amount):,.2f}. "
                           f"Please follow up with customers.",
                    notification_type='finance_alert',
                    priority='high'
                )

        logger.info(f"Overdue invoice check completed. Found: {overdue_count}")
        return {
            'status': 'success',
            'overdue_count': overdue_count,
            'total_amount': float(total_overdue_amount)
        }

    except Exception as e:
        logger.error(f"Overdue invoice check failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def calculate_seller_commissions():
    """
    Calculate and record seller commissions from completed orders
    """
    from .models import Commission, Transaction
    from orders.models import Order

    try:
        calculated = 0

        # Get delivered orders without commission records
        delivered_orders = Order.objects.filter(
            status='delivered',
            commission_calculated=False
        ).select_related('seller')

        for order in delivered_orders:
            if order.seller and hasattr(order.seller, 'commission_rate'):
                commission_rate = order.seller.commission_rate or Decimal('0.10')  # Default 10%
                commission_amount = order.total_price * commission_rate

                # Create commission record
                Commission.objects.create(
                    order=order,
                    seller=order.seller,
                    order_amount=order.total_price,
                    commission_rate=commission_rate,
                    commission_amount=commission_amount,
                    status='pending'
                )

                # Create transaction record
                Transaction.objects.create(
                    transaction_type='credit',
                    amount=commission_amount,
                    description=f"Commission from order #{order.order_number}",
                    reference_type='commission',
                    reference_id=str(order.id),
                    status='completed'
                )

                order.commission_calculated = True
                order.save(update_fields=['commission_calculated'])
                calculated += 1

        logger.info(f"Commission calculation completed. Calculated: {calculated}")
        return {'status': 'success', 'calculated': calculated}

    except Exception as e:
        logger.error(f"Commission calculation failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def reconcile_daily_transactions():
    """
    Reconcile daily transactions and check for discrepancies
    """
    from .models import Transaction, Invoice
    from orders.models import Order

    try:
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        # Get all transactions from yesterday
        transactions = Transaction.objects.filter(
            created_at__date=yesterday
        )

        credits = transactions.filter(transaction_type='credit').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        debits = transactions.filter(transaction_type='debit').aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0')

        # Get order payments from yesterday
        order_payments = Order.objects.filter(
            payment_date__date=yesterday,
            payment_status='paid'
        ).aggregate(total=Sum('total_price'))['total'] or Decimal('0')

        # Check for discrepancies
        discrepancy = abs(credits - order_payments)

        reconciliation = {
            'date': yesterday.strftime('%Y-%m-%d'),
            'total_credits': float(credits),
            'total_debits': float(debits),
            'order_payments': float(order_payments),
            'discrepancy': float(discrepancy),
            'balanced': discrepancy < Decimal('0.01')
        }

        logger.info(f"Daily reconciliation completed: {reconciliation}")
        return {'status': 'success', 'reconciliation': reconciliation}

    except Exception as e:
        logger.error(f"Daily reconciliation failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}
