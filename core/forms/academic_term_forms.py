"""
FORMS FOR ACADEMIC TERM MANAGEMENT
"""
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone
import re
from datetime import date, timedelta
from core.models.academic_term import AcademicTerm, AcademicYear
from core.models.base import ACADEMIC_PERIOD_SYSTEM_CHOICES


class AcademicTermForm(forms.ModelForm):
    """Form for creating/editing academic terms"""
    
    class Meta:
        model = AcademicTerm
        fields = [
            'period_system', 'period_number', 'academic_year',
            'name', 'start_date', 'end_date', 'is_active'
        ]
        widgets = {
            'period_system': forms.Select(attrs={
                'class': 'form-select',
                'onchange': 'updatePeriodNumberLimits(this.value)'
            }),
            'period_number': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 6
            }),
            'academic_year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'YYYY/YYYY'
            }),
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional custom name'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        help_texts = {
            'academic_year': 'Format: YYYY/YYYY (e.g., 2024/2025)',
            'period_number': '1-3 for Terms, 1-2 for Semesters, 1-4 for Quarters',
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set initial academic year to current if not provided
        if not self.instance.pk and not self.initial.get('academic_year'):
            from core.utils.academic_term import get_current_academic_year
            self.initial['academic_year'] = get_current_academic_year()
    
    def clean_academic_year(self):
        academic_year = self.cleaned_data['academic_year']
        
        # Validate format
        if not re.match(r'^\d{4}/\d{4}$', academic_year):
            raise ValidationError('Academic year must be in format YYYY/YYYY')
        
        # Validate years
        try:
            year1, year2 = map(int, academic_year.split('/'))
            if year2 != year1 + 1:
                raise ValidationError('The second year must be exactly one year after the first')
        except (ValueError, IndexError):
            raise ValidationError('Invalid academic year format')
        
        return academic_year
    
    def clean_period_number(self):
        period_system = self.cleaned_data.get('period_system', self.instance.period_system if self.instance else 'TERM')
        period_number = self.cleaned_data['period_number']
        
        # Define max periods per system
        max_periods = {
            'TERM': 3,
            'SEMESTER': 2,
            'QUARTER': 4,
            'TRIMESTER': 3,
            'CUSTOM': 6,
        }
        
        max_period = max_periods.get(period_system, 3)
        
        if period_number < 1 or period_number > max_period:
            raise ValidationError(
                f'Period number must be between 1 and {max_period} '
                f'for {dict(ACADEMIC_PERIOD_SYSTEM_CHOICES).get(period_system)} system'
            )
        
        return period_number
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        academic_year = cleaned_data.get('academic_year')
        period_system = cleaned_data.get('period_system')
        period_number = cleaned_data.get('period_number')
        
        if start_date and end_date:
            # Validate date order
            if start_date >= end_date:
                raise ValidationError({
                    'end_date': 'End date must be after start date'
                })
            
            # Validate dates within academic year
            if academic_year:
                try:
                    year1, year2 = map(int, academic_year.split('/'))
                    year1_date = date(year1, 9, 1)  # Academic year starts Sep 1
                    year2_date = date(year2, 8, 31)  # Ends Aug 31
                    
                    if start_date < year1_date or end_date > year2_date:
                        raise ValidationError({
                            'start_date': f'Dates must be within academic year {academic_year} '
                                        f'(Sep {year1} - Aug {year2})'
                        })
                except (ValueError, IndexError):
                    pass
        
        # Check for overlapping terms
        if all([academic_year, period_system, start_date, end_date]):
            overlapping = AcademicTerm.objects.filter(
                academic_year=academic_year,
                period_system=period_system,
                start_date__lt=end_date,
                end_date__gt=start_date
            )
            
            if self.instance and self.instance.pk:
                overlapping = overlapping.exclude(pk=self.instance.pk)
            
            if overlapping.exists():
                raise ValidationError(
                    f'Dates overlap with existing {period_system.lower()}: '
                    f'{overlapping.first()}'
                )
        
        return cleaned_data


