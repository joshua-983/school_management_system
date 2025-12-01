# core/context_processors.py
import logging
from django.db.models import Prefetch, Count, Q, Sum, Avg
from django.conf import settings
from django.core.cache import cache
from .models import (
    Notification, ParentGuardian, Student, Teacher, 
    ParentMessage, ParentAnnouncement, ParentEvent,
    Fee, StudentAttendance, Grade
)
from .utils import is_admin, is_teacher

# Set up logger
logger = logging.getLogger(__name__)

def global_context(request):
    """
    Fixed context processor that properly handles user profiles
    """
    context = {
        'is_admin': False,
        'is_teacher': False,
        'is_student': False,
        'is_parent': False,
        'user_parentguardian': None,
        'dashboard_url': 'home',
        'unread_notifications_count': 0,
        'recent_notifications': [],
        # Parent-specific context
        'parent_children_count': 0,
        'parent_unread_messages_count': 0,
        'parent_upcoming_events_count': 0,
        'parent_pending_fees_total': 0,
        'parent_recent_announcements': [],
        'parent_children': []
    }
    
    if not request.user.is_authenticated:
        return context
    
    user = request.user
    
    try:
        # Check user profiles safely
        has_student_profile = hasattr(user, 'student') and user.student is not None
        has_teacher_profile = hasattr(user, 'teacher') and user.teacher is not None
        
        # Get parent status safely
        parent_obj = None
        try:
            parent_obj = ParentGuardian.objects.filter(user=user).select_related('user').first()
        except (ParentGuardian.DoesNotExist, AttributeError):
            pass
        
        is_parent_user = parent_obj is not None
        
        # Set user roles with safe defaults
        context.update({
            'is_admin': is_admin(user),
            'is_teacher': has_teacher_profile,
            'is_student': has_student_profile,
            'is_parent': is_parent_user,
            'user_parentguardian': parent_obj,
            'dashboard_url': get_dashboard_url(user, is_parent_user, parent_obj)
        })
        
        # Get notifications safely
        try:
            notification_data = get_notification_data(user)
            context.update(notification_data)
        except Exception as e:
            logger.error(f"Error loading notifications: {str(e)}")
        
        # Get parent-specific data if user is a parent
        if is_parent_user and parent_obj:
            try:
                parent_data = get_parent_context_data(parent_obj)
                context.update(parent_data)
            except Exception as e:
                logger.error(f"Error loading parent context data: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error in global context processor: {str(e)}")
    
    return context


def parent_context(request):
    """
    Parent-specific context processor
    Provides parent portal data to all templates
    """
    context = {
        'parent_children_count': 0,
        'parent_unread_messages_count': 0,
        'parent_upcoming_events_count': 0,
        'parent_pending_fees_total': 0,
        'parent_recent_announcements': [],
        'parent_children': [],
        'parent_dashboard_stats': {}
    }
    
    if not request.user.is_authenticated:
        return context
    
    try:
        # Check if user is a parent
        parent_obj = None
        try:
            parent_obj = ParentGuardian.objects.filter(user=request.user).select_related('user').first()
        except (ParentGuardian.DoesNotExist, AttributeError):
            pass
        
        if parent_obj:
            parent_data = get_parent_context_data(parent_obj)
            context.update(parent_data)
            
    except Exception as e:
        logger.error(f"Error in parent context processor: {str(e)}")
    
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
        logger.error(f"Error in notification context processor: {str(e)}")
    
    return context


