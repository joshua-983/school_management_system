from django import template

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
    """Get dictionary item by key in templates"""
    return dictionary.get(key)

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
    from ..models import CLASS_LEVEL_CHOICES
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