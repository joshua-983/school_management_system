# core/context_processors.py
from .models import Notification
from .utils import is_admin, is_teacher
from .models import ParentGuardian
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
    
    # Use the same logic as parent_status
    is_parent = ParentGuardian.objects.filter(email=request.user.email).exists()
    
    return {
        'is_admin': is_admin(request.user),
        'is_teacher': is_teacher(request.user),
        'is_student': hasattr(request.user, 'student'),
        'is_parent': is_parent,  # Changed this line
        'dashboard_url': (
            'admin_dashboard' if request.user.is_superuser else
            'teacher_dashboard' if hasattr(request.user, 'teacher') else
            'student_dashboard' if hasattr(request.user, 'student') else
            'parent_dashboard' if is_parent else  # Changed this line too
            'home'
        )
    }
def parent_status(request):
    is_parent = False
    parent_obj = None
    
    if request.user.is_authenticated:
        # Use the same logic as user_permissions
        parent_obj = ParentGuardian.objects.filter(email=request.user.email).first()
        is_parent = parent_obj is not None
    
    return {
        'is_parent': is_parent,
        'user_parentguardian': parent_obj
    }




