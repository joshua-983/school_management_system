# core/context_processors.py
from django.db.models import Prefetch
from .models import Notification, ParentGuardian, Student, Teacher
from .utils import is_admin, is_teacher

def global_context(request):
    """
    Combined context processor for all global template variables
    Optimized with select_related and prefetch_related for better performance
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
    
    user = request.user
    
    # Single query to get all related profiles with select_related
    try:
        # Get parent status and related profiles in optimized way
        parent_obj = ParentGuardian.objects.filter(email=user.email).select_related('user').first()
        has_student_profile = hasattr(user, 'student')
        has_teacher_profile = hasattr(user, 'teacher')
        is_parent_user = parent_obj is not None
        
        # Set user roles
        context.update({
            'is_admin': is_admin(user),
            'is_teacher': is_teacher(user),
            'is_student': has_student_profile,
            'is_parent': is_parent_user,
            'user_parentguardian': parent_obj,
            'dashboard_url': get_dashboard_url(user, is_parent_user, parent_obj)
        })
        
        # Get notifications with optimized queries
        notification_data = get_notification_data(user)
        context.update(notification_data)
        
    except Exception as e:
        # Log error but don't break the site
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in global context processor: {str(e)}")
    
    return context

def notification_context(request):
    """
    Notification-specific context processor
    Provides notification data to all templates
    """
    context = {
        'unread_notifications_count': 0,
        'recent_notifications': []
    }
    
    if not request.user.is_authenticated:
        return context
    
    try:
        # Use your existing notification function
        notification_data = get_notification_data(request.user)
        context.update(notification_data)
    except Exception as e:
        # Log error but don't break the site
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error in notification context processor: {str(e)}")
    
    return context

def get_dashboard_url(user, is_parent_user, parent_obj):
    """
    Determine the appropriate dashboard URL for the user
    """
    if user.is_superuser or is_admin(user):
        return 'admin_dashboard'
    elif hasattr(user, 'teacher'):
        return 'teacher_dashboard'
    elif hasattr(user, 'student'):
        return 'student_dashboard'
    elif is_parent_user:
        return 'parent_dashboard'
    else:
        return 'home'

def get_notification_data(user):
    """
    Get notification data with optimized database queries
    """
    # Use a single query to get both count and recent notifications
    notifications = Notification.objects.filter(recipient=user).order_by('-created_at')
    
    # Get unread count efficiently
    unread_count = notifications.filter(is_read=False).count()
    
    # Get recent notifications (max 5)
    recent_notifications = notifications[:5]
    
    return {
        'unread_notifications_count': unread_count,
        'recent_notifications': recent_notifications
    }

# Alternative optimized version using aggregation (if you need more complex notification handling)
def get_optimized_notification_data(user):
    """
    Alternative optimized version using database aggregation
    """
    from django.db.models import Count, Q
    
    # Single query to get both unread count and recent notifications
    notification_data = Notification.objects.filter(
        recipient=user
    ).aggregate(
        unread_count=Count('id', filter=Q(is_read=False))
    )
    
    recent_notifications = Notification.objects.filter(
        recipient=user
    ).select_related('recipient').order_by('-created_at')[:5]
    
    return {
        'unread_notifications_count': notification_data['unread_count'] or 0,
        'recent_notifications': recent_notifications
    }

# Cache version for high-traffic scenarios (optional)
def get_cached_notification_data(user):
    """
    Cached version for high-traffic applications
    """
    from django.core.cache import cache
    
    cache_key = f"user_{user.id}_notification_data"
    cached_data = cache.get(cache_key)
    
    if cached_data is None:
        # Calculate fresh data
        notifications = Notification.objects.filter(recipient=user).order_by('-created_at')
        unread_count = notifications.filter(is_read=False).count()
        recent_notifications = list(notifications[:5])
        
        cached_data = {
            'unread_count': unread_count,
            'recent_notifications': recent_notifications
        }
        
        # Cache for 2 minutes
        cache.set(cache_key, cached_data, 120)
    
    return {
        'unread_notifications_count': cached_data['unread_count'],
        'recent_notifications': cached_data['recent_notifications']
    }