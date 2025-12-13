# core/templatetags/assignment_filters.py
from django import template
from django.utils import timezone
from datetime import timedelta
import math

register = template.Library()

# ==============================
# STATUS FILTERS
# ==============================

@register.filter
def filter_status(assignments, status):
    """Filter assignments by status"""
    if assignments:
        return [a for a in assignments if a.get('status') == status]
    return []

@register.filter
def filter_by_status(queryset, status):
    """Filter Django queryset by status"""
    if queryset:
        return queryset.filter(status=status)
    return queryset.none()

@register.filter
def has_status(assignment, status):
    """Check if assignment has specific status"""
    if hasattr(assignment, 'status'):
        return assignment.status == status
    return False

@register.filter
def get_status_display(status):
    """Get human readable status"""
    status_map = {
        'PENDING': 'Pending',
        'SUBMITTED': 'Submitted',
        'GRADED': 'Graded',
        'LATE': 'Late Submission',
        'OVERDUE': 'Overdue',
    }
    return status_map.get(status, status)

# ==============================
# DATE AND TIME FILTERS
# ==============================

@register.filter
def is_overdue(assignment):
    """Check if assignment is overdue"""
    if hasattr(assignment, 'assignment'):
        due_date = assignment.assignment.due_date
    elif hasattr(assignment, 'due_date'):
        due_date = assignment.due_date
    else:
        return False
    
    return due_date < timezone.now()

@register.filter
def days_until_due(assignment):
    """Calculate days until assignment is due"""
    if hasattr(assignment, 'assignment'):
        due_date = assignment.assignment.due_date
    elif hasattr(assignment, 'due_date'):
        due_date = assignment.due_date
    else:
        return None
    
    now = timezone.now()
    delta = due_date - now
    return delta.days

@register.filter
def due_soon(assignment):
    """Check if assignment is due within 3 days"""
    days_left = days_until_due(assignment)
    return days_left is not None and 0 <= days_left <= 3

@register.filter
def format_due_date(assignment):
    """Format due date for display"""
    if hasattr(assignment, 'assignment'):
        due_date = assignment.assignment.due_date
    elif hasattr(assignment, 'due_date'):
        due_date = assignment.due_date
    else:
        return "No due date"
    
    now = timezone.now()
    if due_date < now:
        return f"Overdue - {due_date.strftime('%b %d, %Y')}"
    
    days_left = (due_date - now).days
    if days_left == 0:
        return "Due today"
    elif days_left == 1:
        return "Due tomorrow"
    elif days_left <= 7:
        return f"Due in {days_left} days"
    else:
        return due_date.strftime("%b %d, %Y")

@register.filter
def time_ago(date):
    """Get relative time string"""
    if not date:
        return ""
    
    now = timezone.now()
    diff = now - date
    
    if diff.days > 365:
        years = diff.days // 365
        return f"{years} year{'s' if years > 1 else ''} ago"
    elif diff.days > 30:
        months = diff.days // 30
        return f"{months} month{'s' if months > 1 else ''} ago"
    elif diff.days > 0:
        return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
    elif diff.seconds > 3600:
        hours = diff.seconds // 3600
        return f"{hours} hour{'s' if hours > 1 else ''} ago"
    elif diff.seconds > 60:
        minutes = diff.seconds // 60
        return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    else:
        return "Just now"

# ==============================
# DOCUMENT AND ATTACHMENT FILTERS
# ==============================

@register.filter
def has_document(assignment):
    """Check if assignment has document attachment"""
    if hasattr(assignment, 'assignment'):
        return bool(assignment.assignment.attachment)
    elif hasattr(assignment, 'attachment'):
        return bool(assignment.attachment)
    return False

@register.filter
def document_type(assignment):
    """Get document type from filename"""
    if hasattr(assignment, 'assignment'):
        attachment = assignment.assignment.attachment
    elif hasattr(assignment, 'attachment'):
        attachment = assignment.attachment
    else:
        return "Unknown"
    
    if not attachment:
        return "No document"
    
    filename = str(attachment).lower()
    if filename.endswith('.pdf'):
        return "PDF"
    elif filename.endswith('.docx'):
        return "Word"
    elif filename.endswith('.doc'):
        return "Word"
    elif filename.endswith('.txt'):
        return "Text"
    elif filename.endswith('.jpg') or filename.endswith('.jpeg') or filename.endswith('.png'):
        return "Image"
    elif filename.endswith('.xlsx') or filename.endswith('.xls'):
        return "Excel"
    elif filename.endswith('.pptx') or filename.endswith('.ppt'):
        return "PowerPoint"
    else:
        return "Document"

@register.filter
def file_size(assignment):
    """Get human readable file size"""
    if hasattr(assignment, 'assignment'):
        attachment = assignment.assignment.attachment
    elif hasattr(assignment, 'attachment'):
        attachment = assignment.attachment
    else:
        return ""
    
    if not attachment:
        return ""
    
    try:
        size = attachment.size
    except (AttributeError, OSError):
        return "Unknown size"
    
    if size < 1024:
        return f"{size} B"
    elif size < 1024 * 1024:
        return f"{size / 1024:.1f} KB"
    elif size < 1024 * 1024 * 1024:
        return f"{size / (1024 * 1024):.1f} MB"
    else:
        return f"{size / (1024 * 1024 * 1024):.1f} GB"

# ==============================
# SCORE AND GRADE FILTERS
# ==============================

@register.filter
def score_percentage(assignment):
    """Calculate score percentage"""
    if not hasattr(assignment, 'score') or not hasattr(assignment, 'assignment'):
        return 0
    
    if assignment.score is None or assignment.assignment.max_score == 0:
        return 0
    
    return (assignment.score / assignment.assignment.max_score) * 100

@register.filter
def grade_letter(assignment):
    """Get grade letter based on percentage"""
    percentage = score_percentage(assignment)
    
    if percentage >= 90:
        return "A+"
    elif percentage >= 85:
        return "A"
    elif percentage >= 80:
        return "A-"
    elif percentage >= 75:
        return "B+"
    elif percentage >= 70:
        return "B"
    elif percentage >= 65:
        return "C+"
    elif percentage >= 60:
        return "C"
    elif percentage >= 55:
        return "D+"
    elif percentage >= 50:
        return "D"
    else:
        return "F"

@register.filter
def grade_color(assignment):
    """Get color based on grade"""
    percentage = score_percentage(assignment)
    
    if percentage >= 80:
        return "success"
    elif percentage >= 60:
        return "warning"
    else:
        return "danger"

# ==============================
# MATHEMATICAL OPERATIONS
# ==============================

@register.filter
def subtract(value, arg):
    """Subtract arg from value"""
    try:
        return float(value) - float(arg)
    except (TypeError, ValueError):
        return 0

@register.filter
def add(value, arg):
    """Add arg to value"""
    try:
        return float(value) + float(arg)
    except (TypeError, ValueError):
        return value

@register.filter
def multiply(value, arg):
    """Multiply value by arg"""
    try:
        return float(value) * float(arg)
    except (TypeError, ValueError):
        return 0

@register.filter
def divide(value, arg):
    """Divide value by arg"""
    try:
        if float(arg) == 0:
            return 0
        return float(value) / float(arg)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0

@register.filter
def percentage(value, total):
    """Calculate percentage"""
    try:
        if total == 0:
            return 0
        return (float(value) / float(total)) * 100
    except (TypeError, ValueError, ZeroDivisionError):
        return 0

@register.filter
def round_number(value, decimals=2):
    """Round number to specified decimals"""
    try:
        return round(float(value), int(decimals))
    except (TypeError, ValueError):
        return value

