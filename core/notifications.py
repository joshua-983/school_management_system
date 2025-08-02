from django.contrib.auth.models import User
from .models import Notification

def create_notification(recipient, title, message, notification_type='info', link=None):
    """
    Create a new notification for a user
    """
    return Notification.objects.create(
        recipient=recipient,  # Changed from user to recipient for consistency
        title=title,
        message=message,
        notification_type=notification_type,
        link=link
    )

def get_unread_count(user):
    """
    Get count of unread notifications for a user
    """
    return Notification.objects.filter(recipient=user, is_read=False).count()