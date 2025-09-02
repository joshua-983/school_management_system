# core/views/notifications_views.py
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from core.models import Notification
from core.notifications import get_unread_count

# Notification system
class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'core/messaging/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user
        ).order_by('-created_at')
    
    def get(self, request, *args, **kwargs):
        # Mark all unread notifications as read when page is loaded
        unread_notifications = request.user.notifications.filter(is_read=False)
        if unread_notifications.exists():
            unread_notifications.update(is_read=True)
            self.send_ws_update(request.user)
        return super().get(request, *args, **kwargs)
    
    def post(self, request, *args, **kwargs):
        """Handle mark all as read POST request"""
        unread_notifications = request.user.notifications.filter(is_read=False)
        count = unread_notifications.count()
        unread_notifications.update(is_read=True)
        self.send_ws_update(request.user)
        return JsonResponse({'status': 'success', 'count': count})
    
    def send_ws_update(self, user):
        """Send WebSocket update after marking all as read"""
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'notifications_{user.id}',
            {
                'type': 'notification_update',
                'action': 'mark_all_read',
                'unread_count': 0
            }
        )

@login_required
@require_POST
def mark_notification_read(request, pk):
    """API endpoint to mark single notification as read"""
    try:
        notification = Notification.objects.get(
            pk=pk,
            recipient=request.user
        )
        notification.is_read = True
        notification.save()
        
        # Send WS update
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'notifications_{request.user.id}',
            {
                'type': 'notification_update',
                'action': 'single_read',
                'unread_count': get_unread_count(request.user)
            }
        )
        return JsonResponse({'status': 'success'})
    except Notification.DoesNotExist:
        return JsonResponse({'status': 'error'}, status=404)