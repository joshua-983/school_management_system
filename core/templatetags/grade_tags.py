# core/templatetags/grade_tags.py
from django import template
from core.grading_utils import get_grading_system, get_display_grade, get_grade_description, get_grade_color

register = template.Library()

@register.simple_tag
def get_current_grading_system():
    """Get the currently active grading system"""
    return get_grading_system()

@register.filter
def display_grade(grade):
    """Display grade based on system configuration"""
    if not grade:
        return "N/A"
    return grade.get_display_grade()

@register.filter
def grade_description(grade):
    """Get grade description based on system configuration"""
    if not grade:
        return "Not graded"
    return grade.get_grade_description()

@register.filter
def grade_color(grade):
    """Get color for grade display"""
    if not grade:
        return 'secondary'
    return grade.get_grade_color()

@register.simple_tag
def get_grade_display_config():
    """Get grading system configuration for display"""
    system = get_grading_system()
    if system == 'GES':
        return 'GES Number System (1-9)'
    elif system == 'LETTER':
        return 'Letter System (A-F)'
    else:
        return 'Both Systems (1-9 & A-F)'
