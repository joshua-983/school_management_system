# core/templatetags/assignment_filters.py
from django import template

register = template.Library()

@register.filter
def filter_status(assignments, status):
    """Filter assignments by status"""
    if assignments:
        return [a for a in assignments if a.get('status') == status]
    return []

@register.filter
def subtract(value, arg):
    """Subtract arg from value"""
    try:
        return value - arg
    except (TypeError, ValueError):
        return 0

@register.filter
def get_item(dictionary, key):
    """Get item from dictionary"""
    if dictionary:
        return dictionary.get(key)
    return None

@register.filter
def percentage(value, total):
    """Calculate percentage"""
    try:
        if total == 0:
            return 0
        return (value / total) * 100
    except (TypeError, ValueError, ZeroDivisionError):
        return 0