def settings_context(request):
    """
    Expose certain settings to templates
    """
    return {
        'DEBUG': settings.DEBUG,
        'SCHOOL_NAME': getattr(settings, 'SCHOOL_NAME', 'Judith\'s International School'),
        'SCHOOL_SHORT_NAME': getattr(settings, 'SCHOOL_SHORT_NAME', 'JIS'),
        'SCHOOL_EMAIL': getattr(settings, 'SCHOOL_EMAIL', 'info@school.edu'),
        'SCHOOL_PHONE': getattr(settings, 'SCHOOL_PHONE', '+233 054 134 5564'),
        'SCHOOL_ADDRESS': getattr(settings, 'SCHOOL_ADDRESS', '123 Education Street, Academic City'),
        'VERSION': getattr(settings, 'VERSION', '1.0.0'),
        'BUILD_NUMBER': getattr(settings, 'BUILD_NUMBER', '1'),
        'ENABLE_TWO_FACTOR_AUTH': getattr(settings, 'ENABLE_TWO_FACTOR_AUTH', False),
        'ENABLE_API_ACCESS': getattr(settings, 'ENABLE_API_ACCESS', True),
        'ENABLE_BACKGROUND_TASKS': getattr(settings, 'ENABLE_BACKGROUND_TASKS', True),
        'ENABLE_NOTIFICATIONS': getattr(settings, 'ENABLE_NOTIFICATIONS', True),
        'PARENT_PORTAL_ENABLED': getattr(settings, 'PARENT_PORTAL_ENABLED', True),
    }


def get_dashboard_url(user, is_parent_user, parent_obj):
    """
    Safe dashboard URL determination
    """
    try:
        if user.is_superuser or is_admin(user):
            return 'admin_dashboard'
        elif hasattr(user, 'teacher') and user.teacher is not None:
            return 'teacher_dashboard'
        elif hasattr(user, 'student') and user.student is not None:
            return 'student_dashboard'
        elif is_parent_user:
            return 'parent_dashboard'
        else:
            return 'home'
    except Exception as e:
        logger.error(f"Error determining dashboard URL: {str(e)}")
        return 'home'


def get_notification_data(user):
    """
    Get notification data with optimized database queries
    """
    try:
        # Use a single query to get both count and recent notifications
        notifications = Notification.objects.filter(recipient=user).order_by('-created_at')
        
        # Get unread count efficiently
        unread_count = notifications.filter(is_read=False).count()
        
        # Get recent notifications (max 5)
        recent_notifications = list(notifications[:5])
        
        return {
            'unread_notifications_count': unread_count,
            'recent_notifications': recent_notifications
        }
    except Exception as e:
        logger.error(f"Error getting notification data: {str(e)}")
        return {
            'unread_notifications_count': 0,
            'recent_notifications': []
        }


