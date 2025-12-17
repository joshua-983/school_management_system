"""
Report card forms for generating and managing student report cards.
"""
from datetime import timedelta
from decimal import Decimal
import re
import logging
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.utils import timezone

from core.models import (
    ReportCard, Student, Grade, AcademicTerm,
    CLASS_LEVEL_CHOICES, TERM_CHOICES
)

logger = logging.getLogger(__name__)


class ReportCardGenerationForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=Student.objects.filter(is_active=True),
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control select2',
            'data-placeholder': 'Select student...'
        })
    )
    
    academic_year = forms.CharField(
        max_length=9,
        required=True,
        validators=[RegexValidator(r'^\d{4}/\d{4}$', 'Enter a valid academic year in format YYYY/YYYY')],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2024/2025',
            'pattern': r'\d{4}/\d{4}'
        })
    )
    
    term = forms.ChoiceField(
        choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    generate_pdf = forms.BooleanField(
        required=False,
        initial=True,
        label="Generate PDF",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    include_comments = forms.BooleanField(
        required=False,
        initial=True,
        label="Include teacher comments",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    include_attendance = forms.BooleanField(
        required=False,
        initial=True,
        label="Include attendance summary",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        current_year = timezone.now().year
        self.fields['academic_year'].initial = f"{current_year}/{current_year + 1}"
    
    def clean_academic_year(self):
        academic_year = self.cleaned_data.get('academic_year')
        if academic_year:
            try:
                year1, year2 = map(int, academic_year.split('/'))
                if year2 != year1 + 1:
                    raise ValidationError("The second year should be exactly one year after the first year")
            except (ValueError, IndexError):
                raise ValidationError("Invalid academic year format. Use YYYY/YYYY")
        
        return academic_year
    
    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        academic_year = cleaned_data.get('academic_year')
        term = cleaned_data.get('term')
        
        if student and academic_year and term:
            # Check if report card already exists
            existing = ReportCard.objects.filter(
                student=student,
                academic_year=academic_year,
                term=term
            ).exists()
            
            if existing:
                self.add_error(
                    None,
                    f"A report card already exists for {student} for {academic_year} Term {term}"
                )
        
        return cleaned_data


class ReportCardFilterForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=Student.objects.filter(is_active=True),
        required=False,
        empty_label="All Students",
        widget=forms.Select(attrs={
            'class': 'form-control select2',
            'data-placeholder': 'Select student...'
        })
    )
    
    academic_year = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2024/2025'
        })
    )
    
    term = forms.ChoiceField(
        choices=[('', 'All Terms')] + list(TERM_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class_level = forms.ChoiceField(
        choices=[('', 'All Classes')] + list(CLASS_LEVEL_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        current_year = timezone.now().year
        self.fields['academic_year'].initial = f"{current_year}/{current_year + 1}"


class TeacherCommentsForm(forms.ModelForm):
    class Meta:
        model = ReportCard
        fields = ['teacher_remarks', 'principal_remarks']
        widgets = {
            'teacher_remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter teacher comments...'
            }),
            'principal_remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter principal comments...'
            }),
        }


class BulkReportCardForm(forms.Form):
    """Form for generating report cards in bulk"""
    academic_year = forms.CharField(
        max_length=9,
        required=True,
        validators=[RegexValidator(r'^\d{4}/\d{4}$', 'Enter a valid academic year in format YYYY/YYYY')],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2024/2025'
        })
    )
    
    term = forms.ChoiceField(
        choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class_levels = forms.MultipleChoiceField(
        choices=CLASS_LEVEL_CHOICES,
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': '6'}),
        help_text="Select specific class levels (leave blank for all)"
    )
    
    include_pdf = forms.BooleanField(
        required=False,
        initial=False,
        label="Generate PDF files",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    overwrite_existing = forms.BooleanField(
        required=False,
        initial=False,
        label="Overwrite existing report cards",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        current_year = timezone.now().year
        self.fields['academic_year'].initial = f"{current_year}/{current_year + 1}"