"""
Timetable forms for creating and managing class schedules.
"""
import re
import logging
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models import (
    TimeSlot, Timetable, TimetableEntry, ClassAssignment, Subject, Teacher,
    AcademicTerm, CLASS_LEVEL_CHOICES, TERM_CHOICES
)

logger = logging.getLogger(__name__)


class TimeSlotForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        fields = ['period_number', 'start_time', 'end_time', 'is_break', 'break_name']
        widgets = {
            'period_number': forms.Select(attrs={'class': 'form-control'}),
            'start_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'end_time': forms.TimeInput(attrs={'type': 'time', 'class': 'form-control'}),
            'is_break': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'break_name': forms.TextInput(attrs={'class': 'form-control'}),
        }


class TimetableForm(forms.ModelForm):
    class Meta:
        model = Timetable
        fields = ['class_level', 'day_of_week', 'academic_year', 'term', 'is_active']
        widgets = {
            'class_level': forms.Select(attrs={'class': 'form-control'}),
            'day_of_week': forms.Select(attrs={'class': 'form-control'}),
            'academic_year': forms.TextInput(attrs={'class': 'form-control'}),
            'term': forms.Select(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        current_year = timezone.now().year
        next_year = current_year + 1
        self.fields['academic_year'].initial = f"{current_year}/{next_year}"


class TimetableEntryForm(forms.ModelForm):
    class Meta:
        model = TimetableEntry
        fields = ['time_slot', 'subject', 'teacher', 'classroom', 'is_break']
        widgets = {
            'time_slot': forms.Select(attrs={'class': 'form-control'}),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'teacher': forms.Select(attrs={'class': 'form-control'}),
            'classroom': forms.TextInput(attrs={'class': 'form-control'}),
            'is_break': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        timetable = kwargs.pop('timetable', None)
        super().__init__(*args, **kwargs)
        
        if timetable:
            class_assignments = ClassAssignment.objects.filter(
                class_level=timetable.class_level
            )
            self.fields['teacher'].queryset = Teacher.objects.filter(
                classassignment__in=class_assignments
            ).distinct()
            self.fields['subject'].queryset = Subject.objects.filter(
                classassignment__in=class_assignments
            ).distinct()


class TimetableFilterForm(forms.Form):
    class_level = forms.ChoiceField(
        choices=[('', 'All Classes')] + list(CLASS_LEVEL_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    academic_year = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'YYYY/YYYY'
        })
    )
    
    term = forms.ChoiceField(
        choices=[('', 'All Terms')] + list(TERM_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    day_of_week = forms.ChoiceField(
        choices=[('', 'All Days')] + list(Timetable.DAYS_OF_WEEK),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    is_active = forms.ChoiceField(
        choices=[
            ('', 'All Statuses'),
            ('true', 'Active Only'),
            ('false', 'Inactive Only')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        current_year = timezone.now().year
        self.fields['academic_year'].initial = f"{current_year}/{current_year + 1}"
        
        current_term = AcademicTerm.objects.filter(is_active=True).first()
        if current_term:
            self.fields['term'].initial = current_term.term
    
    def clean_academic_year(self):
        academic_year = self.cleaned_data.get('academic_year')
        if academic_year:
            academic_year = academic_year.replace('-', '/')
            
            if not re.match(r'^\d{4}/\d{4}$', academic_year):
                raise ValidationError("Academic year must be in format YYYY/YYYY")
            
            try:
                year1, year2 = map(int, academic_year.split('/'))
                if year2 != year1 + 1:
                    raise ValidationError("The second year should be exactly one year after the first year")
            except (ValueError, IndexError):
                raise ValidationError("Invalid academic year format")
        
        return academic_year