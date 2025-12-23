"""
Academic-specific utilities.
"""
from .main import (
    get_current_academic_year, get_class_level_choices, get_class_level_display,
    get_grade_choices, get_term_choices, calculate_letter_grade,
    get_grade_color, get_performance_level, calculate_total_score
)

__all__ = [
    'get_current_academic_year', 'get_class_level_choices', 'get_class_level_display',
    'get_grade_choices', 'get_term_choices', 'calculate_letter_grade',
    'get_grade_color', 'get_performance_level', 'calculate_total_score'
]