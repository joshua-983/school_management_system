import json
from channels.generic.websocket import AsyncWebsocketConsumer

class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        if self.scope["user"].is_anonymous:
            await self.close()
        else:
            self.user = self.scope["user"]
            self.notification_group = f'notifications_{self.user.id}'
            self.announcement_group = f'announcements_{self.user.id}'
            
            # Join both notification and announcement groups
            await self.channel_layer.group_add(
                self.notification_group,
                self.channel_name
            )
            await self.channel_layer.group_add(
                self.announcement_group,
                self.channel_name
            )
            
            await self.accept()

    async def disconnect(self, close_code):
        # Leave both groups
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

    async def receive(self, text_data):
        """Handle incoming WebSocket messages from client"""
        try:
            data = json.loads(text_data)
            if data.get('type') == 'mark_as_read':
                await self.handle_mark_as_read(data)
        except json.JSONDecodeError:
            pass

    async def handle_mark_as_read(self, data):
        """Handle mark as read requests from client"""
        pass

    # ===== NOTIFICATION HANDLERS =====
    async def notification_update(self, event):
        """Handle notification updates"""
        await self.send(text_data=json.dumps({
            'type': 'notification_update',
            'action': event.get('action'),
            'unread_count': event.get('unread_count', 0)
        }))

    # ===== ANNOUNCEMENT HANDLERS =====
    async def new_announcement(self, event):
        """Handle new announcement broadcasts"""
        await self.send(text_data=json.dumps({
            'type': 'announcement',
            'announcement': event['announcement']
        }))

    async def announcement_update(self, event):
        """Handle general announcement updates"""
        await self.send(text_data=json.dumps({
            'type': 'announcement_update',
            'action': event.get('action'),
            'data': event.get('data', {})
        }))

    async def announcement_expired(self, event):
        """Handle announcement expiry notifications"""
        await self.send(text_data=json.dumps({
            'type': 'announcement_expired',
            'announcement_id': event.get('announcement_id')
        }))