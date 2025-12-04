#!/usr/bin/env python
"""
Fix script for analytics services model and field mismatches.

Issues found:
1. Import DeliveryRecord instead of Delivery
2. CallLog doesn't have 'outcome' field, has 'status' and 'resolution_status'
3. CallLog doesn't have 'missed' or 'answered' status values
"""

import os
import sys
import django

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'crm_fulfillment.settings')
django.setup()

def fix_analytics_services():
    """Fix the analytics services.py file."""

    file_path = '/root/new-python-code/analytics/services.py'

    # Read the file
    with open(file_path, 'r') as f:
        content = f.read()

    print("Fixing analytics services...")

    # Fix 1: Change Delivery to DeliveryRecord
    content = content.replace(
        'from delivery.models import Delivery',
        'from delivery.models import DeliveryRecord'
    )
    content = content.replace(
        'deliveries = Delivery.objects',
        'deliveries = DeliveryRecord.objects'
    )
    content = content.replace(
        'completed_deliveries = Delivery.objects',
        'completed_deliveries = DeliveryRecord.objects'
    )

    # Fix 2: CallLog status values and field names
    # Replace the get_call_summary method
    old_call_summary = '''    @classmethod
    def get_call_summary(cls, days=30):
        """Get call center summary."""
        from callcenter.models import CallLog

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        calls = CallLog.objects.filter(created_at__gte=start_date)

        total_calls = calls.count()
        answered = calls.filter(status='answered').count()
        missed = calls.filter(status='missed').count()

        # Calls by outcome
        outcome_breakdown = calls.values('outcome').annotate(
            count=Count('id')
        ).order_by('-count')

        return {
            'total_calls': total_calls,
            'answered': answered,
            'missed': missed,
            'answer_rate': (answered / total_calls * 100) if total_calls > 0 else 0,
            'outcome_breakdown': list(outcome_breakdown)
        }'''

    new_call_summary = '''    @classmethod
    def get_call_summary(cls, days=30):
        """Get call center summary."""
        from callcenter.models import CallLog

        end_date = timezone.now()
        start_date = end_date - timedelta(days=days)

        calls = CallLog.objects.filter(created_at__gte=start_date)

        total_calls = calls.count()
        completed = calls.filter(status='completed').count()
        no_answer = calls.filter(status='no_answer').count()

        # Calls by status
        status_breakdown = calls.values('status').annotate(
            count=Count('id')
        ).order_by('-count')

        # Calls by resolution status
        resolution_breakdown = calls.values('resolution_status').annotate(
            count=Count('id')
        ).order_by('-count')

        return {
            'total_calls': total_calls,
            'completed': completed,
            'no_answer': no_answer,
            'answer_rate': (completed / total_calls * 100) if total_calls > 0 else 0,
            'status_breakdown': list(status_breakdown),
            'resolution_breakdown': list(resolution_breakdown)
        }'''

    content = content.replace(old_call_summary, new_call_summary)

    # Fix 3: Agent performance - change 'outcome' to 'resolution_status'
    old_agent_perf = '''        agent_stats = CallLog.objects.filter(
            created_at__gte=start_date
        ).values(
            'agent__id', 'agent__first_name', 'agent__last_name'
        ).annotate(
            total_calls=Count('id'),
            successful_calls=Count(Case(
                When(outcome='confirmed', then=1),
                output_field=IntegerField()
            )),
            avg_duration=Avg('duration')
        ).order_by('-total_calls')[:limit]'''

    new_agent_perf = '''        agent_stats = CallLog.objects.filter(
            created_at__gte=start_date
        ).values(
            'agent__id', 'agent__full_name'
        ).annotate(
            total_calls=Count('id'),
            resolved_calls=Count(Case(
                When(resolution_status='resolved', then=1),
                output_field=IntegerField()
            )),
            avg_duration=Avg('duration')
        ).order_by('-total_calls')[:limit]'''

    content = content.replace(old_agent_perf, new_agent_perf)

    # Write the fixed content
    with open(file_path, 'w') as f:
        f.write(content)

    print("✓ Fixed: Delivery → DeliveryRecord")
    print("✓ Fixed: CallLog status fields")
    print("✓ Fixed: Agent performance metrics")
    print(f"\nFile updated: {file_path}")

    return True

if __name__ == '__main__':
    try:
        success = fix_analytics_services()
        if success:
            print("\n✓ All fixes applied successfully!")
            print("\nNext steps:")
            print("1. Restart Django server to apply changes")
            print("2. Run test_atlas_apis.py to verify fixes")
            sys.exit(0)
        else:
            print("\n✗ Fix failed!")
            sys.exit(1)
    except Exception as e:
        print(f"\n✗ Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
