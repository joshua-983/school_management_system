"""
Parent/Guardian models and related communication models.
"""
import logging
import re
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.db.models import Q

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
        indexes = [
            models.Index(fields=['account_status', 'last_login_date']),
            models.Index(fields=['email']),
            models.Index(fields=['phone_number']),
            models.Index(fields=['relationship']),
            models.Index(fields=['created_at']),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=['phone_number'],
                condition=~models.Q(phone_number=''),
                name='unique_phone_number'
            ),
        ]
        
    def __str__(self):
        student_names = ", ".join([student.get_full_name() for student in self.students.all()[:3]])  # Limit to 3
        if student_names and len(self.students.all()) > 3:
            student_names += f" and {len(self.students.all()) - 3} more"
        
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
    
    def get_active_children(self):
        """Get only active students"""
        return self.students.filter(is_active=True)
    
    def get_primary_child(self):
        """Get the first/primary child (useful for notifications)"""
        return self.students.filter(is_active=True).first()
    
    def get_children_count(self):
        """Get number of children"""
        return self.students.count()
    
    def get_active_children_count(self):
        """Get number of active children"""
        return self.students.filter(is_active=True).count()
    
    def update_login_stats(self):
        """Update login statistics"""
        if self.user:
            self.last_login_date = timezone.now()
            self.login_count += 1
            self.save(update_fields=['last_login_date', 'login_count', 'account_updated'])
    
    def create_user_account(self, password=None, save=True):
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
        
        if save:
            self.save()
        
        return user
    
    def has_valid_phone(self):
        """Check if phone number is valid and can receive SMS"""
        return bool(re.match(r'^0\d{9}$', self.phone_number))
    
    def notification_preferences(self):
        """Get notification preferences"""
        return {
            'email': bool(self.email),
            'sms': self.has_valid_phone(),
            'in_app': True,  # Always true for parent messages
            'email_verified': bool(self.email),
            'sms_verified': self.has_valid_phone(),
        }
    
    def get_communication_channels(self):
        """Get available communication channels for this parent"""
        channels = []
        if self.email:
            channels.append({
                'type': 'email',
                'value': self.email,
                'verified': True  # Assuming email is verified if in database
            })
        if self.phone_number and self.has_valid_phone():
            channels.append({
                'type': 'sms',
                'value': self.phone_number,
                'verified': True  # Assuming phone is verified if in database
            })
        if self.user:
            channels.append({
                'type': 'in_app',
                'value': self.user.username,
                'verified': True
            })
        return channels

    def clean(self):
        """Validate model data"""
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
                # Create new user account (don't save - create_user_account will save)
                instance.create_user_account(save=True)
                
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
    is_active = models.BooleanField(default=True, help_text="Whether this announcement is currently active")
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Parent Announcement'
        verbose_name_plural = 'Parent Announcements'
        indexes = [
            models.Index(fields=['target_type', 'is_active', '-created_at']),
            models.Index(fields=['target_class', 'is_active']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        importance = "❗ " if self.is_important else ""
        return f"{importance}{self.title}"
    
    def get_target_count(self):
        """Get count of target parents"""
        if self.target_type == 'ALL':
            return ParentGuardian.objects.count()
        elif self.target_type == 'CLASS' and self.target_class:
            return ParentGuardian.objects.filter(students__class_level=self.target_class).distinct().count()
        elif self.target_type == 'INDIVIDUAL':
            return self.target_parents.count()
        return 0
    
    def deactivate(self):
        """Deactivate this announcement"""
        self.is_active = False
        self.save(update_fields=['is_active'])
    
    def is_relevant_for_parent(self, parent):
        """Check if this announcement is relevant for a specific parent"""
        if not self.is_active:
            return False
        
        if self.target_type == 'ALL':
            return True
        elif self.target_type == 'CLASS' and self.target_class:
            return parent.students.filter(class_level=self.target_class).exists()
        elif self.target_type == 'INDIVIDUAL':
            return self.target_parents.filter(id=parent.id).exists()
        return False


class ParentMessage(models.Model):
    PRIORITY_CHOICES = [
        ('normal', 'Normal'),
        ('high', 'High'),
        ('urgent', 'Urgent'),
    ]
    
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_parent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_parent_messages')
    parent = models.ForeignKey('ParentGuardian', on_delete=models.CASCADE, null=True, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    # Bulk messaging support
    is_bulk = models.BooleanField(default=False)
    bulk_id = models.CharField(max_length=100, blank=True, null=True, help_text="ID to group messages from same bulk send")
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    
    # Notification tracking
    email_sent = models.BooleanField(default=False)
    sms_sent = models.BooleanField(default=False)
    email_sent_at = models.DateTimeField(null=True, blank=True)
    sms_sent_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Parent Message'
        verbose_name_plural = 'Parent Messages'
        indexes = [
            models.Index(fields=['receiver', 'is_read', '-timestamp']),
            models.Index(fields=['sender', '-timestamp']),
            models.Index(fields=['parent', '-timestamp']),
            models.Index(fields=['is_bulk', 'bulk_id']),
            models.Index(fields=['priority', '-timestamp']),
            models.Index(fields=['email_sent', 'sms_sent']),
        ]
    
    def __str__(self):
        read_status = "📧" if self.is_read else "📬"
        priority_icon = {
            'normal': '',
            'high': '⚠️ ',
            'urgent': '🚨 '
        }.get(self.priority, '')
        return f"{priority_icon}{read_status} {self.subject} - {self.sender} to {self.receiver}"
    
    def mark_as_read(self):
        """Mark message as read"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
    
    def mark_as_unread(self):
        """Mark message as unread"""
        if self.is_read:
            self.is_read = False
            self.save(update_fields=['is_read'])
    
    def get_conversation(self, limit=50):
        """Get conversation thread between sender and receiver"""
        return ParentMessage.objects.filter(
            Q(sender=self.sender, receiver=self.receiver) |
            Q(sender=self.receiver, receiver=self.sender)
        ).order_by('timestamp')[:limit]
    
    def is_part_of_conversation(self):
        """Check if this is part of a conversation (has replies)"""
        return ParentMessage.objects.filter(
            Q(sender=self.receiver, receiver=self.sender)
        ).exists()
    
    def get_reply_count(self):
        """Get count of replies in this conversation"""
        return ParentMessage.objects.filter(
            sender=self.receiver,
            receiver=self.sender
        ).count()
    
    def mark_email_sent(self):
        """Mark email as sent"""
        self.email_sent = True
        self.email_sent_at = timezone.now()
        self.save(update_fields=['email_sent', 'email_sent_at'])
    
    def mark_sms_sent(self):
        """Mark SMS as sent"""
        self.sms_sent = True
        self.sms_sent_at = timezone.now()
        self.save(update_fields=['sms_sent', 'sms_sent_at'])
    
    def get_delivery_status(self):
        """Get delivery status summary"""
        status = {
            'in_app': True,  # Always delivered in app
            'email': self.email_sent,
            'sms': self.sms_sent,
        }
        
        if self.email_sent_at:
            status['email_sent_at'] = self.email_sent_at
        
        if self.sms_sent_at:
            status['sms_sent_at'] = self.sms_sent_at
        
        return status
    
    @classmethod
    def get_unread_count(cls, user):
        """Get count of unread messages for user"""
        return cls.objects.filter(receiver=user, is_read=False).count()
    
    @classmethod
    def get_bulk_messages(cls, bulk_id):
        """Get all messages from a bulk send"""
        return cls.objects.filter(bulk_id=bulk_id)
    
    @classmethod
    def create_bulk_message(cls, sender, parent, subject, message, bulk_id=None, priority='normal'):
        """Helper to create a bulk message"""
        return cls.objects.create(
            sender=sender,
            receiver=parent.user,
            parent=parent,
            subject=subject,
            message=message,
            is_bulk=True,
            bulk_id=bulk_id or f"bulk_{timezone.now().timestamp()}",
            priority=priority
        )


@receiver(post_save, sender=ParentMessage)
def notify_parent_message(sender, instance, created, **kwargs):
    """Send notifications when new message is created"""
    if created:
        try:
            # Log the message creation
            logger.info(f"New ParentMessage created: {instance.id} from {instance.sender} to {instance.receiver}")
            
            # You can add email/SMS sending logic here
            # Example:
            # if instance.receiver.email:
            #     # Send email notification
            #     from django.core.mail import send_mail
            #     send_mail(
            #         subject=f"New Message: {instance.subject}",
            #         message=f"You have a new message from {instance.sender.get_full_name()}:\n\n{instance.message[:200]}...",
            #         from_email='school@example.com',
            #         recipient_list=[instance.receiver.email],
            #         fail_silently=True,
            #     )
            #     instance.mark_email_sent()
            
        except Exception as e:
            logger.error(f"Failed to send notification for message {instance.id}: {e}")


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
    
    # Additional fields for better event management
    event_type = models.CharField(
        max_length=50,
        choices=[
            ('meeting', 'Parent-Teacher Meeting'),
            ('workshop', 'Workshop/Seminar'),
            ('celebration', 'Celebration/Performance'),
            ('sports', 'Sports Event'),
            ('academic', 'Academic Event'),
            ('other', 'Other'),
        ],
        default='meeting'
    )
    is_mandatory = models.BooleanField(default=False)
    max_attendees = models.PositiveIntegerField(null=True, blank=True, help_text="Maximum number of attendees (if applicable)")
    registration_deadline = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['start_date']
        verbose_name = 'Parent Event'
        verbose_name_plural = 'Parent Events'
        indexes = [
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['is_whole_school', 'class_level']),
            models.Index(fields=['event_type', 'start_date']),
            models.Index(fields=['is_mandatory', 'start_date']),
        ]
    
    def __str__(self):
        type_icon = {
            'meeting': '🤝',
            'workshop': '🎓',
            'celebration': '🎉',
            'sports': '⚽',
            'academic': '📚',
            'other': '📅'
        }.get(self.event_type, '📅')
        
        mandatory = "⚠️ " if self.is_mandatory else ""
        return f"{type_icon} {mandatory}{self.title} - {self.start_date.strftime('%b %d, %Y')}"
    
    def is_upcoming(self):
        """Check if event is upcoming (not yet started)"""
        return self.start_date > timezone.now()
    
    def is_ongoing(self):
        """Check if event is currently ongoing"""
        now = timezone.now()
        return self.start_date <= now <= self.end_date
    
    def is_past(self):
        """Check if event has passed"""
        return self.end_date < timezone.now()
    
    def get_status(self):
        """Get event status"""
        if self.is_upcoming():
            return 'upcoming'
        elif self.is_ongoing():
            return 'ongoing'
        else:
            return 'past'
    
    def get_duration(self):
        """Get event duration in hours"""
        duration = self.end_date - self.start_date
        return round(duration.total_seconds() / 3600, 1)
    
    def is_relevant_for_parent(self, parent):
        """Check if this event is relevant for a specific parent"""
        if self.is_whole_school:
            return True
        elif self.class_level:
            return parent.students.filter(class_level=self.class_level).exists()
        return False
    
    def get_estimated_attendees(self):
        """Get estimated number of attendees"""
        if self.is_whole_school:
            return ParentGuardian.objects.count()
        elif self.class_level:
            return ParentGuardian.objects.filter(
                students__class_level=self.class_level
            ).distinct().count()
        return 0
    
    def can_register(self):
        """Check if registration is still open"""
        if not self.registration_deadline:
            return self.is_upcoming()
        return timezone.now() <= self.registration_deadline
    
    def is_full(self):
        """Check if event is full (if max_attendees is set)"""
        if self.max_attendees:
            # You would need a registration model to track actual registrations
            # For now, return estimated
            return self.get_estimated_attendees() >= self.max_attendees
        return False