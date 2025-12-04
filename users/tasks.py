"""
Celery tasks for Users module
"""
from celery import shared_task
from django.utils import timezone
from django.contrib.sessions.models import Session
from datetime import timedelta
import logging

logger = logging.getLogger('atlas_crm')


@shared_task
def clean_old_sessions():
    """
    Clean expired sessions from database
    Runs at 3 AM daily
    """
    try:
        # Delete expired sessions
        expired = Session.objects.filter(
            expire_date__lt=timezone.now()
        )
        count = expired.count()
        expired.delete()

        logger.info(f"Cleaned {count} expired sessions")
        return {'status': 'success', 'cleaned': count}

    except Exception as e:
        logger.error(f"Session cleanup failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def deactivate_inactive_users():
    """
    Deactivate users who haven't logged in for 90 days
    """
    from .models import User

    try:
        threshold = timezone.now() - timedelta(days=90)

        # Get users who haven't logged in for 90 days
        # Exclude superusers and recently created accounts
        inactive_users = User.objects.filter(
            is_active=True,
            is_superuser=False,
            last_login__lt=threshold,
            date_joined__lt=threshold
        )

        count = inactive_users.count()

        # Mark as inactive instead of deleting
        inactive_users.update(is_active=False)

        logger.info(f"Deactivated {count} inactive users")
        return {'status': 'success', 'deactivated': count}

    except Exception as e:
        logger.error(f"User deactivation task failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def send_password_expiry_reminders():
    """
    Send reminders to users whose passwords are about to expire
    """
    from .models import User
    from notifications.models import Notification

    try:
        # Users whose password will expire in 7 days
        expiry_threshold = timezone.now() - timedelta(days=83)  # 90 - 7 days

        users_to_notify = User.objects.filter(
            is_active=True,
            password_changed_at__lt=expiry_threshold,
            password_changed_at__gt=expiry_threshold - timedelta(days=1)  # Only notify once
        )

        notified = 0
        for user in users_to_notify:
            Notification.objects.create(
                user=user,
                title="Password Expiry Reminder",
                message="Your password will expire in 7 days. Please update your password "
                       "to avoid being locked out of your account.",
                notification_type='security',
                priority='high'
            )
            notified += 1

        logger.info(f"Password expiry reminders sent: {notified}")
        return {'status': 'success', 'notified': notified}

    except Exception as e:
        logger.error(f"Password expiry reminder task failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def generate_user_activity_report():
    """
    Generate weekly user activity report for admins
    """
    from .models import User, UserActivity
    from notifications.models import Notification
    from django.db.models import Count

    try:
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)

        # Get activity statistics
        active_users = User.objects.filter(
            last_login__gte=week_ago
        ).count()

        total_users = User.objects.filter(is_active=True).count()

        # Get new users this week
        new_users = User.objects.filter(
            date_joined__gte=week_ago
        ).count()

        # Get login activity if UserActivity model exists
        try:
            login_stats = UserActivity.objects.filter(
                timestamp__gte=week_ago,
                activity_type='login'
            ).values('user').annotate(
                login_count=Count('id')
            ).count()
        except:
            login_stats = 0

        report = {
            'period': f"{week_ago.strftime('%Y-%m-%d')} to {today.strftime('%Y-%m-%d')}",
            'total_active_users': total_users,
            'users_logged_in': active_users,
            'new_users': new_users,
            'login_activity': login_stats,
            'activity_rate': round((active_users / total_users * 100), 2) if total_users > 0 else 0
        }

        # Notify admins
        admins = User.objects.filter(
            is_active=True,
            userrole__role__role_type='admin'
        ).distinct()

        for admin in admins:
            Notification.objects.create(
                user=admin,
                title="Weekly User Activity Report",
                message=f"Active users: {active_users}/{total_users} ({report['activity_rate']}%), "
                       f"New users: {new_users}",
                notification_type='report',
                priority='normal'
            )

        logger.info(f"User activity report generated: {report}")
        return {'status': 'success', 'report': report}

    except Exception as e:
        logger.error(f"User activity report failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def sync_user_permissions():
    """
    Sync user permissions based on their roles
    """
    from .models import User, UserRole, Role
    from django.contrib.auth.models import Permission

    try:
        synced = 0

        # Get all active users with roles
        users_with_roles = User.objects.filter(
            is_active=True,
            userrole__isnull=False
        ).prefetch_related('userrole_set__role__permissions').distinct()

        for user in users_with_roles:
            # Collect all permissions from all roles
            role_permissions = set()
            for user_role in user.userrole_set.all():
                if user_role.role and hasattr(user_role.role, 'permissions'):
                    for perm in user_role.role.permissions.all():
                        role_permissions.add(perm)

            # Update user permissions
            current_permissions = set(user.user_permissions.all())

            if role_permissions != current_permissions:
                user.user_permissions.set(role_permissions)
                synced += 1

        logger.info(f"User permissions synced: {synced}")
        return {'status': 'success', 'synced': synced}

    except Exception as e:
        logger.error(f"Permission sync failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}


@shared_task
def clear_axes_lockouts():
    """
    Clear old axes lockout records (older than 24 hours)
    """
    try:
        from axes.models import AccessAttempt, AccessLog

        threshold = timezone.now() - timedelta(hours=24)

        # Clear old access attempts
        old_attempts = AccessAttempt.objects.filter(
            attempt_time__lt=threshold
        )
        attempts_count = old_attempts.count()
        old_attempts.delete()

        # Clear old access logs (keep last 7 days)
        log_threshold = timezone.now() - timedelta(days=7)
        old_logs = AccessLog.objects.filter(
            attempt_time__lt=log_threshold
        )
        logs_count = old_logs.count()
        old_logs.delete()

        logger.info(f"Cleared {attempts_count} old access attempts and {logs_count} old logs")
        return {
            'status': 'success',
            'attempts_cleared': attempts_count,
            'logs_cleared': logs_count
        }

    except ImportError:
        logger.warning("Axes not installed, skipping lockout cleanup")
        return {'status': 'skipped', 'reason': 'Axes not installed'}
    except Exception as e:
        logger.error(f"Axes cleanup failed: {str(e)}")
        return {'status': 'error', 'message': str(e)}
