# core/models/audit.py
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
import json

User = get_user_model()

class FinancialAuditTrail(models.Model):
    """Track all financial transactions for compliance"""
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('VIEW', 'View'),
        ('PAYMENT', 'Payment'),
        ('REFUND', 'Refund'),
        ('CANCEL', 'Cancel'),
    ]
    
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=100)  # e.g., 'Bill', 'Fee', 'Payment'
    object_id = models.CharField(max_length=100)  # The ID of the object
    user = models.ForeignKey(User, on_delete=models.PROTECT, related_name='audit_actions')
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    before_state = models.JSONField(null=True, blank=True)  # Object state before change
    after_state = models.JSONField(null=True, blank=True)   # Object state after change
    changes = models.JSONField(null=True, blank=True)       # What specifically changed
    timestamp = models.DateTimeField(default=timezone.now)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['user', 'timestamp']),
            models.Index(fields=['action', 'timestamp']),
        ]
    
    def __str__(self):
        return f"{self.action} {self.model_name} #{self.object_id} by {self.user} at {self.timestamp}"
    
    @classmethod
    def log_action(cls, action, model_name, object_id, user, request=None, 
                   before_state=None, after_state=None, changes=None, notes=''):
        """Helper method to log audit trail"""
        audit = cls(
            action=action,
            model_name=model_name,
            object_id=str(object_id),
            user=user,
            notes=notes,
            before_state=before_state,
            after_state=after_state,
            changes=changes
        )
        
        if request:
            audit.ip_address = cls.get_client_ip(request)
            audit.user_agent = request.META.get('HTTP_USER_AGENT', '')
        
        audit.save()
        return audit
    
    @staticmethod
    def get_client_ip(request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip