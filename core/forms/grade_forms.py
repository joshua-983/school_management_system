"""
Grade forms for entering and managing student grades - UPDATED FOR PERCENTAGE SYSTEM
"""
import logging
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from decimal import Decimal
from django.core.validators import MinValueValidator, MaxValueValidator

from core.models import (
    Grade, Student, Subject, ClassAssignment, 
    Assignment, AcademicTerm, Teacher,
    CLASS_LEVEL_CHOICES, TERM_CHOICES
)
from core.models.configuration import SchoolConfiguration
from core.utils import is_teacher, is_admin

logger = logging.getLogger(__name__)


class GradeEntryForm(forms.ModelForm):
    """Form for entering grades with percentage-based system"""
    
    class Meta:
        model = Grade
        fields = [
            'student', 'subject', 'class_level', 'academic_year', 'term',
            'homework_percentage', 'classwork_percentage', 
            'test_percentage', 'exam_percentage', 'remarks'
        ]
        widgets = {
            'student': forms.Select(attrs={'class': 'form-select', 'data-live-search': 'true'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'class_level': forms.Select(attrs={'class': 'form-select'}),
            'academic_year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'YYYY/YYYY',
                'pattern': r'\d{4}/\d{4}'
            }),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'homework_percentage': forms.NumberInput(attrs={
                'class': 'form-control percentage-input',
                'step': '0.1',
                'min': '0',
                'max': '100',
                'placeholder': '0-100%'
            }),
            'classwork_percentage': forms.NumberInput(attrs={
                'class': 'form-control percentage-input',
                'step': '0.1',
                'min': '0',
                'max': '100',
                'placeholder': '0-100%'
            }),
            'test_percentage': forms.NumberInput(attrs={
                'class': 'form-control percentage-input',
                'step': '0.1',
                'min': '0',
                'max': '100',
                'placeholder': '0-100%'
            }),
            'exam_percentage': forms.NumberInput(attrs={
                'class': 'form-control percentage-input',
                'step': '0.1',
                'min': '0',
                'max': '100',
                'placeholder': '0-100%'
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional remarks or comments...'
            }),
        }
        labels = {
            'homework_percentage': 'Homework Score (%)',
            'classwork_percentage': 'Classwork Score (%)',
            'test_percentage': 'Test Score (%)',
            'exam_percentage': 'Exam Score (%)',
        }
        help_texts = {
            'homework_percentage': 'Enter percentage score (0-100%)',
            'classwork_percentage': 'Enter percentage score (0-100%)',
            'test_percentage': 'Enter percentage score (0-100%)',
            'exam_percentage': 'Enter percentage score (0-100%)',
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.config = kwargs.pop('config', None)
        super().__init__(*args, **kwargs)
        
        # Set current academic year if not provided
        if not self.instance.pk and not self.data.get('academic_year'):
            current_year = timezone.now().year
            self.initial['academic_year'] = f"{current_year}/{current_year + 1}"
        
        # Set default term if not provided
        if not self.instance.pk and not self.data.get('term'):
            self.initial['term'] = 1
        
        # Add configuration info to form
        if self.config:
            self.fields['homework_percentage'].help_text += f" (Weight: {self.config.homework_weight}%)"
            self.fields['classwork_percentage'].help_text += f" (Weight: {self.config.classwork_weight}%)"
            self.fields['test_percentage'].help_text += f" (Weight: {self.config.test_weight}%)"
            self.fields['exam_percentage'].help_text += f" (Weight: {self.config.exam_weight}%)"
        
        # Configure percentage fields
        self._configure_percentage_fields()
        
        # Setup form based on user role
        if self.user:
            if is_teacher(self.user):
                self.setup_teacher_form()
            elif is_admin(self.user):
                self.setup_admin_form()
    
    def _configure_percentage_fields(self):
        """Configure percentage fields with 0-100% validation"""
        percentage_fields = {
            'homework_percentage': 'Homework percentage score',
            'classwork_percentage': 'Classwork percentage score',
            'test_percentage': 'Test percentage score',
            'exam_percentage': 'Exam percentage score',
        }
        
        for field_name, help_text in percentage_fields.items():
            self.fields[field_name].widget = forms.NumberInput(attrs={
                'class': 'form-control percentage-input',
                'step': '0.1',
                'min': '0',
                'max': '100',
                'placeholder': '0-100%',
                'data-type': 'percentage'
            })
            self.fields[field_name].help_text = f'{help_text} (0-100%)'
            
            # Set validators for percentage fields
            self.fields[field_name].validators = [
                MinValueValidator(
                    Decimal('0.00'), 
                    message='Percentage cannot be negative'
                ),
                MaxValueValidator(
                    Decimal('100.00'), 
                    message='Percentage cannot exceed 100%'
                )
            ]
    
    def clean_academic_year(self):
        """Validate academic year format"""
        year = self.cleaned_data.get('academic_year')
        if year:
            import re
            pattern = r'^\d{4}/\d{4}$'
            if not re.match(pattern, year):
                raise ValidationError('Academic year must be in format YYYY/YYYY')
            
            # Check consecutive years
            years = year.split('/')
            try:
                year1 = int(years[0])
                year2 = int(years[1])
                if year2 != year1 + 1:
                    raise ValidationError('Academic years must be consecutive (e.g., 2024/2025)')
            except ValueError:
                raise ValidationError('Invalid year values')
        
        return year
    
    def clean(self):
        """
        Comprehensive validation for grade entry including class level matching
        and configuration-based validation
        """
        cleaned_data = super().clean()
        
        # Validate percentage scores
        percentage_fields = [
            'homework_percentage',
            'classwork_percentage',
            'test_percentage',
            'exam_percentage'
        ]
        
        for field in percentage_fields:
            value = cleaned_data.get(field)
            if value is not None:
                try:
                    decimal_value = Decimal(str(value))
                    if decimal_value < Decimal('0.00'):
                        self.add_error(field, 'Percentage cannot be negative')
                    elif decimal_value > Decimal('100.00'):
                        self.add_error(field, 'Percentage cannot exceed 100%')
                except (ValueError, TypeError):
                    self.add_error(field, 'Invalid percentage value')
        
        student = cleaned_data.get('student')
        class_level = cleaned_data.get('class_level')
        subject = cleaned_data.get('subject')
        academic_year = cleaned_data.get('academic_year')
        term = cleaned_data.get('term')
        
        # Validate student-class level match
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
        
        # Calculate and validate weighted total doesn't exceed 100%
        if self.config and all(field in cleaned_data for field in percentage_fields):
            weighted_total = self.calculate_weighted_total(cleaned_data)
            
            if weighted_total > Decimal('100.00'):
                raise ValidationError({
                    '__all__': f'Weighted total cannot exceed 100%. Current total: {weighted_total:.2f}%'
                })
            
            # Store calculated total for display
            self.calculated_total = weighted_total
        
        return cleaned_data
    
    def calculate_weighted_total(self, cleaned_data):
        """Calculate weighted total from percentages"""
        if not self.config:
            return Decimal('0.00')
        
        # Get percentages or default to 0
        homework_percentage = cleaned_data.get('homework_percentage', Decimal('0.00'))
        classwork_percentage = cleaned_data.get('classwork_percentage', Decimal('0.00'))
        test_percentage = cleaned_data.get('test_percentage', Decimal('0.00'))
        exam_percentage = cleaned_data.get('exam_percentage', Decimal('0.00'))
        
        # Get weights from config
        homework_weight = self.config.homework_weight / Decimal('100.00')
        classwork_weight = self.config.classwork_weight / Decimal('100.00')
        test_weight = self.config.test_weight / Decimal('100.00')
        exam_weight = self.config.exam_weight / Decimal('100.00')
        
        # Calculate weighted contributions
        homework_contribution = (homework_percentage / Decimal('100.00')) * homework_weight * Decimal('100.00')
        classwork_contribution = (classwork_percentage / Decimal('100.00')) * classwork_weight * Decimal('100.00')
        test_contribution = (test_percentage / Decimal('100.00')) * test_weight * Decimal('100.00')
        exam_contribution = (exam_percentage / Decimal('100.00')) * exam_weight * Decimal('100.00')
        
        total = homework_contribution + classwork_contribution + test_contribution + exam_contribution
        
        return total
    
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
            logger.error(f"Error getting available subjects: {e}")
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
            logger.error(f"Error setting up teacher form: {e}")
            # Ultimate fallback - show all active subjects
            self.fields['subject'].queryset = Subject.objects.filter(is_active=True).order_by('name')
    
    def setup_admin_form(self):
        """Setup form for admin users"""
        try:
            self.fields['student'].queryset = Student.objects.filter(
                is_active=True
            ).order_by('class_level', 'last_name', 'first_name')
            
            self.fields['subject'].queryset = Subject.objects.filter(
                is_active=True
            ).order_by('name')
        except Exception as e:
            logger.error(f"Error setting up admin form: {e}")
    
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
                logger.warning(f"No teacher found for subject {subject.name} and class {class_level}")
                return None
            
            # Create the class assignment
            class_assignment = ClassAssignment.objects.create(
                class_level=class_level,
                subject=subject,
                teacher=teacher,
                academic_year=academic_year,
                is_active=True
            )
            
            logger.info(f"Created new class assignment: {class_assignment}")
            return class_assignment
            
        except Exception as e:
            logger.error(f"Error creating class assignment: {e}")
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
                logger.error(f"Error creating class assignment during save: {e}")
        
        # Set recorded_by if available
        if hasattr(self, 'user') and self.user:
            self.instance.recorded_by = self.user
        
        return super().save(commit=commit)

class GradeUpdateForm(forms.ModelForm):
    """Simplified form for updating existing grades (percentage-based) - includes hidden required fields"""
    
    class Meta:
        model = Grade
        fields = [
            'homework_percentage', 'classwork_percentage', 'test_percentage', 'exam_percentage', 'remarks'
        ]  # REMOVE required fields from here - they will be handled differently
        widgets = {
            'homework_percentage': forms.NumberInput(attrs={
                'class': 'form-control percentage-input',
                'step': '0.1',
                'min': '0',
                'max': '100',
                'placeholder': '0-100%'
            }),
            'classwork_percentage': forms.NumberInput(attrs={
                'class': 'form-control percentage-input',
                'step': '0.1',
                'min': '0',
                'max': '100',
                'placeholder': '0-100%'
            }),
            'test_percentage': forms.NumberInput(attrs={
                'class': 'form-control percentage-input',
                'step': '0.1',
                'min': '0',
                'max': '100',
                'placeholder': '0-100%'
            }),
            'exam_percentage': forms.NumberInput(attrs={
                'class': 'form-control percentage-input',
                'step': '0.1',
                'min': '0',
                'max': '100',
                'placeholder': '0-100%'
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Optional remarks or comments...'
            }),
        }
        labels = {
            'homework_percentage': 'Homework Score (%)',
            'classwork_percentage': 'Classwork Score (%)',
            'test_percentage': 'Test Score (%)',
            'exam_percentage': 'Exam Score (%)',
        }
        help_texts = {
            'homework_percentage': 'Enter percentage score (0-100%)',
            'classwork_percentage': 'Enter percentage score (0-100%)',
            'test_percentage': 'Enter percentage score (0-100%)',
            'exam_percentage': 'Enter percentage score (0-100%)',
        }
        
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        self.config = kwargs.pop('config', None)
        super().__init__(*args, **kwargs)
        
        # Add configuration info to form
        if self.config:
            self.fields['homework_percentage'].help_text += f" (Weight: {self.config.homework_weight}%)"
            self.fields['classwork_percentage'].help_text += f" (Weight: {self.config.classwork_weight}%)"
            self.fields['test_percentage'].help_text += f" (Weight: {self.config.test_weight}%)"
            self.fields['exam_percentage'].help_text += f" (Weight: {self.config.exam_weight}%)"
        
        # Configure percentage fields with validation
        percentage_fields = {
            'homework_percentage': 'Homework percentage score',
            'classwork_percentage': 'Classwork percentage score',
            'test_percentage': 'Test percentage score',
            'exam_percentage': 'Exam percentage score',
        }
        
        for field_name, help_text in percentage_fields.items():
            if field_name in self.fields:
                self.fields[field_name].help_text = f'{help_text} (0-100%)'
                self.fields[field_name].validators = [
                    MinValueValidator(
                        Decimal('0.00'), 
                        message='Percentage cannot be negative'
                    ),
                    MaxValueValidator(
                        Decimal('100.00'), 
                        message='Percentage cannot exceed 100%'
                    )
                ]
    
    def clean(self):
        """Validate form data for grade updates"""
        cleaned_data = super().clean()
        
        # Validate percentage scores
        percentage_fields = [
            'homework_percentage',
            'classwork_percentage',
            'test_percentage',
            'exam_percentage'
        ]
        
        for field in percentage_fields:
            value = cleaned_data.get(field)
            if value is not None:
                try:
                    decimal_value = Decimal(str(value))
                    if decimal_value < Decimal('0.00'):
                        self.add_error(field, 'Percentage cannot be negative')
                    elif decimal_value > Decimal('100.00'):
                        self.add_error(field, 'Percentage cannot exceed 100%')
                except (ValueError, TypeError):
                    self.add_error(field, 'Invalid percentage value')
        
        # Calculate and validate weighted total doesn't exceed 100%
        if self.config and all(field in cleaned_data for field in percentage_fields):
            weighted_total = self.calculate_weighted_total(cleaned_data)
            
            if weighted_total > Decimal('100.00'):
                raise ValidationError({
                    '__all__': f'Weighted total cannot exceed 100%. Current total: {weighted_total:.2f}%'
                })
            
            # Store calculated total for display
            self.calculated_total = weighted_total
        
        return cleaned_data
    
    def calculate_weighted_total(self, cleaned_data):
        """Calculate weighted total from percentages"""
        if not self.config:
            return Decimal('0.00')
        
        # Get percentages or default to 0
        homework_percentage = cleaned_data.get('homework_percentage', Decimal('0.00'))
        classwork_percentage = cleaned_data.get('classwork_percentage', Decimal('0.00'))
        test_percentage = cleaned_data.get('test_percentage', Decimal('0.00'))
        exam_percentage = cleaned_data.get('exam_percentage', Decimal('0.00'))
        
        # Get weights from config
        homework_weight = self.config.homework_weight / Decimal('100.00')
        classwork_weight = self.config.classwork_weight / Decimal('100.00')
        test_weight = self.config.test_weight / Decimal('100.00')
        exam_weight = self.config.exam_weight / Decimal('100.00')
        
        # Calculate weighted contributions
        homework_contribution = (homework_percentage / Decimal('100.00')) * homework_weight * Decimal('100.00')
        classwork_contribution = (classwork_percentage / Decimal('100.00')) * classwork_weight * Decimal('100.00')
        test_contribution = (test_percentage / Decimal('100.00')) * test_weight * Decimal('100.00')
        exam_contribution = (exam_percentage / Decimal('100.00')) * exam_weight * Decimal('100.00')
        
        total = homework_contribution + classwork_contribution + test_contribution + exam_contribution
        
        return total
    
    def save(self, commit=True):
        """Save the grade with calculated fields"""
        # Ensure class_level is set from student if not already set
        if self.instance.student and not self.instance.class_level:
            self.instance.class_level = self.instance.student.class_level
        
        # Set recorded_by if available
        if hasattr(self, 'user') and self.user:
            self.instance.recorded_by = self.user
        
        return super().save(commit=commit)

class BulkGradeUploadForm(forms.Form):
    """Form for bulk grade upload - UPDATED FOR PERCENTAGE SYSTEM"""
    
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
        label="Grade File (CSV/Excel)",
        help_text="File must contain columns: student_id, homework_%, classwork_%, test_%, exam_%",
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


class QuickGradeEntryForm(forms.Form):
    """Quick grade entry form for multiple students at once"""
    
    subject = forms.ModelChoiceField(
        queryset=Subject.objects.filter(is_active=True),
        label="Subject",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    academic_year = forms.CharField(
        max_length=9,
        initial=f"{timezone.now().year}/{timezone.now().year + 1}",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'YYYY/YYYY'
        })
    )
    
    term = forms.TypedChoiceField(
        choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        coerce=int,
        label="Term",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if self.user and is_teacher(self.user):
            teacher = self.user.teacher
            self.fields['subject'].queryset = Subject.objects.filter(
                classassignment__teacher=teacher,
                classassignment__is_active=True,
                is_active=True
            ).distinct()


class GradeConfigurationForm(forms.ModelForm):
    """Form for updating grade configuration"""
    class Meta:
        from core.models.configuration import SchoolConfiguration
        model = SchoolConfiguration
        fields = [
            'grading_system',
            'school_level',
            'grade_1_min', 'grade_2_min', 'grade_3_min', 'grade_4_min', 
            'grade_5_min', 'grade_6_min', 'grade_7_min', 'grade_8_min', 'grade_9_max',
            'letter_a_plus_min', 'letter_a_min', 'letter_b_plus_min', 'letter_b_min',
            'letter_c_plus_min', 'letter_c_min', 'letter_d_plus_min', 'letter_d_min', 'letter_f_max',
            'classwork_weight', 'homework_weight', 'test_weight', 'exam_weight',
            'passing_mark',
            'is_locked',
        ]
        widgets = {
            'grading_system': forms.Select(attrs={'class': 'form-select'}),
            'school_level': forms.Select(attrs={'class': 'form-select'}),
            'passing_mark': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100'
            }),
            'is_locked': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Add CSS classes to all number fields
        for field_name, field in self.fields.items():
            if isinstance(field, forms.DecimalField):
                field.widget.attrs.update({
                    'class': 'form-control grade-boundary-input',
                    'step': '0.01',
                    'min': '0',
                    'max': '100'
                })
    
    def clean(self):
        """Validate grade boundaries and weights"""
        cleaned_data = super().clean()
        
        # Validate grade boundaries are in descending order
        grade_boundaries = [
            cleaned_data.get('grade_1_min'),
            cleaned_data.get('grade_2_min'),
            cleaned_data.get('grade_3_min'),
            cleaned_data.get('grade_4_min'),
            cleaned_data.get('grade_5_min'),
            cleaned_data.get('grade_6_min'),
            cleaned_data.get('grade_7_min'),
            cleaned_data.get('grade_8_min')
        ]
        
        for i in range(len(grade_boundaries) - 1):
            if grade_boundaries[i] <= grade_boundaries[i + 1]:
                self.add_error(f'grade_{i+1}_min', 
                    f'Grade {i+1} minimum must be greater than Grade {i+2} minimum')
        
        # Validate letter grade boundaries
        letter_boundaries = [
            cleaned_data.get('letter_a_plus_min'),
            cleaned_data.get('letter_a_min'),
            cleaned_data.get('letter_b_plus_min'),
            cleaned_data.get('letter_b_min'),
            cleaned_data.get('letter_c_plus_min'),
            cleaned_data.get('letter_c_min'),
            cleaned_data.get('letter_d_plus_min'),
            cleaned_data.get('letter_d_min')
        ]
        
        for i in range(len(letter_boundaries) - 1):
            if letter_boundaries[i] <= letter_boundaries[i + 1]:
                boundary_names = ['A+', 'A', 'B+', 'B', 'C+', 'C', 'D+', 'D']
                self.add_error(f'letter_{boundary_names[i].lower().replace("+", "_plus")}_min',
                    f'{boundary_names[i]} minimum must be greater than {boundary_names[i+1]} minimum')
        
        # Validate weights total 100%
        total_weight = sum([
            cleaned_data.get('classwork_weight', Decimal('0.00')),
            cleaned_data.get('homework_weight', Decimal('0.00')),
            cleaned_data.get('test_weight', Decimal('0.00')),
            cleaned_data.get('exam_weight', Decimal('0.00'))
        ])
        
        if abs(total_weight - Decimal('100.00')) > Decimal('0.01'):
            self.add_error('__all__', 
                f'Assessment weights must total 100%. Current total: {total_weight:.2f}%')
        
        return cleaned_data


class GradingSystemSelectorForm(forms.Form):
    """Simple form for selecting grading system"""
    grading_system = forms.ChoiceField(
        choices=SchoolConfiguration.GRADING_SYSTEM_CHOICES,
        widget=forms.Select(attrs={
            'class': 'form-select',
            'onchange': 'this.form.submit()'
        }),
        label="Select Grading System"
    )


__all__ = [
    'GradeEntryForm',
    'GradeUpdateForm',
    'BulkGradeUploadForm',
    'QuickGradeEntryForm',
    'GradeConfigurationForm',
    'GradingSystemSelectorForm',
]