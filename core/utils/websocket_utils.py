# Add to consumers.py or create utils/websocket_utils.py
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.utils import timezone

# ===== NOTIFICATION UTILITIES =====

def send_notification(user, notification_data):
    """Send notification to specific user"""
    channel_layer = get_channel_layer()
    
    async_to_sync(channel_layer.group_send)(
        f'notifications_{user.id}',
        {
            'type': 'notification_created',
            'notification': notification_data,
            'timestamp': timezone.now().isoformat()
        }
    )

def broadcast_announcement(announcement_data, target_group=None):
    """Broadcast announcement to users"""
    channel_layer = get_channel_layer()
    group_name = target_group or 'announcements_all'
    
    async_to_sync(channel_layer.group_send)(
        group_name,
        {
            'type': 'new_announcement',
            'announcement': announcement_data,
            'timestamp': timezone.now().isoformat()
        }
    )

def update_unread_count(user, count):
    """Update unread notification count for user"""
    channel_layer = get_channel_layer()
    
    async_to_sync(channel_layer.group_send)(
        f'notifications_{user.id}',
        {
            'type': 'notification_update',
            'action': 'count_updated',
            'unread_count': count,
            'timestamp': timezone.now().isoformat()
        }
    )

# ===== SECURITY UTILITIES =====

def send_login_alert(user, ip_address, user_agent, is_suspicious=False, location="Unknown"):
    """Send login alert to user"""
    channel_layer = get_channel_layer()
    
    async_to_sync(channel_layer.group_send)(
        f'security_{user.id}',
        {
            'type': 'login_alert',
            'ip_address': ip_address,
            'device': user_agent,
            'location': location,
            'is_suspicious': is_suspicious,
            'timestamp': timezone.now().isoformat(),
            'recommendation': 'Change your password if this was not you.' if is_suspicious else ''
        }
    )

def send_security_alert(user, level, title, message, action_required=False, actions=None):
    """Send security alert to specific user"""
    channel_layer = get_channel_layer()
    
    async_to_sync(channel_layer.group_send)(
        f'security_{user.id}',
        {
            'type': 'security_alert',
            'level': level,
            'title': title,
            'message': message,
            'action_required': action_required,
            'actions': actions or [],
            'timestamp': timezone.now().isoformat()
        }
    )

def broadcast_system_alert(level, component, message, urgency='medium', affected_users=0):
    """Broadcast system alert to all admin users"""
    channel_layer = get_channel_layer()
    
    async_to_sync(channel_layer.group_send)(
        'security_global',
        {
            'type': 'system_alert',
            'level': level,
            'component': component,
            'message': message,
            'urgency': urgency,
            'affected_users': affected_users,
            'timestamp': timezone.now().isoformat()
        }
    )

def send_session_alert(user, action, reason="", sessions_affected=1):
    """Send session-related alert to user"""
    channel_layer = get_channel_layer()
    
    async_to_sync(channel_layer.group_send)(
        f'security_{user.id}',
        {
            'type': 'session_alert',
            'action': action,
            'reason': reason,
            'sessions_affected': sessions_affected,
            'timestamp': timezone.now().isoformat()
        }
    )