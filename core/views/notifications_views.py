# core/views/notifications_views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.db import models
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

from core.models import Notification, Announcement, UserAnnouncementView

logger = logging.getLogger(__name__)

class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'core/messaging/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user
        ).order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add active announcements to context
        announcements = Announcement.objects.filter(
            is_active=True,
            start_date__lte=timezone.now(),
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=timezone.now())
        )
        
        # Filter by user's class if they're a student
        if hasattr(self.request.user, 'student'):
            student = self.request.user.student
            announcements = announcements.filter(
                models.Q(target_audience__isnull=True) | 
                models.Q(target_audience=student.class_level)
            )
        
        announcements = announcements.distinct().order_by('-priority', '-created_at')
        
        # Check which announcements user has dismissed
        dismissed_announcements = UserAnnouncementView.objects.filter(
            user=self.request.user,
            dismissed=True
        ).values_list('announcement_id', flat=True)
        
        context['active_announcements'] = [
            ann for ann in announcements 
            if ann.id not in dismissed_announcements
        ]
        return context
    
    def get(self, request, *args, **kwargs):
        # Mark all unread notifications as read when page is loaded
        unread_notifications = request.user.notifications.filter(is_read=False)
        if unread_notifications.exists():
            unread_notifications.update(is_read=True)
            self.send_ws_update(request.user, 'mark_all_read', 0)
        return super().get(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """Handle mark all as read POST request"""
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
            unread_notifications = request.user.notifications.filter(is_read=False)
            count = unread_notifications.count()
            if count > 0:
                unread_notifications.update(is_read=True)
                self.send_ws_update(request.user, 'mark_all_read', 0)
            return JsonResponse({'status': 'success', 'count': count})
        
        return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)

    def send_ws_update(self, user, action, unread_count):
        """Send WebSocket update"""
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'notifications_{user.id}',
                {
                    'type': 'notification_update',
                    'action': action,
                    'unread_count': unread_count
                }
            )
        except Exception as e:
            logger.error(f"WebSocket update failed: {str(e)}")

@login_required
@require_POST
def mark_notification_read(request, pk):
    """API endpoint to mark single notification as read"""
    try:
        notification = Notification.objects.get(
            pk=pk,
            recipient=request.user
        )
        notification.is_read = True
        notification.save()
        
        # Send WS update
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'notifications_{request.user.id}',
                {
                    'type': 'notification_update',
                    'action': 'single_read',
                    'unread_count': Notification.get_unread_count_for_user(request.user)
                }
            )
        except Exception as e:
            logger.error(f"WebSocket update failed: {str(e)}")
            
        return JsonResponse({'status': 'success'})
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error'}, status=404)

# Notification creation functions
def create_notification(recipient, title, message, notification_type="INFO", link=None, related_object=None):
    """
    Create a notification and send it via WebSocket
    """
    try:
        # Use the Notification class method to create notification
        notification = Notification.create_notification(
            recipient=recipient,
            title=title,
            message=message,
            notification_type=notification_type,
            link=link,
            related_object=related_object
        )
        
        logger.info(f"Notification created for {recipient.username}: {title}")
        return notification
        
    except Exception as e:
        logger.error(f"Failed to create notification: {str(e)}")
        return None

def send_ws_notification_update(user):
    """
    Send WebSocket update for notification count
    """
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'notifications_{user.id}',
            {
                'type': 'notification_update',
                'action': 'new_notification',
                'unread_count': Notification.get_unread_count_for_user(user)
            }
        )
    except Exception as e:
        logger.error(f"WebSocket notification update failed: {str(e)}")

def get_unread_count(user):
    """Get unread notification count for a user"""
    return Notification.get_unread_count_for_user(user)

def send_assignment_notification(assignment):
    """
    Send notifications to all students in the class about a new assignment
    """
    try:
        from core.models import Student
        
        # Get all students in the class level
        students = Student.objects.filter(class_level=assignment.class_assignment.class_level)
        
        notification_count = 0
        for student in students:
            # Create notification for each student using the class method
            notification = Notification.create_notification(
                recipient=student.user,
                title="New Assignment Created",
                message=f"New assignment '{assignment.title}' has been created for {assignment.subject.name}. Due date: {assignment.due_date.strftime('%b %d, %Y at %I:%M %p')}",
                notification_type="ASSIGNMENT",
                link=reverse('assignment_detail', kwargs={'pk': assignment.pk}),
                related_object=assignment
            )
            if notification:
                notification_count += 1
        
        logger.info(f"Assignment notifications sent to {notification_count} students for assignment '{assignment.title}'")
        return notification_count
        
    except Exception as e:
        logger.error(f"Failed to send assignment notifications: {str(e)}")
        return 0

