# custom_filters.py
from django import template
from django.utils import timezone
from core.models import Subject
from datetime import datetime, date

register = template.Library()

@register.filter
def subtract(value, arg):
    """Subtract the argument from the value"""
    try:
        return float(value) - float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def get_item(dictionary, key):
    """Get dictionary item by key in templates - returns empty dict if not found"""
    if dictionary is None:
        return {}
    return dictionary.get(key, {})

@register.filter
def is_admin(user):
    """Check if user is in Admin group or is superuser"""
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name='Admin').exists() or user.is_superuser

@register.filter
def is_teacher(user):
    """Check if user is in Teacher group"""
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name='Teacher').exists()

@register.filter
def is_student(user):
    """Check if user is in Student group"""
    if not user or not user.is_authenticated:
        return False
    return user.groups.filter(name='Student').exists()

@register.filter
def multiply(value, arg):
    """Multiply the value by the argument"""
    try:
        return float(value) * float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def divide(value, arg):
    """Divide the value by the argument"""
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (ValueError, TypeError):
        return 0

@register.filter
def in_list(value, arg):
    """Check if value is in the comma-separated list"""
    if not value or not arg:
        return False
    return str(value) in arg.split(',')

@register.filter
def get_class_level_display(class_level):
    """Get display name for class level"""
    from core.models import CLASS_LEVEL_CHOICES
    return dict(CLASS_LEVEL_CHOICES).get(class_level, class_level)

@register.filter
def percentage(value, total):
    """Calculate percentage of value from total"""
    try:
        if float(total) == 0:
            return 0
        return (float(value) / float(total)) * 100
    except (ValueError, TypeError):
        return 0

@register.filter
def round_value(value, decimals=0):
    """Round value to specified decimal places"""
    try:
        return round(float(value), int(decimals))
    except (ValueError, TypeError):
        return value

@register.filter
def default_if_none(value, default):
    """Return default value if value is None"""
    return value if value is not None else default

@register.filter
def format_grade(value):
    """Format grade value for display"""
    try:
        return f"{float(value):.1f}"
    except (ValueError, TypeError):
        return value

@register.filter
def can_edit_grade(user, grade):
    """Check if user can edit a specific grade"""
    if not user or not user.is_authenticated:
        return False
    
    if user.is_superuser or user.groups.filter(name='Admin').exists():
        return True
    
    if hasattr(user, 'teacher') and grade.teacher == user.teacher:
        return True
    
    return False

@register.filter
def get_range(value):
    """Get range for template loops"""
    return range(value)

@register.filter
def add_class(field, css_class):
    """Add CSS class to form field"""
    return field.as_widget(attrs={"class": css_class})

@register.filter
def get_type(value):
    """Get type of variable"""
    return type(value).__name__

@register.filter(name='dict_key')
def dict_key(dictionary, key):
    """Get dictionary value by key, returns empty list if not found"""
    if dictionary is None:
        return []
    return dictionary.get(key, [])

# NEW FILTERS ADDED BELOW

@register.filter
def days_since(value):
    """Calculate days since a date"""
    if not value:
        return 0
    try:
        # Handle both datetime and date objects
        if isinstance(value, datetime):
            delta = timezone.now().date() - value.date()
        elif isinstance(value, date):
            delta = timezone.now().date() - value
        else:
            # Try to parse string
            try:
                value_date = datetime.strptime(str(value), '%Y-%m-%d').date()
                delta = timezone.now().date() - value_date
            except ValueError:
                # Try with timezone datetime format
                if hasattr(value, 'date'):
                    delta = timezone.now().date() - value.date()
                else:
                    return 0
        return abs(delta.days)
    except (ValueError, TypeError):
        return 0

@register.filter
def get_subject_name(subject_id):
    """Get subject name from ID"""
    try:
        subject = Subject.objects.get(id=subject_id)
        return subject.name
    except (Subject.DoesNotExist, ValueError, TypeError):
        return "Unknown"

@register.filter
def pluralize(value, suffix='s'):
    """Add plural suffix if value is not 1"""
    try:
        if int(value) == 1:
            return ''
        return suffix
    except (ValueError, TypeError):
        return suffix

@register.filter
def timesince_simple(value):
    """Simple timesince filter that returns formatted string"""
    if not value:
        return "N/A"
    
    days = days_since(value)
    if days == 0:
        return "Today"
    elif days == 1:
        return "1 day ago"
    else:
        return f"{days} days ago"

@register.filter
def is_overdue(due_date):
    """Check if a due date is overdue"""
    if not due_date:
        return False
    try:
        if isinstance(due_date, datetime):
            return due_date < timezone.now()
        elif isinstance(due_date, date):
            return due_date < timezone.now().date()
        return False
    except (ValueError, TypeError):
        return False

@register.filter
def get_due_status(due_date):
    """Get status badge class based on due date"""
    if not due_date:
        return "secondary"
    
    if not is_overdue(due_date):
        return "success"
    
    days = days_since(due_date)
    if days >= 14:
        return "danger"
    elif days >= 7:
        return "warning"
    else:
        return "info"

@register.filter
def format_date(value, format_str="M d, Y"):
    """Format date with custom format"""
    if not value:
        return ""
    try:
        if isinstance(value, (datetime, date)):
            return value.strftime(format_str)
        return value
    except (ValueError, AttributeError):
        return value

@register.filter
def safe_int(value, default=0):
    """Safely convert to integer"""
    try:
        return int(value)
    except (ValueError, TypeError):
        return default

@register.filter
def is_empty(value):
    """Check if value is empty (None, empty string, empty list/dict)"""
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, dict, tuple)) and len(value) == 0:
        return True
    return False

@register.filter
def truncate_chars(value, max_chars=50):
    """Truncate string to max characters"""
    if not value:
        return ""
    if len(str(value)) <= max_chars:
        return value
    return str(value)[:max_chars] + "..."

# UPDATED REPLACE FILTER
@register.filter
def replace(value, arg):
    """Replace substring in string - usage: {{ value|replace:"old:new" }}"""
    if not value:
        return ""
    
    if ':' not in arg:
        return str(value)
    
    try:
        old, new = arg.split(':', 1)
        return str(value).replace(str(old), str(new))
    except ValueError:
        return str(value)


@register.filter
def shorten_timetable(value):
    """Shorten 'Timetable ' to 'T ' in group names"""
    if not value:
        return ""
    return str(value).replace("Timetable ", "T ")