class AcademicYearCreationForm(forms.Form):
    """Form for creating a complete academic year"""
    
    academic_year = forms.CharField(
        max_length=9,
        validators=[RegexValidator(r'^\d{4}/\d{4}$')],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'YYYY/YYYY'
        }),
        help_text='Format: YYYY/YYYY (e.g., 2024/2025)'
    )
    
    period_system = forms.ChoiceField(
        choices=ACADEMIC_PERIOD_SYSTEM_CHOICES,
        initial='TERM',
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    auto_generate_dates = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Auto-generate dates based on Ghana Education System calendar'
    )
    
    set_first_term_active = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Set the first term as active'
    )
    
    def clean_academic_year(self):
        academic_year = self.cleaned_data['academic_year']
        
        # Check if academic year already exists
        if AcademicTerm.objects.filter(academic_year=academic_year).exists():
            raise ValidationError(
                f'Academic year {academic_year} already exists. '
                f'Please delete existing terms first or choose a different year.'
            )
        
        return academic_year
    
    def get_term_data(self):
        """Get term data based on form input"""
        academic_year = self.cleaned_data['academic_year']
        period_system = self.cleaned_data['period_system']
        auto_generate = self.cleaned_data['auto_generate_dates']
        
        if auto_generate:
            # Return default dates based on system
            year1, year2 = map(int, academic_year.split('/'))
            
            if period_system == 'TERM':
                return [
                    {
                        'number': 1,
                        'name': 'First Term',
                        'start_date': date(year1, 9, 2),
                        'end_date': date(year1, 12, 18),
                    },
                    {
                        'number': 2,
                        'name': 'Second Term',
                        'start_date': date(year2, 1, 8),
                        'end_date': date(year2, 4, 1),
                    },
                    {
                        'number': 3,
                        'name': 'Third Term',
                        'start_date': date(year2, 4, 21),
                        'end_date': date(year2, 7, 23),
                    },
                ]
            elif period_system == 'SEMESTER':
                return [
                    {
                        'number': 1,
                        'name': 'First Semester',
                        'start_date': date(year1, 9, 2),
                        'end_date': date(year2, 1, 15),
                    },
                    {
                        'number': 2,
                        'name': 'Second Semester',
                        'start_date': date(year2, 1, 22),
                        'end_date': date(year2, 6, 15),
                    },
                ]
            # Add other systems as needed
        
        # For custom dates, you'd need additional form fields
        return []


class TermLockForm(forms.ModelForm):
    """Form for locking/unlocking academic terms"""
    
    confirm = forms.BooleanField(
        required=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        label='I understand the implications of this action'
    )
    
    reason = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Optional reason for locking/unlocking'
        }),
        help_text='Optional: Add a note about why you are locking/unlocking this term'
    )
    
    class Meta:
        model = AcademicTerm
        fields = ['is_locked']
        widgets = {
            'is_locked': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set initial value opposite to current
        if self.instance:
            self.initial['is_locked'] = not self.instance.is_locked


class TermBulkCreationForm(forms.Form):
    """Form for bulk academic term actions"""
    
    ACTION_CHOICES = [
        ('create', 'Create Academic Years'),
        ('lock', 'Lock Terms'),
        ('unlock', 'Unlock Terms'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    academic_years = forms.CharField(
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 5,
            'placeholder': 'Enter one academic year per line\n2024/2025\n2025/2026\n2026/2027'
        }),
        help_text='One academic year per line (YYYY/YYYY format)'
    )
    
    period_system = forms.ChoiceField(
        choices=ACADEMIC_PERIOD_SYSTEM_CHOICES,
        initial='TERM',
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text='Required for creating new academic years'
    )
    
    def clean_academic_years(self):
        academic_years = self.cleaned_data['academic_years']
        valid_years = []
        
        for line in academic_years.strip().split('\n'):
            year = line.strip()
            if not year:
                continue
            
            # Validate format
            if not re.match(r'^\d{4}/\d{4}$', year):
                raise ValidationError(f'Invalid academic year format: {year}')
            
            # Validate year sequence
            try:
                year1, year2 = map(int, year.split('/'))
                if year2 != year1 + 1:
                    raise ValidationError(f'Invalid year sequence: {year}')
            except (ValueError, IndexError):
                raise ValidationError(f'Invalid academic year: {year}')
            
            valid_years.append(year)
        
        if not valid_years:
            raise ValidationError('Please enter at least one academic year')
        
        return valid_years