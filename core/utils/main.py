# core/utils/main.py
"""
Main utility module - contains all core utility functions.
"""

import re
import hashlib
import json
import logging
from datetime import datetime, timedelta, date
from decimal import Decimal
from django.utils import timezone
from django.db.models import Q, Avg, Sum, Count
from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)
User = get_user_model()

# ============================================
# PERMISSION & AUTHENTICATION UTILITIES
# ============================================

def is_admin(user):
    """Check if user is admin/staff"""
    return user.is_authenticated and (user.is_staff or user.is_superuser)

def is_teacher(user):
    """Check if user is a teacher"""
    return user.is_authenticated and hasattr(user, 'teacher')

def is_student(user):
    """Check if user is a student"""
    return user.is_authenticated and hasattr(user, 'student_profile')

def is_parent(user):
    """Check if user is a parent/guardian"""
    return user.is_authenticated and hasattr(user, 'parentguardian')

def is_teacher_or_admin(user):
    """Check if user is teacher or admin"""
    return is_teacher(user) or is_admin(user)

def is_student_or_parent(user):
    """Check if user is student or parent"""
    return is_student(user) or is_parent(user)

def get_user_role(user):
    """Get user's role as string"""
    if not user.is_authenticated:
        return 'anonymous'
    elif is_admin(user):
        return 'admin'
    elif is_teacher(user):
        return 'teacher'
    elif is_student(user):
        return 'student'
    elif is_parent(user):
        return 'parent'
    else:
        return 'user'

def check_report_card_permission(user, student, report_card=None):
    """Check if user has permission to access a report card"""
    if is_admin(user):
        return True
    
    if is_student(user) and user.student_profile == student:
        return True
    
    if is_teacher(user):
        from core.models import ClassAssignment
        return ClassAssignment.objects.filter(
            class_level=student.class_level,
            teacher=user.teacher
        ).exists()
    
    if is_parent(user):
        # Check if parent is associated with this student
        return student in user.parentguardian.students.all()
    
    return False

def can_edit_grades(user, student):
    """Check if user can edit grades for a student"""
    return is_teacher_or_admin(user)

def can_view_grades(user, student):
    """Check if user can view grades for a student"""
    if is_admin(user):
        return True
    if is_student(user) and user.student_profile == student:
        return True
    if is_teacher(user):
        from core.models import ClassAssignment
        return ClassAssignment.objects.filter(
            class_level=student.class_level,
            teacher=user.teacher
        ).exists()
    if is_parent(user):
        return student in user.parentguardian.students.all()
    return False

# ============================================
# ACADEMIC UTILITIES
# ============================================

def get_current_academic_year():
    """Get current academic year in YYYY/YYYY format"""
    now = timezone.now()
    year = now.year
    # Assuming academic year runs from September to August
    if now.month >= 9:  # September or later
        return f"{year}/{year + 1}"
    else:  # January to August
        return f"{year - 1}/{year}"

def get_class_level_choices():
    """Return standardized class level choices"""
    return (
        ('P1', 'Primary 1'),
        ('P2', 'Primary 2'), 
        ('P3', 'Primary 3'),
        ('P4', 'Primary 4'),
        ('P5', 'Primary 5'),
        ('P6', 'Primary 6'),
        ('J1', 'JHS 1'),
        ('J2', 'JHS 2'),
        ('J3', 'JHS 3'),
    )

def get_class_level_display(class_level):
    """Get display name for class level"""
    choices_dict = dict(get_class_level_choices())
    return choices_dict.get(class_level, class_level)

def get_grade_choices():
    """Return standardized grade choices"""
    return (
        ('A+', 'A+ (90-100)'),
        ('A', 'A (80-89)'),
        ('B+', 'B+ (70-79)'),
        ('B', 'B (60-69)'),
        ('C+', 'C+ (50-59)'),
        ('C', 'C (40-49)'),
        ('D+', 'D+ (30-39)'),
        ('D', 'D (20-29)'),
        ('E', 'E (0-19)'),
    )

def get_term_choices():
    """Return term choices"""
    return (
        (1, 'Term 1'),
        (2, 'Term 2'),
        (3, 'Term 3'),
    )

def calculate_letter_grade(score):
    """Calculate letter grade based on numerical score"""
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
    """Get Bootstrap color class for grade"""
    if grade in ['A+', 'A']:
        return 'success'
    elif grade in ['B+', 'B']:
        return 'info'
    elif grade in ['C+', 'C']:
        return 'warning'
    elif grade in ['D+', 'D']:
        return 'warning'
    elif grade == 'E':
        return 'danger'
    else:
        return 'secondary'

def get_performance_level(score):
    """Get performance level description"""
    try:
        score = float(score)
        if score >= 80:
            return 'Excellent'
        elif score >= 70:
            return 'Very Good'
        elif score >= 60:
            return 'Good'
        elif score >= 50:
            return 'Average'
        elif score >= 40:
            return 'Below Average'
        elif score >= 30:
            return 'Poor'
        else:
            return 'Very Poor'
    except (ValueError, TypeError):
        return 'Not Available'

def calculate_total_score(homework, classwork, test, exam):
    """Calculate total score from components"""
    try:
        homework = float(homework or 0)
        classwork = float(classwork or 0)
        test = float(test or 0)
        exam = float(exam or 0)
        return homework + classwork + test + exam
    except (ValueError, TypeError):
        return 0.0

# ============================================
# FINANCIAL UTILITIES
# ============================================

def format_currency(amount):
    """Format amount as currency"""
    try:
        amount = Decimal(str(amount))
        return f"GHS {amount:,.2f}"
    except:
        return f"GHS 0.00"

def calculate_balance(amount_payable, amount_paid):
    """Calculate balance amount"""
    try:
        payable = Decimal(str(amount_payable or 0))
        paid = Decimal(str(amount_paid or 0))
        return payable - paid
    except:
        return Decimal('0.00')

def get_payment_status(amount_payable, amount_paid):
    """Determine payment status"""
    try:
        payable = Decimal(str(amount_payable or 0))
        paid = Decimal(str(amount_paid or 0))
        balance = payable - paid
        
        if balance <= 0:
            return 'paid'
        elif paid > 0:
            return 'partial'
        else:
            return 'unpaid'
    except:
        return 'unpaid'

def is_overdue(due_date, check_date=None):
    """Check if a due date is overdue"""
    if not due_date:
        return False
    
    check_date = check_date or timezone.now().date()
    return due_date < check_date

# ============================================
# DATE & TIME UTILITIES
# ============================================

def get_current_term():
    """Get current term based on date"""
    now = timezone.now()
    month = now.month
    
    # Simple logic: Jan-Apr = Term 1, May-Aug = Term 2, Sep-Dec = Term 3
    if month <= 4:
        return 1
    elif month <= 8:
        return 2
    else:
        return 3

def parse_academic_year(year_str):
    """Parse academic year string into start and end years"""
    try:
        if '/' in year_str:
            start, end = year_str.split('/')
            return int(start), int(end)
        elif '-' in year_str:
            start, end = year_str.split('-')
            return int(start), int(end)
    except:
        current_year = timezone.now().year
        return current_year, current_year + 1

def academic_year_to_string(start_year, end_year):
    """Convert start/end years to academic year string"""
    return f"{start_year}/{end_year}"

def get_days_between(start_date, end_date):
    """Get number of days between two dates"""
    if not start_date or not end_date:
        return 0
    return (end_date - start_date).days

def format_date(date_obj, format_str='%B %d, %Y'):
    """Format date object to string"""
    if not date_obj:
        return ''
    return date_obj.strftime(format_str)

def parse_date(date_str, format_str='%Y-%m-%d'):
    """Parse date string to date object"""
    try:
        return datetime.strptime(date_str, format_str).date()
    except:
        return None

# ============================================
# DATA VALIDATION UTILITIES
# ============================================

def validate_academic_year(year_str):
    """Validate academic year format (YYYY/YYYY)"""
    pattern = r'^\d{4}/\d{4}$'
    if not re.match(pattern, year_str):
        return False, "Academic year must be in format YYYY/YYYY"
    
    try:
        start, end = map(int, year_str.split('/'))
        if end != start + 1:
            return False, "The second year should be exactly one year after the first"
        return True, "Valid"
    except:
        return False, "Invalid academic year"

def validate_email(email):
    """Validate email address"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return bool(re.match(pattern, email))

def validate_phone(phone):
    """Validate Ghanaian phone number"""
    pattern = r'^(?:\+233|0)[235]\d{8}$'
    return bool(re.match(pattern, phone))

def validate_student_id(student_id):
    """Validate student ID format"""
    pattern = r'^[A-Z]{2,3}\d{3,5}$'
    return bool(re.match(pattern, student_id))

def validate_percentage(value):
    """Validate percentage value (0-100)"""
    try:
        num = float(value)
        return 0 <= num <= 100
    except:
        return False

def validate_score(value, max_score=100):
    """Validate score value"""
    try:
        num = float(value)
        return 0 <= num <= max_score
    except:
        return False

# ============================================
# DATA FORMATTING UTILITIES
# ============================================

def format_name(first_name, last_name, middle_name=''):
    """Format full name"""
    parts = []
    if first_name:
        parts.append(first_name)
    if middle_name:
        parts.append(middle_name)
    if last_name:
        parts.append(last_name)
    return ' '.join(parts)

def truncate_text(text, length=100, suffix='...'):
    """Truncate text to specified length"""
    if not text:
        return ''
    if len(text) <= length:
        return text
    return text[:length].rsplit(' ', 1)[0] + suffix

def format_file_size(size_in_bytes):
    """Format file size in human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_in_bytes < 1024.0:
            return f"{size_in_bytes:.1f} {unit}"
        size_in_bytes /= 1024.0
    return f"{size_in_bytes:.1f} TB"

def generate_avatar_url(name, size=100, background='007bff', color='ffffff'):
    """Generate avatar URL from name"""
    # Simple implementation - you can use a service like Gravatar or DiceBear
    initials = ''.join([part[0].upper() for part in name.split()[:2]]) if name else '?'
    return f"https://ui-avatars.com/api/?name={initials}&size={size}&background={background}&color={color}&bold=true"

# ============================================
# REPORT CARD SPECIFIC UTILITIES
# ============================================

def calculate_report_card_average(grades):
    """Calculate average score from grades"""
    if not grades:
        return 0.0
    
    total_scores = [grade.total_score for grade in grades if grade.total_score is not None]
    if not total_scores:
        return 0.0
    
    return sum(total_scores) / len(total_scores)

def get_attendance_summary(student, academic_year, term):
    """Get attendance summary for student"""
    from core.models import StudentAttendance, AcademicTerm
    
    try:
        academic_term = AcademicTerm.objects.filter(
            academic_year=academic_year,
            term=term
        ).first()
        
        if not academic_term:
            return {
                'total_days': 0,
                'present_days': 0,
                'absence_count': 0,
                'attendance_rate': 0,
            }
        
        attendance_records = StudentAttendance.objects.filter(
            student=student,
            term=academic_term
        )
        
        total_days = attendance_records.count()
        if total_days == 0:
            return {
                'total_days': 0,
                'present_days': 0,
                'absence_count': 0,
                'attendance_rate': 0,
            }
        
        present_days = attendance_records.filter(
            Q(status='present') | Q(status='late') | Q(status='excused')
        ).count()
        
        absence_count = attendance_records.filter(status='absent').count()
        attendance_rate = round((present_days / total_days) * 100, 1)
        
        return {
            'total_days': total_days,
            'present_days': present_days,
            'absence_count': absence_count,
            'attendance_rate': attendance_rate,
        }
    except Exception as e:
        logger.error(f"Error getting attendance summary: {str(e)}")
        return {
            'total_days': 0,
            'present_days': 0,
            'absence_count': 0,
            'attendance_rate': 0,
        }

def get_student_position_in_class(student, academic_year, term):
    """Calculate student's position in class"""
    try:
        from core.models import Student, Grade
        
        classmates = Student.objects.filter(
            class_level=student.class_level,
            is_active=True
        ).exclude(pk=student.pk)
        
        student_scores = []
        
        # Get current student's average
        current_grades = Grade.objects.filter(
            student=student,
            academic_year=academic_year,
            term=term
        )
        current_avg = current_grades.aggregate(avg=Avg('total_score'))['avg'] or 0
        student_scores.append({
            'student': student,
            'average_score': float(current_avg)
        })
        
        # Get classmates' averages
        for classmate in classmates:
            grades = Grade.objects.filter(
                student=classmate,
                academic_year=academic_year,
                term=term
            )
            if grades.exists():
                avg_score = grades.aggregate(avg=Avg('total_score'))['avg'] or 0
                student_scores.append({
                    'student': classmate,
                    'average_score': float(avg_score)
                })
        
        # Sort by average score descending
        student_scores.sort(key=lambda x: x['average_score'], reverse=True)
        
        # Find current student's position
        for index, score_data in enumerate(student_scores, 1):
            if score_data['student'] == student:
                if index == 1:
                    return "1st"
                elif index == 2:
                    return "2nd" 
                elif index == 3:
                    return "3rd"
                else:
                    return f"{index}th"
        
        return "Not ranked"
        
    except Exception as e:
        logger.error(f"Error calculating class position: {str(e)}")
        return "Not ranked"

