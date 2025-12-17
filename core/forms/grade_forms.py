"""
Grade forms for entering and managing student grades.
"""
import logging
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models import (
    Grade, Student, Subject, ClassAssignment, 
    Assignment, AcademicTerm, Teacher,
    CLASS_LEVEL_CHOICES, TERM_CHOICES
)
from core.utils import is_teacher, is_admin

logger = logging.getLogger(__name__)


class GradeEntryForm(forms.ModelForm):
    class_level = forms.ChoiceField(
        choices=CLASS_LEVEL_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'id': 'id_class_level'
        }),
        help_text="Select the student's class level"
    )
    
    class Meta:
        model = Grade
        fields = [
            'student', 'subject', 'class_level', 'academic_year', 'term',
            'classwork_score', 'homework_score', 'test_score', 'exam_score', 'remarks'
        ]
        widgets = {
            'academic_year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'YYYY/YYYY'
            }),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional teacher remarks...'
            }),
            'classwork_score': forms.NumberInput(attrs={
                'class': 'form-control score-input',
                'step': '0.01',
                'min': '0',
                'max': '30',
                'placeholder': '0-30'
            }),
            'homework_score': forms.NumberInput(attrs={
                'class': 'form-control score-input',
                'step': '0.01',
                'min': '0',
                'max': '10',
                'placeholder': '0-10'
            }),
            'test_score': forms.NumberInput(attrs={
                'class': 'form-control score-input',
                'step': '0.01',
                'min': '0',
                'max': '10',
                'placeholder': '0-10'
            }),
            'exam_score': forms.NumberInput(attrs={
                'class': 'form-control score-input',
                'step': '0.01',
                'min': '0',
                'max': '50',
                'placeholder': '0-50'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set current academic year and term
        current_year = timezone.now().year
        self.initial['academic_year'] = f"{current_year}/{current_year + 1}"
        
        try:
            active_term = AcademicTerm.objects.filter(is_active=True).first()
            if active_term:
                self.initial['term'] = active_term.term
            else:
                self.initial['term'] = 1
        except:
            self.initial['term'] = 1
        
        # Set initial class_level for existing instances
        if self.instance and self.instance.pk and self.instance.student:
            self.initial['class_level'] = self.instance.student.class_level
        
        # Filter students and subjects based on user role
        if self.user and is_teacher(self.user):
            self.setup_teacher_form()
        else:
            self.setup_admin_form()

    def setup_teacher_form(self):
        """Setup form for teacher users with comprehensive fallback"""
        if not self.user or not hasattr(self.user, 'teacher'):
            return
            
        teacher = self.user.teacher
        
        try:
            # Get class levels this teacher teaches
            teacher_class_levels = ClassAssignment.objects.filter(
                teacher=teacher,
                is_active=True
            ).values_list('class_level', flat=True).distinct()
            
            # Filter class level choices
            self.fields['class_level'].choices = [
                (level, display) for level, display in CLASS_LEVEL_CHOICES 
                if level in teacher_class_levels
            ]
            
            # Filter students to only those in teacher's classes
            self.fields['student'].queryset = Student.objects.filter(
                class_level__in=teacher_class_levels,
                is_active=True
            ).order_by('class_level', 'last_name', 'first_name')
            
            # Get subjects from active class assignments
            class_assignments = ClassAssignment.objects.filter(
                teacher=teacher,
                is_active=True
            ).select_related('subject')
            
            subject_ids = class_assignments.values_list('subject_id', flat=True).distinct()
            
            subjects_queryset = Subject.objects.filter(
                id__in=subject_ids,
                is_active=True
            ).distinct().order_by('name')
            
            # FALLBACK 1: If no subjects from class assignments, use teacher's assigned subjects
            if not subjects_queryset.exists():
                subjects_queryset = teacher.subjects.filter(is_active=True).order_by('name')
            
            # FALLBACK 2: If still no subjects, show all active subjects
            if not subjects_queryset.exists():
                subjects_queryset = Subject.objects.filter(is_active=True).order_by('name')
            
            self.fields['subject'].queryset = subjects_queryset
            
        except Exception as e:
            # Ultimate fallback - show all active subjects
            self.fields['subject'].queryset = Subject.objects.filter(is_active=True).order_by('name')

    def setup_admin_form(self):
        """Setup form for admin users"""
        self.fields['student'].queryset = Student.objects.filter(
            is_active=True
        ).order_by('class_level', 'last_name', 'first_name')
        
        self.fields['subject'].queryset = Subject.objects.filter(
            is_active=True
        ).order_by('name')

    def clean(self):
        """
        Comprehensive validation for grade entry including class level matching
        """
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        class_level = cleaned_data.get('class_level')
        subject = cleaned_data.get('subject')
        academic_year = cleaned_data.get('academic_year')
        term = cleaned_data.get('term')

        # Validate student-class level match (CRITICAL FIX)
        if student and class_level:
            if student.class_level != class_level:
                student_class_display = student.get_class_level_display()
                selected_class_display = dict(CLASS_LEVEL_CHOICES).get(class_level, class_level)
            
                raise ValidationError({
                    'class_level': (
                        f'Cannot assign {selected_class_display} to student {student.get_full_name()} '
                        f'who is currently in {student_class_display}. '
                        f'Please select the correct class level ({student_class_display}) for this student.'
                    )
                })
    
        # Validate subject availability for class level
        if class_level and subject:
            available_subjects = self.get_available_subjects_for_class_level(class_level)
            if subject not in available_subjects:
                raise ValidationError({
                    'subject': (
                        f'Subject "{subject.name}" is not available for {dict(CLASS_LEVEL_CHOICES).get(class_level, class_level)}. '
                        f'Please select a subject that is taught in this class level.'
                    )
                })
    
        # Check for duplicate grades
        if student and subject and academic_year and term:
            existing_grade = Grade.objects.filter(
                student=student,
                subject=subject,
                academic_year=academic_year,
                term=term
            ).exists()
        
            if existing_grade and not self.instance.pk:  # Only for new grades, not updates
                raise ValidationError({
                    '__all__': (
                        f'A grade already exists for {student.get_full_name()} in {subject.name} '
                        f'for {academic_year} Term {term}. Please update the existing grade instead.'
                    )
                })
    
        return cleaned_data

    def get_available_subjects_for_class_level(self, class_level):
        """Get subjects available for a specific class level based on user role"""
        try:
            if hasattr(self, 'user') and is_teacher(self.user):
                # For teachers, only show subjects they teach for that class level
                return Subject.objects.filter(
                    classassignment__class_level=class_level,
                    classassignment__teacher=self.user.teacher,
                    classassignment__is_active=True,
                    is_active=True
                ).distinct()
            else:
                # For admins, show all active subjects for that class level
                return Subject.objects.filter(
                    classassignment__class_level=class_level,
                    classassignment__is_active=True,
                    is_active=True
                ).distinct()
        except Exception as e:
            return Subject.objects.none()

    def clean_class_level(self):
        """Additional validation for class level field"""
        class_level = self.cleaned_data.get('class_level')
        student = self.cleaned_data.get('student')
        
        if student and class_level and student.class_level != class_level:
            raise ValidationError(
                f'Class level must match student\'s current class ({student.get_class_level_display()})'
            )
        
        return class_level

    def get_or_create_class_assignment(self, class_level, subject, academic_year):
        """
        Get or create class assignment for the given parameters with enhanced logic
        """
        try:
            # First try to find existing ACTIVE class assignment
            class_assignment = ClassAssignment.objects.filter(
                class_level=class_level,
                subject=subject,
                academic_year=academic_year,
                is_active=True
            ).first()
            
            if class_assignment:
                return class_assignment
            
            # If no active assignment found, check for any existing assignment (even inactive)
            existing_inactive = ClassAssignment.objects.filter(
                class_level=class_level,
                subject=subject,
                academic_year=academic_year
            ).first()
            
            if existing_inactive:
                # Reactivate the existing assignment
                existing_inactive.is_active = True
                existing_inactive.save()
                return existing_inactive
            
            # If no existing assignment, create a new one
            teacher = None
            
            if self.user and hasattr(self.user, 'teacher'):
                current_teacher = self.user.teacher
                if (current_teacher.is_active and 
                    current_teacher.subjects.filter(id=subject.id).exists()):
                    teacher = current_teacher
            
            # If current teacher not available or not qualified, find any available teacher
            if not teacher:
                teacher = Teacher.objects.filter(
                    subjects=subject,
                    is_active=True
                ).first()
            
            if not teacher:
                return None
            
            # Create the class assignment
            class_assignment = ClassAssignment.objects.create(
                class_level=class_level,
                subject=subject,
                teacher=teacher,
                academic_year=academic_year,
                is_active=True
            )
            
            return class_assignment
            
        except Exception as e:
            return None

    def save(self, commit=True):
        """
        Save the grade with calculated fields and auto-create class assignment
        """
        # Ensure class_level is set from student if not already set
        if self.instance.student and not self.instance.class_level:
            self.instance.class_level = self.instance.student.class_level
        
        # Auto-create class_assignment if not set
        if (not self.instance.class_assignment_id and 
            self.instance.student and 
            self.instance.subject and 
            self.instance.academic_year):
            
            try:
                class_assignment = self.get_or_create_class_assignment(
                    self.instance.class_level,
                    self.instance.subject,
                    self.instance.academic_year.replace('/', '-')
                )
                
                if class_assignment:
                    self.instance.class_assignment = class_assignment
            except Exception as e:
                pass
        
        # Calculate total score and grades
        self.instance.calculate_total_score()
        self.instance.determine_grades()
    
        # Set recorded_by if available
        if hasattr(self, 'user') and self.user:
            self.instance.recorded_by = self.user
    
        return super().save(commit=commit)


class BulkGradeUploadForm(forms.Form):
    assignment = forms.ModelChoiceField(
        queryset=Assignment.objects.none(),
        label="Assignment",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    term = forms.TypedChoiceField(
        choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        coerce=int,
        label="Term",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    file = forms.FileField(
        label="Grade File",
        help_text="CSV or Excel file with student_id and score columns",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.xls'
        })
    )
    
    overwrite_existing = forms.BooleanField(
        required=False,
        initial=False,
        label="Overwrite Existing Grades",
        help_text="Replace existing grades for this assignment",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )

    def __init__(self, *args, **kwargs):
        request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        if request:
            self.fields['assignment'].queryset = self.get_assignments_queryset(request.user)

    def get_assignments_queryset(self, user):
        if is_admin(user):
            return Assignment.objects.all()
        elif is_teacher(user):
            try:
                return Assignment.objects.filter(
                    class_assignment__teacher=user.teacher
                )
            except AttributeError:
                return Assignment.objects.none()
        return Assignment.objects.none()
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            if not file.name.endswith(('.csv', '.xlsx', '.xls')):
                raise ValidationError("Please upload a CSV or Excel file")
            
            if file.size > 5 * 1024 * 1024:
                raise ValidationError("File size must be less than 5MB")
        
        return file