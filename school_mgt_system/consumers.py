import json
import logging
from channels.generic.websocket import AsyncWebsocketConsumer
from asgiref.sync import sync_to_async
from django.utils import timezone
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()

class NotificationConsumer(AsyncWebsocketConsumer):
    """
    Handles real-time notifications and announcements
    """
    async def connect(self):
        """Handle WebSocket connection for notifications"""
        try:
            if self.scope["user"].is_anonymous:
                await self.close(code=4001)
                return

            self.user = self.scope["user"]
            self.notification_group = f'notifications_{self.user.id}'
            self.announcement_group = f'announcements_{self.user.id}'
            self.user_group = f'user_{self.user.id}'
            
            # Join notification and announcement groups
            await self.channel_layer.group_add(
                self.notification_group,
                self.channel_name
            )
            await self.channel_layer.group_add(
                self.announcement_group,
                self.channel_name
            )
            await self.channel_layer.group_add(
                self.user_group,
                self.channel_name
            )
            
            await self.accept()
            
            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'Notifications connected',
                'timestamp': timezone.now().isoformat(),
                'user_id': self.user.id
            }))
            
            logger.info(f"Notification WebSocket connected for user {self.user.username}")
            
        except Exception as e:
            logger.error(f"Notification WebSocket connection error: {e}")
            await self.close(code=4000)

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            if hasattr(self, 'notification_group'):
                await self.channel_layer.group_discard(
                    self.notification_group,
                    self.channel_name
                )
            if hasattr(self, 'announcement_group'):
                await self.channel_layer.group_discard(
                    self.announcement_group,
                    self.channel_name
                )
            if hasattr(self, 'user_group'):
                await self.channel_layer.group_discard(
                    self.user_group,
                    self.channel_name
                )
                
            logger.info(f"Notification WebSocket disconnected for user {getattr(self, 'user', 'Unknown')}")
        except Exception as e:
            logger.error(f"Notification WebSocket disconnection error: {e}")

    async def receive(self, text_data):
        """Handle incoming WebSocket messages from client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'heartbeat':
                # Client heartbeat to keep connection alive
                await self.send(text_data=json.dumps({
                    'type': 'heartbeat_response',
                    'timestamp': timezone.now().isoformat()
                }))
                
            elif message_type == 'mark_as_read':
                await self.handle_mark_as_read(data)
                
            elif message_type == 'get_unread_count':
                await self.handle_get_unread_count()
                
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON received: {text_data}")
        except Exception as e:
            logger.error(f"Error processing message: {e}")

    async def handle_mark_as_read(self, data):
        """Handle mark as read requests from client"""
        # Implement your mark as read logic here
        notification_id = data.get('notification_id')
        
        # Broadcast update to user's notification group
        await self.channel_layer.group_send(
            self.notification_group,
            {
                'type': 'notification_update',
                'action': 'marked_read',
                'notification_id': notification_id,
                'unread_count': data.get('unread_count', 0),
                'timestamp': timezone.now().isoformat()
            }
        )

    async def handle_get_unread_count(self):
        """Handle request for unread count"""
        # Implement your unread count logic here
        unread_count = 0  # Replace with actual count
        
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': unread_count,
            'timestamp': timezone.now().isoformat()
        }))

    # ===== NOTIFICATION HANDLERS =====

    async def notification_created(self, event):
        """Handle new notification creation"""
        await self.send(text_data=json.dumps({
            'type': 'notification_created',
            'notification': event.get('notification', {}),
            'unread_count': event.get('unread_count', 0),
            'timestamp': event.get('timestamp')
        }))

    async def notification_update(self, event):
        """Handle notification updates"""
        await self.send(text_data=json.dumps({
            'type': 'notification_update',
            'action': event.get('action'),
            'notification_id': event.get('notification_id'),
            'unread_count': event.get('unread_count', 0),
            'timestamp': event.get('timestamp')
        }))

    async def notification_bulk_update(self, event):
        """Handle bulk notification updates"""
        await self.send(text_data=json.dumps({
            'type': 'notification_bulk_update',
            'action': event.get('action'),
            'affected_count': event.get('affected_count', 0),
            'unread_count': event.get('unread_count', 0),
            'timestamp': event.get('timestamp')
        }))

    # ===== ANNOUNCEMENT HANDLERS =====

    async def new_announcement(self, event):
        """Handle new announcement broadcasts"""
        await self.send(text_data=json.dumps({
            'type': 'announcement_created',
            'announcement': event['announcement'],
            'priority': event.get('priority', 'normal'),
            'timestamp': event.get('timestamp')
        }))

    async def announcement_update(self, event):
        """Handle general announcement updates"""
        await self.send(text_data=json.dumps({
            'type': 'announcement_update',
            'action': event.get('action'),
            'announcement_id': event.get('announcement_id'),
            'data': event.get('data', {}),
            'timestamp': event.get('timestamp')
        }))

    async def announcement_expired(self, event):
        """Handle announcement expiry notifications"""
        await self.send(text_data=json.dumps({
            'type': 'announcement_expired',
            'announcement_id': event.get('announcement_id'),
            'title': event.get('title', ''),
            'timestamp': event.get('timestamp')
        }))

    # ===== USER-SPECIFIC MESSAGES =====

    async def user_message(self, event):
        """Handle direct messages to user"""
        await self.send(text_data=json.dumps({
            'type': 'user_message',
            'message': event.get('message', {}),
            'category': event.get('category', 'info'),
            'timestamp': event.get('timestamp')
        }))


class SecurityConsumer(AsyncWebsocketConsumer):
    """
    Handles real-time security monitoring and alerts
    """
    async def connect(self):
        """Handle WebSocket connection for security monitoring"""
        try:
            if self.scope["user"].is_anonymous:
                await self.close(code=4001)
                return

            self.user = self.scope["user"]
            self.security_group = f'security_{self.user.id}'
            self.user_group = f'user_{self.user.id}'
            self.global_security_group = 'security_global'
            
            # Join user-specific security groups
            await self.channel_layer.group_add(
                self.security_group,
                self.channel_name
            )
            await self.channel_layer.group_add(
                self.user_group,
                self.channel_name
            )
            
            # If user is staff/admin, join global security group
            if self.user.is_staff or self.user.is_superuser:
                await self.channel_layer.group_add(
                    self.global_security_group,
                    self.channel_name
                )
            
            await self.accept()
            
            # Send connection confirmation
            await self.send(text_data=json.dumps({
                'type': 'security_connection',
                'message': 'Security monitoring active',
                'user_type': 'admin' if (self.user.is_staff or self.user.is_superuser) else 'user',
                'timestamp': timezone.now().isoformat()
            }))
            
            logger.info(f"Security WebSocket connected for user {self.user.username}")
            
        except Exception as e:
            logger.error(f"Security WebSocket connection error: {e}")
            await self.close(code=4000)

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            if hasattr(self, 'security_group'):
                await self.channel_layer.group_discard(
                    self.security_group,
                    self.channel_name
                )
            if hasattr(self, 'user_group'):
                await self.channel_layer.group_discard(
                    self.user_group,
                    self.channel_name
                )
            if hasattr(self, 'global_security_group'):
                await self.channel_layer.group_discard(
                    self.global_security_group,
                    self.channel_name
                )
                
            logger.info(f"Security WebSocket disconnected for user {getattr(self, 'user', 'Unknown')}")
        except Exception as e:
            logger.error(f"Security WebSocket disconnection error: {e}")

    async def receive(self, text_data):
        """Handle incoming security messages from client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'heartbeat':
                # Client heartbeat to keep connection alive
                await self.send(text_data=json.dumps({
                    'type': 'heartbeat_response',
                    'timestamp': timezone.now().isoformat()
                }))
                
            elif message_type == 'report_activity':
                await self.handle_activity_report(data)
                
            elif message_type == 'acknowledge_alert':
                await self.handle_acknowledge_alert(data)
                
        except json.JSONDecodeError as e:
            logger.warning(f"Invalid JSON received in security WebSocket: {text_data}")
        except Exception as e:
            logger.error(f"Error processing security message: {e}")

    async def handle_activity_report(self, data):
        """Handle activity reports from client"""
        activity_data = {
            'user_id': self.user.id,
            'username': self.user.username,
            'activity_type': data.get('activity_type'),
            'page': data.get('page'),
            'action': data.get('action'),
            'timestamp': timezone.now().isoformat(),
            'user_agent': self.scope.get('headers', {}).get('user-agent', '')
        }
        
        # Log activity (you can save to database here)
        logger.info(f"User activity: {activity_data}")
        
        # Broadcast to admin monitoring if user is staff/admin
        if self.user.is_staff or self.user.is_superuser:
            await self.channel_layer.group_send(
                self.global_security_group,
                {
                    'type': 'user_activity',
                    'activity': activity_data
                }
            )

    async def handle_acknowledge_alert(self, data):
        """Handle alert acknowledgements from client"""
        alert_id = data.get('alert_id')
        # Implement your alert acknowledgement logic here
        logger.info(f"User {self.user.username} acknowledged alert {alert_id}")

    # ===== SECURITY EVENT HANDLERS =====

    async def login_alert(self, event):
        """Notify user of new login"""
        await self.send(text_data=json.dumps({
            'type': 'login_alert',
            'alert_id': event.get('alert_id'),
            'ip_address': event.get('ip_address'),
            'location': event.get('location', 'Unknown'),
            'device': event.get('device', 'Unknown'),
            'browser': event.get('browser', 'Unknown'),
            'timestamp': event.get('timestamp'),
            'is_suspicious': event.get('is_suspicious', False),
            'recommendation': event.get('recommendation', '')
        }))

    async def security_alert(self, event):
        """Send security alerts to user"""
        await self.send(text_data=json.dumps({
            'type': 'security_alert',
            'alert_id': event.get('alert_id'),
            'level': event.get('level', 'info'),  # info, warning, danger, critical
            'title': event.get('title', 'Security Notice'),
            'message': event.get('message', ''),
            'action_required': event.get('action_required', False),
            'actions': event.get('actions', []),
            'timestamp': event.get('timestamp'),
            'expires_at': event.get('expires_at')
        }))

    async def session_alert(self, event):
        """Session-related notifications"""
        await self.send(text_data=json.dumps({
            'type': 'session_alert',
            'alert_id': event.get('alert_id'),
            'action': event.get('action'),  # expired, terminated, renewed, multiple_sessions
            'reason': event.get('reason', ''),
            'sessions_affected': event.get('sessions_affected', 1),
            'timestamp': event.get('timestamp')
        }))

    async def password_alert(self, event):
        """Password-related security alerts"""
        await self.send(text_data=json.dumps({
            'type': 'password_alert',
            'alert_id': event.get('alert_id'),
            'action': event.get('action'),  # changed, reset_attempt, weak_password
            'is_successful': event.get('is_successful', True),
            'timestamp': event.get('timestamp'),
            'recommendation': event.get('recommendation', '')
        }))

    async def user_activity(self, event):
        """Receive user activity reports (for admin monitoring)"""
        if self.user.is_staff or self.user.is_superuser:
            await self.send(text_data=json.dumps({
                'type': 'user_activity_report',
                'activity': event.get('activity'),
                'timestamp': event.get('timestamp')
            }))

    async def system_alert(self, event):
        """System-wide security alerts (for admins)"""
        if self.user.is_staff or self.user.is_superuser:
            await self.send(text_data=json.dumps({
                'type': 'system_alert',
                'alert_id': event.get('alert_id'),
                'level': event.get('level', 'warning'),
                'component': event.get('component', 'System'),
                'message': event.get('message', ''),
                'urgency': event.get('urgency', 'medium'),  # low, medium, high, critical
                'affected_users': event.get('affected_users', 0),
                'timestamp': event.get('timestamp'),
                'resolution_eta': event.get('resolution_eta')
            }))

    async def audit_event(self, event):
        """Audit trail events (for admins)"""
        if self.user.is_staff or self.user.is_superuser:
            await self.send(text_data=json.dumps({
                'type': 'audit_event',
                'event_type': event.get('event_type'),
                'user_id': event.get('user_id'),
                'username': event.get('username'),
                'action': event.get('action'),
                'resource': event.get('resource'),
                'details': event.get('details', {}),
                'ip_address': event.get('ip_address'),
                'timestamp': event.get('timestamp')
            }))