"""
FORMS FOR ACADEMIC TERM MANAGEMENT - UPDATED FOR STANDALONE SYSTEM
"""
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone
import re
from datetime import date, timedelta
from core.models.academic_term import AcademicTerm, AcademicYear
from core.models.base import ACADEMIC_PERIOD_SYSTEM_CHOICES


class AcademicYearForm(forms.ModelForm):
    """Form for creating/editing academic years in standalone system"""
    
    auto_sync_terms = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text='Auto-create terms based on Ghana Education System (365 days)'
    )
    
    class Meta:
        model = AcademicYear
        fields = ['name', 'start_date', 'end_date', 'is_active', 'auto_sync_terms', 'description']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'YYYY/YYYY'
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
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional description...'
            }),
        }
        help_texts = {
            'name': 'Format: YYYY/YYYY (e.g., 2024/2025)',
            'start_date': 'Typically September 1st of first year',
            'end_date': 'Typically August 31st of second year',
            'auto_sync_terms': 'Creates 3 terms with Ghana Education System dates (108 + 84 + 94 = 286 teaching days)',
        }
    
    def clean_name(self):
        name = self.cleaned_data['name']
        
        # Validate format
        if not re.match(r'^\d{4}/\d{4}$', name):
            raise ValidationError('Academic year must be in format YYYY/YYYY')
        
        # Validate years
        try:
            year1, year2 = map(int, name.split('/'))
            if year2 != year1 + 1:
                raise ValidationError('The second year must be exactly one year after the first')
            
            # Check if academic year with this name already exists
            if AcademicYear.objects.filter(name=name).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise ValidationError(f'Academic year {name} already exists')
                
        except (ValueError, IndexError):
            raise ValidationError('Invalid academic year format')
        
        return name
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        name = cleaned_data.get('name')
        
        if start_date and end_date:
            # Validate date order
            if start_date >= end_date:
                raise ValidationError({
                    'end_date': 'End date must be after start date'
                })
            
            # Validate dates match name
            if name:
                try:
                    year1, year2 = map(int, name.split('/'))
                    
                    # Check if dates roughly match academic year
                    if start_date.year != year1 or end_date.year != year2:
                        self.add_warning('start_date', 
                            f"Dates don't match academic year name {name}. "
                            f"Expected year1={year1}, year2={year2}")
                
                except (ValueError, IndexError):
                    pass
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        if commit:
            instance.save()
            
            # Auto-create terms if requested
            if self.cleaned_data.get('auto_sync_terms', True):
                terms_created = AcademicTerm.create_default_terms_for_year(instance, 'TERM')
                if terms_created:
                    self.add_success_message = f"Created {terms_created} terms for academic year {instance.name}"
        
        return instance


class AcademicTermForm(forms.ModelForm):
    """Form for creating/editing academic terms"""
    
    class Meta:
        model = AcademicTerm
        fields = [
            'academic_year', 'period_system', 'period_number',
            'name', 'start_date', 'end_date', 'is_active'
        ]
        widgets = {
            'academic_year': forms.Select(attrs={
                'class': 'form-select',
                'placeholder': 'Select academic year'
            }),
            'period_system': forms.Select(attrs={
                'class': 'form-select',
                'onchange': 'updatePeriodNumberLimits(this.value)'
            }),
            'period_number': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
                'max': 6
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
            'academic_year': 'Select from existing academic years',
            'period_number': '1-3 for Terms, 1-2 for Semesters, 1-4 for Quarters',
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set queryset for academic_year field
        self.fields['academic_year'].queryset = AcademicYear.objects.all().order_by('-name')
        
        # Set initial academic year to current if not provided
        if not self.instance.pk and not self.initial.get('academic_year'):
            current_year = AcademicYear.get_current_year()
            if current_year:
                self.initial['academic_year'] = current_year
    
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
                if start_date < academic_year.start_date or end_date > academic_year.end_date:
                    raise ValidationError({
                        'start_date': f'Dates must be within academic year {academic_year.name} '
                                    f'({academic_year.start_date} - {academic_year.end_date})'
                    })
        
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
    """Form for creating a complete academic year with its terms"""
    
    name = forms.CharField(
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
    
    def clean_name(self):
        name = self.cleaned_data['name']
        
        # Check if academic year already exists
        if AcademicYear.objects.filter(name=name).exists():
            raise ValidationError(
                f'Academic year {name} already exists. '
                f'Please use the existing one or choose a different year.'
            )
        
        return name
    
    def create_academic_year_with_terms(self):
        """Create academic year and its terms based on form data"""
        name = self.cleaned_data['name']
        period_system = self.cleaned_data['period_system']
        auto_generate = self.cleaned_data['auto_generate_dates']
        set_first_active = self.cleaned_data['set_first_term_active']
        
        try:
            year1, year2 = map(int, name.split('/'))
            
            # Create AcademicYear
            if auto_generate:
                academic_year = AcademicYear.objects.create(
                    name=name,
                    start_date=date(year1, 9, 1),
                    end_date=date(year2, 8, 31)
                )
            else:
                academic_year = AcademicYear.objects.create(name=name)
            
            # Create terms using the model's create_default_terms method
            if auto_generate:
                terms = AcademicTerm.create_default_terms(
                    academic_year=academic_year,
                    period_system=period_system
                )
            else:
                # Just create the AcademicYear without terms
                terms = []
            
            # Set first term as active if requested
            if set_first_active and terms:
                # Deactivate all other terms first
                AcademicTerm.objects.filter(is_active=True).exclude(
                    pk=terms[0].pk
                ).update(is_active=False)
                terms[0].is_active = True
                terms[0].save()
            
            return academic_year, terms
            
        except Exception as e:
            # Rollback if there's an error
            if 'academic_year' in locals():
                academic_year.delete()
            raise ValidationError(f'Error creating academic year: {str(e)}')


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
    """Form for bulk academic year actions"""
    
    ACTION_CHOICES = [
        ('create', 'Create Academic Years'),
        ('activate', 'Activate Years'),
        ('deactivate', 'Deactivate Years'),
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
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        period_system = cleaned_data.get('period_system')
        
        # Validate period_system is provided for create action
        if action == 'create' and not period_system:
            raise ValidationError({
                'period_system': 'Period system is required for creating academic years'
            })
        
        return cleaned_data