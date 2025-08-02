# core/utils.py
from django.apps import apps
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def send_notification(recipient, notification_type, title, message, related_object=None):
    """
    Create and send a notification
    Args:
        recipient: User object
        notification_type: One of 'GRADE', 'FEE', 'ASSIGNMENT', 'GENERAL'
        title: Notification title
        message: Notification message
        related_object: Optional related object for linking
    """
    # Create notification
    notification = Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        related_object_id=related_object.id if related_object else None,
        related_content_type=related_object.__class__.__name__ if related_object else ''
    )
    
    # Send via WebSocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'notifications_{recipient.id}',
        {
            'type': 'send_notification',
            'notification_type': notification_type,
            'title': title,
            'message': message,
            'notification_id': notification.id
        }
    )
    
    return notification

def is_admin(user):
    return user.is_authenticated and (user.is_superuser or hasattr(user, 'admin'))

def is_teacher(user):
    return user.is_authenticated and hasattr(user, 'teacher')