"""
Core utilities package - simplified to avoid circular imports.
"""

# Import core functions directly
def is_admin(user):
    """Check if user is admin/superuser"""
    if not user.is_authenticated:
        return False
    # Check for Django superuser/staff OR custom admin attribute
    return user.is_superuser or user.is_staff or hasattr(user, 'admin')

def is_teacher(user):
    """Check if user is teacher"""
    return hasattr(user, 'teacher')

def is_student(user):
    """Check if user is student"""
    return hasattr(user, 'student')

def is_parent(user):
    """Check if user is parent"""
    return hasattr(user, 'parentguardian')

def is_teacher_or_admin(user):
    """Check if user is teacher or admin"""
    return is_teacher(user) or is_admin(user)

def is_student_or_parent(user):
    """Check if user is student or parent"""
    return is_student(user) or is_parent(user)

def get_user_role(user):
    """Get user's role"""
    if is_admin(user):
        return 'admin'
    elif is_teacher(user):
        return 'teacher'
    elif is_student(user):
        return 'student'
    elif is_parent(user):
        return 'parent'
    else:
        return 'unknown'

# Academic utilities
def get_current_academic_year():
    from django.utils import timezone
    current_year = timezone.now().year
    return f"{current_year}/{current_year + 1}"

def calculate_letter_grade(score):
    """Calculate letter grade based on score"""
    if score is None:
        return 'N/A'
    try:
        score = float(score)
        if score >= 90: return 'A+'
        elif score >= 80: return 'A'
        elif score >= 70: return 'B+'
        elif score >= 60: return 'B'
        elif score >= 50: return 'C+'
        elif score >= 40: return 'C'
        elif score >= 30: return 'D+'
        elif score >= 20: return 'D'
        else: return 'E'
    except (ValueError, TypeError):
        return 'N/A'

def get_grade_color(grade):
    """Get color for a grade"""
    grade_colors = {
        'A+': 'success',
        'A': 'success',
        'B+': 'primary',
        'B': 'primary',
        'C+': 'warning',
        'C': 'warning',
        'D+': 'danger',
        'D': 'danger',
        'E': 'danger',
        'N/A': 'secondary'
    }
    return grade_colors.get(grade, 'secondary')

def get_performance_level(score):
    """Get performance level based on score"""
    try:
        score = float(score)
        if score >= 80: return 'Excellent'
        elif score >= 60: return 'Good'
        elif score >= 40: return 'Average'
        elif score >= 20: return 'Needs Improvement'
        else: return 'Poor'
    except (ValueError, TypeError):
        return 'Not Assessed'

def format_date(date_obj):
    """Format date object to string"""
    if not date_obj:
        return "Not set"
    
    from django.utils import timezone
    
    try:
        # Check if it's a timezone-aware datetime
        if timezone.is_aware(date_obj):
            return timezone.localtime(date_obj).strftime("%B %d, %Y")
    except (AttributeError, ValueError):
        # This happens for date objects or naive datetime objects
        pass
    
    # Format all other cases (date objects, naive datetime)
    return date_obj.strftime("%B %d, %Y")

def calculate_total_score(homework, classwork, test, exam):
    """Calculate total score from components"""
    try:
        total = (float(homework or 0) + float(classwork or 0) + 
                float(test or 0) + float(exam or 0))
        return round(total, 2)
    except (ValueError, TypeError):
        return 0.0

def validate_academic_year(year):
    """Validate academic year format"""
    import re
    # Check if year is in format YYYY/YYYY or YYYY-YYYY
    if not year:
        return False, "Academic year is required"
    
    # Check format
    pattern = r'^\d{4}[/-]\d{4}$'
    if not re.match(pattern, str(year)):
        return False, "Academic year must be in format YYYY/YYYY or YYYY-YYYY"
    
    # Check if years are consecutive
    years = re.split(r'[/-]', str(year))
    if len(years) != 2:
        return False, "Invalid academic year format"
    
    try:
        year1 = int(years[0])
        year2 = int(years[1])
        if year2 != year1 + 1:
            return False, "Academic years must be consecutive (e.g., 2024/2025)"
        return True, "Valid"
    except ValueError:
        return False, "Invalid year values"

# Simple validation functions
def validate_email(email):
    """Validate email format"""
    import re
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))

def check_report_card_permission(user, student):
    """Check if user has permission to view report card"""
    if is_admin(user):
        return True
    elif is_teacher(user):
        # Teacher can view report cards for students in their classes
        from core.models import ClassAssignment
        teacher_classes = ClassAssignment.objects.filter(
            teacher=user.teacher
        ).values_list('class_level', flat=True).distinct()
        return student.class_level in teacher_classes
    elif is_student(user):
        # Student can only view their own report cards
        return user.student == student
    elif is_parent(user):
        # Parent can view report cards for their children
        return student in user.parentguardian.children.all()
    return False

def can_edit_grades(user, student):
    """Check if user can edit grades"""
    if is_admin(user):
        return True
    elif is_teacher(user):
        # Teacher can edit grades for students in their classes
        from core.models import ClassAssignment
        teacher_classes = ClassAssignment.objects.filter(
            teacher=user.teacher
        ).values_list('class_level', flat=True).distinct()
        return student.class_level in teacher_classes
    return False

