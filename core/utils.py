# core/utils.py
from django.apps import apps
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth.models import Group
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

def send_email(subject, message, recipient, html_message=None, from_email=None):
    """
    Send an email using Django's email backend
    
    Args:
        subject: Email subject
        message: Plain text message
        recipient: Email recipient or list of recipients
        html_message: Optional HTML content
        from_email: Optional sender email (uses DEFAULT_FROM_EMAIL if not provided)
    """
    try:
        if from_email is None:
            from_email = settings.DEFAULT_FROM_EMAIL
        
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[recipient] if isinstance(recipient, str) else recipient,
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        # You might want to log this error in production
        return False

def send_email_template(subject, template_name, context, recipient, from_email=None):
    """
    Send an email using a Django template
    
    Args:
        subject: Email subject
        template_name: Path to the template (e.g., 'emails/payment_reminder.html')
        context: Context data for the template
        recipient: Email recipient
        from_email: Optional sender email
    """
    try:
        # Render HTML content from template
        html_message = render_to_string(template_name, context)
        # Create plain text version by stripping HTML tags
        plain_message = strip_tags(html_message)
        
        return send_email(
            subject=subject,
            message=plain_message,
            recipient=recipient,
            html_message=html_message,
            from_email=from_email
        )
    except Exception as e:
        print(f"Error sending template email: {e}")
        return False

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

def is_student(user):
    return user.is_authenticated and hasattr(user, 'student_profile')

def is_parent(user):
    return user.is_authenticated and hasattr(user, 'parentguardian')