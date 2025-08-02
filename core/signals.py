from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from core.models import AuditLog
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import logging
from django.utils import timezone

logger = logging.getLogger(__name__)

def log_audit(action, instance, user, request=None):
    """Enhanced audit logging with WebSocket notifications"""
    details = {
        'fields': {field.name: getattr(instance, field.name) for field in instance._meta.fields},
        'repr': str(instance),
    }
    
    # Create audit log
    audit_log = AuditLog(
        user=user,
        action=action,
        model=f"{instance._meta.app_label}.{instance._meta.model_name}",
        object_id=str(instance.pk),
        details=details,
    )
    
    if request:
        audit_log.ip_address = request.META.get('REMOTE_ADDR')
        audit_log.user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
    
    audit_log.save()
    
    # Send WebSocket notification for specific models
    send_model_notification(action, instance, user)

def send_model_notification(action, instance, user):
    """Send WebSocket notifications based on model changes"""
    try:
        model_name = instance._meta.model_name.lower()
        channel_layer = get_channel_layer()
        
        # Grade-specific notifications
        if model_name == 'grade' and action in ['CREATE', 'UPDATE']:
            recipient_id = instance.student.user.id
            notification_data = {
                'type': 'send_notification',
                'notification_type': 'GRADE',
                'title': 'Grade Updated' if action == 'UPDATE' else 'New Grade',
                'message': f'Your {instance.class_assignment.subject} grade is now {instance.grade}',
                'related_object_id': instance.class_assignment.id,
                'timestamp': str(timezone.now()),
                'action': action.lower()
            }
            
            async_to_sync(channel_layer.group_send)(
                f'notifications_{recipient_id}',
                notification_data
            )
            
            # Optional: Notify teacher/admin about the change
            if user != instance.class_assignment.teacher.user:
                notify_third_party(
                    user=user,
                    target_user=instance.class_assignment.teacher.user,
                    action=action,
                    instance=instance
                )
        
        # Add other model notifications here
        elif model_name == 'assignment' and action == 'CREATE':
            # Notification logic for new assignments
            pass
            
    except Exception as e:
        logger.error(f"Notification error for {instance}: {str(e)}")

def notify_third_party(user, target_user, action, instance):
    """Notify other interested parties about changes"""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'notifications_{target_user.id}',
            {
                'type': 'send_notification',
                'notification_type': 'SYSTEM',
                'title': f'Grade {action.capitalize()}',
                'message': f'{user} modified grade for {instance.student}',
                'related_object_id': instance.id,
                'timestamp': str(timezone.now())
            }
        )
    except Exception as e:
        logger.error(f"Third-party notification failed: {str(e)}")

@receiver(post_save)
def post_save_audit(sender, instance, created, **kwargs):
    if sender._meta.app_label in ['auth', 'admin', 'sessions', 'contenttypes']:
        return
    
    request = getattr(instance, '_request', None)
    user = getattr(instance, '_request_user', None) or (request.user if request and hasattr(request, 'user') else None)
    
    if user and user.is_authenticated:
        action = 'CREATE' if created else 'UPDATE'
        log_audit(action, instance, user, request)

@receiver(post_delete)
def post_delete_audit(sender, instance, **kwargs):
    if sender._meta.app_label in ['auth', 'admin', 'sessions', 'contenttypes']:
        return
    
    request = getattr(instance, '_request', None)
    user = getattr(instance, '_request_user', None) or (request.user if request and hasattr(request, 'user') else None)
    
    if user and user.is_authenticated:
        log_audit('DELETE', instance, user, request)