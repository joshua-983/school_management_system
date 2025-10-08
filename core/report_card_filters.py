from django import template
from django.db.models import Q
from datetime import datetime

register = template.Library()

@register.filter
def filter_by_published(queryset, is_published):
    """Filter report cards by published status"""
    return [item for item in queryset if getattr(item, 'is_published', False) == is_published]

@register.filter
def avg_score(queryset):
    """Calculate average score from a queryset of report cards"""
    if not queryset:
        return 0
    total = sum(getattr(item, 'average_score', 0) for item in queryset if getattr(item, 'average_score', 0) is not None)
    return total / len(queryset) if len(queryset) > 0 else 0

@register.filter
def filter_by_grade(queryset, grade_range):
    """
    Filter report cards by grade range.
    Usage: {{ report_cards|filter_by_grade:"E,D,D+,C" }}
    """
    if not queryset or not grade_range:
        return queryset
    
    grade_list = [grade.strip() for grade in grade_range.split(',')]
    filtered_items = []
    
    for item in queryset:
        item_grade = getattr(item, 'overall_grade', '').strip()
        if item_grade in grade_list:
            filtered_items.append(item)
    
    return filtered_items

@register.filter
def filter_by_current_term(queryset):
    """Filter report cards for the current term"""
    if not queryset:
        return queryset
    
    current_year = datetime.now().year
    next_year = current_year + 1
    current_academic_year = f"{current_year}/{next_year}"
    
    # Assuming current term is Term 2 (you might want to make this dynamic)
    current_term = 2
    
    filtered_items = []
    for item in queryset:
        academic_year = getattr(item, 'academic_year', '')
        term = getattr(item, 'term', 0)
        
        if academic_year == current_academic_year and term == current_term:
            filtered_items.append(item)
    
    return filtered_items

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary by key"""
    return dictionary.get(key)

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
        return float(value) / float(arg)
    except (ValueError, TypeError, ZeroDivisionError):
        return 0

@register.filter
def percentage(value, total):
    """Calculate percentage"""
    try:
        if total == 0:
            return 0
        return (float(value) / float(total)) * 100
    except (ValueError, TypeError):
        return 0

@register.filter
def start_index(page_obj):
    """Get starting index for pagination"""
    if page_obj and hasattr(page_obj, 'start_index'):
        return page_obj.start_index()
    return 1

@register.filter
def end_index(page_obj):
    """Get ending index for pagination"""
    if page_obj and hasattr(page_obj, 'end_index'):
        return page_obj.end_index()
    return 0