# core/models/academic_term.py
"""
STANDALONE Academic Term Management System
Only contains AcademicYear and AcademicTerm models
"""

import re
import logging
from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from datetime import date, timedelta

# REMOVE THIS CIRCULAR IMPORT:
# from core.models.academic_term import AcademicYear, AcademicTerm  # DELETE THIS LINE!

# Import only from base, not from itself
from core.models.base import (
    BaseModel,
    TimeStampedModel,
    ACADEMIC_PERIOD_SYSTEM_CHOICES,
    get_period_choices_for_system,
    get_period_display,
)

logger = logging.getLogger(__name__)


class AcademicYear(BaseModel, TimeStampedModel):
    """
    Standalone Academic Year Model
    """
    name = models.CharField(
        max_length=9,
        unique=True,
        validators=[RegexValidator(r'^\d{4}/\d{4}$')],
        verbose_name=_('Academic Year'),
        help_text=_('Format: YYYY/YYYY (e.g., 2024/2025)')
    )
    
    start_date = models.DateField(
        verbose_name=_('Start Date'),
        help_text=_('Academic year start date (typically September 1)')
    )
    
    end_date = models.DateField(
        verbose_name=_('End Date'),
        help_text=_('Academic year end date (typically August 31)')
    )
    
    is_active = models.BooleanField(
        default=False,
        verbose_name=_('Active Academic Year'),
        help_text=_('Mark as the current academic year')
    )
    
    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )
    
    class Meta:
        ordering = ['-start_date']
        verbose_name = _('Academic Year')
        verbose_name_plural = _('Academic Years')
    
    def __str__(self):
        return self.name
    
    def clean(self):
        """Validate academic year data"""
        errors = {}
        
        # Validate format
        if not re.match(r'^\d{4}/\d{4}$', self.name):
            errors['name'] = _('Must be in format YYYY/YYYY')
        else:
            try:
                year1, year2 = map(int, self.name.split('/'))
                if year2 != year1 + 1:
                    errors['name'] = _('Second year must be exactly one year after first')
            except ValueError:
                errors['name'] = _('Invalid academic year format')
        
        # Validate dates
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                errors['end_date'] = _('End date must be after start date')
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        # Ensure only one active academic year
        if self.is_active:
            AcademicYear.objects.filter(is_active=True).exclude(pk=self.pk).update(is_active=False)
        
        self.clean()
        super().save(*args, **kwargs)
    
    def get_total_days(self):
        """Get total days in academic year"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0
    
    def get_progress_percentage(self):
        """Get academic year progress percentage"""
        if not self.start_date or not self.end_date:
            return 0
        
        today = timezone.now().date()
        
        if today < self.start_date:
            return 0
        elif today > self.end_date:
            return 100
        
        total_days = self.get_total_days()
        days_passed = (today - self.start_date).days + 1
        return min(100, round((days_passed / total_days) * 100, 2))
    
    @classmethod
    def get_current_year(cls):
        """Get current academic year"""
        # Try active year first
        active_year = cls.objects.filter(is_active=True).first()
        if active_year:
            return active_year
        
        # Fallback: year containing today
        today = timezone.now().date()
        return cls.objects.filter(
            start_date__lte=today,
            end_date__gte=today
        ).first()


class AcademicTerm(BaseModel, TimeStampedModel):
    """
    Standalone Academic Term Model
    """
    TERM_STATUS = [
        ('PLANNED', _('Planned')),
        ('ACTIVE', _('Active')),
        ('COMPLETED', _('Completed')),
        ('ARCHIVED', _('Archived')),
    ]
    
    academic_year = models.ForeignKey(
        AcademicYear,  # No import needed - it's defined above
        on_delete=models.CASCADE,
        related_name='terms',
        verbose_name=_('Academic Year')
    )
    
    period_system = models.CharField(
        max_length=10,
        choices=ACADEMIC_PERIOD_SYSTEM_CHOICES,
        default='TERM',
        verbose_name=_('Period System')
    )
    
    period_number = models.PositiveSmallIntegerField(
        verbose_name=_('Period Number'),
        help_text=_('1, 2, 3 for Terms; 1, 2 for Semesters')
    )
    
    name = models.CharField(
        max_length=100,
        verbose_name=_('Term Name'),
        help_text=_('e.g., "First Term", "Fall Semester"')
    )
    
    status = models.CharField(
        max_length=10,
        choices=TERM_STATUS,
        default='PLANNED',
        verbose_name=_('Term Status')
    )
    
    start_date = models.DateField(
        verbose_name=_('Start Date')
    )
    
    end_date = models.DateField(
        verbose_name=_('End Date')
    )
    
    is_active = models.BooleanField(
        default=False,
        verbose_name=_('Active Term'),
        help_text=_('Mark as current active term')
    )
    
    is_locked = models.BooleanField(
        default=False,
        verbose_name=_('Locked'),
        help_text=_('Lock term to prevent modifications')
    )
    
    sequence_num = models.PositiveSmallIntegerField(
        default=1,
        verbose_name=_('Sequence Number')
    )
    
    description = models.TextField(
        blank=True,
        verbose_name=_('Description')
    )
    
    class Meta:
        unique_together = ('academic_year', 'period_system', 'period_number')
        ordering = ['academic_year', 'sequence_num']
        verbose_name = _('Academic Term')
        verbose_name_plural = _('Academic Terms')
    
    def __str__(self):
        return f"{self.name} - {self.academic_year.name}"
    
    def clean(self):
        """Validate term data"""
        errors = {}
        
        # Validate dates
        if self.start_date and self.end_date:
            if self.start_date >= self.end_date:
                errors['end_date'] = _('End date must be after start date')
            
            # Check term is within academic year
            if self.academic_year:
                if self.start_date < self.academic_year.start_date:
                    errors['start_date'] = _('Term cannot start before academic year')
                if self.end_date > self.academic_year.end_date:
                    errors['end_date'] = _('Term cannot end after academic year')
        
        # Validate period number
        max_periods = {
            'TERM': 3,
            'SEMESTER': 2,
            'QUARTER': 4,
            'TRIMESTER': 3,
        }
        
        max_period = max_periods.get(self.period_system, 3)
        if self.period_number < 1 or self.period_number > max_period:
            errors['period_number'] = _(
                f'Period number must be 1-{max_period} for {self.get_period_system_display()} system'
            )
        
        if errors:
            raise ValidationError(errors)
    
    def save(self, *args, **kwargs):
        # Auto-generate name if not provided
        if not self.name:
            system_names = {
                'TERM': f'Term {self.period_number}',
                'SEMESTER': f'Semester {self.period_number}',
                'QUARTER': f'Quarter {self.period_number}',
                'TRIMESTER': f'Trimester {self.period_number}',
            }
            self.name = system_names.get(self.period_system, f'Period {self.period_number}')
        
        # Update status based on dates
        today = timezone.now().date()
        if self.start_date and self.end_date:
            if today < self.start_date:
                self.status = 'PLANNED'
            elif today > self.end_date:
                if self.status != 'ARCHIVED':
                    self.status = 'COMPLETED'
            else:
                self.status = 'ACTIVE'
        
        # Ensure only one active term per academic year
        if self.is_active:
            AcademicTerm.objects.filter(
                academic_year=self.academic_year,
                is_active=True
            ).exclude(pk=self.pk).update(is_active=False)
        
        # Auto-calculate sequence number for new terms
        if self._state.adding and not self.sequence_num:
            last_term = AcademicTerm.objects.filter(
                academic_year=self.academic_year,
                period_system=self.period_system
            ).order_by('-sequence_num').first()
            self.sequence_num = (last_term.sequence_num + 1) if last_term else 1
        
        self.clean()
        super().save(*args, **kwargs)
    
    def get_period_display(self):
        """Get display name for period"""
        return get_period_display(self.period_system, self.period_number)
    
    def get_total_days(self):
        """Get total days in term"""
        if self.start_date and self.end_date:
            return (self.end_date - self.start_date).days + 1
        return 0
    
    def get_progress_percentage(self):
        """Get term progress percentage"""
        if not self.start_date or not self.end_date:
            return 0
        
        today = timezone.now().date()
        
        if today < self.start_date:
            return 0
        elif today > self.end_date:
            return 100
        
        total_days = self.get_total_days()
        days_passed = (today - self.start_date).days + 1
        return min(100, round((days_passed / total_days) * 100, 2))
    
    def get_remaining_days(self):
        """Get remaining days in term"""
        if not self.end_date:
            return 0
        
        today = timezone.now().date()
        if today > self.end_date:
            return 0
        
        return (self.end_date - today).days + 1
    
    def lock_term(self):
        """Lock the term"""
        if not self.is_locked:
            self.is_locked = True
            self.save()
            return True
        return False
    
    def unlock_term(self):
        """Unlock the term"""
        if self.is_locked:
            self.is_locked = False
            self.save()
            return True
        return False
    
    @classmethod
    def get_current_term(cls):
        """Get current active term"""
        # Try active term first
        active_term = cls.objects.filter(is_active=True).first()
        if active_term:
            return active_term
        
        # Fallback: term containing today
        today = timezone.now().date()
        return cls.objects.filter(
            start_date__lte=today,
            end_date__gte=today,
            status='ACTIVE'
        ).first()
    
    @classmethod
    def create_default_terms(cls, academic_year, period_system='TERM'):
        """Create default terms for an academic year"""
        year1, year2 = map(int, academic_year.name.split('/'))
        
        term_data = {
            'TERM': [
                {'number': 1, 'name': 'First Term', 'start': (9, 2), 'end': (12, 18)},
                {'number': 2, 'name': 'Second Term', 'start': (1, 8), 'end': (4, 1)},
                {'number': 3, 'name': 'Third Term', 'start': (4, 21), 'end': (7, 23)},
            ],
            'SEMESTER': [
                {'number': 1, 'name': 'First Semester', 'start': (9, 2), 'end': (1, 15)},
                {'number': 2, 'name': 'Second Semester', 'start': (1, 22), 'end': (6, 15)},
            ],
        }
        
        terms = []
        for term_info in term_data.get(period_system, term_data['TERM']):
            start_month, start_day = term_info['start']
            end_month, end_day = term_info['end']
            
            # Adjust years
            start_year = year2 if start_month < 9 else year1
            end_year = year2 if end_month < 9 else year1
            
            term = cls.objects.create(
                academic_year=academic_year,
                period_system=period_system,
                period_number=term_info['number'],
                name=term_info['name'],
                start_date=date(start_year, start_month, start_day),
                end_date=date(end_year, end_month, end_day),
                is_active=False
            )
            terms.append(term)
        
        return terms


# Export only these two models
__all__ = ['AcademicYear', 'AcademicTerm']