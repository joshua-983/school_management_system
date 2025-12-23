# core/grading_utils.py
import logging
from decimal import Decimal, InvalidOperation
from typing import Dict, List, Optional, Tuple, Any
from django.db import transaction
from django.db.models import Avg, Count, Q, F, ExpressionWrapper, FloatField
from django.utils import timezone
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.core.cache import cache

from .models import Grade, Student, Subject, AcademicTerm, SchoolConfiguration
from .exceptions import GradingSystemException, DataValidationError
from core.models.configuration import SchoolConfiguration

logger = logging.getLogger(__name__)

def get_grading_system():
    """Get the currently active grading system"""
    try:
        config = SchoolConfiguration.get_config()
        return config.grading_system
    except Exception as e:
        logger.error(f"Error getting grading system: {str(e)}")
        return 'GES'  # Default to GES if there's an error

def calculate_ges_grade(score):
    """Calculate GES grade (1-9)"""
    if score is None:
        return 'N/A'
    
    try:
        score = float(score)
        if score >= 90: return '1'
        elif score >= 80: return '2'
        elif score >= 70: return '3'
        elif score >= 60: return '4'
        elif score >= 50: return '5'
        elif score >= 40: return '6'
        elif score >= 30: return '7'
        elif score >= 20: return '8'
        else: return '9'
    except (ValueError, TypeError):
        return 'N/A'

def calculate_letter_grade(score):
    """Calculate letter grade (A-F)"""
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
        else: return 'F'
    except (ValueError, TypeError):
        return 'N/A'

def get_grade_descriptions():
    """Get descriptions for both grading systems"""
    return {
        'GES': {
            '1': 'Excellent - Outstanding performance',
            '2': 'Very Good - Strong performance',
            '3': 'Good - Above average performance',
            '4': 'Satisfactory - Meets expectations',
            '5': 'Fair - Needs improvement',
            '6': 'Marginal - Below expectations',
            '7': 'Poor - Significant improvement needed',
            '8': 'Very Poor - Concerning performance',
            '9': 'Fail - Immediate intervention required',
            'N/A': 'Grade not available'
        },
        'LETTER': {
            'A+': 'Excellent - Outstanding performance',
            'A': 'Excellent - Strong performance',
            'B+': 'Very Good - Above average',
            'B': 'Good - Meets expectations',
            'C+': 'Satisfactory - Average performance',
            'C': 'Fair - Needs improvement',
            'D+': 'Marginal - Below expectations',
            'D': 'Poor - Significant improvement needed',
            'F': 'Fail - Immediate intervention required',
            'N/A': 'Grade not available'
        }
    }

def get_all_grades(score):
    """Calculate both GES and Letter grades for a score"""
    return {
        'ges_grade': calculate_ges_grade(score),
        'letter_grade': calculate_letter_grade(score),
        'score': score,
        'is_passing': score >= 40.0 if score is not None else False
    }

def get_display_grade(ges_grade, letter_grade):
    """Get the grade to display based on system configuration"""
    grading_system = get_grading_system()
    
    if grading_system == 'GES':
        return ges_grade or 'N/A'
    elif grading_system == 'LETTER':
        return letter_grade or 'N/A'
    else:  # BOTH
        ges_display = ges_grade or 'N/A'
        letter_display = letter_grade or 'N/A'
        return f"{ges_display} ({letter_display})"

def get_grade_description(ges_grade, letter_grade):
    """Get grade description based on active system"""
    grading_system = get_grading_system()
    descriptions = get_grade_descriptions()
    
    if grading_system == 'GES':
        return descriptions['GES'].get(ges_grade, 'Not graded')
    elif grading_system == 'LETTER':
        return descriptions['LETTER'].get(letter_grade, 'Not graded')
    else:
        ges_desc = descriptions['GES'].get(ges_grade, 'Not graded')
        letter_desc = descriptions['LETTER'].get(letter_grade, 'Not graded')
        return f"GES: {ges_desc} | Letter: {letter_desc}"

def get_grade_color(ges_grade):
    """Get color for grade display"""
    if not ges_grade or ges_grade == 'N/A':
        return 'secondary'
    
    colors = {
        '1': 'success',    # Green
        '2': 'success',    # Green
        '3': 'info',       # Blue
        '4': 'info',       # Blue
        '5': 'warning',    # Yellow
        '6': 'warning',    # Yellow
        '7': 'danger',     # Red
        '8': 'danger',     # Red
        '9': 'danger',     # Red
    }
    return colors.get(ges_grade, 'secondary')

def calculate_class_performance(subject, class_level, academic_year, term):
    """
    Calculate comprehensive class performance statistics using current grading system
    """
    grades = Grade.objects.filter(
        subject=subject,
        student__class_level=class_level,
        academic_year=academic_year,
        term=term
    ).exclude(total_score__isnull=True)
    
    if not grades.exists():
        return None
    
    scores = [float(grade.total_score) for grade in grades if grade.total_score]
    total_students = len(scores)
    
    # Calculate basic statistics
    average_score = round(sum(scores) / total_students, 2)
    highest_score = max(scores)
    lowest_score = min(scores)
    
    # Calculate grade distribution based on current system
    grading_system = get_grading_system()
    
    if grading_system == 'GES':
        grade_distribution = {
            '1': len([s for s in scores if s >= 90]),
            '2': len([s for s in scores if 80 <= s < 90]),
            '3': len([s for s in scores if 70 <= s < 80]),
            '4': len([s for s in scores if 60 <= s < 70]),
            '5': len([s for s in scores if 50 <= s < 60]),
            '6': len([s for s in scores if 40 <= s < 50]),
            '7': len([s for s in scores if 30 <= s < 40]),
            '8': len([s for s in scores if 20 <= s < 30]),
            '9': len([s for s in scores if s < 20]),
        }
    else:  # LETTER or BOTH
        grade_distribution = {
            'A+': len([s for s in scores if s >= 90]),
            'A': len([s for s in scores if 80 <= s < 90]),
            'B+': len([s for s in scores if 70 <= s < 80]),
            'B': len([s for s in scores if 60 <= s < 70]),
            'C+': len([s for s in scores if 50 <= s < 60]),
            'C': len([s for s in scores if 40 <= s < 50]),
            'D+': len([s for s in scores if 30 <= s < 40]),
            'D': len([s for s in scores if 20 <= s < 30]),
            'F': len([s for s in scores if s < 20]),
        }
    
    # Calculate passing rate (40% and above is passing in both systems)
    passing_count = len([s for s in scores if s >= 40])
    passing_rate = round((passing_count / total_students) * 100, 1)
    
    return {
        'total_students': total_students,
        'average_score': average_score,
        'highest_score': highest_score,
        'lowest_score': lowest_score,
        'grade_distribution': grade_distribution,
        'passing_rate': passing_rate,
        'grading_system': grading_system,
    }