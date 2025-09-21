# core/context_processors.py
from .models import Notification, ParentGuardian
from .utils import is_admin, is_teacher

def global_context(request):
    """
    Combined context processor for all global template variables
    """
    context = {
        'is_admin': False,
        'is_teacher': False,
        'is_student': False,
        'is_parent': False,
        'user_parentguardian': None,
        'dashboard_url': 'home',
        'unread_notifications_count': 0,
        'recent_notifications': []
    }
    
    if not request.user.is_authenticated:
        return context
    
    # Get parent status (single query)
    parent_obj = ParentGuardian.objects.filter(email=request.user.email).first()
    is_parent_user = parent_obj is not None
    
    # Set user roles
    context.update({
        'is_admin': is_admin(request.user),
        'is_teacher': is_teacher(request.user),
        'is_student': hasattr(request.user, 'student'),
        'is_parent': is_parent_user,
        'user_parentguardian': parent_obj,
        'dashboard_url': (
            'admin_dashboard' if request.user.is_superuser else
            'teacher_dashboard' if hasattr(request.user, 'teacher') else
            'student_dashboard' if hasattr(request.user, 'student') else
            'parent_dashboard' if is_parent_user else
            'home'
        )
    })
    
    # Get notifications (only if user is authenticated)
    context['unread_notifications_count'] = Notification.objects.filter(
        recipient=request.user,
        is_read=False
    ).count()
    
    context['recent_notifications'] = Notification.objects.filter(
        recipient=request.user
    ).order_by('-created_at')[:5]
    
    return context