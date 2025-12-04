# callcenter/models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import uuid

class CallLog(models.Model):
    CALL_STATUS = (
        ('completed', 'Completed'),
        ('no_answer', 'No Answer'),
        ('busy', 'Busy'),
        ('wrong_number', 'Wrong Number'),
        ('voicemail', 'Voicemail'),
        ('call_back', 'Call Back Requested'),
        ('escalated', 'Escalated'),
    )
    
    RESOLUTION_STATUS = (
        ('resolved', 'Resolved'),
        ('pending', 'Pending'),
        ('escalated', 'Escalated'),
        ('follow_up_required', 'Follow Up Required'),
    )
    
    # Using default BigAutoField instead of UUID to maintain compatibility with migrations
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='call_logs')
    agent = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='call_logs')
    call_time = models.DateTimeField(default=timezone.now, verbose_name='Call Time')
    duration = models.PositiveIntegerField(default=0, verbose_name='Duration (seconds)')
    status = models.CharField(max_length=20, choices=CALL_STATUS, verbose_name='Call Status')
    notes = models.TextField(blank=True, verbose_name='Call Notes')
    customer_satisfaction = models.PositiveIntegerField(blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(5)], verbose_name='Customer Satisfaction')
    resolution_status = models.CharField(choices=RESOLUTION_STATUS, default='pending', max_length=20, verbose_name='Resolution Status')
    escalation_reason = models.TextField(blank=True, verbose_name='Escalation Reason')
    follow_up_date = models.DateTimeField(blank=True, null=True, verbose_name='Follow Up Date')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-call_time']
        verbose_name = 'Call Log'
        verbose_name_plural = 'Call Logs'

class AgentSession(models.Model):
    STATUS_CHOICES = (
        ('available', 'Available'),
        ('busy', 'Busy'),
        ('break', 'On Break'),
        ('offline', 'Offline'),
        ('training', 'In Training'),
    )
    
    agent = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='agent_sessions')
    login_time = models.DateTimeField(default=timezone.now)
    logout_time = models.DateTimeField(blank=True, null=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='offline')
    concurrent_orders = models.PositiveIntegerField(default=0)
    last_activity = models.DateTimeField(auto_now=True)
    workstation_id = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-login_time']
        verbose_name = 'Agent Session'
        verbose_name_plural = 'Agent Sessions'

class CustomerInteraction(models.Model):
    INTERACTION_TYPES = (
        ('call', 'Call'),
        ('email', 'Email'),
        ('chat', 'Chat'),
        ('follow_up', 'Follow Up'),
    )
    
    RESOLUTION_STATUS = (
        ('resolved', 'Resolved'),
        ('pending', 'Pending'),
        ('escalated', 'Escalated'),
        ('follow_up_required', 'Follow Up Required'),
    )
    
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='customer_interactions')
    agent = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='customer_interactions')
    customer = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='interactions_received', blank=True, null=True)
    interaction_type = models.CharField(max_length=20, choices=INTERACTION_TYPES)
    interaction_time = models.DateTimeField(default=timezone.now)
    duration_minutes = models.PositiveIntegerField(default=0)
    resolution_status = models.CharField(max_length=20, choices=RESOLUTION_STATUS, default='pending')
    interaction_notes = models.TextField(blank=True)
    customer_satisfaction = models.PositiveIntegerField(blank=True, null=True, validators=[MinValueValidator(1), MaxValueValidator(5)])
    follow_up_date = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-interaction_time']
        verbose_name = 'Customer Interaction'
        verbose_name_plural = 'Customer Interactions'

class OrderStatusHistory(models.Model):
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='status_history')
    agent = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='status_changes')
    changed_by = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='status_changes_made', null=True, blank=True)
    previous_status = models.CharField(max_length=50)
    new_status = models.CharField(max_length=50)
    status_change_reason = models.TextField(blank=True)
    cancellation_reason = models.TextField(blank=True)
    change_timestamp = models.DateTimeField(default=timezone.now)
    customer_notified = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-change_timestamp']
        verbose_name = 'Order Status History'
        verbose_name_plural = 'Order Status Histories'

