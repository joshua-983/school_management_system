"""
Parent/Guardian models and related communication models.
"""
import logging
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

from core.models.student import Student
from core.models.base import CLASS_LEVEL_CHOICES

logger = logging.getLogger(__name__)
User = get_user_model()


class ParentGuardian(models.Model):
    RELATIONSHIP_CHOICES = [
        ('F', 'Father'),
        ('M', 'Mother'),
        ('B', 'Brother'),
        ('S', 'Sister'),
        ('G', 'Guardian'),
        ('O', 'Other Relative'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parentguardian', null=True, blank=True)
    students = models.ManyToManyField(Student, related_name='parents')
    occupation = models.CharField(max_length=100, blank=True)
    relationship = models.CharField(max_length=1, choices=RELATIONSHIP_CHOICES)
    phone_number = models.CharField(
        max_length=10, 
        validators=[
            RegexValidator(
                r'^0\d{9}$',
                message="Phone number must be 10 digits starting with 0 (e.g., 0245478847)"
            )
        ],
        help_text="10-digit phone number starting with 0 (e.g., 0245478847)"
    )
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_emergency_contact = models.BooleanField(default=False)
    emergency_contact_priority = models.PositiveSmallIntegerField(
        default=1, 
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    # Account management fields
    account_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Activation'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('suspended', 'Suspended'),
        ],
        default='pending'
    )
    last_login_date = models.DateTimeField(null=True, blank=True)
    login_count = models.PositiveIntegerField(default=0)
    account_created = models.DateTimeField(auto_now_add=True)
    account_updated = models.DateTimeField(auto_now=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['emergency_contact_priority', 'user__last_name']
        verbose_name_plural = "Parents/Guardians"
        verbose_name = "Parent/Guardian"
        
    def __str__(self):
        student_names = ", ".join([student.get_full_name() for student in self.students.all()])
        if self.user:
            return f"{self.user.get_full_name()} ({self.get_relationship_display()}) - {student_names}"
        return f"{self.get_relationship_display()} - {student_names}"
    
    def get_user_full_name(self):
        if self.user:
            return self.user.get_full_name()
        return "No User Account"
    
    def has_active_account(self):
        """Check if parent has an active user account"""
        return self.user is not None and self.account_status == 'active'
    
    def can_login(self):
        """Check if parent can login"""
        return self.has_active_account() and self.account_status == 'active'
    
    def get_children(self):
        """Get all children/students associated with this parent"""
        return self.students.all()
    
    def get_children_count(self):
        """Get number of children"""
        return self.students.count()
    
    def update_login_stats(self):
        """Update login statistics"""
        if self.user:
            self.last_login_date = timezone.now()
            self.login_count += 1
            self.save(update_fields=['last_login_date', 'login_count', 'account_updated'])
    
    def create_user_account(self, password=None):
        """Create a user account for this parent"""
        if self.user:
            return self.user
        
        if not self.email:
            raise ValueError("Email is required to create a user account")
        
        # Generate username from email
        base_username = self.email.split('@')[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=self.email,
            password=password or User.objects.make_random_password(),
            first_name="Parent",
            last_name=self.email.split('@')[0]
        )
        
        self.user = user
        self.account_status = 'active'
        self.save()
        
        return user

    def clean(self):
        # Validate email uniqueness
        if self.email:
            existing = ParentGuardian.objects.filter(
                email=self.email
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError({'email': 'This email is already registered'})
        
        # Additional phone number validation
        if self.phone_number:
            cleaned_phone = self.phone_number.replace(' ', '').replace('-', '')
            if len(cleaned_phone) != 10 or not cleaned_phone.startswith('0'):
                raise ValidationError({
                    'phone_number': 'Phone number must be exactly 10 digits starting with 0'
                })
            self.phone_number = cleaned_phone


@receiver(post_save, sender=ParentGuardian)
def handle_parent_user_account(sender, instance, created, **kwargs):
    """Automatically create user account for parents with email"""
    if created and instance.email and not instance.user:
        try:
            user = User.objects.filter(email=instance.email).first()
            if user:
                # Link existing user
                instance.user = user
                instance.account_status = 'active'
                instance.save(update_fields=['user', 'account_status'])
            else:
                # Create new user account
                instance.create_user_account()
                
        except Exception as e:
            logger.error(f"Error creating user for parent {instance.email}: {e}")


@receiver(post_save, sender=User)
def update_parent_login_stats(sender, instance, **kwargs):
    """Update parent login statistics when user logs in"""
    try:
        if hasattr(instance, 'parentguardian'):
            parent = instance.parentguardian
            parent.update_login_stats()
    except ParentGuardian.DoesNotExist:
        pass


class ParentAnnouncement(models.Model):
    TARGET_TYPES = [
        ('ALL', 'All Parents'),
        ('CLASS', 'Specific Class'),
        ('INDIVIDUAL', 'Individual Parents'),
    ]
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    target_type = models.CharField(max_length=20, choices=TARGET_TYPES, default='ALL')
    target_class = models.CharField(max_length=50, blank=True, null=True)
    target_parents = models.ManyToManyField('ParentGuardian', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_important = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Parent Announcement'
        verbose_name_plural = 'Parent Announcements'
    
    def __str__(self):
        return self.title


class ParentMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_parent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_parent_messages')
    parent = models.ForeignKey('ParentGuardian', on_delete=models.CASCADE, null=True, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Parent Message'
        verbose_name_plural = 'Parent Messages'
    
    def __str__(self):
        return f"{self.subject} - {self.sender} to {self.receiver}"


class ParentEvent(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    location = models.CharField(max_length=200, blank=True)
    is_whole_school = models.BooleanField(default=False)
    class_level = models.CharField(max_length=50, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['start_date']
        verbose_name = 'Parent Event'
        verbose_name_plural = 'Parent Events'
    
    def __str__(self):
        return self.title