def send_assignment_update_notification(assignment, old_due_date=None):
    """
    Send notifications about assignment updates
    """
    try:
        from core.models import Student
        
        students = Student.objects.filter(class_level=assignment.class_assignment.class_level)
        
        notification_count = 0
        for student in students:
            if old_due_date:
                # Due date change notification
                notification = Notification.create_notification(
                    recipient=student.user,
                    title="Assignment Due Date Updated",
                    message=f"Due date for '{assignment.title}' has been changed from {old_due_date.strftime('%b %d, %Y')} to {assignment.due_date.strftime('%b %d, %Y at %I:%M %p')}",
                    notification_type="ASSIGNMENT",
                    link=reverse('assignment_detail', kwargs={'pk': assignment.pk}),
                    related_object=assignment
                )
            else:
                # General assignment update notification
                notification = Notification.create_notification(
                    recipient=student.user,
                    title="Assignment Updated",
                    message=f"Assignment '{assignment.title}' has been updated. Please check for changes.",
                    notification_type="ASSIGNMENT",
                    link=reverse('assignment_detail', kwargs={'pk': assignment.pk}),
                    related_object=assignment
                )
            
            if notification:
                notification_count += 1
        
        logger.info(f"Assignment update notifications sent to {notification_count} students for assignment '{assignment.title}'")
        return notification_count
        
    except Exception as e:
        logger.error(f"Failed to send assignment update notifications: {str(e)}")
        return 0

def send_grading_notification(student_assignment):
    """
    Send notification to student when their assignment is graded
    """
    try:
        assignment = student_assignment.assignment
        student = student_assignment.student
        
        # Calculate percentage
        percentage = (student_assignment.score / assignment.max_score) * 100
        
        # Performance message
        if percentage >= 80:
            performance_msg = "Excellent work!"
        elif percentage >= 70:
            performance_msg = "Good job!"
        elif percentage >= 50:
            performance_msg = "Satisfactory performance."
        else:
            performance_msg = "Needs improvement."
        
        notification = Notification.create_notification(
            recipient=student.user,
            title="Assignment Graded",
            message=(
                f"Your assignment '{assignment.title}' has been graded. "
                f"Score: {student_assignment.score}/{assignment.max_score} ({percentage:.1f}%). "
                f"{performance_msg}"
            ),
            notification_type="GRADE",
            link=reverse('assignment_detail', kwargs={'pk': assignment.pk}),
            related_object=student_assignment
        )
        
        logger.info(f"Grading notification sent to {student.user.username} for assignment '{assignment.title}'")
        return notification is not None
        
    except Exception as e:
        logger.error(f"Failed to send grading notification: {str(e)}")
        return False

def create_announcement_notification(announcement):
    """
    Create notifications for all relevant users about a new announcement
    """
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Get target users based on announcement settings
        target_class_levels = announcement.get_target_class_levels()
        
        if target_class_levels:
            # Specific classes - get students in those classes
            student_users = User.objects.filter(
                student__class_level__in=target_class_levels,
                is_active=True
            )
            
            # Get parents of students in those classes
            parent_users = User.objects.filter(
                parentguardian__students__class_level__in=target_class_levels,
                is_active=True
            ).distinct()
            
            # Include teachers/staff
            teacher_users = User.objects.filter(
                teacher__isnull=False,
                is_active=True
            )
            
            staff_users = User.objects.filter(
                is_staff=True,
                is_active=True
            )
            
            # Combine all users
            target_users = student_users.union(parent_users).union(teacher_users).union(staff_users)
        else:
            # School-wide announcement - send to all active users
            target_users = User.objects.filter(is_active=True)
        
        notification_count = 0
        for user in target_users:
            notification = Notification.create_notification(
                recipient=user,
                title=f"New Announcement: {announcement.title}",
                message=announcement.message[:100] + "..." if len(announcement.message) > 100 else announcement.message,
                notification_type="GENERAL",
                link=reverse('announcement_list'),
                related_object=announcement
            )
            if notification:
                notification_count += 1
        
        logger.info(f"Announcement notifications sent to {notification_count} users: {announcement.title}")
        return notification_count
        
    except Exception as e:
        logger.error(f"Failed to send announcement notifications: {str(e)}")
        return 0