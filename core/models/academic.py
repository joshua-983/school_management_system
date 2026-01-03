# models/academic.py - COMPLETE UPDATE
"""
Academic models: Subject, AcademicTerm, ClassAssignment
"""
import re
import logging
from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q
from datetime import timedelta, date
from django.utils.dateparse import parse_date  # ADDED


from core.models.base import (
    CLASS_LEVEL_CHOICES,
    TERM_CHOICES,
    ACADEMIC_PERIOD_SYSTEM_CHOICES,
    get_period_choices_for_system,
    get_period_display,
    GhanaEducationMixin
)

logger = logging.getLogger(__name__)


class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True, editable=False)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'

    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def get_assignment_count(self):
        """Get number of assignments for this subject"""
        from core.models.assignments import Assignment
        return Assignment.objects.filter(subject=self, is_active=True).count()
    
    def generate_subject_code(self):
        """Generate a 3-letter subject code from the name"""
        # Remove common words and get first letters
        common_words = ['and', 'the', 'of', 'for', 'in', 'with', 'to', 'on', 'at', 'from', 'by', 'about', 'as', 'into', 'like', 'through', 'after', 'over', 'between', 'out', 'against', 'during', 'without', 'before', 'under', 'around', 'among']
        
        words = self.name.upper().split()
        meaningful_words = [word for word in words if word.lower() not in common_words]
        
        if meaningful_words:
            # If single word, take first 3 letters
            if len(meaningful_words) == 1:
                code = meaningful_words[0][:3]
            else:
                # If multiple words, take first letter of each (max 3)
                code = ''.join(word[0] for word in meaningful_words[:3])
        else:
            # Fallback: take first 3 letters of first word
            code = words[0][:3] if words else 'SUB'
        
        # Ensure code is exactly 3 characters
        code = code.ljust(3, 'X')[:3]
        
        # Make unique if code already exists
        base_code = code
        counter = 1
        while Subject.objects.filter(code=code).exclude(pk=self.pk).exists():
            code = f"{base_code}{counter}"
            counter += 1
        
        return code
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_subject_code()
        super().save(*args, **kwargs)


