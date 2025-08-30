# core/context_processors.py
from .models import Notification
from .utils import is_admin, is_teacher

def notification_count(request):
    if request.user.is_authenticated:
        return {
            'unread_notifications_count': Notification.objects.filter(
                recipient=request.user,  # Changed from 'user' to 'recipient'
                is_read=False
            ).count(),
            'recent_notifications': Notification.objects.filter(
                recipient=request.user
            ).order_by('-created_at')[:5] if request.user.is_authenticated else []
        }
    return {'unread_notifications_count': 0, 'recent_notifications': []}

def user_permissions(request):
    if not request.user.is_authenticated:
        return {
            'is_admin': False,
            'is_teacher': False,
            'is_student': False,
            'is_parent': False,
            'dashboard_url': 'home'
        }
    
    return {
        'is_admin': is_admin(request.user),
        'is_teacher': is_teacher(request.user),
        'is_student': hasattr(request.user, 'student'),
        'is_parent': hasattr(request.user, 'parentguardian'),
        'dashboard_url': (
            'admin_dashboard' if request.user.is_superuser else
            'teacher_dashboard' if hasattr(request.user, 'teacher') else
            'student_dashboard' if hasattr(request.user, 'student') else
            'parent_dashboard' if hasattr(request.user, 'parentguardian') else
            'home'
        )
    }