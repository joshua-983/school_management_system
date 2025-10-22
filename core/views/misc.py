# core/views/misc.py
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.urls import reverse
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

from core.models import Notification

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

    def send_ws_update(self, user, action, unread_count=None):
        """Send WebSocket update for notification changes"""
        try:
            if unread_count is None:
                unread_count = Notification.get_unread_count_for_user(user)
            
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

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['unread_count'] = Notification.get_unread_count_for_user(self.request.user)
        context['total_count'] = self.get_queryset().count()
        return context

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
        
        if not notification.is_read:
            notification.mark_as_read()
            return JsonResponse({
                'status': 'success', 
                'message': 'Notification marked as read',
                'unread_count': Notification.get_unread_count_for_user(request.user)
            })
        else:
            return JsonResponse({
                'status': 'success', 
                'message': 'Notification already read',
                'unread_count': Notification.get_unread_count_for_user(request.user)
            })
            
    except Notification.DoesNotExist:
        logger.error(f"Notification {pk} not found for user {request.user}")
        return JsonResponse({
            'status': 'error', 
            'message': 'Notification not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error marking notification {pk} as read: {str(e)}")
        return JsonResponse({
            'status': 'error', 
            'message': 'Internal server error'
        }, status=500)

@login_required
@require_POST
def mark_all_notifications_read(request):
    """API endpoint to mark all notifications as read for current user"""
    try:
        updated_count = Notification.mark_all_read_for_user(request.user)
        
        return JsonResponse({
            'status': 'success', 
            'message': f'Marked {updated_count} notifications as read',
            'updated_count': updated_count,
            'unread_count': 0
        })
        
    except Exception as e:
        logger.error(f"Error marking all notifications as read: {str(e)}")
        return JsonResponse({
            'status': 'error', 
            'message': str(e)
        }, status=500)

@login_required
def notification_count(request):
    """API endpoint to get unread notification count for current user"""
    try:
        count = Notification.get_unread_count_for_user(request.user)
        return JsonResponse({
            'status': 'success',
            'unread_count': count,
            'total_count': request.user.notifications.count()
        })
    except Exception as e:
        logger.error(f"Error getting notification count: {str(e)}")
        return JsonResponse({
            'status': 'error', 
            'message': str(e)
        }, status=500)

@login_required
def notification_detail(request, pk):
    """Get notification details and mark as read when viewed"""
    try:
        notification = get_object_or_404(
            Notification, 
            pk=pk, 
            recipient=request.user
        )
        
        # Mark as read when viewing details
        if not notification.is_read:
            notification.mark_as_read()
        
        return JsonResponse({
            'status': 'success',
            'notification': {
                'id': notification.id,
                'title': notification.title,
                'message': notification.message,
                'type': notification.notification_type,
                'is_read': notification.is_read,
                'created_at': notification.created_at.isoformat(),
                'formatted_created_at': notification.formatted_created_at,
                'link': notification.get_absolute_url()
            }
        })
        
    except Notification.DoesNotExist:
        return JsonResponse({
            'status': 'error', 
            'message': 'Notification not found'
        }, status=404)
    except Exception as e:
        logger.error(f"Error getting notification {pk}: {str(e)}")
        return JsonResponse({
            'status': 'error', 
            'message': str(e)
        }, status=500)

@login_required
def recent_notifications(request):
    """Get recent notifications for dropdown menu"""
    try:
        notifications = Notification.get_recent_notifications(request.user, count=5)
        
        notifications_data = []
        for notification in notifications:
            notifications_data.append({
                'id': notification.id,
                'title': notification.title,
                'message': notification.message,
                'type': notification.notification_type,
                'is_read': notification.is_read,
                'created_at': notification.formatted_created_at,
                'link': notification.get_absolute_url()
            })
        
        return JsonResponse({
            'status': 'success',
            'notifications': notifications_data,
            'unread_count': Notification.get_unread_count_for_user(request.user)
        })
        
    except Exception as e:
        logger.error(f"Error getting recent notifications: {str(e)}")
        return JsonResponse({
            'status': 'error', 
            'message': str(e)
        }, status=500)

# Notification creation utilities
def create_notification(recipient, title, message, notification_type='GENERAL', link=None, related_object=None):
    """
    Create a new notification for a user with proper error handling
    """
    try:
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
            return notification
        else:
            logger.error(f"Failed to create notification for {recipient.username}")
            return None
            
    except Exception as e:
        logger.error(f"Error in create_notification: {str(e)}")
        return None

def create_assignment_notification(assignment, students=None):
    """
    Create notifications for students about a new assignment
    """
    try:
        from core.models import Student
        
        if students is None:
            # Get all students in the class level
            students = Student.objects.filter(class_level=assignment.class_assignment.class_level)
        
        notifications_created = 0
        for student in students:
            notification = create_notification(
                recipient=student.user,
                title="New Assignment Created",
                message=f"New assignment '{assignment.title}' has been created for {assignment.subject.name}. Due date: {assignment.due_date.strftime('%b %d, %Y at %I:%M %p')}",
                notification_type="ASSIGNMENT",
                link=reverse('assignment_detail', kwargs={'pk': assignment.pk}),
                related_object=assignment
            )
            if notification:
                notifications_created += 1
        
        logger.info(f"Assignment notifications created: {notifications_created} for '{assignment.title}'")
        return notifications_created
        
    except Exception as e:
        logger.error(f"Error creating assignment notifications: {str(e)}")
        return 0

def create_grading_notification(student_assignment):
    """
    Create notification for student when assignment is graded
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
            logger.info(f"Grading notification sent to {student.user.username} for '{assignment.title}'")
            return True
        else:
            logger.error(f"Failed to send grading notification to {student.user.username}")
            return False
            
    except Exception as e:
        logger.error(f"Error creating grading notification: {str(e)}")
        return False

def get_unread_count(user):
    """
    Get count of unread notifications for a user
    """
    return Notification.get_unread_count_for_user(user)

def send_bulk_notifications(recipients, title, message, notification_type='GENERAL', link=None):
    """
    Send notifications to multiple recipients
    """
    try:
        notifications_created = 0
        for recipient in recipients:
            notification = create_notification(
                recipient=recipient,
                title=title,
                message=message,
                notification_type=notification_type,
                link=link
            )
            if notification:
                notifications_created += 1
        
        logger.info(f"Bulk notifications sent: {notifications_created} recipients")
        return notifications_created
        
    except Exception as e:
        logger.error(f"Error sending bulk notifications: {str(e)}")
        return 0
