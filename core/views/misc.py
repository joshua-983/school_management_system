from django.views.decorators.http import require_POST
from django.views.generic import ListView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

from .base_views import *
from ..models import Notification

class NotificationListView(LoginRequiredMixin, ListView):
    model = Notification
    template_name = 'core/messaging/notification_list.html'
    context_object_name = 'notifications'
    paginate_by = 20
    
    def get_queryset(self):
        return Notification.objects.filter(
            recipient=self.request.user
        ).order_by('-created_at')
    
    # Continue with notification views...

@login_required
@require_POST
def mark_notification_read(request, pk):
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

# Other miscellaneous views...

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