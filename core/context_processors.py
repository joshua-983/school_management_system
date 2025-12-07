# core/context_processors.py - UPDATED VERSION with Timetable Context
import logging
from django.db.models import Prefetch, Count, Q, Sum, Avg
from django.conf import settings
from django.core.cache import cache
from .models import (
    Notification, ParentGuardian, Student, Teacher, 
    ParentMessage, ParentAnnouncement, ParentEvent,
    Fee, StudentAttendance, Grade, ClassAssignment, Timetable, TimeSlot
)
from .utils import is_admin, is_teacher, is_student, is_parent
from django.utils import timezone

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
        'parent_children': [],
        # Timetable context
        'has_timetable_access': False,
        'current_timetable_period': None,
        'next_period': None,
        'today_timetable': None,
        'teacher_timetable_stats': {},
        'student_timetable_stats': {}
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
        
        # Get timetable context based on user role
        try:
            timetable_context = get_timetable_context(user)
            context.update(timetable_context)
        except Exception as e:
            logger.error(f"Error loading timetable context: {str(e)}")
        
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
        'parent_dashboard_stats': {},
        'parent_children_timetables': []
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
            
            # Get children's timetables
            try:
                children_timetables = get_children_timetables(parent_obj)
                context['parent_children_timetables'] = children_timetables
            except Exception as e:
                logger.error(f"Error loading children timetables: {str(e)}")
            
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


