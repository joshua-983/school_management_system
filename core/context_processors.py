from .models import Notification
from .utils import is_admin, is_teacher
def notification_count(request):
    if request.user.is_authenticated:
        return {
            'unread_notifications_count': Notification.objects.filter(
                user=request.user, 
                is_read=False
            ).count()
        }
    return {}


# In your context_processors.py (create if it doesn't exist)
def user_permissions(request):
    return {
        'is_admin': is_admin(request.user) if request.user.is_authenticated else False,
        'is_teacher': is_teacher(request.user) if request.user.is_authenticated else False,
        'is_student': hasattr(request.user, 'student') if request.user.is_authenticated else False,
        'is_parent': hasattr(request.user, 'parentguardian') if request.user.is_authenticated else False,
    }