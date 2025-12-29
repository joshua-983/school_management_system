"""
Security and audit models.
"""
import logging
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.core.files.storage import default_storage
from django.conf import settings

logger = logging.getLogger(__name__)
User = get_user_model()


class AuditAlertRule(models.Model):
    SEVERITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'), 
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    CONDITION_TYPES = [
        ('FREQUENCY', 'Frequency Threshold'),
        ('PATTERN', 'Pattern Detection'),
        ('RISK_SCORE', 'Risk Score Threshold'),
        ('CUSTOM', 'Custom Condition'),
    ]
    
    ACTION_CHOICES = [
        ('ALERT', 'Generate Alert'),
        ('NOTIFY', 'Send Notification'),
        ('BLOCK', 'Block Action'),
        ('ESCALATE', 'Escalate to Admin'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    condition_type = models.CharField(max_length=20, choices=CONDITION_TYPES)
    condition_config = models.JSONField(default=dict)  # Store condition parameters
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='MEDIUM')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default='ALERT')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_alert_rules')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Audit Alert Rule"
        verbose_name_plural = "Audit Alert Rules"


class SecurityEvent(models.Model):
    # Define SEVERITY_CHOICES here - use the same as AuditAlertRule
    SEVERITY_CHOICES = AuditAlertRule.SEVERITY_CHOICES
    
    EVENT_TYPES = [
        ('LOGIN_ATTEMPT', 'Login Attempt'),
        ('DATA_ACCESS', 'Data Access'),
        ('DATA_MODIFICATION', 'Data Modification'),
        ('CONFIG_CHANGE', 'Configuration Change'),
        ('SECURITY_ALERT', 'Security Alert'),
        ('SYSTEM_EVENT', 'System Event'),
    ]
    
    rule = models.ForeignKey(AuditAlertRule, on_delete=models.CASCADE, related_name='security_events', null=True, blank=True)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, null=True, blank=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES, default='SYSTEM_EVENT')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='MEDIUM')
    title = models.CharField(max_length=255)
    description = models.TextField()
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_events')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.created_at}"

    class Meta:
        verbose_name = "Security Event"
        verbose_name_plural = "Security Events"
        ordering = ['-created_at']


class AuditReport(models.Model):
    REPORT_TYPES = [
        ('DAILY', 'Daily Report'),
        ('WEEKLY', 'Weekly Report'),
        ('MONTHLY', 'Monthly Report'),
        ('SECURITY', 'Security Report'),
        ('COMPLIANCE', 'Compliance Report'),
        ('CUSTOM', 'Custom Report'),
    ]
    
    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    parameters = models.JSONField(default=dict)
    generated_by = models.ForeignKey(User, on_delete=models.CASCADE)
    generated_at = models.DateTimeField(auto_now_add=True)
    file_path = models.FileField(upload_to='audit_reports/', null=True, blank=True)
    is_archived = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} - {self.generated_at}"

    class Meta:
        verbose_name = "Audit Report"
        verbose_name_plural = "Audit Reports"


class DataRetentionPolicy(models.Model):
    RETENTION_TYPES = [
        ('AUDIT_LOG', 'Audit Logs'),
        ('SECURITY_EVENT', 'Security Events'),
        ('USER_DATA', "User Data"),
        ('BACKUP', 'Backup Files'),
    ]
    
    name = models.CharField(max_length=200)
    retention_type = models.CharField(max_length=20, choices=RETENTION_TYPES)
    retention_period_days = models.IntegerField(help_text="Number of days to retain data")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Data Retention Policy"
        verbose_name_plural = "Data Retention Policies"


class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('ACCESS', 'Access'),
        ('BULK_MESSAGE_SENT', 'Bulk Message Sent'),  # 17 characters!
        ('OTHER', 'Other'),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    
    # CHANGE THIS: Increase max_length from 10 to at least 20
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, db_index=True)  # Changed from 10 to 20
    
    model_name = models.CharField(max_length=50, db_index=True)
    object_id = models.CharField(max_length=50, db_index=True, blank=True, null=True)      
    details = models.JSONField(blank=True, null=True, default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)        
    
    # ADD THIS FIELD - user_agent
    user_agent = models.TextField(blank=True, null=True, db_index=False, 
                                  help_text="User agent string from the HTTP request")
    
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user']),
            models.Index(fields=['action']),
        ]

    def __str__(self):
        username = self.user.username if self.user else 'System'
        return f"{username} - {self.action} - {self.model_name} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"

    @classmethod
    def log_action(cls, user, action, model_name=None, object_id=None, details=None, ip_address=None):
        return cls.objects.create(
            user=user,
            action=action,
            model_name=model_name or '',
            object_id=str(object_id) if object_id else None,
            details=details or {},
            ip_address=ip_address
        )


class UserProfile(models.Model):
    """Extended user profile for additional user management features"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    is_blocked = models.BooleanField(default=False)
    blocked_reason = models.TextField(blank=True, null=True)
    blocked_at = models.DateTimeField(blank=True, null=True)
    blocked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    block_duration = models.DurationField(blank=True, null=True, help_text="Duration for temporary block")
    block_until = models.DateTimeField(blank=True, null=True, help_text="Block until this date/time")
    auto_unblock_at = models.DateTimeField(blank=True, null=True)
    
    login_attempts = models.PositiveIntegerField(default=0)
    last_login_attempt = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

    def __str__(self):
        return f"{self.user.username} - {'Blocked' if self.is_blocked else 'Active'}"

    def block_user(self, blocked_by, reason="", duration=None):
        """Block this user"""
        self.is_blocked = True
        self.blocked_reason = reason
        self.blocked_at = timezone.now()
        self.blocked_by = blocked_by
        
        if duration:
            self.block_duration = duration
            self.block_until = timezone.now() + duration
            self.auto_unblock_at = self.block_until
        else:
            self.block_duration = None
            self.block_until = None
            
        self.save()
        
        # Log the action
        details = {
            'reason': reason,
            'username': self.user.username,
            'blocked_at': self.blocked_at.isoformat(),
            'duration': str(duration) if duration else 'permanent'
        }
        AuditLog.log_action(
            user=blocked_by,
            action='BLOCK',
            model_name="User",
            object_id=self.user.id,
            details=details
        )

    def unblock_user(self, unblocked_by, reason=""):
        """Unblock this user"""
        self.is_blocked = False
        self.blocked_reason = ""
        self.blocked_at = None
        self.blocked_by = None
        self.block_duration = None
        self.block_until = None
        self.auto_unblock_at = None
        self.login_attempts = 0
        self.save()
        
        # Log the action
        AuditLog.log_action(
            user=unblocked_by,
            action='UNBLOCK',
            model_name="User",
            object_id=self.user.id,
            details={
                'reason': reason,
                'username': self.user.username,
                'unblocked_at': timezone.now().isoformat()
            }
        )