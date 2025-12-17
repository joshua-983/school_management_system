"""
Assignment forms for creating and managing assignments.
"""
import os
import logging
from decimal import Decimal
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.urls import reverse

from core.models import (
    Subject, ClassAssignment, Assignment, AssignmentTemplate, 
    StudentAssignment, Teacher, Student, Notification,
    CLASS_LEVEL_CHOICES
)
from core.utils import is_teacher, is_admin

logger = logging.getLogger(__name__)


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'description', 'is_active']
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter subject name'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter subject description (optional)'
            }),
            'is_active': forms.CheckboxInput(attrs={
                'class': 'form-check-input'
            }),
        }
        labels = {
            'name': 'Subject Name',
            'description': 'Description',
            'is_active': 'Is Active'
        }
        help_texts = {
            'name': 'Enter the full name of the subject. The subject code will be automatically generated.',
            'is_active': 'Uncheck to hide this subject from selection'
        }
    
    def clean_name(self):
        name = self.cleaned_data.get('name')
        if name:
            name = name.strip()
            
            existing = Subject.objects.filter(name__iexact=name)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError("A subject with this name already exists.")
        
        return name
    
    def save(self, commit=True):
        if not self.instance.pk and not self.instance.code:
            self.instance.code = self.instance.generate_subject_code()
        return super().save(commit=commit)