class OrderAssignment(models.Model):
    PRIORITY_LEVELS = (
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    )
    
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='assignments')
    manager = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='assignments_made')
    agent = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='callcenter_assignments')
    assignment_date = models.DateTimeField(default=timezone.now)
    manager_notes = models.TextField(blank=True)
    priority_level = models.CharField(max_length=10, choices=PRIORITY_LEVELS, default='medium')
    expected_completion = models.DateTimeField(blank=True, null=True)
    assignment_reason = models.TextField(blank=True)
    previous_agent = models.ForeignKey('users.User', on_delete=models.SET_NULL, blank=True, null=True, related_name='previous_assignments')
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        ordering = ['-assignment_date']
        verbose_name = 'Order Assignment'
        verbose_name_plural = 'Order Assignments'

class ManagerNote(models.Model):
    NOTE_TYPES = (
        ('instruction', 'Instruction'),
        ('reminder', 'Reminder'),
        ('priority', 'Priority'),
        ('escalation', 'Escalation'),
    )
    
    order = models.ForeignKey('orders.Order', on_delete=models.CASCADE, related_name='manager_notes')
    manager = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='notes_created')
    agent = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='notes_received')
    note_text = models.TextField()
    note_type = models.CharField(max_length=20, choices=NOTE_TYPES, default='instruction')
    is_urgent = models.BooleanField(default=False)
    is_read_by_agent = models.BooleanField(default=False)
    created_at = models.DateTimeField(default=timezone.now)
    read_at = models.DateTimeField(blank=True, null=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Manager Note'
        verbose_name_plural = 'Manager Notes'

class TeamPerformance(models.Model):
    team = models.CharField(max_length=100, blank=True)  # For future team implementation
    date = models.DateField()
    total_agents = models.PositiveIntegerField(default=0)
    orders_handled = models.PositiveIntegerField(default=0)
    orders_confirmed = models.PositiveIntegerField(default=0)
    orders_cancelled = models.PositiveIntegerField(default=0)
    average_handle_time = models.DecimalField(decimal_places=2, default=0, max_digits=5)
    team_confirmation_rate = models.DecimalField(decimal_places=2, default=0, max_digits=5)
    team_satisfaction_avg = models.DecimalField(decimal_places=2, default=0, max_digits=3)
    top_performer_agent = models.ForeignKey('users.User', on_delete=models.SET_NULL, blank=True, null=True, related_name='top_performances')
    lowest_performer_agent = models.ForeignKey('users.User', on_delete=models.SET_NULL, blank=True, null=True, related_name='lowest_performances')
    created_at = models.DateTimeField(default=timezone.now)
    
    class Meta:
        unique_together = ('team', 'date')
        ordering = ['-date']
        verbose_name = 'Team Performance'
        verbose_name_plural = 'Team Performances'

class AgentPerformance(models.Model):
    agent = models.ForeignKey('users.User', on_delete=models.CASCADE, related_name='performance_records')
    date = models.DateField(verbose_name='Date')
    total_calls_made = models.PositiveIntegerField(default=0, verbose_name='Total Calls Made')
    successful_calls = models.PositiveIntegerField(default=0, verbose_name='Successful Calls')
    orders_confirmed = models.PositiveIntegerField(default=0, verbose_name='Orders Confirmed')
    orders_cancelled = models.PositiveIntegerField(default=0, verbose_name='Orders Cancelled')
    orders_postponed = models.PositiveIntegerField(default=0, verbose_name='Orders Postponed')
    total_orders_handled = models.PositiveIntegerField(default=0, verbose_name='Total Orders Handled')
    average_call_duration = models.DecimalField(decimal_places=2, default=0, max_digits=5, verbose_name='Average Call Duration (minutes)')
    resolution_rate = models.DecimalField(decimal_places=2, default=0, max_digits=5, verbose_name='Resolution Rate (%)')
    first_call_resolution_rate = models.DecimalField(decimal_places=2, default=0, max_digits=5, verbose_name='First Call Resolution Rate (%)')
    customer_satisfaction_avg = models.DecimalField(decimal_places=2, default=0, max_digits=3, verbose_name='Average Customer Satisfaction')
    total_work_time_minutes = models.PositiveIntegerField(default=0, verbose_name='Total Work Time (minutes)')
    break_time_minutes = models.PositiveIntegerField(default=0, verbose_name='Break Time (minutes)')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('agent', 'date')
        ordering = ['-date']
        verbose_name = 'Agent Performance'
        verbose_name_plural = 'Agent Performances'