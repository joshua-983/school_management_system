"""
Communication models: Announcements, Notifications, etc.
"""
import logging
from django.db import models
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.urls import reverse
from django.db.models import Q, Count
from django.utils.safestring import mark_safe

from core.models.base import CLASS_LEVEL_CHOICES
from core.models.student import Student
from core.models.parent import ParentGuardian

logger = logging.getLogger(__name__)
User = get_user_model()


class Announcement(models.Model):
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    TARGET_CHOICES = [
        ('ALL', 'All Users'),
        ('STUDENTS', 'Students'),
        ('TEACHERS', 'Teachers'),
        ('ADMINS', 'Administrators'),
        ('CLASS', 'Specific Classes'),
    ]
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='NORMAL')
    target_roles = models.CharField(max_length=20, choices=TARGET_CHOICES, default='ALL')
    target_class_levels = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="Comma-separated class levels (e.g., P1,P2,P3) or leave blank for all"
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(blank=True, null=True)
    attachment = models.FileField(upload_to='announcements/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Announcement'
        verbose_name_plural = 'Announcements'
    
    def __str__(self):
        return self.title
    
    def get_target_class_levels(self):
        """Get list of target class levels"""
        if not self.target_class_levels:
            return []
        return [level.strip() for level in self.target_class_levels.split(',')]
    
    def is_for_class_level(self, class_level):
        """Check if announcement is for a specific class level"""
        if not self.target_class_levels:
            return True
        return class_level in self.get_target_class_levels()
    
    def is_expired(self):
        """Check if announcement has expired"""
        if self.end_date:
            return timezone.now() > self.end_date
        return False
    
    def is_active_now(self):
        """Check if announcement is currently active"""
        return self.is_active and not self.is_expired()
    
    def get_priority_color(self):
        """Get Bootstrap color for priority"""
        colors = {
            'URGENT': 'danger',
            'HIGH': 'warning', 
            'NORMAL': 'info',
            'LOW': 'secondary'
        }
        return colors.get(self.priority, 'secondary')
    
    @property
    def views_count(self):
        """Get the number of views for this announcement"""
        return self.userannouncementview_set.count()
    
    @property
    def is_expired_property(self):
        """Property version of is_expired for template usage"""
        return self.is_expired()
    
    @property
    def is_active_now_property(self):
        """Property version of is_active_now for template usage"""
        return self.is_active_now()
    
    def get_days_remaining(self):
        """Get number of days remaining until expiry"""
        if self.end_date and not self.is_expired():
            remaining = self.end_date - timezone.now()
            return max(0, remaining.days)
        return None
    
    def get_status_display(self):
        """Get human-readable status"""
        if not self.is_active:
            return "Inactive"
        elif self.is_expired():
            return "Expired"
        elif self.start_date > timezone.now():
            return "Scheduled"
        else:
            return "Active"
    
    def get_status_color(self):
        """Get Bootstrap color for status"""
        if not self.is_active:
            return "secondary"
        elif self.is_expired():
            return "warning"
        elif self.start_date > timezone.now():
            return "info"
        else:
            return "success"
    
    def get_audience_display(self):
        """Get human-readable audience description"""
        target_classes = self.get_target_class_levels()
        if self.target_roles == 'CLASS' and target_classes:
            class_names = []
            for class_level in target_classes:
                class_display_map = dict(CLASS_LEVEL_CHOICES)
                class_names.append(class_display_map.get(class_level, class_level))
            return f"Classes: {', '.join(class_names)}"
        else:
            return self.get_target_roles_display()
    
    def can_user_access(self, user):
        """Check if user has permission to view this announcement"""
        # Staff and teachers can see all announcements
        if user.is_staff or hasattr(user, 'teacher'):
            return True
        
        # Check if announcement is active and not expired
        if not self.is_active_now():
            return False
        
        # Check target roles
        if self.target_roles == 'STUDENTS' and not hasattr(user, 'student'):
            return False
        elif self.target_roles == 'TEACHERS' and not (hasattr(user, 'teacher') or user.is_staff):
            return False
        elif self.target_roles == 'ADMINS' and not user.is_staff:
            return False
        elif self.target_roles == 'CLASS':
            target_classes = self.get_target_class_levels()
            if hasattr(user, 'student') and user.student.class_level in target_classes:
                return True
            elif hasattr(user, 'parentguardian'):
                # Parents can see announcements for their children's classes
                children_classes = user.parentguardian.students.values_list('class_level', flat=True)
                if any(cls in target_classes for cls in children_classes):
                    return True
            return False
        
        # ALL role or passed other checks
        return True
    
    def mark_as_viewed(self, user):
        """Mark announcement as viewed by a user"""
        UserAnnouncementView.objects.get_or_create(
            user=user,
            announcement=self,
            defaults={'viewed_at': timezone.now()}
        )
    
    def get_view_stats(self):
        """Get viewing statistics for this announcement"""
        views = self.userannouncementview_set.all()
        total_views = views.count()
        unique_viewers = views.values('user').distinct().count()
        dismissed_count = views.filter(dismissed=True).count()
        
        return {
            'total_views': total_views,
            'unique_viewers': unique_viewers,
            'dismissed_count': dismissed_count,
            'engagement_rate': round((unique_viewers / max(1, self.get_target_user_count())) * 100, 1)
        }
    
    def get_target_user_count(self):
        """Estimate number of target users for this announcement"""
        target_classes = self.get_target_class_levels()
        user_query = Q(is_active=True)
        
        if self.target_roles == 'STUDENTS':
            user_query &= Q(student__isnull=False)
            if target_classes:
                user_query &= Q(student__class_level__in=target_classes)
        elif self.target_roles == 'TEACHERS':
            user_query &= (Q(teacher__isnull=False) | Q(is_staff=True))
        elif self.target_roles == 'ADMINS':
            user_query &= Q(is_staff=True)
        elif self.target_roles == 'CLASS' and target_classes:
            user_query &= (
                Q(student__class_level__in=target_classes) |
                Q(parentguardian__students__class_level__in=target_classes) |
                Q(teacher__isnull=False) |
                Q(is_staff=True)
            )
        # ALL role includes all active users
        
        return User.objects.filter(user_query).distinct().count()
    
    def duplicate(self, new_title=None):
        """Create a duplicate of this announcement"""
        duplicate = Announcement.objects.get(pk=self.pk)
        duplicate.pk = None
        duplicate.title = new_title or f"Copy of {self.title}"
        duplicate.created_at = timezone.now()
        duplicate.updated_at = timezone.now()
        duplicate.is_active = False  # Keep duplicate inactive by default
        duplicate.save()
        return duplicate
    
    def extend_expiry(self, days=7):
        """Extend the expiry date by specified number of days"""
        if self.end_date:
            self.end_date += timezone.timedelta(days=days)
        else:
            self.end_date = timezone.now() + timezone.timedelta(days=days)
        self.save()
    
    def get_time_until_expiry(self):
        """Get human-readable time until expiry"""
        if not self.end_date or self.is_expired():
            return "No expiry" if not self.end_date else "Expired"
        
        delta = self.end_date - timezone.now()
        
        if delta.days > 0:
            return f"{delta.days} day{'s' if delta.days != 1 else ''}"
        elif delta.seconds // 3600 > 0:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            minutes = (delta.seconds % 3600) // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"


class UserAnnouncementView(models.Model):
    """Track which users have seen/dismissed which announcements"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE)
    dismissed = models.BooleanField(default=False)
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'announcement')
        verbose_name = 'User Announcement View'
        verbose_name_plural = 'User Announcement Views'
        ordering = ['-viewed_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.announcement.title} ({'Dismissed' if self.dismissed else 'Viewed'})"
    
    @classmethod
    def get_user_unread_count(cls, user):
        """Get count of unread announcements for a user"""
        # Import here to avoid circular import
        from core.models.communication import Announcement
        
        active_announcements = Announcement.objects.filter(
            is_active=True,
            start_date__lte=timezone.now(),
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=timezone.now())
        )
        
        unread_count = 0
        for announcement in active_announcements:
            if (announcement.can_user_access(user) and 
                not cls.objects.filter(user=user, announcement=announcement).exists()):
                unread_count += 1
        
        return unread_count


class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('GRADE', 'Grade Update'),
        ('FEE', 'Fee Payment'),
        ('ASSIGNMENT', 'Assignment'),
        ('ATTENDANCE', 'Attendance'),
        ('GENERAL', 'General'),
        ('ANNOUNCEMENT', 'Announcement'),
        ('SYSTEM', 'System'),
        ('SECURITY', 'Security'),
    ]
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='GENERAL')
    title = models.CharField(max_length=200)
    message = models.TextField()
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    related_content_type = models.CharField(max_length=50, blank=True)
    link = models.CharField(max_length=500, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', 'created_at']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.title} - {self.recipient.username}"
    
    def get_absolute_url(self):
        if self.link:
            return self.link
            
        if self.related_object_id and self.related_content_type:
            try:
                from django.apps import apps
                model_class = apps.get_model('core', self.related_content_type)
                obj = model_class.objects.get(pk=self.related_object_id)
                if hasattr(obj, 'get_absolute_url'):
                    return obj.get_absolute_url()
            except Exception as e:
                logger.warning(f"Could not get absolute URL for notification {self.id}: {str(e)}")
        
        return reverse('notification_list')
    
    @classmethod
    def get_unread_count_for_user(cls, user):
        """
        Get unread notification count for a specific user
        """
        try:
            # Handle different object types safely
            if hasattr(user, 'is_authenticated'):
                # It's a User object
                if not user or not user.is_authenticated:
                    return 0
            elif hasattr(user, 'user'):
                # It's a request object, extract the user
                user = user.user
                if not user or not user.is_authenticated:
                    return 0
            else:
                # Unknown type or None, return 0
                return 0
            
            return cls.objects.filter(recipient=user, is_read=False).count()
            
        except Exception as e:
            logger.error(f"Error getting unread count: {str(e)}")
            return 0
    
    def mark_as_read(self):
        """Mark notification as read and send WebSocket update"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
            self.send_websocket_update()
            return True
        return False
    
    def send_websocket_update(self):
        """Send WebSocket update for this notification"""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'notifications_{self.recipient.id}',
                {
                    'type': 'notification_update',
                    'action': 'single_read',
                    'notification_id': self.id,
                    'unread_count': self.get_unread_count_for_user(self.recipient)
                }
            )
        except Exception as e:
            logger.error(f"WebSocket update failed for notification {self.id}: {str(e)}")
    
    def send_new_notification_ws(self):
        """Send WebSocket notification when a new notification is created"""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'notifications_{self.recipient.id}',
                {
                    'type': 'notification_update',
                    'action': 'new_notification',
                    'notification': {
                        'id': self.id,
                        'title': self.title,
                        'message': self.message,
                        'notification_type': self.notification_type,
                        'created_at': self.created_at.isoformat(),
                        'is_read': self.is_read,
                    },
                    'unread_count': self.get_unread_count_for_user(self.recipient)
                }
            )
        except Exception as e:
            logger.error(f"WebSocket new notification failed: {str(e)}")
    
    @classmethod
    def create_notification(cls, recipient, title, message, notification_type="GENERAL", link=None, related_object=None):
        """Create a notification and send WebSocket update"""
        try:
            notification = cls.objects.create(
                recipient=recipient,
                title=title,
                message=message,
                notification_type=notification_type,
                link=link
            )
            
            if related_object:
                notification.related_object_id = related_object.pk
                notification.related_content_type = related_object._meta.model_name
                notification.save()
            
            # Send WebSocket notification
            notification.send_new_notification_ws()
            
            logger.info(f"Notification created successfully for {recipient.username}: {title}")
            return notification
            
        except Exception as e:
            logger.error(f"Failed to create notification: {str(e)}")
            return None
    
    def save(self, *args, **kwargs):
        """Override save to handle WebSocket notifications"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Send WebSocket notification for new notifications
        if is_new:
            self.send_new_notification_ws()