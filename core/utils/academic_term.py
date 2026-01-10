"""
ACADEMIC UTILITY FUNCTIONS - UPDATED FOR STANDALONE SYSTEM
"""
import logging
from django.utils import timezone
from datetime import date, timedelta
import re
from core.models.academic_term import AcademicYear

logger = logging.getLogger(__name__)


def get_current_academic_year_string():
    """
    Get current academic year as string in YYYY/YYYY format
    """
    now = timezone.now()
    year = now.year
    
    # September (9) to August (8) of next year
    if now.month >= 9:  # September or later
        return f"{year}/{year + 1}"
    else:  # January to August
        return f"{year - 1}/{year}"


def get_current_academic_year_object():
    """
    Get current academic year as AcademicYear object
    Auto-creates if doesn't exist
    """
    # Try to find active academic year
    active_year = AcademicYear.objects.filter(is_active=True).first()
    if active_year:
        return active_year
    
    # Fallback: check date ranges
    today = timezone.now().date()
    year_in_range = AcademicYear.objects.filter(
        start_date__lte=today,
        end_date__gte=today
    ).first()
    
    if year_in_range:
        return year_in_range
    
    # Auto-create using the professional method
    try:
        AcademicYear.ensure_years_exist(years_ahead=1)
        return AcademicYear.get_current_year()
    except Exception as e:
        logger.error(f"Error in get_current_academic_year_object: {str(e)}")
        # Fallback to string method
        year_str = get_current_academic_year_string()
        year1, year2 = map(int, year_str.split('/'))
        return AcademicYear.objects.create(
            name=year_str,
            start_date=date(year1, 9, 1),
            end_date=date(year2, 8, 31),
            is_active=True
        )


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
    Returns: (start_date, end_date, total_days)
    """
    start_year, end_year = parse_academic_year(academic_year_str)
    
    term_dates = {
        1: (date(start_year, 9, 2), date(start_year, 12, 18), 108),
        2: (date(end_year, 1, 8), date(end_year, 4, 1), 84),
        3: (date(end_year, 4, 21), date(end_year, 7, 23), 94),
    }
    
    dates = term_dates.get(term_number, (None, None, 0))
    return dates[0], dates[1], dates[2]


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


def initialize_academic_system():
    """
    Initialize the academic system with professional auto-generation
    Call this on system startup or when needed
    """
    try:
        # Ensure academic years exist
        created_years = AcademicYear.ensure_years_exist(years_ahead=2)
        
        # Ensure school configuration is linked
        from core.models import SchoolConfiguration
        config = SchoolConfiguration.get_config()
        config.auto_sync_with_academic_system()
        config.save()
        
        logger.info("✅ Academic system initialized successfully")
        return True, f"Initialized with {len(created_years)} new academic years"
        
    except Exception as e:
        logger.error(f"❌ Error initializing academic system: {str(e)}")
        return False, str(e)


def get_academic_year_summary(academic_year_obj):
    """
    Get comprehensive summary of an academic year
    """
    if not academic_year_obj:
        return None
    
    terms = academic_year_obj.terms.all().order_by('sequence_num')
    
    term_summaries = []
    total_teaching_days = 0
    
    for term in terms:
        term_days = term.get_total_days()
        total_teaching_days += term_days
        
        term_summaries.append({
            'name': term.name,
            'number': term.period_number,
            'start_date': term.start_date,
            'end_date': term.end_date,
            'total_days': term_days,
            'remaining_days': term.get_remaining_days(),
            'progress': term.get_progress_percentage(),
            'is_active': term.is_active,
            'is_locked': term.is_locked,
        })
    
    academic_year_days = academic_year_obj.get_total_days()
    
    return {
        'academic_year': academic_year_obj.name,
        'start_date': academic_year_obj.start_date,
        'end_date': academic_year_obj.end_date,
        'total_days': academic_year_days,
        'teaching_days': total_teaching_days,
        'vacation_days': academic_year_days - total_teaching_days,
        'is_active': academic_year_obj.is_active,
        'progress': academic_year_obj.get_progress_percentage(),
        'terms': term_summaries,
        'term_count': len(terms),
    }