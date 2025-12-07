from django import template
from django.contrib.auth import get_user_model

register = template.Library()
User = get_user_model()

@register.filter
def get_first_name(full_name):
    """Get the first name from a full name"""
    if full_name:
        return full_name.split()[0] if full_name.split() else ''
    return ''

@register.filter
def get_last_name(full_name):
    """Get the last name from a full name"""
    if full_name:
        parts = full_name.split()
        return ' '.join(parts[1:]) if len(parts) > 1 else ''
    return ''

@register.filter
def pending_approvals_count(user):
    """Return the count of pending approvals for admin users."""
    if user.has_role_admin or user.is_superuser:
        return User.objects.filter(approval_status='pending').count()
    return 0

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    if dictionary is None:
        return 0
    return dictionary.get(key, 0) 