# ============================================
# EMAIL UTILITIES
# ============================================

def send_email(subject, message, recipient, html_message=None, from_email=None):
    """
    Send an email using Django's email backend
    """
    try:
        if from_email is None:
            from_email = settings.DEFAULT_FROM_EMAIL
        
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[recipient] if isinstance(recipient, str) else recipient,
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        logger.error(f"Error sending email: {e}")
        return False

def send_email_template(subject, template_name, context, recipient, from_email=None):
    """
    Send an email using a Django template
    """
    try:
        # Render HTML content from template
        html_message = render_to_string(template_name, context)
        # Create plain text version by stripping HTML tags
        plain_message = strip_tags(html_message)
        
        return send_email(
            subject=subject,
            message=plain_message,
            recipient=recipient,
            html_message=html_message,
            from_email=from_email
        )
    except Exception as e:
        logger.error(f"Error sending template email: {e}")
        return False

# ============================================
# SECURITY & HASHING UTILITIES
# ============================================

def generate_hash(data):
    """Generate SHA256 hash of data"""
    if isinstance(data, dict):
        data = json.dumps(data, sort_keys=True)
    return hashlib.sha256(str(data).encode()).hexdigest()

def mask_sensitive_data(text, visible_chars=4):
    """Mask sensitive data (like phone numbers, emails)"""
    if not text:
        return ''
    
    if '@' in text:  # Email
        local, domain = text.split('@')
        if len(local) <= 2:
            return f"{'*' * len(local)}@{domain}"
        return f"{local[0]}***{local[-1]}@{domain}"
    elif text.replace('+', '').isdigit():  # Phone number
        if len(text) <= visible_chars:
            return '*' * len(text)
        return f"{'*' * (len(text) - visible_chars)}{text[-visible_chars:]}"
    else:
        if len(text) <= visible_chars:
            return '*' * len(text)
        return f"{text[:visible_chars]}{'*' * (len(text) - visible_chars)}"

# ============================================
# TEMPLATE CONTEXT UTILITIES
# ============================================

def get_base_context(request):
    """Get base context data for templates"""
    context = {
        'current_year': timezone.now().year,
        'current_date': timezone.now().date(),
        'current_academic_year': get_current_academic_year(),
        'current_term': get_current_term(),
        'is_teacher': is_teacher(request.user) if request.user.is_authenticated else False,
        'is_admin': is_admin(request.user) if request.user.is_authenticated else False,
        'is_student': is_student(request.user) if request.user.is_authenticated else False,
        'is_parent': is_parent(request.user) if request.user.is_authenticated else False,
        'user_role': get_user_role(request.user) if request.user.is_authenticated else 'anonymous',
    }
    return context

# ============================================
# ERROR HANDLING UTILITIES
# ============================================

class ValidationError(Exception):
    """Custom validation error"""
    def __init__(self, message, field=None):
        self.message = message
        self.field = field
        super().__init__(self.message)

def handle_exception(e, context=None):
    """Handle exceptions with logging and user-friendly messages"""
    logger.error(f"Exception: {str(e)}", exc_info=True)
    
    if context:
        logger.error(f"Context: {context}")
    
    # Return user-friendly message
    if isinstance(e, ValidationError):
        return str(e)
    else:
        return "An unexpected error occurred. Please try again or contact support."

# ============================================
# SYSTEM STATISTICS UTILITIES
# ============================================

def get_system_stats():
    """Get system statistics"""
    from core.models import Student, Teacher, ParentGuardian, Subject
    
    try:
        return {
            'total_students': Student.objects.filter(is_active=True).count(),
            'total_teachers': Teacher.objects.filter(is_active=True).count(),
            'total_parents': ParentGuardian.objects.count(),
            'total_subjects': Subject.objects.count(),
            'active_academic_year': get_current_academic_year(),
            'current_term': get_current_term(),
        }
    except Exception as e:
        logger.error(f"Error getting system stats: {str(e)}")
        return {}