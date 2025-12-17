"""
System configuration models.
"""
import logging
import re
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models.base import TERM_CHOICES, CLASS_LEVEL_CHOICES

logger = logging.getLogger(__name__)
User = get_user_model()


class SchoolConfiguration(models.Model):
    GRADING_SYSTEM_CHOICES = [
        ('GES', 'Ghana Education System (1-9)'),
        ('LETTER', 'Letter Grading System (A-F)'),
        ('BOTH', 'Both Systems'),
    ]
    
    grading_system = models.CharField(
        max_length=10, 
        choices=GRADING_SYSTEM_CHOICES, 
        default='GES'
    )
    is_locked = models.BooleanField(default=False, help_text="Lock the grading system to prevent changes")
    academic_year = models.CharField(max_length=9, default=f"{timezone.now().year}/{timezone.now().year + 1}")
    current_term = models.PositiveSmallIntegerField(choices=TERM_CHOICES, default=1)
    school_name = models.CharField(max_length=200, default="Ghana Education Service School")
    school_address = models.TextField(default="")
    school_phone = models.CharField(
        max_length=10,
        blank=True,
        validators=[
            RegexValidator(
                r'^0\d{9}$',
                message="Phone number must be 10 digits starting with 0 (e.g., 0245478847)"
            )
        ],
        help_text="10-digit phone number starting with 0 (e.g., 0245478847)"
    )
    school_email = models.EmailField(blank=True)
    principal_name = models.CharField(max_length=100, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "School Configuration"
        verbose_name_plural = "School Configuration"
    
    def save(self, *args, **kwargs):
        if SchoolConfiguration.objects.exists() and not self.pk:
            raise ValidationError("Only one school configuration can exist")
        
        # Clean phone number before saving
        if self.school_phone:
            self.school_phone = self.school_phone.replace(' ', '').replace('-', '')
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"School Configuration - {self.school_name}"
    
    def clean(self):
        """Additional validation for phone number"""
        if self.school_phone:
            # Remove any spaces or dashes that might have been entered
            cleaned_phone = self.school_phone.replace(' ', '').replace('-', '')
            if len(cleaned_phone) != 10 or not cleaned_phone.startswith('0'):
                raise ValidationError({
                    'school_phone': 'Phone number must be exactly 10 digits starting with 0'
                })
            # Update the field with cleaned value
            self.school_phone = cleaned_phone
    
    @classmethod
    def get_config(cls):
        """Get or create the single configuration instance"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
    
    def get_grading_system_display_name(self):
        """Get user-friendly grading system name"""
        return dict(self.GRADING_SYSTEM_CHOICES).get(self.grading_system, 'GES')


class MaintenanceMode(models.Model):
    """Model to track system maintenance mode"""
    is_active = models.BooleanField(default=False)
    message = models.TextField(blank=True, help_text="Message to display to users during maintenance")
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    allowed_ips = models.TextField(blank=True, help_text="Comma-separated list of IPs allowed during maintenance")
    
    # Allow specific users to bypass maintenance mode
    allowed_users = models.ManyToManyField(
        User,
        blank=True,
        related_name='maintenance_bypass_users',
        help_text="Users who can access the system during maintenance"
    )
    
    # Allow all staff users to bypass
    allow_staff_access = models.BooleanField(
        default=True,
        help_text="Allow all staff users to access the system during maintenance"
    )
    
    # Allow all superusers to bypass  
    allow_superuser_access = models.BooleanField(
        default=True,
        help_text="Allow all superusers to access the system during maintenance"
    )
    
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Maintenance Mode'
        verbose_name_plural = 'Maintenance Mode'
    
    def __str__(self):
        return f"Maintenance Mode - {'Active' if self.is_active else 'Inactive'}"
    
    def is_currently_active(self):
        """Check if maintenance is currently active based on time window"""
        if not self.is_active:
            return False
        
        now = timezone.now()
        if self.start_time and now < self.start_time:
            return False
        if self.end_time and now > self.end_time:
            return False
            
        return True
    
    def can_user_bypass(self, user):
        """Check if user can bypass maintenance mode"""
        if not user or not user.is_authenticated:
            return False
            
        # Superusers can always bypass if allowed
        if self.allow_superuser_access and user.is_superuser:
            return True
            
        # Staff users can bypass if allowed
        if self.allow_staff_access and user.is_staff:
            return True
            
        # Specific allowed users can bypass
        if self.allowed_users.filter(id=user.id).exists():
            return True
            
        return False
    
    @classmethod
    def get_current_maintenance(cls):
        """Get the current maintenance mode instance"""
        return cls.objects.filter(is_active=True).first()
    
    @classmethod
    def can_user_access(cls, user):
        """Check if user can access the system (bypass maintenance)"""
        maintenance = cls.get_current_maintenance()
        
        # No active maintenance - everyone can access
        if not maintenance or not maintenance.is_currently_active():
            return True
            
        # Check if user can bypass maintenance
        return maintenance.can_user_bypass(user)


class ScheduledMaintenance(models.Model):
    """Model for scheduled maintenance windows"""
    MAINTENANCE_TYPES = [
        ('EMERGENCY', 'Emergency Maintenance'),
        ('SCHEDULED', 'Scheduled Maintenance'),
        ('UPGRADE', 'System Upgrade'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPES, default='SCHEDULED')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    message = models.TextField(help_text="Message to display to users during maintenance")
    is_active = models.BooleanField(default=True)
    was_executed = models.BooleanField(default=False)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Scheduled Maintenance'
        verbose_name_plural = 'Scheduled Maintenance'
        ordering = ['-start_time']
    
    def __str__(self):
        return f"{self.title} ({self.start_time} to {self.end_time})"
    
    def is_currently_active(self):
        """Check if maintenance is currently active"""
        now = timezone.now()
        return self.start_time <= now <= self.end_time and self.is_active
    
    def is_upcoming(self):
        """Check if maintenance is upcoming"""
        return self.start_time > timezone.now() and self.is_active
    
    def duration(self):
        """Calculate maintenance duration"""
        return self.end_time - self.start_time