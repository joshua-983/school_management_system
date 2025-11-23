# school_mgt_system/consumers.py
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
            # Check if user is authenticated
            if self.scope["user"].is_anonymous:
                logger.warning("Anonymous user attempted WebSocket connection")
                await self.close(code=4001)
                return

            self.user = self.scope["user"]
            self.user_id = self.user.id
            self.notification_group = f'notifications_{self.user_id}'
            
            # Join notification group
            await self.channel_layer.group_add(
                self.notification_group,
                self.channel_name
            )
            
            await self.accept()
            
            # Send initial unread count
            unread_count = await self.get_unread_count()
            await self.send(text_data=json.dumps({
                'type': 'connection_established',
                'message': 'Notifications connected successfully',
                'unread_count': unread_count,
                'timestamp': timezone.now().isoformat(),
                'user_id': self.user_id
            }))
            
            logger.info(f"✅ Notification WebSocket connected for user {self.user.username} (ID: {self.user_id})")
            
        except Exception as e:
            logger.error(f"❌ Notification WebSocket connection error: {str(e)}")
            await self.close(code=4000)

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            if hasattr(self, 'notification_group'):
                await self.channel_layer.group_discard(
                    self.notification_group,
                    self.channel_name
                )
                
            logger.info(f"🔌 Notification WebSocket disconnected for user {getattr(self, 'user', 'Unknown')}")
        except Exception as e:
            logger.error(f"❌ Notification WebSocket disconnection error: {str(e)}")

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
                
            elif message_type == 'get_unread_count':
                await self.handle_get_unread_count()
                
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Invalid JSON received: {text_data}")
        except Exception as e:
            logger.error(f"❌ Error processing WebSocket message: {str(e)}")

    async def handle_get_unread_count(self):
        """Handle request for unread count"""
        unread_count = await self.get_unread_count()
        await self.send(text_data=json.dumps({
            'type': 'unread_count',
            'count': unread_count,
            'timestamp': timezone.now().isoformat()
        }))

    @sync_to_async
    def get_unread_count(self):
        """Get unread notification count for the user"""
        try:
            from core.models import Notification
            return Notification.get_unread_count_for_user(self.user)
        except Exception as e:
            logger.error(f"❌ Error getting unread count: {str(e)}")
            return 0

    # ===== NOTIFICATION HANDLERS =====

    async def notification_update(self, event):
        """Handle notification updates from the system"""
        try:
            await self.send(text_data=json.dumps({
                'type': 'notification_update',
                'action': event.get('action'),
                'notification_id': event.get('notification_id'),
                'unread_count': event.get('unread_count', 0),
                'timestamp': event.get('timestamp', timezone.now().isoformat())
            }))
        except Exception as e:
            logger.error(f"❌ Error sending notification update: {str(e)}")

    async def new_notification(self, event):
        """Handle new notification creation from the system"""
        try:
            await self.send(text_data=json.dumps({
                'type': 'new_notification',
                'notification': event.get('notification', {}),
                'unread_count': event.get('unread_count', 0),
                'timestamp': event.get('timestamp', timezone.now().isoformat())
            }))
        except Exception as e:
            logger.error(f"❌ Error sending new notification: {str(e)}")


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
            
            # Join security group
            await self.channel_layer.group_add(
                self.security_group,
                self.channel_name
            )
            
            # If user is staff/admin, join global security group
            if self.user.is_staff or self.user.is_superuser:
                await self.channel_layer.group_add(
                    'security_global',
                    self.channel_name
                )
            
            await self.accept()
            
            await self.send(text_data=json.dumps({
                'type': 'security_connection',
                'message': 'Security monitoring active',
                'user_type': 'admin' if (self.user.is_staff or self.user.is_superuser) else 'user',
                'timestamp': timezone.now().isoformat()
            }))
            
            logger.info(f"✅ Security WebSocket connected for user {self.user.username}")
            
        except Exception as e:
            logger.error(f"❌ Security WebSocket connection error: {str(e)}")
            await self.close(code=4000)

    async def disconnect(self, close_code):
        """Handle WebSocket disconnection"""
        try:
            if hasattr(self, 'security_group'):
                await self.channel_layer.group_discard(
                    self.security_group,
                    self.channel_name
                )
            if hasattr(self, 'user') and (self.user.is_staff or self.user.is_superuser):
                await self.channel_layer.group_discard(
                    'security_global',
                    self.channel_name
                )
                
            logger.info(f"🔌 Security WebSocket disconnected for user {getattr(self, 'user', 'Unknown')}")
        except Exception as e:
            logger.error(f"❌ Security WebSocket disconnection error: {str(e)}")

    async def receive(self, text_data):
        """Handle incoming security messages from client"""
        try:
            data = json.loads(text_data)
            message_type = data.get('type')
            
            if message_type == 'heartbeat':
                await self.send(text_data=json.dumps({
                    'type': 'heartbeat_response',
                    'timestamp': timezone.now().isoformat()
                }))
                
        except json.JSONDecodeError as e:
            logger.warning(f"⚠️ Invalid JSON received in security WebSocket: {text_data}")
        except Exception as e:
            logger.error(f"❌ Error processing security message: {str(e)}")

    async def security_alert(self, event):
        """Send security alerts to user"""
        try:
            await self.send(text_data=json.dumps({
                'type': 'security_alert',
                'alert_id': event.get('alert_id'),
                'level': event.get('level', 'info'),
                'title': event.get('title', 'Security Notice'),
                'message': event.get('message', ''),
                'action_required': event.get('action_required', False),
                'timestamp': event.get('timestamp', timezone.now().isoformat())
            }))
        except Exception as e:
            logger.error(f"❌ Error sending security alert: {str(e)}")