def get_parent_context_data(parent_obj):
    """
    Get comprehensive parent portal context data with optimized queries - FIXED VERSION
    """
    try:
        # FIXED: Use either select_related OR only(), not both together
        children = parent_obj.students.all().select_related('user')
        
        children_count = children.count()
        
        # Get unread messages count
        unread_messages_count = ParentMessage.objects.filter(
            receiver=parent_obj.user, 
            is_read=False
        ).count()
        
        # Get upcoming events count (next 7 days)
        from django.utils import timezone
        from datetime import timedelta
        
        next_week = timezone.now() + timedelta(days=7)
        upcoming_events_count = ParentEvent.objects.filter(
            Q(is_whole_school=True) | Q(class_level__in=children.values_list('class_level', flat=True)),
            start_date__gte=timezone.now(),
            start_date__lte=next_week
        ).count()
        
        # Get pending fees total
        pending_fees_total = Fee.objects.filter(
            student__in=children,
            payment_status__in=['unpaid', 'partial']
        ).aggregate(total=Sum('balance'))['total'] or 0
        
        # Get recent announcements (last 5)
        child_classes = children.values_list('class_level', flat=True).distinct()
        recent_announcements = ParentAnnouncement.objects.filter(
            Q(target_type='ALL') | 
            Q(target_type='CLASS', target_class__in=child_classes) |
            Q(target_type='INDIVIDUAL', target_parents=parent_obj)
        ).select_related('created_by').order_by('-created_at')[:5]
        
        # Get children with basic academic summary
        children_with_summary = []
        for child in children:
            # Get recent attendance summary (current month)
            current_month = timezone.now().month
            current_year = timezone.now().year
            
            attendance_summary = StudentAttendance.objects.filter(
                student=child,
                date__month=current_month,
                date__year=current_year
            ).aggregate(
                present=Count('id', filter=Q(status='present')),
                total=Count('id')
            )
            
            # Calculate attendance percentage
            total_attendance = attendance_summary['total'] or 0
            present_count = attendance_summary['present'] or 0
            attendance_percentage = round((present_count / total_attendance * 100), 1) if total_attendance > 0 else 0
            
            # Get recent grades average
            recent_grades_avg = Grade.objects.filter(
                student=child
            ).aggregate(avg_score=Avg('total_score'))['avg_score'] or 0
            
            children_with_summary.append({
                'id': child.id,
                'full_name': child.get_full_name(),
                'student_id': child.student_id,
                'class_level': child.get_class_level_display(),
                'attendance_percentage': attendance_percentage,
                'average_grade': round(float(recent_grades_avg), 1),
                'has_attendance_issues': attendance_percentage < 80,
                'has_academic_issues': recent_grades_avg < 50
            })
        
        # Calculate dashboard statistics
        dashboard_stats = {
            'total_children': children_count,
            'children_with_attendance_issues': sum(1 for child in children_with_summary if child['has_attendance_issues']),
            'children_with_academic_issues': sum(1 for child in children_with_summary if child['has_academic_issues']),
            'children_with_pending_fees': Fee.objects.filter(
                student__in=children,
                payment_status__in=['unpaid', 'partial']
            ).values('student').distinct().count(),
            'overall_attendance_rate': round(
                sum(child['attendance_percentage'] for child in children_with_summary) / len(children_with_summary) 
                if children_with_summary else 0, 1
            )
        }
        
        return {
            'parent_children_count': children_count,
            'parent_unread_messages_count': unread_messages_count,
            'parent_upcoming_events_count': upcoming_events_count,
            'parent_pending_fees_total': pending_fees_total,
            'parent_recent_announcements': list(recent_announcements),
            'parent_children': children_with_summary,
            'parent_dashboard_stats': dashboard_stats
        }
        
    except Exception as e:
        logger.error(f"Error getting parent context data: {str(e)}")
        return {
            'parent_children_count': 0,
            'parent_unread_messages_count': 0,
            'parent_upcoming_events_count': 0,
            'parent_pending_fees_total': 0,
            'parent_recent_announcements': [],
            'parent_children': [],
            'parent_dashboard_stats': {}
        }


