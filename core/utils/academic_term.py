"""
ACADEMIC UTILITY FUNCTIONS
Centralized academic year and term calculations
"""
from django.utils import timezone
from datetime import date, timedelta
import logging
import re

logger = logging.getLogger(__name__)


def get_current_academic_year():
    """
    Get current academic year in YYYY/YYYY format
    Assuming academic year runs from September to August
    """
    now = timezone.now()
    year = now.year
    
    # September (9) to August (8) of next year
    if now.month >= 9:  # September or later
        return f"{year}/{year + 1}"
    else:  # January to August
        return f"{year - 1}/{year}"


def get_current_term_number():
    """
    Get current term number (1, 2, or 3) based on Ghana Education System
    """
    month = timezone.now().month
    
    if month in [9, 10, 11, 12]:  # Sep-Dec
        return 1
    elif month in [1, 2, 3, 4]:   # Jan-Apr
        return 2
    else:                         # May-Aug
        return 3


def get_academic_year_from_date(target_date=None):
    """
    Get academic year for a specific date
    """
    if target_date is None:
        target_date = timezone.now().date()
    
    year = target_date.year
    month = target_date.month
    
    if month >= 9:  # September or later
        return f"{year}/{year + 1}"
    else:  # January to August
        return f"{year - 1}/{year}"


def parse_academic_year(academic_year_str):
    """
    Parse academic year string into start and end years
    Returns: (start_year, end_year) as integers
    """
    try:
        start_year, end_year = map(int, academic_year_str.split('/'))
        return start_year, end_year
    except (ValueError, IndexError):
        raise ValueError(f"Invalid academic year format: {academic_year_str}")


def validate_academic_year(academic_year_str):
    """
    Validate academic year format and sequence
    Returns: (is_valid, error_message)
    """
    if not academic_year_str:
        return False, "Academic year is required"
    
    # Check format
    if not re.match(r'^\d{4}/\d{4}$', academic_year_str):
        return False, "Academic year must be in format YYYY/YYYY"
    
    # Check year sequence
    try:
        start_year, end_year = parse_academic_year(academic_year_str)
        if end_year != start_year + 1:
            return False, "The second year must be exactly one year after the first"
        return True, ""
    except ValueError as e:
        return False, str(e)


def get_academic_year_start(academic_year_str):
    """
    Get the start date of an academic year (September 1)
    """
    start_year, _ = parse_academic_year(academic_year_str)
    return date(start_year, 9, 1)


def get_academic_year_end(academic_year_str):
    """
    Get the end date of an academic year (August 31)
    """
    _, end_year = parse_academic_year(academic_year_str)
    return date(end_year, 8, 31)


def get_term_dates(academic_year_str, term_number):
    """
    Get default term dates for Ghana Education System
    Returns: (start_date, end_date)
    """
    start_year, end_year = parse_academic_year(academic_year_str)
    
    term_dates = {
        1: (date(start_year, 9, 2), date(start_year, 12, 18)),
        2: (date(end_year, 1, 8), date(end_year, 4, 1)),
        3: (date(end_year, 4, 21), date(end_year, 7, 23)),
    }
    
    return term_dates.get(term_number, (None, None))


def get_next_academic_year(current_academic_year):
    """
    Get next academic year
    """
    start_year, end_year = parse_academic_year(current_academic_year)
    return f"{end_year}/{end_year + 1}"


def get_previous_academic_year(current_academic_year):
    """
    Get previous academic year
    """
    start_year, end_year = parse_academic_year(current_academic_year)
    return f"{start_year - 1}/{start_year}"


def is_date_in_academic_year(target_date, academic_year_str):
    """
    Check if a date falls within an academic year
    """
    start_date = get_academic_year_start(academic_year_str)
    end_date = get_academic_year_end(academic_year_str)
    return start_date <= target_date <= end_date


def get_academic_year_progress(academic_year_str):
    """
    Get progress percentage through academic year
    """
    start_date = get_academic_year_start(academic_year_str)
    end_date = get_academic_year_end(academic_year_str)
    today = timezone.now().date()
    
    if today < start_date:
        return 0
    elif today > end_date:
        return 100
    
    total_days = (end_date - start_date).days
    days_passed = (today - start_date).days
    return min(100, round((days_passed / total_days) * 100, 1))


def get_term_progress(term):
    """
    Get progress percentage through a term
    """
    from core.models.academic import AcademicTerm
    
    if isinstance(term, AcademicTerm):
        return term.get_progress_percentage()
    
    # If term is a dictionary or tuple with dates
    start_date = term.get('start_date') if isinstance(term, dict) else term[0]
    end_date = term.get('end_date') if isinstance(term, dict) else term[1]
    
    if not start_date or not end_date:
        return 0
    
    today = timezone.now().date()
    
    if today < start_date:
        return 0
    elif today > end_date:
        return 100
    
    total_days = (end_date - start_date).days
    days_passed = (today - start_date).days
    return min(100, round((days_passed / total_days) * 100, 1))