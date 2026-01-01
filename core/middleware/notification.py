"""
Notification Middleware
"""
class NotificationMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        # Add notifications to request context
        if request.user.is_authenticated:
            try:
                # Try to import Notification model
                from core.models import Notification
                request.unread_notifications = Notification.objects.filter(
                    user=request.user, 
                    read=False
                )[:10]
            except Exception:
                # If there's any error, set empty list
                request.unread_notifications = []
        else:
            request.unread_notifications = []
        return self.get_response(request)