def get_optimized_parent_context_data(parent_obj):
    """
    Alternative optimized version using database aggregation for parent data - FIXED VERSION
    """
    try:
        from django.db.models import Count, Sum, Avg, Q
        from django.utils import timezone
        from datetime import timedelta
        
        # FIXED: Use select_related without only() to avoid the conflict
        children_data = parent_obj.students.annotate(
            recent_attendance_present=Count(
                'studentattendance',
                filter=Q(
                    studentattendance__date__month=timezone.now().month,
                    studentattendance__date__year=timezone.now().year,
                    studentattendance__status='present'
                )
            ),
            recent_attendance_total=Count(
                'studentattendance',
                filter=Q(
                    studentattendance__date__month=timezone.now().month,
                    studentattendance__date__year=timezone.now().year
                )
            ),
            average_grade=Avg('grade__total_score'),
            pending_fees_count=Count(
                'fee',
                filter=Q(fee__payment_status__in=['unpaid', 'partial'])
            ),
            pending_fees_total=Sum(
                'fee__balance',
                filter=Q(fee__payment_status__in=['unpaid', 'partial'])
            )
        ).select_related('user')  # Removed .only() to fix the conflict
        
        children_count = children_data.count()
        
        # Process children data
        children_with_summary = []
        for child in children_data:
            total_attendance = getattr(child, 'recent_attendance_total', 0) or 0
            present_count = getattr(child, 'recent_attendance_present', 0) or 0
            attendance_percentage = round((present_count / total_attendance * 100), 1) if total_attendance > 0 else 0
            
            children_with_summary.append({
                'id': child.id,
                'full_name': child.get_full_name(),
                'student_id': child.student_id,
                'class_level': child.get_class_level_display(),
                'attendance_percentage': attendance_percentage,
                'average_grade': round(float(getattr(child, 'average_grade', 0) or 0), 1),
                'pending_fees': getattr(child, 'pending_fees_total', 0) or 0,
                'has_attendance_issues': attendance_percentage < 80,
                'has_academic_issues': (getattr(child, 'average_grade', 0) or 0) < 50,
                'has_fee_issues': (getattr(child, 'pending_fees_total', 0) or 0) > 0
            })
        
        # Get other parent data
        unread_messages_count = ParentMessage.objects.filter(
            receiver=parent_obj.user, 
            is_read=False
        ).count()
        
        next_week = timezone.now() + timedelta(days=7)
        upcoming_events_count = ParentEvent.objects.filter(
            Q(is_whole_school=True) | Q(class_level__in=children_data.values_list('class_level', flat=True)),
            start_date__gte=timezone.now(),
            start_date__lte=next_week
        ).count()
        
        # Calculate dashboard statistics
        dashboard_stats = {
            'total_children': children_count,
            'children_with_attendance_issues': sum(1 for child in children_with_summary if child['has_attendance_issues']),
            'children_with_academic_issues': sum(1 for child in children_with_summary if child['has_academic_issues']),
            'children_with_fee_issues': sum(1 for child in children_with_summary if child['has_fee_issues']),
            'total_pending_fees': sum(child['pending_fees'] for child in children_with_summary),
            'overall_attendance_rate': round(
                sum(child['attendance_percentage'] for child in children_with_summary) / len(children_with_summary) 
                if children_with_summary else 0, 1
            )
        }
        
        return {
            'parent_children_count': children_count,
            'parent_unread_messages_count': unread_messages_count,
            'parent_upcoming_events_count': upcoming_events_count,
            'parent_pending_fees_total': dashboard_stats['total_pending_fees'],
            'parent_children': children_with_summary,
            'parent_dashboard_stats': dashboard_stats
        }
        
    except Exception as e:
        logger.error(f"Error in optimized parent context: {str(e)}")
        return {
            'parent_children_count': 0,
            'parent_unread_messages_count': 0,
            'parent_upcoming_events_count': 0,
            'parent_pending_fees_total': 0,
            'parent_children': [],
            'parent_dashboard_stats': {}
        }


# Alternative optimized version using aggregation (if you need more complex notification handling)
def get_optimized_notification_data(user):
    """
    Alternative optimized version using database aggregation
    """
    try:
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
    except Exception as e:
        logger.error(f"Error in optimized notification data: {str(e)}")
        return {
            'unread_notifications_count': 0,
            'recent_notifications': []
        }


# Cache version for high-traffic scenarios (optional)
def get_cached_notification_data(user):
    """
    Cached version for high-traffic applications
    """
    try:
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
    except Exception as e:
        logger.error(f"Error in cached notification data: {str(e)}")
        return {
            'unread_notifications_count': 0,
            'recent_notifications': []
        }


def get_cached_parent_context_data(parent_obj):
    """
    Cached version of parent context data for better performance
    """
    try:
        cache_key = f"parent_{parent_obj.id}_context_data"
        cached_data = cache.get(cache_key)
        
        if cached_data is None:
            # Calculate fresh data using optimized function
            cached_data = get_optimized_parent_context_data(parent_obj)
            
            # Cache for 5 minutes (parent data doesn't change frequently)
            cache.set(cache_key, cached_data, 300)
        
        return cached_data
        
    except Exception as e:
        logger.error(f"Error in cached parent context: {str(e)}")
        return {
            'parent_children_count': 0,
            'parent_unread_messages_count': 0,
            'parent_upcoming_events_count': 0,
            'parent_pending_fees_total': 0,
            'parent_children': [],
            'parent_dashboard_stats': {}
        }