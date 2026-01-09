"""
School configuration forms for system settings and configuration.
"""
from decimal import Decimal
import re
import logging
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone

logger = logging.getLogger(__name__)


class SchoolConfigurationForm(forms.ModelForm):
    school_phone = forms.CharField(
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '0245478847',
            'pattern': r'0\d{9}',
            'title': '10-digit number starting with 0'
        }),
        help_text="10-digit phone number starting with 0 (e.g., 0245478847)",
        validators=[
            RegexValidator(
                r'^0\d{9}$',
                message="Phone number must be 10 digits starting with 0 (e.g., 0245478847)"
            )
        ]
    )
    
    # NEW: Current academic year field for standalone system
    current_academic_year = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'}),
        help_text="Select current academic year from standalone system"
    )
    
    class Meta:
        model = None  # Will be set in __init__
        fields = [
            'grading_system', 'is_locked', 'current_academic_year', 'default_academic_period_system',
            'school_name', 'school_address', 'school_phone', 'school_email', 'principal_name'
        ]
        widgets = {
            'grading_system': forms.Select(attrs={'class': 'form-control'}),
            'is_locked': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'default_academic_period_system': forms.Select(attrs={'class': 'form-control'}),
            'school_name': forms.TextInput(attrs={'class': 'form-control'}),
            'school_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'school_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'principal_name': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        # Lazy import to avoid circular imports
        from core.models import SchoolConfiguration
        from core.models.academic_term import AcademicYear, ACADEMIC_PERIOD_SYSTEM_CHOICES
        
        self.Meta.model = SchoolConfiguration
        super().__init__(*args, **kwargs)
        
        # Set queryset for current_academic_year field
        self.fields['current_academic_year'].queryset = AcademicYear.objects.all().order_by('-name')
        
        # Set choices for default_academic_period_system
        self.fields['default_academic_period_system'].choices = ACADEMIC_PERIOD_SYSTEM_CHOICES
        
        # Set initial value for current_academic_year if instance has one
        if self.instance and self.instance.current_academic_year:
            self.initial['current_academic_year'] = self.instance.current_academic_year
        
        # Remove old academic_year field if it exists in instance
        if hasattr(self.instance, 'academic_year'):
            # This handles migration from old CharField to new ForeignKey
            if self.instance.academic_year and not self.instance.current_academic_year:
                # Try to find matching AcademicYear
                try:
                    matching_year = AcademicYear.objects.get(name=self.instance.academic_year)
                    self.initial['current_academic_year'] = matching_year
                except AcademicYear.DoesNotExist:
                    # Create new AcademicYear if doesn't exist
                    try:
                        year1, year2 = map(int, self.instance.academic_year.split('/'))
                        matching_year = AcademicYear.objects.create(
                            name=self.instance.academic_year,
                            start_date=timezone.datetime(year1, 9, 1).date(),
                            end_date=timezone.datetime(year2, 8, 31).date(),
                            is_active=True
                        )
                        self.initial['current_academic_year'] = matching_year
                    except:
                        pass  # If creation fails, leave as None
    
    def clean_school_phone(self):
        phone_number = self.cleaned_data.get('school_phone')
        if phone_number:
            phone_number = phone_number.replace(' ', '').replace('-', '')
            if len(phone_number) != 10 or not phone_number.startswith('0'):
                raise ValidationError("Phone number must be exactly 10 digits starting with 0")
        return phone_number
    
    def clean(self):
        """Additional validation."""
        cleaned_data = super().clean()
        
        # Sync current_academic_year with AcademicYear.is_active
        current_academic_year = cleaned_data.get('current_academic_year')
        if current_academic_year:
            # If we're setting a current academic year, mark it as active
            from core.models.academic_term import AcademicYear
            
            # Deactivate all other academic years
            AcademicYear.objects.filter(is_active=True).exclude(pk=current_academic_year.pk).update(is_active=False)
            
            # Activate this one
            if not current_academic_year.is_active:
                current_academic_year.is_active = True
                current_academic_year.save()
        
        return cleaned_data
    
    def save(self, commit=True):
        """Save the form and handle academic year activation."""
        instance = super().save(commit=False)
        
        if commit:
            instance.save()
            self.save_m2m()
        
        return instance