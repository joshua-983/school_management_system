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

from core.models import Student, ClassAssignment
from core.utils import is_teacher, is_admin

from core.models import (
    ReportCard, Student, Grade, AcademicTerm,
    CLASS_LEVEL_CHOICES, TERM_CHOICES
)

logger = logging.getLogger(__name__)

# ===== REPORT CARD FORMS =====

class ReportCardForm(forms.ModelForm):
    class Meta:
        model = ReportCard
        fields = ['student', 'academic_year', 'term', 'is_published', 'teacher_remarks', 'principal_remarks']
        widgets = {
            'academic_year': forms.Select(choices=[
                ('', 'Select Academic Year'),
                ('2023/2024', '2023/2024'),
                ('2024/2025', '2024/2025'),
                ('2025/2026', '2025/2026'),
            ], attrs={'class': 'form-select'}),
            'term': forms.Select(choices=[
                ('', 'Select Term'),
                (1, 'Term 1'),
                (2, 'Term 2'),
                (3, 'Term 3'),
            ], attrs={'class': 'form-select'}),
            'student': forms.Select(attrs={'class': 'form-select'}),
            'is_published': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'teacher_remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'principal_remarks': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        # FIX: Extract 'user' AND let Django handle 'instance' automatically
        self.user = kwargs.pop('user', None)
        
        # Call parent __init__ FIRST to let Django handle instance properly
        super().__init__(*args, **kwargs)
        
        current_year = timezone.now().year
        next_year = current_year + 1
        current_academic_year = f"{current_year}/{next_year}"
        
        if not self.instance.pk:
            self.initial['academic_year'] = current_academic_year
        
        from .models import Student, ClassAssignment
        from .utils import is_teacher, is_admin
        
        if self.user and self.user.is_authenticated:
            if is_teacher(self.user):
                teacher_classes = ClassAssignment.objects.filter(
                    teacher=self.user.teacher
                ).values_list('class_level', flat=True)
                
                self.fields['student'].queryset = Student.objects.filter(
                    class_level__in=teacher_classes,
                    is_active=True
                ).order_by('class_level', 'last_name', 'first_name')
            elif is_admin(self.user):
                self.fields['student'].queryset = Student.objects.filter(
                    is_active=True
                ).order_by('class_level', 'last_name', 'first_name')
            else:
                self.fields['student'].queryset = Student.objects.none()
        else:
            self.fields['student'].queryset = Student.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        academic_year = cleaned_data.get('academic_year')
        term = cleaned_data.get('term')

        if student and academic_year and term:
            existing_report_card = ReportCard.objects.filter(
                student=student,
                academic_year=academic_year,
                term=term
            )
            
            if self.instance.pk:
                existing_report_card = existing_report_card.exclude(pk=self.instance.pk)
            
            if existing_report_card.exists():
                raise forms.ValidationError(
                    f"A report card already exists for {student.get_full_name()} "
                    f"for {academic_year} Term {term}."
                )

        return cleaned_data



class ReportCardSelectionForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=Student.objects.filter(is_active=True),
        required=True,
        empty_label="Select a student...",
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'student-select'})
    )
    academic_year = forms.ChoiceField(
        choices=[],
        required=True,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'academic-year-select'})
    )
    term = forms.ChoiceField(
        choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        required=True,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'term-select'})
    )
    view_as = forms.ChoiceField(
        choices=[('web', 'Web View'), ('pdf', 'PDF Download')],
        required=True,
        widget=forms.Select(attrs={'class': 'form-control', 'id': 'view-as-select'})
    )
    
    def __init__(self, *args, **kwargs):
        # Handle request parameter if passed
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        # Populate academic years dynamically
        current_year = timezone.now().year
        academic_years = []
        for year in range(current_year - 2, current_year + 1):
            academic_years.append((f"{year}/{year+1}", f"{year}/{year+1}"))
        self.fields['academic_year'].choices = academic_years



# In forms/report_card_forms.py
class ReportCardGenerationForm(forms.Form):
    student = forms.ModelChoiceField(
        queryset=Student.objects.none(),  # Will be set in __init__
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control select2',
            'data-placeholder': 'Select student...'
        })
    )
    
    academic_year = forms.ChoiceField(
        choices=[],  # Will be populated dynamically
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    term = forms.ChoiceField(
        choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    is_published = forms.BooleanField(
        required=False,
        initial=False,
        label="Publish immediately",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Populate academic years
        current_year = timezone.now().year
        academic_years = []
        for i in range(3):  # Last 3 years and next year
            year = current_year - i
            academic_years.append((f"{year}/{year+1}", f"{year}/{year+1}"))
        
        self.fields['academic_year'].choices = [('', 'Select Academic Year')] + academic_years
        
        # Set default academic year to current
        self.fields['academic_year'].initial = f"{current_year}/{current_year+1}"
        
        # Filter students based on user role
        if self.request and self.request.user.is_authenticated:
            if is_teacher(self.request.user):
                # Get teacher's assigned classes
                teacher_classes = ClassAssignment.objects.filter(
                    teacher=self.request.user.teacher
                ).values_list('class_level', flat=True)
                
                self.fields['student'].queryset = Student.objects.filter(
                    class_level__in=teacher_classes,
                    is_active=True
                ).order_by('class_level', 'last_name', 'first_name')
            elif is_admin(self.request.user):
                self.fields['student'].queryset = Student.objects.filter(
                    is_active=True
                ).order_by('class_level', 'last_name', 'first_name')
            else:
                self.fields['student'].queryset = Student.objects.none()
    
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
                raise forms.ValidationError(
                    f"A report card already exists for {student.get_full_name()} "
                    f"for {academic_year} Term {term}. Please view or edit the existing one."
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