def get_student_position_in_class(student, academic_year, term):
    """Get student's position in class"""
    try:
        from core.models import Grade, Student
        from django.db.models import Avg
        
        # Get all students in the same class
        class_students = Student.objects.filter(
            class_level=student.class_level,
            is_active=True
        )
        
        # Calculate average scores for all students
        student_averages = []
        for s in class_students:
            avg = Grade.objects.filter(
                student=s,
                academic_year=academic_year,
                term=term
            ).aggregate(avg_score=Avg('total_score'))['avg_score'] or 0
            
            student_averages.append({
                'student': s,
                'average': avg
            })
        
        # Sort by average score (descending)
        student_averages.sort(key=lambda x: x['average'], reverse=True)
        
        # Find position of current student
        for i, item in enumerate(student_averages, 1):
            if item['student'] == student:
                return f"{i} out of {len(student_averages)}"
        
        return "Not ranked"
    except Exception:
        return "Not ranked"

def get_attendance_summary(student, academic_year, term):
    """Get attendance summary for student"""
    try:
        from core.models import StudentAttendance
        from django.db.models import Count
        
        attendance_records = StudentAttendance.objects.filter(
            student=student,
            academic_year=academic_year,
            term=term
        )
        
        total_days = attendance_records.count()
        present_days = attendance_records.filter(status='present').count()
        absent_days = attendance_records.filter(status='absent').count()
        
        attendance_rate = round((present_days / total_days * 100), 2) if total_days > 0 else 0
        
        return {
            'present_days': present_days,
            'total_days': total_days,
            'absence_count': absent_days,
            'attendance_rate': attendance_rate,
            'attendance_status': 'Good' if attendance_rate >= 80 else 'Needs Improvement'
        }
    except Exception:
        return {
            'present_days': 0,
            'total_days': 0,
            'absence_count': 0,
            'attendance_rate': 0,
            'attendance_status': 'No Data'
        }

def get_class_level_display(class_level):
    """Get display name for class level"""
    class_levels = {
        'P1': 'Primary 1',
        'P2': 'Primary 2',
        'P3': 'Primary 3',
        'P4': 'Primary 4',
        'P5': 'Primary 5',
        'P6': 'Primary 6',
        'J1': 'Junior 1',
        'J2': 'Junior 2',
        'J3': 'Junior 3',
        'S1': 'Senior 1',
        'S2': 'Senior 2',
        'S3': 'Senior 3',
        'S4': 'Senior 4',
    }
    return class_levels.get(class_level, class_level)

# Formatting functions
def format_name(first_name, last_name):
    """Format full name"""
    return f"{first_name} {last_name}".strip()

# Lazy imports for other modules (import only when needed)
_permissions_module = None
_academic_module = None
_financial_module = None

def get_permissions():
    """Lazy import permissions module"""
    global _permissions_module
    if _permissions_module is None:
        from . import permissions as mod
        _permissions_module = mod
    return _permissions_module

def get_academic():
    """Lazy import academic module"""
    global _academic_module
    if _academic_module is None:
        from . import academic as mod
        _academic_module = mod
    return _academic_module

def get_financial():
    """Lazy import financial module"""
    global _financial_module
    if _financial_module is None:
        from . import financial as mod
        _financial_module = mod
    return _financial_module


def send_email(subject, message, recipient_list, html_message=None, from_email=None):
    """Send email with optional HTML content"""
    from django.core.mail import send_mail
    from django.conf import settings
    
    try:
        if not from_email:
            from_email = settings.DEFAULT_FROM_EMAIL
        
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=recipient_list,
            html_message=html_message,
            fail_silently=False
        )
        return True
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send email: {str(e)}")
        return False

def send_template_email(template_name, context, subject, recipient_list):
    """Send email using a template"""
    from django.core.mail import EmailMessage
    from django.template.loader import render_to_string
    from django.conf import settings
    
    try:
        html_content = render_to_string(template_name, context)
        text_content = f"Please view this email in an HTML compatible client."
        
        msg = EmailMessage(
            subject=subject,
            body=html_content,
            from_email=settings.DEFAULT_FROM_EMAIL,
            to=recipient_list,
        )
        msg.content_subtype = "html"
        msg.send(fail_silently=False)
        return True
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send template email: {str(e)}")
        return False

def send_bulk_email(subject, message, recipient_lists, batch_size=50):
    """Send email in batches to avoid rate limiting"""
    from django.core.mail import send_mass_mail
    from django.conf import settings
    
    try:
        emails = []
        for recipient in recipient_lists:
            emails.append((
                subject,
                message,
                settings.DEFAULT_FROM_EMAIL,
                [recipient]
            ))
        
        # Send in batches
        for i in range(0, len(emails), batch_size):
            batch = emails[i:i + batch_size]
            send_mass_mail(batch, fail_silently=False)
        
        return True
    except Exception as e:
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to send bulk email: {str(e)}")
        return False

def format_email_subject(subject, prefix=None):
    """Format email subject with optional prefix"""
    from django.conf import settings
    
    if prefix:
        return f"[{prefix}] {subject}"
    elif hasattr(settings, 'EMAIL_SUBJECT_PREFIX'):
        return f"{settings.EMAIL_SUBJECT_PREFIX} {subject}"
    else:
        return subject

# Export everything
__all__ = [
    'is_admin', 'is_teacher', 'is_student', 'is_parent',
    'is_teacher_or_admin', 'is_student_or_parent', 'get_user_role',
    'get_current_academic_year', 'calculate_letter_grade',
    'get_grade_color', 'get_performance_level', 'format_date',
    'calculate_total_score', 'validate_academic_year',
    'check_report_card_permission', 'can_edit_grades',
    'get_student_position_in_class', 'get_attendance_summary',
    'get_class_level_display', 'validate_email',
    'format_name',
    # Email functions
    'send_email', 'send_template_email', 'send_bulk_email', 'format_email_subject',
    # Lazy imports
    'get_permissions', 'get_academic', 'get_financial',
]