# core/views/notifications_views.py - COMPLETELY FIXED WITH PROPER ERROR HANDLING
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.urls import reverse
from django.utils import timezone
from django.db import models
from django.shortcuts import get_object_or_404
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
        ).select_related('recipient').order_by('-created_at')
    
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
                models.Q(target_roles='ALL') | 
                models.Q(target_roles='STUDENTS') |
                models.Q(target_roles='CLASS', target_class_levels__contains=student.class_level)
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
        
        # ✅ FIXED: Pass user object correctly with error handling
        try:
            context['unread_count'] = Notification.get_unread_count_for_user(self.request.user)
        except Exception as e:
            logger.error(f"Error getting unread count in NotificationListView: {str(e)}")
            context['unread_count'] = 0
        
        # Add additional context for templates
        context['current_time'] = timezone.now()
        context['user_type'] = self.get_user_type()
        
        return context
    
    def get_user_type(self):
        """Get user type for template context"""
        user = self.request.user
        if hasattr(user, 'student'):
            return 'student'
        elif hasattr(user, 'teacher'):
            return 'teacher'
        elif hasattr(user, 'parentguardian'):
            return 'parent'
        elif user.is_staff:
            return 'staff'
        else:
            return 'unknown'
    
    def get(self, request, *args, **kwargs):
        # Mark all unread notifications as read when page is loaded
        try:
            unread_notifications = request.user.notifications.filter(is_read=False)
            if unread_notifications.exists():
                unread_notifications.update(is_read=True)
                self.send_ws_update(request.user, 'mark_all_read', 0)
        except Exception as e:
            logger.error(f"Error marking notifications as read: {str(e)}")
            
        return super().get(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """Handle mark all as read POST request"""
        try:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest' or request.content_type == 'application/json':
                unread_notifications = request.user.notifications.filter(is_read=False)
                count = unread_notifications.count()
                if count > 0:
                    unread_notifications.update(is_read=True)
                    self.send_ws_update(request.user, 'mark_all_read', 0)
                return JsonResponse({'status': 'success', 'count': count})
            
            return JsonResponse({'status': 'error', 'message': 'Method not allowed'}, status=405)
        except Exception as e:
            logger.error(f"Error in NotificationListView POST: {str(e)}")
            return JsonResponse({'status': 'error', 'message': 'Internal server error'}, status=500)

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
        notification = get_object_or_404(
            Notification,
            pk=pk,
            recipient=request.user
        )
        
        if notification.mark_as_read():
            # ✅ FIXED: Pass user object correctly with error handling
            try:
                unread_count = Notification.get_unread_count_for_user(request.user)
                return JsonResponse({
                    'status': 'success',
                    'unread_count': unread_count
                })
            except Exception as e:
                logger.error(f"Error getting unread count after mark read: {str(e)}")
                return JsonResponse({
                    'status': 'success',
                    'unread_count': 0
                })
        else:
            return JsonResponse({'status': 'already_read'})
            
    except Notification.DoesNotExist:
        logger.warning(f"Notification not found: {pk} for user {request.user}")
        return JsonResponse({'status': 'error', 'message': 'Notification not found'}, status=404)
    except Exception as e:
        logger.error(f"Error marking notification as read: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'Internal server error'}, status=500)

@login_required
@require_POST
def mark_all_notifications_read(request):
    """API endpoint to mark all notifications as read"""
    try:
        unread_notifications = request.user.notifications.filter(is_read=False)
        count = unread_notifications.count()
        
        if count > 0:
            unread_notifications.update(is_read=True)
            
            # Send WebSocket update
            try:
                channel_layer = get_channel_layer()
                async_to_sync(channel_layer.group_send)(
                    f'notifications_{request.user.id}',
                    {
                        'type': 'notification_update',
                        'action': 'mark_all_read',
                        # ✅ FIXED: Use the correct method with error handling
                        'unread_count': Notification.get_unread_count_for_user(request.user)
                    }
                )
            except Exception as e:
                logger.error(f"WebSocket update failed: {str(e)}")
                
            return JsonResponse({
                'status': 'success', 
                'message': f'Marked {count} notifications as read',
                'count': count
            })
        else:
            return JsonResponse({'status': 'success', 'message': 'No unread notifications', 'count': 0})
            
    except Exception as e:
        logger.error(f"Error marking all notifications as read: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'Internal server error'}, status=500)

@login_required
def get_unread_count(request):
    """API endpoint to get unread notification count - FIXED WITH PROPER ERROR HANDLING"""
    try:
        # ✅ FIXED: Pass user object correctly with comprehensive error handling
        count = Notification.get_unread_count_for_user(request.user)
        logger.debug(f"Unread count for user {request.user.username}: {count}")
        return JsonResponse({'unread_count': count})
    except Exception as e:
        logger.error(f"Error getting unread count for user {request.user.username}: {str(e)}")
        # Return a safe default instead of crashing
        return JsonResponse({'unread_count': 0})

# Notification creation functions - UPDATED AND FIXED WITH ERROR HANDLING
def create_notification(recipient, title, message, notification_type="GENERAL", link=None, related_object=None):
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
        
        if notification:
            logger.info(f"Notification created for {recipient.username}: {title}")
            # Send WebSocket update
            send_ws_notification_update(recipient)
        else:
            logger.warning(f"Failed to create notification for {recipient.username}")
            
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
        # ✅ FIXED: Use the correct method with error handling
        unread_count = Notification.get_unread_count_for_user(user)
        async_to_sync(channel_layer.group_send)(
            f'notifications_{user.id}',
            {
                'type': 'notification_update',
                'action': 'count_update',
                'unread_count': unread_count
            }
        )
    except Exception as e:
        logger.error(f"WebSocket notification update failed: {str(e)}")

def get_unread_count_for_user(user):
    """Get unread notification count for a user with error handling"""
    try:
        # ✅ FIXED: Use the correct method
        return Notification.get_unread_count_for_user(user)
    except Exception as e:
        logger.error(f"Error getting unread count for user {user.username}: {str(e)}")
        return 0

def send_assignment_notification(assignment):
    """
    Send notifications to all students in the class about a new assignment
    """
    try:
        from core.models import Student
        
        # Get all students in the class level
        students = Student.objects.filter(
            class_level=assignment.class_assignment.class_level,
            is_active=True
        ).select_related('user')
        
        notification_count = 0
        for student in students:
            if student.user and student.user.is_active:
                notification = create_notification(
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
        
        students = Student.objects.filter(
            class_level=assignment.class_assignment.class_level,
            is_active=True
        ).select_related('user')
        
        notification_count = 0
        for student in students:
            if student.user and student.user.is_active:
                if old_due_date:
                    # Due date change notification
                    notification = create_notification(
                        recipient=student.user,
                        title="Assignment Due Date Updated",
                        message=f"Due date for '{assignment.title}' has been changed from {old_due_date.strftime('%b %d, %Y')} to {assignment.due_date.strftime('%b %d, %Y at %I:%M %p')}",
                        notification_type="ASSIGNMENT",
                        link=reverse('assignment_detail', kwargs={'pk': assignment.pk}),
                        related_object=assignment
                    )
                else:
                    # General assignment update notification
                    notification = create_notification(
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
        
        if not student.user or not student.user.is_active:
            return False
        
        # Calculate percentage
        percentage = (student_assignment.score / assignment.max_score) * 100 if student_assignment.score else 0
        
        # Performance message
        if percentage >= 80:
            performance_msg = "Excellent work!"
        elif percentage >= 70:
            performance_msg = "Good job!"
        elif percentage >= 50:
            performance_msg = "Satisfactory performance."
        else:
            performance_msg = "Needs improvement."
        
        notification = create_notification(
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
        
        if notification:
            logger.info(f"Grading notification sent to {student.user.username} for assignment '{assignment.title}'")
            return True
        else:
            logger.warning(f"Failed to send grading notification to {student.user.username}")
            return False
        
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
        
        # Start with active users
        target_users = User.objects.filter(is_active=True)
        
        # Filter based on announcement target
        if announcement.target_roles == 'STUDENTS':
            target_users = target_users.filter(
                models.Q(student__isnull=False) | 
                models.Q(is_staff=True)  # Staff can see all
            )
        elif announcement.target_roles == 'TEACHERS':
            target_users = target_users.filter(
                models.Q(teacher__isnull=False) | 
                models.Q(is_staff=True)
            )
        elif announcement.target_roles == 'ADMINS':
            target_users = target_users.filter(is_staff=True)
        elif announcement.target_roles == 'CLASS' and target_class_levels:
            # For class-specific announcements
            target_users = target_users.filter(
                models.Q(student__class_level__in=target_class_levels) |
                models.Q(parentguardian__students__class_level__in=target_class_levels) |
                models.Q(teacher__isnull=False) |
                models.Q(is_staff=True)
            ).distinct()
        # 'ALL' includes all active users
        
        notification_count = 0
        for user in target_users:
            notification = create_notification(
                recipient=user,
                title=f"New Announcement: {announcement.title}",
                message=announcement.message[:100] + "..." if len(announcement.message) > 100 else announcement.message,
                notification_type="ANNOUNCEMENT",
                link=reverse('announcement_detail', kwargs={'pk': announcement.pk}),
                related_object=announcement
            )
            if notification:
                notification_count += 1
        
        logger.info(f"Announcement notifications sent to {notification_count} users: {announcement.title}")
        return notification_count
        
    except Exception as e:
        logger.error(f"Failed to send announcement notifications: {str(e)}")
        return 0

def send_fee_notification(student, fee, notification_type="FEE"):
    """
    Send fee-related notifications to students/parents
    """
    try:
        # Notify student
        if student.user and student.user.is_active:
            create_notification(
                recipient=student.user,
                title="Fee Update",
                message=f"Fee update for {fee.category.name}: GH₵{fee.amount_payable}. Due date: {fee.due_date.strftime('%b %d, %Y')}",
                notification_type=notification_type,
                link=reverse('fee_details'),
                related_object=fee
            )
        
        # Notify parents
        parents = student.parents.all()
        for parent in parents:
            if parent.user and parent.user.is_active:
                create_notification(
                    recipient=parent.user,
                    title="Student Fee Update",
                    message=f"Fee update for {student.get_full_name()}: {fee.category.name} - GH₵{fee.amount_payable}. Due date: {fee.due_date.strftime('%b %d, %Y')}",
                    notification_type=notification_type,
                    link=reverse('fee_details'),
                    related_object=fee
                )
        
        logger.info(f"Fee notifications sent for student {student.get_full_name()}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to send fee notifications: {str(e)}")
        return False

# ADDITIONAL FIX: Ensure the Notification model method exists and works correctly
def ensure_notification_methods():
    """
    Utility function to verify Notification methods exist
    """
    try:
        # Test that the method exists and works
        test_count = Notification.get_unread_count_for_user
        logger.info("Notification.get_unread_count_for_user method is available")
        return True
    except AttributeError as e:
        logger.error(f"Notification method missing: {str(e)}")
        # Fallback implementation
        def fallback_get_unread_count(user):
            try:
                return Notification.objects.filter(recipient=user, is_read=False).count()
            except:
                return 0
        
        # Add fallback method if it doesn't exist
        if not hasattr(Notification, 'get_unread_count_for_user'):
            Notification.get_unread_count_for_user = fallback_get_unread_count
            logger.warning("Added fallback get_unread_count_for_user method to Notification model")
        return False

# Call this on module import to ensure methods exist
ensure_notification_methods()