def timetable_context(request):
    """
    Timetable-specific context processor
    Provides timetable data to all templates
    """
    context = {
        'has_timetable_access': False,
        'current_timetable_period': None,
        'next_period': None,
        'today_timetable': None,
        'teacher_timetable_stats': {},
        'student_timetable_stats': {},
        'available_timeslots': [],
        'timetable_days': [
            (0, 'Monday'),
            (1, 'Tuesday'),
            (2, 'Wednesday'),
            (3, 'Thursday'),
            (4, 'Friday'),
            (5, 'Saturday'),
        ]
    }
    
    if not request.user.is_authenticated:
        return context
    
    try:
        # Get timetable context based on user role
        timetable_data = get_timetable_context(request.user)
        context.update(timetable_data)
    except Exception as e:
        logger.error(f"Error in timetable context processor: {str(e)}")
    
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
        'TIMETABLE_ENABLED': getattr(settings, 'TIMETABLE_ENABLED', True),
        'TIMETABLE_PERIOD_DURATION': getattr(settings, 'TIMETABLE_PERIOD_DURATION', 60),  # minutes
        'TIMETABLE_START_TIME': getattr(settings, 'TIMETABLE_START_TIME', '08:00'),
        'TIMETABLE_END_TIME': getattr(settings, 'TIMETABLE_END_TIME', '16:00'),
        'SCHOOL_WEEK_DAYS': getattr(settings, 'SCHOOL_WEEK_DAYS', ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday']),
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


def get_timetable_context(user):
    """
    Get timetable context based on user role
    """
    context = {
        'has_timetable_access': False,
        'current_timetable_period': None,
        'next_period': None,
        'today_timetable': None,
        'teacher_timetable_stats': {},
        'student_timetable_stats': {},
        'available_timeslots': [],
    }
    
    try:
        # Check if user has timetable access
        has_access = is_admin(user) or is_teacher(user) or is_student(user)
        context['has_timetable_access'] = has_access
        
        if not has_access:
            return context
        
        # Get available timeslots
        try:
            timeslots = TimeSlot.objects.filter(is_active=True).order_by('period_number')
            context['available_timeslots'] = list(timeslots.values('id', 'period_number', 'start_time', 'end_time', 'is_break', 'break_name'))
        except Exception as e:
            logger.error(f"Error loading timeslots: {str(e)}")
        
        # Get current period info
        try:
            current_period = get_current_period_info()
            if current_period:
                context['current_timetable_period'] = current_period
                context['next_period'] = get_next_period_info(current_period.get('period_number', 0))
        except Exception as e:
            logger.error(f"Error getting current period info: {str(e)}")
        
        # Role-specific timetable data
        if is_admin(user):
            context.update(get_admin_timetable_context(user))
        elif is_teacher(user):
            context.update(get_teacher_timetable_context(user))
        elif is_student(user):
            context.update(get_student_timetable_context(user))
        
        # Get today's timetable
        try:
            today_data = get_today_timetable(user)
            context['today_timetable'] = today_data
        except Exception as e:
            logger.error(f"Error getting today's timetable: {str(e)}")
        
    except Exception as e:
        logger.error(f"Error in timetable context: {str(e)}")
    
    return context


def get_admin_timetable_context(user):
    """Get timetable context for admin users"""
    try:
        # Get all active timetables count
        active_timetables = Timetable.objects.filter(is_active=True).count()
        
        # Get timetables without entries
        empty_timetables = Timetable.objects.filter(
            is_active=True,
            entries__isnull=True
        ).count()
        
        # Get recent timetable updates
        recent_updates = Timetable.objects.filter(
            updated_at__gte=timezone.now() - timezone.timedelta(days=7)
        ).count()
        
        return {
            'admin_timetable_stats': {
                'total_active': active_timetables,
                'empty_timetables': empty_timetables,
                'recent_updates': recent_updates,
                'total_timeslots': TimeSlot.objects.count(),
            }
        }
    except Exception as e:
        logger.error(f"Error getting admin timetable context: {str(e)}")
        return {}


def get_teacher_timetable_context(user):
    """Get timetable context for teacher users"""
    try:
        teacher = user.teacher
        
        # Get classes assigned to teacher
        assigned_classes = ClassAssignment.objects.filter(
            teacher=teacher
        ).values_list('class_level', flat=True).distinct()
        
        # Get teacher's timetables
        teacher_timetables = Timetable.objects.filter(
            class_level__in=assigned_classes,
            is_active=True
        )
        
        # Get teacher's schedule for current week
        current_year = timezone.now().year
        next_year = current_year + 1
        academic_year = f"{current_year}/{next_year}"
        
        current_term = getattr(settings, 'CURRENT_TERM', 1)
        
        teacher_periods_count = 0
        today_periods_count = 0
        
        for timetable in teacher_timetables:
            entries_count = timetable.entries.filter(teacher=teacher).count()
            teacher_periods_count += entries_count
            
            # Check today's day of week (0=Monday, 1=Tuesday, etc.)
            today = timezone.now().weekday()
            if timetable.day_of_week == today:
                today_periods_count += entries_count
        
        # Get teacher's upcoming classes (next 3 days)
        upcoming_classes = get_teacher_upcoming_classes(teacher)
        
        return {
            'teacher_timetable_stats': {
                'assigned_classes': len(assigned_classes),
                'total_timetables': teacher_timetables.count(),
                'total_periods': teacher_periods_count,
                'today_periods': today_periods_count,
                'upcoming_classes': upcoming_classes,
            }
        }
    except Exception as e:
        logger.error(f"Error getting teacher timetable context: {str(e)}")
        return {}


def get_student_timetable_context(user):
    """Get timetable context for student users"""
    try:
        student = user.student
        class_level = student.class_level
        
        # Get student's timetable for current term
        current_year = timezone.now().year
        next_year = current_year + 1
        academic_year = f"{current_year}/{next_year}"
        
        current_term = getattr(settings, 'CURRENT_TERM', 1)
        
        # Get today's timetable
        today = timezone.now().weekday()
        today_timetable = Timetable.objects.filter(
            class_level=class_level,
            day_of_week=today,
            academic_year=academic_year,
            term=current_term,
            is_active=True
        ).first()
        
        # Get weekly timetable summary
        weekly_timetable = Timetable.objects.filter(
            class_level=class_level,
            academic_year=academic_year,
            term=current_term,
            is_active=True
        )
        
        total_periods = 0
        for timetable in weekly_timetable:
            total_periods += timetable.entries.count()
        
        # Get next class
        next_class = get_student_next_class(student)
        
        return {
            'student_timetable_stats': {
                'class_level': class_level,
                'today_timetable_exists': today_timetable is not None,
                'weekly_periods': total_periods,
                'next_class': next_class,
            }
        }
    except Exception as e:
        logger.error(f"Error getting student timetable context: {str(e)}")
        return {}


def get_current_period_info():
    """Get current period information based on time"""
    try:
        now = timezone.now()
        current_time = now.time()
        
        # Get all active time slots
        timeslots = TimeSlot.objects.filter(is_active=True).order_by('period_number')
        
        for timeslot in timeslots:
            if timeslot.start_time <= current_time <= timeslot.end_time:
                return {
                    'period_number': timeslot.period_number,
                    'period_name': timeslot.get_period_number_display(),
                    'start_time': timeslot.start_time.strftime('%H:%M'),
                    'end_time': timeslot.end_time.strftime('%H:%M'),
                    'is_break': timeslot.is_break,
                    'break_name': timeslot.break_name,
                    'remaining_minutes': calculate_remaining_minutes(timeslot.end_time, current_time)
                }
        
        # Check if before first period
        if timeslots.exists():
            first_period = timeslots.first()
            if current_time < first_period.start_time:
                return {
                    'status': 'before_school',
                    'next_period': {
                        'period_number': first_period.period_number,
                        'period_name': first_period.get_period_number_display(),
                        'start_time': first_period.start_time.strftime('%H:%M'),
                    }
                }
        
        # Check if after last period
        if timeslots.exists():
            last_period = timeslots.last()
            if current_time > last_period.end_time:
                return {
                    'status': 'after_school',
                    'message': 'School has ended for the day'
                }
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting current period info: {str(e)}")
        return None


def get_next_period_info(current_period_number):
    """Get next period information"""
    try:
        next_period = TimeSlot.objects.filter(
            period_number__gt=current_period_number,
            is_active=True
        ).order_by('period_number').first()
        
        if next_period:
            return {
                'period_number': next_period.period_number,
                'period_name': next_period.get_period_number_display(),
                'start_time': next_period.start_time.strftime('%H:%M'),
                'end_time': next_period.end_time.strftime('%H:%M'),
                'is_break': next_period.is_break,
                'break_name': next_period.break_name,
            }
        
        return None
    except Exception as e:
        logger.error(f"Error getting next period info: {str(e)}")
        return None


def calculate_remaining_minutes(end_time, current_time):
    """Calculate remaining minutes in current period"""
    from datetime import datetime, timedelta
    
    # Convert times to datetime objects for calculation
    end_datetime = datetime.combine(datetime.today(), end_time)
    current_datetime = datetime.combine(datetime.today(), current_time)
    
    if current_datetime > end_datetime:
        return 0
    
    remaining = end_datetime - current_datetime
    return int(remaining.total_seconds() / 60)


def get_today_timetable(user):
    """Get today's timetable for the user"""
    try:
        today = timezone.now().weekday()
        
        if is_student(user):
            student = user.student
            current_year = timezone.now().year
            next_year = current_year + 1
            academic_year = f"{current_year}/{next_year}"
            current_term = getattr(settings, 'CURRENT_TERM', 1)
            
            timetable = Timetable.objects.filter(
                class_level=student.class_level,
                day_of_week=today,
                academic_year=academic_year,
                term=current_term,
                is_active=True
            ).prefetch_related('entries__subject', 'entries__teacher', 'entries__time_slot').first()
            
            if timetable:
                return {
                    'exists': True,
                    'class_level': student.get_class_level_display(),
                    'entries': list(timetable.entries.order_by('time_slot__period_number').values(
                        'id', 'time_slot__period_number', 'time_slot__start_time', 
                        'time_slot__end_time', 'subject__name', 'teacher__user__first_name',
                        'teacher__user__last_name', 'classroom', 'is_break'
                    ))
                }
        
        elif is_teacher(user):
            teacher = user.teacher
            # Get all timetables for today where teacher has classes
            timetables = Timetable.objects.filter(
                day_of_week=today,
                is_active=True,
                entries__teacher=teacher
            ).distinct().prefetch_related('entries__subject', 'entries__time_slot')
            
            if timetables.exists():
                entries = []
                for timetable in timetables:
                    teacher_entries = timetable.entries.filter(teacher=teacher).order_by('time_slot__period_number')
                    for entry in teacher_entries:
                        entries.append({
                            'class_level': timetable.get_class_level_display(),
                            'period': entry.time_slot.period_number,
                            'time': f"{entry.time_slot.start_time.strftime('%H:%M')} - {entry.time_slot.end_time.strftime('%H:%M')}",
                            'subject': entry.subject.name if entry.subject else None,
                            'classroom': entry.classroom,
                            'is_break': entry.is_break
                        })
                
                return {
                    'exists': True,
                    'entries': entries
                }
        
        return {'exists': False, 'message': 'No timetable for today'}
        
    except Exception as e:
        logger.error(f"Error getting today's timetable: {str(e)}")
        return {'exists': False, 'error': str(e)}


def get_teacher_upcoming_classes(teacher, days=3):
    """Get teacher's upcoming classes for next N days"""
    try:
        from datetime import timedelta
        
        upcoming_classes = []
        today = timezone.now().date()
        
        for day_offset in range(1, days + 1):
            target_date = today + timedelta(days=day_offset)
            target_day = target_date.weekday()
            
            # Get timetables for this day
            timetables = Timetable.objects.filter(
                day_of_week=target_day,
                is_active=True,
                entries__teacher=teacher
            ).distinct().prefetch_related('entries__subject', 'entries__time_slot')
            
            for timetable in timetables:
                teacher_entries = timetable.entries.filter(teacher=teacher).order_by('time_slot__period_number')
                for entry in teacher_entries:
                    upcoming_classes.append({
                        'date': target_date.strftime('%Y-%m-%d'),
                        'day': target_date.strftime('%A'),
                        'class_level': timetable.get_class_level_display(),
                        'period': entry.time_slot.period_number,
                        'time': f"{entry.time_slot.start_time.strftime('%H:%M')} - {entry.time_slot.end_time.strftime('%H:%M')}",
                        'subject': entry.subject.name if entry.subject else None,
                        'classroom': entry.classroom,
                    })
        
        return upcoming_classes[:5]  # Limit to 5 upcoming classes
        
    except Exception as e:
        logger.error(f"Error getting teacher upcoming classes: {str(e)}")
        return []


def get_student_next_class(student):
    """Get student's next class"""
    try:
        now = timezone.now()
        today = now.weekday()
        current_time = now.time()
        
        # Get student's timetable for today
        current_year = timezone.now().year
        next_year = current_year + 1
        academic_year = f"{current_year}/{next_year}"
        current_term = getattr(settings, 'CURRENT_TERM', 1)
        
        timetable = Timetable.objects.filter(
            class_level=student.class_level,
            day_of_week=today,
            academic_year=academic_year,
            term=current_term,
            is_active=True
        ).prefetch_related('entries__subject', 'entries__teacher', 'entries__time_slot').first()
        
        if not timetable:
            return None
        
        # Find next period
        for entry in timetable.entries.order_by('time_slot__period_number'):
            if entry.time_slot.start_time > current_time:
                return {
                    'subject': entry.subject.name if entry.subject and not entry.is_break else entry.break_name,
                    'teacher': entry.teacher.get_full_name() if entry.teacher else None,
                    'time': f"{entry.time_slot.start_time.strftime('%H:%M')} - {entry.time_slot.end_time.strftime('%H:%M')}",
                    'classroom': entry.classroom,
                    'minutes_until': calculate_minutes_until(entry.time_slot.start_time, current_time)
                }
        
        return None
        
    except Exception as e:
        logger.error(f"Error getting student next class: {str(e)}")
        return None


def calculate_minutes_until(start_time, current_time):
    """Calculate minutes until a given start time"""
    from datetime import datetime, timedelta
    
    # Convert times to datetime objects for calculation
    start_datetime = datetime.combine(datetime.today(), start_time)
    current_datetime = datetime.combine(datetime.today(), current_time)
    
    if current_datetime > start_datetime:
        return 0
    
    difference = start_datetime - current_datetime
    return int(difference.total_seconds() / 60)


def get_children_timetables(parent_obj):
    """Get timetables for parent's children"""
    try:
        children = parent_obj.students.all().select_related('user')
        children_timetables = []
        
        current_year = timezone.now().year
        next_year = current_year + 1
        academic_year = f"{current_year}/{next_year}"
        current_term = getattr(settings, 'CURRENT_TERM', 1)
        
        for child in children:
            # Get today's timetable for the child
            today = timezone.now().weekday()
            timetable = Timetable.objects.filter(
                class_level=child.class_level,
                day_of_week=today,
                academic_year=academic_year,
                term=current_term,
                is_active=True
            ).prefetch_related('entries__subject', 'entries__teacher', 'entries__time_slot').first()
            
            if timetable:
                entries = list(timetable.entries.order_by('time_slot__period_number').values(
                    'time_slot__period_number', 'time_slot__start_time', 'time_slot__end_time',
                    'subject__name', 'teacher__user__first_name', 'teacher__user__last_name',
                    'classroom', 'is_break'
                ))
                
                children_timetables.append({
                    'child_name': child.get_full_name(),
                    'class_level': child.get_class_level_display(),
                    'timetable': entries
                })
        
        return children_timetables
        
    except Exception as e:
        logger.error(f"Error getting children timetables: {str(e)}")
        return []


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


def get_cached_timetable_context(user):
    """
    Cached version of timetable context for better performance
    """
    try:
        cache_key = f"user_{user.id}_timetable_context"
        cached_data = cache.get(cache_key)
        
        if cached_data is None:
            # Calculate fresh data
            cached_data = get_timetable_context(user)
            
            # Cache for 1 minute (timetable data can change during the day)
            cache.set(cache_key, cached_data, 60)
        
        return cached_data
        
    except Exception as e:
        logger.error(f"Error in cached timetable context: {str(e)}")
        return {
            'has_timetable_access': False,
            'current_timetable_period': None,
            'next_period': None,
            'today_timetable': None,
            'teacher_timetable_stats': {},
            'student_timetable_stats': {}
        }