# ==============================
# DICTIONARY AND LIST OPERATIONS
# ==============================

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary"""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None

@register.filter
def dict_key_exists(dictionary, key):
    """Check if key exists in dictionary"""
    return isinstance(dictionary, dict) and key in dictionary

@register.filter
def list_length(items):
    """Get length of list"""
    if items:
        return len(items)
    return 0

@register.filter
def slice_list(items, count):
    """Slice list to specified count"""
    if items:
        return items[:int(count)]
    return []

@register.filter
def join_list(items, separator=", "):
    """Join list with separator"""
    if items:
        return separator.join(str(item) for item in items)
    return ""

# ==============================
# FORMATTING FILTERS
# ==============================

@register.filter
def format_currency(value):
    """Format value as currency"""
    try:
        return f"GH₵{float(value):,.2f}"
    except (TypeError, ValueError):
        return f"GH₵0.00"

@register.filter
def truncate_text(text, length=100):
    """Truncate text to specified length"""
    if not text:
        return ""
    
    if len(text) <= length:
        return text
    
    return text[:length] + "..."

@register.filter
def capitalize_words(text):
    """Capitalize each word in text"""
    if not text:
        return ""
    return ' '.join(word.capitalize() for word in str(text).split())

@register.filter
def replace(value, args):
    """Replace characters in string"""
    if not value:
        return ""
    
    try:
        old, new = args.split(',')
        return str(value).replace(old.strip(), new.strip())
    except (ValueError, AttributeError):
        return value

# ==============================
# BOOLEAN AND CONDITIONAL FILTERS
# ==============================

@register.filter
def is_empty(value):
    """Check if value is empty"""
    if isinstance(value, (list, tuple, dict, set)):
        return len(value) == 0
    return not bool(value)

@register.filter
def default_if_empty(value, default):
    """Return default if value is empty"""
    if is_empty(value):
        return default
    return value

@register.filter
def yesno(value, args):
    """Return yes or no based on boolean value"""
    try:
        yes_text, no_text = args.split(',')
    except ValueError:
        yes_text, no_text = 'Yes', 'No'
    
    return yes_text.strip() if bool(value) else no_text.strip()

# ==============================
# ASSIGNMENT-SPECIFIC FILTERS
# ==============================

@register.filter
def assignment_progress(assignment):
    """Calculate assignment progress percentage"""
    if hasattr(assignment, 'status'):
        status_map = {
            'PENDING': 25,
            'LATE': 50,
            'SUBMITTED': 75,
            'GRADED': 100,
        }
        return status_map.get(assignment.status, 0)
    return 0

@register.filter
def can_submit(assignment):
    """Check if assignment can be submitted"""
    if not hasattr(assignment, 'status') or not hasattr(assignment, 'assignment'):
        return False
    
    now = timezone.now()
    due_date = assignment.assignment.due_date
    
    # Can submit if status is PENDING and not past due date (or allow late submissions)
    return assignment.status in ['PENDING', 'LATE'] and (now <= due_date or hasattr(assignment.assignment, 'allow_late_submissions'))

@register.filter
def needs_attention(assignment):
    """Check if assignment needs student attention"""
    if not hasattr(assignment, 'status'):
        return False
    
    now = timezone.now()
    if hasattr(assignment, 'assignment'):
        due_date = assignment.assignment.due_date
        days_left = (due_date - now).days if due_date > now else 0
    else:
        days_left = 0
    
    # Needs attention if: pending and due within 3 days, or overdue, or late
    return (assignment.status == 'PENDING' and days_left <= 3) or assignment.status in ['OVERDUE', 'LATE']

@register.filter
def priority_level(assignment):
    """Get priority level for assignment"""
    if not hasattr(assignment, 'status'):
        return "low"
    
    if assignment.status == 'OVERDUE':
        return "high"
    elif assignment.status == 'LATE':
        return "medium-high"
    elif assignment.status == 'PENDING':
        if hasattr(assignment, 'assignment'):
            now = timezone.now()
            due_date = assignment.assignment.due_date
            if due_date <= now + timedelta(days=1):
                return "high"
            elif due_date <= now + timedelta(days=3):
                return "medium"
        return "low"
    else:
        return "completed"

# ==============================
# COMPLEX FILTERS FOR TEMPLATES
# ==============================

@register.filter
def sort_by(queryset, field):
    """Sort queryset by field"""
    if hasattr(queryset, 'order_by'):
        return queryset.order_by(field)
    return queryset

@register.filter
def group_by(items, attribute):
    """Group items by attribute"""
    if not items:
        return {}
    
    grouped = {}
    for item in items:
        key = getattr(item, attribute, None)
        if key not in grouped:
            grouped[key] = []
        grouped[key].append(item)
    
    return grouped

@register.filter
def filter_has_document(assignments):
    """Filter assignments that have documents"""
    if hasattr(assignments, 'filter'):
        return assignments.filter(assignment__attachment__isnull=False)
    else:
        return [a for a in assignments if has_document(a)]

@register.simple_tag
def calculate_average_score(assignments):
    """Calculate average score from graded assignments"""
    graded = [a for a in assignments if hasattr(a, 'score') and a.score is not None]
    if not graded:
        return 0
    
    total = sum(a.score for a in graded)
    return total / len(graded)

@register.simple_tag
def assignment_statistics(assignments):
    """Get comprehensive assignment statistics"""
    stats = {
        'total': len(assignments) if hasattr(assignments, '__len__') else 0,
        'with_docs': 0,
        'submitted': 0,
        'graded': 0,
        'pending': 0,
        'overdue': 0,
    }
    
    if not stats['total']:
        return stats
    
    for assignment in assignments:
        if has_document(assignment):
            stats['with_docs'] += 1
        
        if hasattr(assignment, 'status'):
            if assignment.status in ['SUBMITTED', 'LATE']:
                stats['submitted'] += 1
            elif assignment.status == 'GRADED':
                stats['graded'] += 1
            elif assignment.status == 'PENDING':
                stats['pending'] += 1
        
        if is_overdue(assignment):
            stats['overdue'] += 1
    
    return stats