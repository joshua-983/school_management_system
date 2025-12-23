"""
Data validation utilities.
"""
from .main import (
    validate_academic_year, validate_email, validate_phone,
    validate_student_id, validate_percentage, validate_score
)

__all__ = [
    'validate_academic_year', 'validate_email', 'validate_phone',
    'validate_student_id', 'validate_percentage', 'validate_score'
]