class AssignmentForm(forms.ModelForm):
    """Enhanced assignment form with better validation and auto-assignment creation"""
    
    class Meta:
        model = Assignment
        fields = [
            'title', 'description', 'assignment_type', 
            'due_date', 'max_score', 'weight', 'attachment'
        ]
        widgets = {
            'due_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local', 
                'class': 'form-control',
                'min': timezone.now().strftime('%Y-%m-%dT%H:%M')
            }),
            'description': forms.Textarea(attrs={
                'rows': 4, 
                'class': 'form-control',
                'placeholder': 'Provide detailed instructions and requirements for this assignment...'
            }),
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter assignment title'
            }),
            'assignment_type': forms.Select(attrs={'class': 'form-control'}),
            'max_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '100',
                'step': '1',
                'value': '100'
            }),
            'weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '100',
                'step': '1',
                'value': '10'
            }),
            'attachment': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.txt,.zip,.jpg,.jpeg,.png,.ppt,.pptx'
            }),
        }
        help_texts = {
            'attachment': 'Upload assignment document, instructions, or resources (optional) - Max 50MB',
            'max_score': 'Maximum score students can achieve (1-100)',
            'weight': 'How much this assignment counts toward the final grade (1-100%)',
            'due_date': 'Date and time when assignment is due',
        }
        labels = {
            'assignment_type': 'Assignment Type',
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        self.class_assignment_id = kwargs.pop('class_assignment_id', None)
        self.class_level = kwargs.pop('class_level', None)
        self.subject_id = kwargs.pop('subject_id', None)
        
        super().__init__(*args, **kwargs)
        
        current_year = timezone.now().year
        self.academic_year = f"{current_year}/{current_year + 1}"
        
        if not self.instance.pk:
            default_due_date = timezone.now() + timezone.timedelta(days=7)
            self.fields['due_date'].initial = default_due_date
        
        self.fields['max_score'].initial = 100
        self.fields['weight'].initial = 10

    def clean(self):
        """Validate form data and handle class_assignment creation"""
        cleaned_data = super().clean()
        due_date = cleaned_data.get('due_date')
        weight = cleaned_data.get('weight')
        max_score = cleaned_data.get('max_score')
        
        if due_date and due_date <= timezone.now():
            self.add_error('due_date', 'Due date must be in the future.')
        
        if weight and (weight < 1 or weight > 100):
            self.add_error('weight', 'Weight must be between 1 and 100 percent.')
        
        if max_score and (max_score < 1 or max_score > 100):
            self.add_error('max_score', 'Maximum score must be between 1 and 100.')
        
        if not self.errors:
            self.handle_class_assignment()
        
        return cleaned_data
    
    def handle_class_assignment(self):
        """Handle class assignment creation or selection"""
        if self.class_assignment_id:
            try:
                class_assignment = ClassAssignment.objects.get(
                    id=self.class_assignment_id,
                    is_active=True
                )
                self.instance.class_assignment = class_assignment
            except ClassAssignment.DoesNotExist:
                raise ValidationError("Selected class assignment is no longer active or doesn't exist.")
        
        elif self.class_level and self.subject_id and self.request:
            try:
                subject = Subject.objects.get(id=self.subject_id, is_active=True)
                
                class_assignment = ClassAssignment.objects.filter(
                    class_level=self.class_level,
                    subject=subject,
                    academic_year=self.academic_year,
                    is_active=True
                ).first()
                
                if class_assignment:
                    self.instance.class_assignment = class_assignment
                else:
                    if is_teacher(self.request.user):
                        teacher = self.request.user.teacher
                        if subject in teacher.subjects.all():
                            class_assignment = ClassAssignment.objects.create(
                                class_level=self.class_level,
                                subject=subject,
                                teacher=teacher,
                                academic_year=self.academic_year,
                                is_active=True
                            )
                            self.instance.class_assignment = class_assignment
                        else:
                            raise ValidationError(
                                f"You are not qualified to teach {subject.name}. "
                                "Please contact administration to update your subject qualifications."
                            )
                    elif is_admin(self.request.user):
                        teacher = Teacher.objects.filter(
                            subjects=subject,
                            is_active=True
                        ).first()
                        
                        if teacher:
                            class_assignment = ClassAssignment.objects.create(
                                class_level=self.class_level,
                                subject=subject,
                                teacher=teacher,
                                academic_year=self.academic_year,
                                is_active=True
                            )
                            self.instance.class_assignment = class_assignment
                        else:
                            raise ValidationError(
                                f"No active teacher found for {subject.name}. "
                                "Please assign a teacher to this subject first."
                            )
            except Subject.DoesNotExist:
                raise ValidationError("Selected subject is no longer active or doesn't exist.")
    
    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        if attachment:
            max_size = 50 * 1024 * 1024  # 50MB
            
            if attachment.size > max_size:
                raise ValidationError(
                    f"File size must be less than 50MB. Your file is {attachment.size / (1024 * 1024):.1f}MB."
                )
            
            allowed_extensions = ['.pdf', '.doc', '.docx', '.txt', '.zip', '.jpg', '.jpeg', '.png', '.ppt', '.pptx']
            file_extension = os.path.splitext(attachment.name)[1].lower()
            
            if file_extension not in allowed_extensions:
                raise ValidationError(
                    f"File type '{file_extension}' is not allowed. "
                    f"Allowed types: {', '.join([ext for ext in allowed_extensions if ext])}"
                )
        
        return attachment

    def save(self, commit=True):
        """Save the assignment and create student assignments"""
        assignment = super().save(commit=False)
    
        if assignment.class_assignment and not assignment.subject_id:
            assignment.subject = assignment.class_assignment.subject
    
        if commit:
            assignment.save()
        
            try:
                assignment.create_student_assignments()
                self.send_assignment_notifications(assignment)
            except Exception as e:
                logger.error(f"Error creating student assignments for assignment {assignment.id}: {str(e)}")
    
        return assignment

    def send_assignment_notifications(self, assignment):
        """Send notifications to students about the new assignment"""
        try:
            # Import here to avoid circular import
            from core.models import Student
            
            students = Student.objects.filter(
                class_level=assignment.class_assignment.class_level,
                is_active=True
            )
            
            for student in students:
                Notification.objects.create(
                    recipient=student.user,
                    title="New Assignment Created",
                    message=f"New assignment '{assignment.title}' has been created for {assignment.subject.name}. Due date: {assignment.due_date.strftime('%b %d, %Y at %I:%M %p')}",
                    notification_type="ASSIGNMENT",
                    link=reverse('assignment_detail', kwargs={'pk': assignment.pk})
                )
            
            logger.info(f"Sent assignment notifications to {students.count()} students")
            
        except Exception as e:
            logger.error(f"Error sending assignment notifications: {str(e)}")


class AssignmentTemplateForm(forms.ModelForm):
    """Form for creating assignment templates"""
    class_levels = forms.MultipleChoiceField(
        choices=CLASS_LEVEL_CHOICES,
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'size': '6'
        }),
        help_text="Select class levels this template applies to (hold Ctrl to select multiple)"
    )
    
    class Meta:
        model = AssignmentTemplate
        fields = [
            'title', 'description', 'assignment_type', 'subject',
            'max_score', 'weight', 'attachment', 'is_public'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter assignment title'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Enter assignment description and instructions...'
            }),
            'assignment_type': forms.Select(attrs={'class': 'form-control'}),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'max_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '100'
            }),
            'weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '100'
            }),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
            'is_public': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'title': 'Template Title',
            'description': 'Description',
            'assignment_type': 'Assignment Type',
            'subject': 'Subject',
            'max_score': 'Maximum Score',
            'weight': 'Weight (%)',
            'attachment': 'Template File',
            'is_public': 'Make Template Public'
        }
        help_texts = {
            'max_score': 'Maximum possible score for this assignment',
            'weight': 'Percentage weight in final grade (1-100)',
            'is_public': 'Allow other teachers to use this template'
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        if self.request and hasattr(self.request.user, 'teacher'):
            teacher = self.request.user.teacher
            self.fields['subject'].queryset = teacher.subjects.all()
            
            teacher_classes = ClassAssignment.objects.filter(
                teacher=teacher
            ).values_list('class_level', flat=True).distinct()
            
            self.fields['class_levels'].choices = [
                (level, name) for level, name in CLASS_LEVEL_CHOICES
                if level in teacher_classes
            ]
    
    def clean_weight(self):
        weight = self.cleaned_data.get('weight')
        if weight and (weight < 1 or weight > 100):
            raise ValidationError("Weight must be between 1 and 100 percent")
        return weight
    
    def clean_max_score(self):
        max_score = self.cleaned_data.get('max_score')
        if max_score and max_score < 1:
            raise ValidationError("Maximum score must be at least 1")
        return max_score


class StudentAssignmentForm(forms.ModelForm):
    """Form for teachers to grade student assignments"""
    class Meta:
        model = StudentAssignment
        fields = ['score', 'feedback', 'status']
        widgets = {
            'score': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0',
                'max': '100'
            }),
            'feedback': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Provide feedback to the student...'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'score': 'Score',
            'feedback': 'Feedback',
            'status': 'Status'
        }
        help_texts = {
            'score': 'Enter score between 0 and assignment maximum score',
            'feedback': 'Provide constructive feedback to help student improve'
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        self.fields['score'].required = False
        self.fields['feedback'].required = False
        
        if self.instance and self.instance.assignment:
            max_score = self.instance.assignment.max_score
            self.fields['score'].widget.attrs['max'] = max_score
            self.fields['score'].help_text = f'Maximum score: {max_score}'

    def clean_score(self):
        score = self.cleaned_data.get('score')
        if score is not None:
            assignment = self.instance.assignment
            if score < 0 or score > assignment.max_score:
                raise ValidationError(
                    f"Score must be between 0 and {assignment.max_score}"
                )
        return score

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        score = cleaned_data.get('score')

        if status == 'GRADED' and score is None:
            raise ValidationError(
                "A score is required for graded assignments"
            )

        return cleaned_data


class TeacherGradingForm(forms.ModelForm):
    """Form for teachers to grade student assignments with enhanced features"""
    class Meta:
        model = StudentAssignment
        fields = ['score', 'feedback', 'status', 'submitted_date']
        widgets = {
            'score': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0'
            }),
            'feedback': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Provide detailed feedback to the student...'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'submitted_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
        }
        labels = {
            'score': 'Assignment Score',
            'feedback': 'Teacher Feedback',
            'status': 'Assignment Status',
            'submitted_date': 'Submission Date'
        }
        help_texts = {
            'score': 'Enter the score for this assignment',
            'feedback': 'Provide constructive feedback to help the student improve',
            'submitted_date': 'Date and time when assignment was submitted'
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.assignment:
            max_score = self.instance.assignment.max_score
            self.fields['score'].widget.attrs['max'] = max_score
            self.fields['score'].help_text = f'Maximum score: {max_score}'
            
            if self.instance.score:
                percentage = (float(self.instance.score) / max_score) * 100
                self.fields['score'].help_text += f' | Current: {self.instance.score}/{max_score} ({percentage:.1f}%)'

    def clean_score(self):
        score = self.cleaned_data.get('score')
        if score is not None:
            assignment = self.instance.assignment
            if score < 0 or score > assignment.max_score:
                raise ValidationError(
                    f"Score must be between 0 and {assignment.max_score}"
                )
        return score

    def clean(self):
        cleaned_data = super().clean()
        status = cleaned_data.get('status')
        score = cleaned_data.get('score')
        submitted_date = cleaned_data.get('submitted_date')

        if status == 'GRADED' and score is None:
            raise ValidationError(
                "A score is required for graded assignments"
            )

        if status in ['SUBMITTED', 'LATE', 'GRADED'] and not submitted_date:
            raise ValidationError(
                "Submission date is required for completed assignments"
            )

        if status == 'PENDING' and submitted_date:
            raise ValidationError(
                "Pending assignments shouldn't have a submission date"
            )

        return cleaned_data


class StudentAssignmentSubmissionForm(forms.ModelForm):
    """Enhanced form for student assignment submission with better file validation"""
    
    class Meta:
        model = StudentAssignment
        fields = ['file', 'feedback']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.txt,.zip,.rar,.jpg,.jpeg,.png,.ppt,.pptx,.xls,.xlsx'
            }),
            'feedback': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Add any comments or notes about your submission...'
            }),
        }
        labels = {
            'file': 'Upload Your Completed Work',
            'feedback': 'Submission Comments (Optional)'
        }
        help_texts = {
            'file': 'Supported formats: PDF, Word, Excel, PowerPoint, Images, ZIP (Max 25MB)',
        }

    def __init__(self, *args, **kwargs):
        self.assignment = kwargs.pop('assignment', None)
        self.student_assignment = kwargs.pop('student_assignment', None)
        super().__init__(*args, **kwargs)
        
        if self.student_assignment and self.student_assignment.file:
            current_file = self.student_assignment.file.name.split('/')[-1]
            self.fields['file'].help_text += f'<br><small>Current file: {current_file}</small>'
            self.fields['file'].required = False
        else:
            self.fields['file'].required = True

    def clean_file(self):
        file = self.cleaned_data.get('file')
        
        if not file and self.instance and self.instance.file:
            return self.instance.file
            
        if file:
            max_size = 25 * 1024 * 1024  # 25MB
            if file.size > max_size:
                raise ValidationError(f"File size must be less than 25MB. Current size: {file.size / (1024*1024):.1f}MB")
            
            allowed_types = [
                'pdf', 'doc', 'docx', 'txt', 'zip', 'rar', 
                'jpg', 'jpeg', 'png', 'ppt', 'pptx', 'xls', 'xlsx'
            ]
            ext = file.name.split('.')[-1].lower()
            if ext not in allowed_types:
                raise ValidationError(
                    f"File type '{ext}' not allowed. Supported types: {', '.join(allowed_types)}"
                )
        
        return file

    def save(self, commit=True):
        student_assignment = super().save(commit=False)
        
        student_assignment.submitted_date = timezone.now()
        
        if student_assignment.submitted_date > student_assignment.assignment.due_date:
            student_assignment.status = 'LATE'
        else:
            student_assignment.status = 'SUBMITTED'
        
        if commit:
            student_assignment.save()
            
            try:
                student_assignment.assignment.update_analytics()
            except Exception as e:
                logger.error(f"Error updating analytics after submission: {str(e)}")
        
        return student_assignment