class AcademicTerm(models.Model, GhanaEducationMixin):
    """Academic Period (Term, Semester, Quarter, etc.)"""
    
    # System type (Term, Semester, Quarter, etc.)
    period_system = models.CharField(
        max_length=10,
        choices=ACADEMIC_PERIOD_SYSTEM_CHOICES,
        default='TERM',
        verbose_name="Academic Period System",
        help_text="Type of academic period system"
    )
    
    # Period number within the system
    period_number = models.PositiveSmallIntegerField(
        verbose_name="Period Number",
        help_text="1, 2, 3 for Terms; 1, 2 for Semesters; 1-4 for Quarters"
    )
    
    academic_year = models.CharField(
        max_length=9, 
        validators=[RegexValidator(r'^\d{4}/\d{4}$')],
        verbose_name="Academic Year"
    )
    
    # Name field for custom naming (optional)
    name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name="Period Name",
        help_text="Optional custom name (e.g., 'First Term', 'Fall Semester')"
    )
    
    start_date = models.DateField(
        verbose_name="Start Date"
    )
    
    end_date = models.DateField(
        verbose_name="End Date"
    )
    
    is_active = models.BooleanField(
        default=False,
        verbose_name="Active Period",
        help_text="Mark as active for current academic period"
    )
    
    # Locking mechanism
    is_locked = models.BooleanField(
        default=False,
        verbose_name="Lock Period",
        help_text="Lock period to prevent modifications"
    )
    
    # Sequence number for ordering (auto-calculated)
    sequence_num = models.PositiveSmallIntegerField(
        default=1,
        editable=False,
        verbose_name="Sequence Number"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('period_system', 'period_number', 'academic_year')
        ordering = ['-academic_year', 'sequence_num']
        verbose_name = 'Academic Period'
        verbose_name_plural = 'Academic Periods'
        indexes = [
            models.Index(fields=['period_system', 'academic_year']),
            models.Index(fields=['is_active']),
            models.Index(fields=['start_date', 'end_date']),
        ]
    
    def __str__(self):
        """Display based on system type"""
        if self.name:
            return f"{self.name} ({self.academic_year})"
        
        system_display = {
            'TERM': f'Term {self.period_number}',
            'SEMESTER': f'Semester {self.period_number}',
            'QUARTER': f'Quarter {self.period_number}',
            'TRIMESTER': f'Trimester {self.period_number}',
            'CUSTOM': f'Period {self.period_number}',
        }
        return f"{system_display.get(self.period_system, f'Period {self.period_number}')} ({self.academic_year})"
    
    def _normalize_date(self, date_value):
        """Convert date value to datetime.date object"""
        if isinstance(date_value, date):
            return date_value
        elif isinstance(date_value, str):
            # Try to parse the date string
            parsed_date = parse_date(date_value)
            if parsed_date:
                return parsed_date
            # Try other common formats
            try:
                from datetime import datetime
                # Try ISO format
                return datetime.strptime(date_value, '%Y-%m-%d').date()
            except ValueError:
                try:
                    # Try another common format
                    return datetime.strptime(date_value, '%d/%m/%Y').date()
                except ValueError:
                    # Last resort: use today
                    logger.warning(f"Could not parse date: {date_value}, using today")
                    return timezone.now().date()
        elif hasattr(date_value, 'date'):
            # If it's a datetime object
            return date_value.date()
        else:
            logger.warning(f"Unexpected date type: {type(date_value)}, using today")
            return timezone.now().date()
    
    def save(self, *args, **kwargs):
        """Calculate sequence number before saving"""
        # Normalize dates to ensure they are date objects
        if self.start_date:
            self.start_date = self._normalize_date(self.start_date)
        if self.end_date:
            self.end_date = self._normalize_date(self.end_date)
        
        # Calculate sequence based on start date within academic year
        if self.start_date and self.end_date:
            # Get all periods in the same academic year and system
            same_year_periods = AcademicTerm.objects.filter(
                academic_year=self.academic_year,
                period_system=self.period_system
            ).exclude(pk=self.pk).order_by('start_date')
            
            # Add current period to list for sorting
            periods_list = list(same_year_periods) + [self]
            
            # Sort by start date
            periods_list.sort(key=lambda x: x.start_date)
            
            # Assign sequence numbers
            for idx, period in enumerate(periods_list, 1):
                if period.pk == self.pk:
                    self.sequence_num = idx
                    break
        
        # Ensure only one active period per academic year
        if self.is_active:
            AcademicTerm.objects.filter(
                academic_year=self.academic_year,
                is_active=True
            ).exclude(pk=self.pk).update(is_active=False)
        
        # Run validation
        self.clean()
        
        super().save(*args, **kwargs)
    
    def clean(self):
        """Validate period data"""
        errors = {}
        
        # Ensure dates are date objects for comparison
        start_date = self._normalize_date(self.start_date)
        end_date = self._normalize_date(self.end_date)
        
        # Date validation
        if start_date and end_date and start_date > end_date:
            errors['end_date'] = "End date must be after start date"
        
        # Validate period number based on system
        max_periods = {
            'TERM': 3,
            'SEMESTER': 2,
            'QUARTER': 4,
            'TRIMESTER': 3,
            'CUSTOM': 6,
        }
        
        max_period = max_periods.get(self.period_system, 3)
        if self.period_number < 1 or self.period_number > max_period:
            errors['period_number'] = f"Period number must be between 1 and {max_period} for {self.get_period_system_display()}"
        
        # Validate academic year format
        if self.academic_year and not re.match(r'^\d{4}/\d{4}$', self.academic_year):
            errors['academic_year'] = 'Academic year must be in format YYYY/YYYY'
        else:
            try:
                year1, year2 = map(int, self.academic_year.split('/'))
                if year2 != year1 + 1:
                    errors['academic_year'] = 'The second year must be exactly one year after the first year'
            except (ValueError, IndexError):
                errors['academic_year'] = 'Invalid academic year format'
        
        if errors:
            raise ValidationError(errors)
    
    def get_period_display(self):
        """Get display name for this period"""
        if self.name:
            return self.name
        
        return get_period_display(self.period_system, self.period_number)
    
    def get_full_display(self):
        """Get full display with system type"""
        system_display = self.get_period_system_display()
        period_display = self.get_period_display()
        return f"{period_display} ({system_display} System)"
    
    @property
    def is_term_system(self):
        """Check if this is a term system period"""
        return self.period_system == 'TERM'
    
    @property
    def is_semester_system(self):
        """Check if this is a semester system period"""
        return self.period_system == 'SEMESTER'
    
    def get_total_school_days(self):
        """Calculate total school days in the period (excluding weekends)"""
        if not self.start_date or not self.end_date:
            return 0
        
        start_date = self._normalize_date(self.start_date)
        end_date = self._normalize_date(self.end_date)
        
        total_days = 0
        current_date = start_date
        
        while current_date <= end_date:
            # Monday = 0, Sunday = 6, so 0-4 are weekdays
            if current_date.weekday() < 5:
                total_days += 1
            current_date += timedelta(days=1)
        
        return total_days
    
    def get_progress_percentage(self):
        """Get period progress percentage"""
        if not self.start_date or not self.end_date:
            return 0
        
        start_date = self._normalize_date(self.start_date)
        end_date = self._normalize_date(self.end_date)
        today = timezone.now().date()
        
        if today < start_date:
            return 0
        elif today > end_date:
            return 100
        
        total_days = (end_date - start_date).days
        if total_days <= 0:
            return 0
        
        days_passed = (today - start_date).days
        percentage = (days_passed / total_days) * 100
        return min(100, round(percentage, 1))
    
    def get_remaining_days(self):
        """Get remaining days in period"""
        if not self.end_date:
            return 0
        
        end_date = self._normalize_date(self.end_date)
        today = timezone.now().date()
        
        if today > end_date:
            return 0
        
        remaining = (end_date - today).days
        return max(0, remaining)
    
    def get_next_period(self):
        """Get the next period in sequence"""
        return AcademicTerm.objects.filter(
            academic_year=self.academic_year,
            period_system=self.period_system,
            sequence_num=self.sequence_num + 1
        ).first()
    
    def get_previous_period(self):
        """Get the previous period in sequence"""
        return AcademicTerm.objects.filter(
            academic_year=self.academic_year,
            period_system=self.period_system,
            sequence_num=self.sequence_num - 1
        ).first()
    
    @classmethod
    def get_current_period(cls):
        """Get the currently active academic period"""
        return cls.objects.filter(is_active=True).first()
    
    @classmethod
    def get_periods_for_year(cls, academic_year, period_system=None):
        """Get all periods for a specific academic year"""
        queryset = cls.objects.filter(academic_year=academic_year)
        if period_system:
            queryset = queryset.filter(period_system=period_system)
        return queryset.order_by('sequence_num')
    
    @classmethod
    def create_academic_year(cls, academic_year, period_system='TERM', start_dates=None, end_dates=None):
        """Create a complete academic year with all periods"""
        # Default dates for Ghana Education System (Terms)
        default_dates = {
            'TERM': {
                1: {'start': date(int(academic_year.split('/')[0]), 9, 2), 'end': date(int(academic_year.split('/')[0]), 12, 18)},
                2: {'start': date(int(academic_year.split('/')[1]), 1, 8), 'end': date(int(academic_year.split('/')[1]), 4, 1)},
                3: {'start': date(int(academic_year.split('/')[1]), 4, 21), 'end': date(int(academic_year.split('/')[1]), 7, 23)},
            },
            'SEMESTER': {
                1: {'start': date(int(academic_year.split('/')[0]), 9, 2), 'end': date(int(academic_year.split('/')[1]), 1, 15)},
                2: {'start': date(int(academic_year.split('/')[1]), 1, 22), 'end': date(int(academic_year.split('/')[1]), 6, 15)},
            },
            # Add defaults for other systems as needed
        }
        
        periods = []
        period_info = default_dates.get(period_system, default_dates['TERM'])
        
        for period_num, dates in period_info.items():
            period = cls(
                period_system=period_system,
                period_number=period_num,
                academic_year=academic_year,
                start_date=dates['start'],
                end_date=dates['end'],
                is_active=False
            )
            period.save()
            periods.append(period)
        
        return periods


class ClassAssignment(models.Model):
    class_level = models.CharField(max_length=2, choices=CLASS_LEVEL_CHOICES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey('Teacher', on_delete=models.CASCADE)
    academic_year = models.CharField(max_length=9, validators=[RegexValidator(r'^\d{4}/\d{4}$')])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('class_level', 'subject', 'academic_year')
        verbose_name = 'Class Assignment'
        verbose_name_plural = 'Class Assignments'
        ordering = ['class_level', 'subject']
        indexes = [
            models.Index(fields=['class_level', 'subject', 'academic_year']),
            models.Index(fields=['teacher', 'is_active']),
            models.Index(fields=['is_active', 'academic_year']),
            models.Index(fields=['class_level', 'is_active']),
        ]

    def __str__(self):
        return f"{self.get_class_level_display()} - {self.subject} - {self.teacher} ({self.academic_year})"
    
    def get_students(self):
        """Get all students in this class"""
        from core.models.student import Student
        return Student.objects.filter(class_level=self.class_level, is_active=True)
    
    def get_students_count(self):
        """Get count of students in this class"""
        return self.get_students().count()