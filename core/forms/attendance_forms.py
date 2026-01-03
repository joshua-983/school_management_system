from core.models import (
    AcademicTerm, AttendancePeriod, StudentAttendance, 
    Student, ClassAssignment, CLASS_LEVEL_CHOICES
)
from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone
import logging
import re

logger = logging.getLogger(__name__)



class AcademicTermForm(forms.ModelForm):
    class Meta:
        model = AcademicTerm
        fields = ['period_system', 'period_number', 'name', 'academic_year', 'start_date', 'end_date', 'is_active']
        widgets = {
            'period_system': forms.Select(attrs={'class': 'form-select'}),
            'period_number': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional custom name (e.g., "First Term")'}),
            'academic_year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'YYYY/YYYY'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'academic_year': 'Format: YYYY/YYYY (e.g., 2024/2025)',
            'is_active': 'Only one period can be active per academic year',
            'name': 'Optional. If empty, will be generated automatically',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Dynamically set period_number choices based on selected system
        if 'period_system' in self.data:
            period_system = self.data.get('period_system')
        elif self.instance.pk:
            period_system = self.instance.period_system
        else:
            period_system = 'TERM'
        
        # Get period choices for the selected system
        from core.models.base import get_period_choices_for_system
        period_choices = get_period_choices_for_system(period_system)
        
        # Update period_number field choices
        self.fields['period_number'].widget = forms.Select(choices=period_choices)
        
        # Make academic_year read-only for existing terms
        if self.instance and self.instance.pk:
            self.fields['academic_year'].widget.attrs['readonly'] = True
            self.fields['academic_year'].widget.attrs['class'] = 'readonly'
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        academic_year = cleaned_data.get('academic_year')
        period_system = cleaned_data.get('period_system')
        period_number = cleaned_data.get('period_number')
        
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError("End date must be after start date")
            
            delta = end_date - start_date
            if delta.days > 150:
                raise ValidationError("Period duration should not exceed 5 months")
            
            overlapping = AcademicTerm.objects.filter(
                Q(start_date__lte=end_date) & Q(end_date__gte=start_date)
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if overlapping.exists():
                raise ValidationError("This academic period overlaps with an existing period")
            
            if academic_year and period_system and period_number:
                existing = AcademicTerm.objects.filter(
                    period_system=period_system,
                    period_number=period_number,
                    academic_year=academic_year
                ).exclude(pk=self.instance.pk if self.instance else None)
                
                if existing.exists():
                    raise ValidationError(
                        f"A {period_system} {period_number} already exists for {academic_year}"
                    )
        
        return cleaned_data


class AttendancePeriodForm(forms.ModelForm):
    class Meta:
        model = AttendancePeriod
        fields = ['period_type', 'name', 'term', 'start_date', 'end_date', 'is_locked']
        widgets = {
            'period_type': forms.Select(attrs={'class': 'form-select'}),
            'name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional custom name'}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'is_locked': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'name': 'Give a custom name for this period (e.g., "Mid-term Assessment")',
            'is_locked': 'Prevent modifications to attendance records in this period',
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        self.fields['term'].queryset = AcademicTerm.objects.filter(is_active=True)
        
        if self.instance and self.instance.period_type == 'custom':
            self.fields['name'].required = True
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        term = cleaned_data.get('term')
        period_type = cleaned_data.get('period_type')
        name = cleaned_data.get('name')
        
        if start_date and end_date and term:
            if start_date > end_date:
                raise ValidationError("End date must be after start date")
            
            if not (term.start_date <= start_date <= term.end_date and
                    term.start_date <= end_date <= term.end_date):
                raise ValidationError("Period must be within term dates")
            
            if period_type == 'custom' and not name:
                raise ValidationError("Custom period requires a name")
        
        return cleaned_data


class StudentAttendanceForm(forms.ModelForm):
    class Meta:
        model = StudentAttendance
        fields = ['student', 'date', 'status', 'term', 'period', 'notes']
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select'}),
            'date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'period': forms.Select(attrs={'class': 'form-select'}),
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2, 'placeholder': 'Additional notes...'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.class_level = kwargs.pop('class_level', None)
        super().__init__(*args, **kwargs)
        
        active_term = AcademicTerm.objects.filter(is_active=True).first()
        if active_term:
            self.fields['term'].initial = active_term
            self.fields['date'].initial = timezone.now().date()
        
        students_queryset = Student.objects.filter(is_active=True)
        
        if self.class_level:
            students_queryset = students_queryset.filter(class_level=self.class_level)
        
        if self.user and hasattr(self.user, 'teacher'):
            teacher_classes = ClassAssignment.objects.filter(
                teacher=self.user.teacher
            ).values_list('class_level', flat=True)
            
            students_queryset = students_queryset.filter(
                class_level__in=teacher_classes
            )
        
        self.fields['student'].queryset = students_queryset.order_by('last_name', 'first_name')
        
        if 'term' in self.data:
            try:
                term_id = int(self.data.get('term'))
                self.fields['period'].queryset = AttendancePeriod.objects.filter(
                    term_id=term_id
                ).order_by('-start_date')
            except (ValueError, TypeError):
                self.fields['period'].queryset = AttendancePeriod.objects.none()
        elif self.instance.pk:
            self.fields['period'].queryset = self.instance.term.attendanceperiod_set.all()
        else:
            self.fields['period'].queryset = AttendancePeriod.objects.none()
        
        for field_name, field in self.fields.items():
            if field_name != 'notes':
                field.widget.attrs['class'] = 'form-control'

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        date = cleaned_data.get('date')
        term = cleaned_data.get('term')
        period = cleaned_data.get('period')
        
        if student and date and term:
            existing = StudentAttendance.objects.filter(
                student=student,
                date=date,
                term=term
            )
            
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError(
                    f"Attendance record already exists for {student} on {date}"
                )
            
            if not (term.start_date <= date <= term.end_date):
                raise ValidationError(
                    f"Date must be within {term.get_period_display()} ({term.start_date} to {term.end_date})"
                )
            
            if period and not (period.start_date <= date <= period.end_date):
                raise ValidationError(
                    f"Date must be within {period} ({period.start_date} to {period.end_date})"
                )
            
            if period and period.is_locked:
                raise ValidationError("Cannot modify attendance for a locked period")
        
        return cleaned_data


class BulkAttendanceForm(forms.Form):
    term = forms.ModelChoiceField(
        queryset=AcademicTerm.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True,
        label="Academic Period"
    )
    
    period = forms.ModelChoiceField(
        queryset=AttendancePeriod.objects.filter(is_locked=False),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        label="Attendance Period"
    )
    
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=True,
        label="Attendance Date"
    )
    
    class_level = forms.ChoiceField(
        choices=CLASS_LEVEL_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True,
        label="Class Level"
    )
    
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control', 'accept': '.csv,.xlsx,.xls'}),
        required=True,
        label="Attendance File",
        help_text="Upload CSV or Excel file with columns: student_id, status, notes"
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        active_term = AcademicTerm.objects.filter(is_active=True).first()
        if active_term:
            self.fields['term'].initial = active_term
            self.fields['date'].initial = timezone.now().date()
        
        if 'term' in self.data:
            try:
                term_id = int(self.data.get('term'))
                self.fields['period'].queryset = AttendancePeriod.objects.filter(
                    term_id=term_id, is_locked=False
                ).order_by('-start_date')
            except (ValueError, TypeError):
                self.fields['period'].queryset = AttendancePeriod.objects.none()
        elif self.initial.get('term'):
            self.fields['period'].queryset = self.initial['term'].attendanceperiod_set.filter(is_locked=False)
        else:
            self.fields['period'].queryset = AttendancePeriod.objects.none()
        
        if self.user and hasattr(self.user, 'teacher'):
            class_levels = ClassAssignment.objects.filter(
                teacher=self.user.teacher
            ).values_list('class_level', flat=True)
            
            self.fields['class_level'].choices = [
                (level, name) for level, name in CLASS_LEVEL_CHOICES
                if level in class_levels
            ]

    def clean_date(self):
        date = self.cleaned_data.get('date')
        term = self.cleaned_data.get('term')
        
        if date and term:
            if not (term.start_date <= date <= term.end_date):
                raise ValidationError(
                    f"Date must be within {term.get_period_display()} ({term.start_date} to {term.end_date})"
                )
            
            if date > timezone.now().date():
                raise ValidationError("Attendance date cannot be in the future")
        
        return date
    
    def clean_csv_file(self):
        csv_file = self.cleaned_data.get('csv_file')
        if csv_file:
            if not csv_file.name.endswith(('.csv', '.xlsx', '.xls')):
                raise ValidationError("Please upload a CSV or Excel file")
            
            if csv_file.size > 5 * 1024 * 1024:
                raise ValidationError("File size must be less than 5MB")
        
        return csv_file


class AttendanceRecordForm(forms.Form):
    """Form for recording attendance for multiple students at once"""
    
    term = forms.ModelChoiceField(
        queryset=AcademicTerm.objects.filter(is_active=True),
        widget=forms.HiddenInput(),
        required=True
    )
    
    period = forms.ModelChoiceField(
        queryset=AttendancePeriod.objects.filter(is_locked=False),
        widget=forms.HiddenInput(),
        required=False
    )
    
    date = forms.DateField(
        widget=forms.HiddenInput(),
        required=True
    )
    
    class_level = forms.ChoiceField(
        choices=CLASS_LEVEL_CHOICES,
        widget=forms.HiddenInput(),
        required=True
    )
    
    def __init__(self, *args, **kwargs):
        self.students = kwargs.pop('students', [])
        super().__init__(*args, **kwargs)
        
        for student in self.students:
            self.fields[f'status_{student.id}'] = forms.ChoiceField(
                choices=StudentAttendance.STATUS_CHOICES,
                initial='present',
                widget=forms.Select(attrs={'class': 'form-select form-select-sm'}),
                label=f"{student.get_full_name()}",
                required=True
            )
            
            self.fields[f'notes_{student.id}'] = forms.CharField(
                required=False,
                widget=forms.TextInput(attrs={
                    'class': 'form-control form-control-sm',
                    'placeholder': 'Optional notes...'
                }),
                label="Notes"
            )


class AttendanceFilterForm(forms.Form):
    STATUS_CHOICES = [
        ('', 'All Statuses'),
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
        ('sick', 'Sick'),
    ]
    
    term = forms.ModelChoiceField(
        queryset=AcademicTerm.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        label="Academic Period"
    )
    
    period = forms.ModelChoiceField(
        queryset=AttendancePeriod.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        label="Attendance Period"
    )
    
    class_level = forms.ChoiceField(
        choices=[('', 'All Classes')] + list(CLASS_LEVEL_CHOICES),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        label="Class Level"
    )
    
    student = forms.ModelChoiceField(
        queryset=Student.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        label="Student"
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        label="Attendance Status"
    )
    
    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="From Date"
    )
    
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="To Date"
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        active_term = AcademicTerm.objects.filter(is_active=True).first()
        if active_term:
            self.fields['term'].initial = active_term
        
        if self.user and hasattr(self.user, 'teacher'):
            teacher_classes = ClassAssignment.objects.filter(
                teacher=self.user.teacher
            ).values_list('class_level', flat=True)
            
            self.fields['class_level'].choices = [
                (level, name) for level, name in CLASS_LEVEL_CHOICES
                if level in teacher_classes
            ]
            
            self.fields['student'].queryset = Student.objects.filter(
                class_level__in=teacher_classes,
                is_active=True
            )
        
        if 'term' in self.data:
            try:
                term_id = int(self.data.get('term'))
                self.fields['period'].queryset = AttendancePeriod.objects.filter(
                    term_id=term_id
                ).order_by('-start_date')
            except (ValueError, TypeError):
                self.fields['period'].queryset = AttendancePeriod.objects.none()
        elif self.initial.get('term'):
            self.fields['period'].queryset = self.initial['term'].attendanceperiod_set.all()
        else:
            self.fields['period'].queryset = AttendancePeriod.objects.none()
    
    def clean(self):
        cleaned_data = super().clean()
        date_from = cleaned_data.get('date_from')
        date_to = cleaned_data.get('date_to')
        
        if date_from and date_to and date_from > date_to:
            raise ValidationError("From date cannot be after To date")
        
        return cleaned_data