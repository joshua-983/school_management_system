# models/base.py
"""
Base classes, constants, and utility functions shared across all models.
"""
import os
import logging
from datetime import date, timedelta
from decimal import Decimal
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

logger = logging.getLogger(__name__)

# ===== SHARED CONSTANTS =====
GENDER_CHOICES = [
    ('M', 'Male'),
    ('F', 'Female'),
]

CLASS_LEVEL_CHOICES = [
    ('P1', 'Primary 1'),
    ('P2', 'Primary 2'),
    ('P3', 'Primary 3'),
    ('P4', 'Primary 4'),
    ('P5', 'Primary 5'),
    ('P6', 'Primary 6'),
    ('J1', 'JHS 1'),
    ('J2', 'JHS 2'),
    ('J3', 'JHS 3'),
]

CLASS_LEVEL_DISPLAY_MAP = dict(CLASS_LEVEL_CHOICES)

# === ACADEMIC PERIOD CONSTANTS ===
# Original TERM_CHOICES kept for backward compatibility
TERM_CHOICES = [
    (1, 'Term 1'),
    (2, 'Term 2'),
    (3, 'Term 3'),
]

# NEW: Academic Period System Choices
ACADEMIC_PERIOD_SYSTEM_CHOICES = [
    ('TERM', '3-Term System'),
    ('SEMESTER', '2-Semester System'),
    ('QUARTER', '4-Quarter System'),
    ('TRIMESTER', '3-Trimester System'),
    ('CUSTOM', 'Custom System'),
]

# NEW: Period choices for each system
PERIOD_CHOICES_BY_SYSTEM = {
    'TERM': [
        (1, 'Term 1'),
        (2, 'Term 2'),
        (3, 'Term 3'),
    ],
    'SEMESTER': [
        (1, 'Semester 1'),
        (2, 'Semester 2'),
    ],
    'QUARTER': [
        (1, 'Quarter 1'),
        (2, 'Quarter 2'),
        (3, 'Quarter 3'),
        (4, 'Quarter 4'),
    ],
    'TRIMESTER': [
        (1, 'Trimester 1'),
        (2, 'Trimester 2'),
        (3, 'Trimester 3'),
    ],
    'CUSTOM': [
        (1, 'Period 1'),
        (2, 'Period 2'),
        (3, 'Period 3'),
        (4, 'Period 4'),
        (5, 'Period 5'),
        (6, 'Period 6'),
    ]
}

# Helper function to get period choices
def get_period_choices_for_system(system='TERM'):
    """Get period choices for a specific academic period system."""
    return PERIOD_CHOICES_BY_SYSTEM.get(system, TERM_CHOICES)

# Helper function to get period display name
def get_period_display(system, period_number):
    """Get display name for a period based on system and number."""
    if system not in PERIOD_CHOICES_BY_SYSTEM:
        return f"Period {period_number}"
    
    choices = dict(PERIOD_CHOICES_BY_SYSTEM[system])
    return choices.get(period_number, f"Period {period_number}")

# Image path functions
def student_image_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{instance.student_id}.{ext}"
    return os.path.join('students', filename)

def teacher_image_path(instance, filename):
    return f'teachers/{instance.employee_id}/{filename}'

def parent_image_path(instance, filename):
    return f'parents/{instance.parent_id}/{filename}'

class GhanaEducationMixin:
    """Mixin for Ghana Education Service specific functionality"""
    
    def get_ghana_academic_calendar(self):
        """Get current Ghana academic calendar structure"""
        current_year = timezone.now().year
        next_year = current_year + 1
        
        # Ghana Education Service Standard Calendar
        ghana_calendar = {
            'academic_year': f"{current_year}/{next_year}",
            'terms': {
                1: {
                    'name': 'Term 1',
                    'start_date': date(current_year, 9, 2),
                    'end_date': date(current_year, 12, 18),
                    'mid_term_break': date(current_year, 10, 16),
                },
                2: {
                    'name': 'Term 2', 
                    'start_date': date(next_year, 1, 8),
                    'end_date': date(next_year, 4, 1),
                    'mid_term_break': date(next_year, 2, 15),
                },
                3: {
                    'name': 'Term 3',
                    'start_date': date(next_year, 4, 21),
                    'end_date': date(next_year, 7, 23),
                    'mid_term_break': date(next_year, 6, 1),
                }
            }
        }
        return ghana_calendar
    
    def is_ghana_school_day(self, check_date):
        """
        Check if date is a valid school day in Ghana
        """
        if check_date.weekday() >= 5:
            return False
        
        # Ghana public holidays
        ghana_holidays = [
            date(check_date.year, 1, 1),
            date(check_date.year, 3, 6),
            date(check_date.year, 5, 1),
            date(check_date.year, 7, 1),
            date(check_date.year, 12, 25),
            date(check_date.year, 12, 26),
        ]
        
        return check_date not in ghana_holidays