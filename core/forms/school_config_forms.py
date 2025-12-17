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
    
    class Meta:
        model = None  # Will be set in __init__
        fields = [
            'grading_system', 'is_locked', 'academic_year', 'current_term',
            'school_name', 'school_address', 'school_phone', 'school_email', 'principal_name'
        ]
        widgets = {
            'grading_system': forms.Select(attrs={'class': 'form-control'}),
            'is_locked': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'academic_year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'YYYY/YYYY'}),
            'current_term': forms.Select(attrs={'class': 'form-control'}),
            'school_name': forms.TextInput(attrs={'class': 'form-control'}),
            'school_address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'school_email': forms.EmailInput(attrs={'class': 'form-control'}),
            'principal_name': forms.TextInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        # Lazy import to avoid circular imports
        from core.models import SchoolConfiguration
        self.Meta.model = SchoolConfiguration
        super().__init__(*args, **kwargs)
    
    def clean_school_phone(self):
        phone_number = self.cleaned_data.get('school_phone')
        if phone_number:
            phone_number = phone_number.replace(' ', '').replace('-', '')
            if len(phone_number) != 10 or not phone_number.startswith('0'):
                raise ValidationError("Phone number must be exactly 10 digits starting with 0")
        return phone_number
    
    def clean_academic_year(self):
        academic_year = self.cleaned_data.get('academic_year')
        if academic_year:
            if not re.match(r'^\d{4}/\d{4}$', academic_year):
                raise forms.ValidationError("Academic year must be in format YYYY/YYYY")
            
            try:
                year1, year2 = map(int, academic_year.split('/'))
                if year2 != year1 + 1:
                    raise forms.ValidationError("The second year should be exactly one year after the first year")
            except (ValueError, IndexError):
                raise forms.ValidationError("Invalid academic year format")
        
        return academic_year


