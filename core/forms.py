from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date
from django.core.validators import RegexValidator
from .models import *
from .models import Announcement  # Add this with your other imports
from .utils import is_admin, is_teacher

from django.db.models import Q
from django.shortcuts import get_object_or_404
from .models import Fee, FeeCategory, Student






class StudentRegistrationForm(forms.ModelForm):
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)
    
    class Meta:
        model = Student
        fields = ['first_name', 'middle_name', 'last_name', 'date_of_birth', 'gender', 
                 'nationality', 'ethnicity', 'religion', 'place_of_birth', 
                 'residential_address', 'profile_picture', 'class_level']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'residential_address': forms.Textarea(attrs={'rows': 3}),
        }
    
    def clean_date_of_birth(self):
        dob = self.cleaned_data['date_of_birth']
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 4:
            raise ValidationError("Student must be at least 4 years old.")
        return dob
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords don't match")
        
        return cleaned_data
    
    def save(self, commit=True):
        student = super().save(commit=False)
        
        # Create a temporary username - it will be updated after save when student_id is generated
        temp_username = f"temp_{timezone.now().timestamp()}"
        
        user = User.objects.create_user(
            username=temp_username,
            password=self.cleaned_data['password1'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
        )
        
        student.user = user
        if commit:
            student.save()
            
            # Update the username to match the generated student_id
            user.username = student.student_id
            user.save()
            
        return student

class ParentGuardianForm(forms.ModelForm):
    class Meta:
        model = ParentGuardian
        fields = ['student', 'full_name', 'occupation', 'relationship', 
                'phone_number', 'email', 'address', 'is_emergency_contact',
                'emergency_contact_priority']
        widgets = {
            'address': forms.Textarea(attrs={'rows': 3}),
            'student': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        student_id = kwargs.pop('student_id', None)
        super().__init__(*args, **kwargs)
        
        if student_id:
            self.fields['student'].initial = student_id
            self.fields['student'].widget = forms.HiddenInput()
    
    def clean(self):
        cleaned_data = super().clean()
        phone_number = cleaned_data.get('phone_number')
        
        if phone_number and not phone_number.isdigit():
            raise ValidationError("Phone number should contain only digits")
        
        return cleaned_data

class FeeCategoryForm(forms.ModelForm):
    class Meta:
        model = FeeCategory
        fields = '__all__'
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
            'class_levels': forms.TextInput(attrs={
                'placeholder': 'P1,P2,J1 etc. Leave blank for all'
            }),
        }

class FeeForm(forms.ModelForm):
    academic_year = forms.CharField(
        help_text="Format: YYYY/YYYY or YYYY-YYYY",
        validators=[RegexValidator(r'^\d{4}[/-]\d{4}$', 'Enter a valid year in format YYYY/YYYY or YYYY-YYYY')]
    )
    
    payment_status = forms.ChoiceField(
        choices=[
            ('paid', 'Paid'),
            ('unpaid', 'Unpaid'),
            ('partial', 'Part Payment'),
            ('overdue', 'Overdue')
        ],
        initial='unpaid'
    )
    
    class Meta:
        model = Fee
        exclude = ['balance', 'receipt_number', 'recorded_by', 'last_updated']
        widgets = {
            'due_date': forms.TextInput(attrs={'readonly': True}),
            'payment_date': forms.TextInput(attrs={'readonly': True}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'amount_payable': forms.NumberInput(attrs={'step': '0.01'}),
            'amount_paid': forms.NumberInput(attrs={'step': '0.01'}),
            'student': forms.HiddenInput(),
        }

    def __init__(self, *args, **kwargs):
        student_id = kwargs.pop('student_id', None)
        super().__init__(*args, **kwargs)
        
        if student_id:
            student = get_object_or_404(Student, pk=student_id)
            self.student = student
            self.fields['student'].initial = student
            
            self.fields['category'].queryset = self.get_applicable_categories(student)
            self.fields['category'].empty_label = "--- Select Fee Type ---"
            
            if not self.initial.get('academic_year'):
                current_year = timezone.now().year
                self.initial['academic_year'] = f"{current_year}/{current_year + 1}"

    def get_applicable_categories(self, student):
        """Get categories that apply to this student's class level"""
        student_class = str(student.class_level)
        
        # Categories that apply to all classes
        qs = FeeCategory.objects.filter(applies_to_all=True)
        
        # Add categories specific to this class level
        specific_categories = FeeCategory.objects.exclude(applies_to_all=True).filter(
            class_levels__contains=student_class
        )
        
        return (qs | specific_categories).distinct().order_by('name')
    
    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        category = cleaned_data.get('category')
        
        # Validate that category is applicable to student's class
        if student and category:
            if not category.applies_to_all:
                student_class = str(student.class_level)
                if not (category.class_levels and student_class in [x.strip() for x in category.class_levels.split(',')]):
                    raise forms.ValidationError(
                        f"The selected category '{category.name}' is not applicable to {student}'s class level."
                    )
        
        amount_payable = cleaned_data.get('amount_payable', Decimal('0.00'))
        amount_paid = cleaned_data.get('amount_paid', Decimal('0.00'))
        payment_status = cleaned_data.get('payment_status')
        
        # Calculate and set balance
        cleaned_data['balance'] = amount_payable - amount_paid
        
        # Validate payment status consistency
        if payment_status == 'paid' and amount_paid != amount_payable:
            raise forms.ValidationError(
                "For 'Paid' status, amount paid must equal amount payable."
            )
        elif payment_status == 'unpaid' and amount_paid > 0:
            raise forms.ValidationError(
                "For 'Unpaid' status, amount paid must be zero."
            )
        elif payment_status == 'partial' and (amount_paid <= 0 or amount_paid >= amount_payable):
            raise forms.ValidationError(
                "For 'Part Payment' status, amount paid must be between 0 and the payable amount."
            )
        elif payment_status == 'overdue' and amount_paid >= amount_payable:
            raise forms.ValidationError(
                "For 'Overdue' status, amount paid must be less than amount payable."
            )
        
        return cleaned_data

    def clean_academic_year(self):
        academic_year = self.cleaned_data['academic_year']
        # Convert to consistent format
        academic_year = academic_year.replace('-', '/')
        
        # Validate the years are consecutive
        try:
            year1, year2 = map(int, academic_year.split('/'))
            if year2 != year1 + 1:
                raise forms.ValidationError("The second year should be exactly one year after the first year.")
        except (ValueError, IndexError):
            raise forms.ValidationError("Invalid academic year format. Use YYYY/YYYY or YYYY-YYYY.")
        
        return academic_year
class FeePaymentForm(forms.ModelForm):
    def __init__(self, *args, **kwargs):
        fee_id = kwargs.pop('fee_id', None)
        super().__init__(*args, **kwargs)
        
        if fee_id:
            fee = get_object_or_404(Fee, pk=fee_id)
            self.fields['fee'].initial = fee
            self.fields['fee'].widget = forms.HiddenInput()
            
            # Set max payment amount as the remaining balance
            self.fields['amount'].widget.attrs['max'] = fee.balance
    
    class Meta:
        model = FeePayment
        fields = '__all__'
        widgets = {
            'payment_date': forms.DateTimeInput(attrs={'type': 'datetime-local'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
        }

class FeeFilterForm(forms.Form):
    academic_year = forms.CharField(required=False)
    term = forms.ChoiceField(
        choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        required=False
    )
    payment_status = forms.ChoiceField(
        choices=Fee.PAYMENT_STATUS_CHOICES,
        required=False
    )
    category = forms.ModelChoiceField(
        queryset=FeeCategory.objects.all(),
        required=False
    )
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        required=False
    )


class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class TeacherRegistrationForm(forms.ModelForm):
    password1 = forms.CharField(label='Password', widget=forms.PasswordInput)
    password2 = forms.CharField(label='Confirm Password', widget=forms.PasswordInput)
    
    class Meta:
        model = Teacher
        fields = ['first_name', 'last_name', 'date_of_birth', 'gender', 'phone_number', 
                 'email', 'address', 'subjects', 'class_levels']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'address': forms.Textarea(attrs={'rows': 3}),
            'subjects': forms.CheckboxSelectMultiple(),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords don't match")
        
        return cleaned_data
    
    def save(self, commit=True):
        teacher = super().save(commit=False)
        user = User.objects.create_user(
            username=f"teacher_{self.cleaned_data['email']}",
            password=self.cleaned_data['password1'],
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
            is_staff=True
        )
        teacher.user = user
        if commit:
            teacher.save()
            self.save_m2m()
        return teacher

class AssignmentForm(forms.ModelForm):
    class Meta:
        model = Assignment
        fields = ['title', 'description', 'assignment_type', 'subject',
                 'class_assignment', 'due_date', 'max_score', 'weight']
        widgets = {
            'due_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'description': forms.Textarea(attrs={'rows': 3}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        if self.request and hasattr(self.request.user, 'teacher'):
            teacher = self.request.user.teacher
            self.fields['subject'].queryset = Subject.objects.filter(teachers=teacher)
            self.fields['class_assignment'].queryset = ClassAssignment.objects.filter(teacher=teacher)

    def clean(self):
        cleaned_data = super().clean()
        
        # Validate teacher can only assign to their classes
        if self.request and hasattr(self.request.user, 'teacher'):
            class_assignment = cleaned_data.get('class_assignment')
            if class_assignment and class_assignment.teacher != self.request.user.teacher:
                raise ValidationError("You can only create assignments for your classes")
        
        return cleaned_data

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        if due_date and due_date < timezone.now():
            raise ValidationError("Due date cannot be in the past")
        return due_date

    def clean_weight(self):
        weight = self.cleaned_data.get('weight')
        if weight and (weight < 0 or weight > 100):
            raise ValidationError("Weight must be between 0 and 100")
        return weight

class ClassAssignmentForm(forms.ModelForm):
    class Meta:
        model = ClassAssignment
        fields = ['subject', 'class_level', 'academic_year']
        
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        if self.request and hasattr(self.request.user, 'teacher'):
            self.fields['subject'].queryset = Subject.objects.filter(
                teachers=self.request.user.teacher
            )

class GradeForm(forms.ModelForm):
    class Meta:
        model = Grade
        fields = ['student', 'subject', 'class_assignment', 'academic_year', 'term',
                'homework_score', 'classwork_score', 'test_score', 'exam_score', 'remarks']
        widgets = {
            'remarks': forms.Textarea(attrs={'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if 'class_assignment' in self.fields and self.instance.pk:
            self.fields['class_assignment'].disabled = True
    
    def clean(self):
        cleaned_data = super().clean()
        homework = cleaned_data.get('homework_score', 0)
        classwork = cleaned_data.get('classwork_score', 0)
        test = cleaned_data.get('test_score', 0)
        exam = cleaned_data.get('exam_score', 0)
        
        if homework > 20:
            self.add_error('homework_score', 'Homework score cannot exceed 20')
        if classwork > 30:
            self.add_error('classwork_score', 'Classwork score cannot exceed 30')
        if test > 10:
            self.add_error('test_score', 'Test score cannot exceed 10')
        if exam > 40:
            self.add_error('exam_score', 'Exam score cannot exceed 40')
        
        return cleaned_data
    
#GRADE ENTRIES FORM
class GradeEntryForm(forms.ModelForm):
    class Meta:
        model = Grade
        fields = ['student', 'subject', 'academic_year', 'term',
                'homework_score', 'classwork_score', 'test_score', 'exam_score', 'remarks']
        widgets = {
            'academic_year': forms.TextInput(attrs={
                'placeholder': 'YYYY/YYYY',
                'class': 'form-control'
            }),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'homework_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '20',
                'step': '0.1'
            }),
            'classwork_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '30',
                'step': '0.1'
            }),
            'test_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '10',
                'step': '0.1'
            }),
            'exam_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '40',
                'step': '0.1'
            }),
            'remarks': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Optional comments...'
            }),
        }

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set current academic year as default
        current_year = timezone.now().year
        self.initial['academic_year'] = f"{current_year}/{current_year + 1}"
        
        # Limit students and subjects based on user role
        if user and hasattr(user, 'teacher'):
            teacher = user.teacher
            # Get students in classes taught by this teacher
            class_levels = ClassAssignment.objects.filter(
                teacher=teacher
            ).values_list('class_level', flat=True)
            self.fields['student'].queryset = Student.objects.filter(
                class_level__in=class_levels
            ).order_by('class_level', 'last_name', 'first_name')
            
            # Get subjects taught by this teacher
            self.fields['subject'].queryset = teacher.subjects.all()
        else:
            # Admin sees all students and subjects
            self.fields['student'].queryset = Student.objects.all().order_by(
                'class_level', 'last_name', 'first_name'
            )
            self.fields['subject'].queryset = Subject.objects.all()

class StudentAssignmentForm(forms.ModelForm):
    class Meta:
        model = StudentAssignment
        fields = ['status', 'submitted_date', 'score', 'feedback', 'file']
        widgets = {
            'submitted_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'form-control'
            }),
            'feedback': forms.Textarea(attrs={
                'rows': 3,
                'class': 'form-control'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
            'score': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set required=False for fields that can be blank
        self.fields['submitted_date'].required = False
        self.fields['score'].required = False
        self.fields['feedback'].required = False
        self.fields['file'].required = False

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
        submitted_date = cleaned_data.get('submitted_date')
        file = cleaned_data.get('file')

        # Validate that submitted assignments have a submission date
        if status in ['SUBMITTED', 'LATE', 'GRADED']:
            if not submitted_date:
                raise ValidationError(
                    "Submitted date is required for completed assignments"
                )
            if not file and not self.instance.file:
                raise ValidationError(
                    "File upload is required for completed assignments"
                )

        # Validate that pending assignments don't have submission data
        if status == 'PENDING':
            if submitted_date or file:
                raise ValidationError(
                    "Pending assignments shouldn't have submission data"
                )

        return cleaned_data

class BulkGradeUploadForm(forms.Form):
    assignment = forms.ModelChoiceField(
        queryset=Assignment.objects.none(),
        label="Assignment"
    )
    term = forms.TypedChoiceField(
        choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        coerce=int,
        label="Term"
    )
    file = forms.FileField(
        label="Grade File",
        help_text="CSV or Excel file with student_id and score columns"
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

class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = ['title', 'content', 'target_roles', 'attachment']
        widgets = {
            'content': forms.Textarea(attrs={'rows': 4}),
            'target_roles': forms.CheckboxSelectMultiple(),
        }

class AuditLogFilterForm(forms.Form):
    ACTION_CHOICES = [
        ('', 'All Actions'),
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
    ]
    
    user = forms.ModelChoiceField(
        queryset=User.objects.all(),
        required=False,
        label="Filter by User"
    )
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=False,
        label="Filter by Action"
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="From Date"
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date'}),
        label="To Date"
    )

class ReportCardFilterForm(forms.Form):
    academic_year = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'placeholder': 'YYYY-YYYY'}),
        validators=[RegexValidator(
            regex=r'^\d{4}-\d{4}$',
            message='Academic year must be in YYYY-YYYY format'
        )]
    )
    term = forms.ChoiceField(
        choices=[('', 'All Terms')] + [(i, f'Term {i}') for i in range(1, 4)],
        required=False
    )


class AcademicTermForm(forms.ModelForm):
    class Meta:
        model = AcademicTerm
        fields = ['term', 'academic_year', 'start_date', 'end_date', 'is_active']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'academic_year': forms.TextInput(attrs={'class': 'form-control'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            # Validate term duration (approximately 4 months)
            delta = end_date - start_date
            if delta.days > 120:  # ~4 months
                raise ValidationError("Term duration should be approximately 4 months (3 months school + 1 month vacation)")
            
            # Check for overlapping terms
            overlapping = AcademicTerm.objects.filter(
                Q(start_date__lte=end_date) & Q(end_date__gte=start_date)
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if overlapping.exists():
                raise ValidationError("This term overlaps with an existing term")
        
        return cleaned_data

class AttendancePeriodForm(forms.ModelForm):
    class Meta:
        model = AttendancePeriod
        fields = ['period_type', 'term', 'start_date', 'end_date', 'is_locked']
        widgets = {
            'period_type': forms.Select(attrs={'class': 'form-select'}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'is_locked': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Only show active terms
        self.fields['term'].queryset = AcademicTerm.objects.filter(is_active=True)
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        term = cleaned_data.get('term')
        
        if start_date and end_date and term:
            if start_date > end_date:
                raise ValidationError("End date must be after start date")
            
            if not (term.start_date <= start_date <= term.end_date and
                    term.start_date <= end_date <= term.end_date):
                raise ValidationError("Period must be within term dates")
        
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
            'notes': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
        }
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set initial term to current active term
        active_term = AcademicTerm.objects.filter(is_active=True).first()
        if active_term:
            self.fields['term'].initial = active_term
            self.fields['date'].initial = timezone.now().date()
        
        # Limit periods to those in the selected term
        if 'term' in self.data:
            try:
                term_id = int(self.data.get('term'))
                self.fields['period'].queryset = AttendancePeriod.objects.filter(
                    term_id=term_id
                ).order_by('-start_date')
            except (ValueError, TypeError):
                pass
        elif self.instance.pk:
            self.fields['period'].queryset = self.instance.term.attendanceperiod_set.all()
        else:
            self.fields['period'].queryset = AttendancePeriod.objects.none()
        
        # For teachers, limit students to those they teach
        if self.user and hasattr(self.user, 'teacher'):
            class_levels = ClassAssignment.objects.filter(
                teacher=self.user.teacher
            ).values_list('class_level', flat=True)
            self.fields['student'].queryset = Student.objects.filter(
                class_level__in=class_levels
            )
        
        # Add date picker class
        self.fields['date'].widget.attrs.update({'class': 'form-control datepicker'})

class BulkAttendanceForm(forms.Form):
    term = forms.ModelChoiceField(
        queryset=AcademicTerm.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True
    )
    period = forms.ModelChoiceField(
        queryset=AttendancePeriod.objects.filter(is_locked=False),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False
    )
    date = forms.DateField(
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        required=True
    )
    class_level = forms.ChoiceField(
        choices=Student.CLASS_LEVEL_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True
    )
    csv_file = forms.FileField(
        widget=forms.FileInput(attrs={'class': 'form-control'}),
        required=True,
        help_text="CSV file with columns: student_id,status,notes"
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set initial term to current active term
        active_term = AcademicTerm.objects.filter(is_active=True).first()
        if active_term:
            self.fields['term'].initial = active_term
            self.fields['date'].initial = timezone.now().date()
        
        # Limit periods to those in the selected term
        if 'term' in self.data:
            try:
                term_id = int(self.data.get('term'))
                self.fields['period'].queryset = AttendancePeriod.objects.filter(
                    term_id=term_id, is_locked=False
                ).order_by('-start_date')
            except (ValueError, TypeError):
                pass
        elif self.initial.get('term'):
            self.fields['period'].queryset = self.initial['term'].attendanceperiod_set.filter(is_locked=False)
        else:
            self.fields['period'].queryset = AttendancePeriod.objects.none()
        
        # For teachers, limit class levels to those they teach
        if self.user and hasattr(self.user, 'teacher'):
            class_levels = ClassAssignment.objects.filter(
                teacher=self.user.teacher
            ).values_list('class_level', flat=True)
            self.fields['class_level'].choices = [
                (level, name) for level, name in Student.CLASS_LEVEL_CHOICES
                if level in class_levels
            ]

class AttendanceSummaryFilterForm(forms.Form):
    PERIOD_CHOICES = [
        ('', 'All Periods'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('termly', 'Termly'),
    ]
    
    term = forms.ModelChoiceField(
        queryset=AcademicTerm.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False
    )
    period_type = forms.ChoiceField(
        choices=PERIOD_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False
    )
    class_level = forms.ChoiceField(
        choices=Student.CLASS_LEVEL_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False
    )
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set initial term to current active term if not specified
        if not self.data.get('term'):
            active_term = AcademicTerm.objects.filter(is_active=True).first()
            if active_term:
                self.fields['term'].initial = active_term
        
        # For teachers, limit students to those they teach
        if self.user and hasattr(self.user, 'teacher'):
            # Get classes taught by this teacher
            class_levels = ClassAssignment.objects.filter(
                teacher=self.user.teacher
            ).values_list('class_level', flat=True)
            self.fields['class_level'].choices = [
                (level, name) for level, name in Student.CLASS_LEVEL_CHOICES
                if level in class_levels
            ]
            self.fields['student'].queryset = Student.objects.filter(
                class_level__in=class_levels
            )


# Add to your forms.py

class ParentFeePaymentForm(forms.Form):
    PAYMENT_METHODS = [
        ('CASH', 'Cash'),
        ('MPESA', 'M-Pesa'),
        ('CARD', 'Credit/Debit Card'),
        ('BANK', 'Bank Transfer'),
    ]
    
    amount = forms.DecimalField(
        label="Amount to Pay",
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={'class': 'form-control'})
    )
    
    payment_method = forms.ChoiceField(
        label="Payment Method",
        choices=PAYMENT_METHODS,
        widget=forms.Select(attrs={'class': 'form-select'})
    )

class ParentAttendanceFilterForm(forms.Form):
    STATUS_CHOICES = [
        ('', 'All Statuses'),
        ('PRESENT', 'Present'),
        ('ABSENT', 'Absent'),
        ('LATE', 'Late'),
        ('EXCUSED', 'Excused'),
    ]
    
    student = forms.ModelChoiceField(
        queryset=Student.objects.none(),
        required=False,
        label="Child",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    date_from = forms.DateField(
        required=False,
        label="From Date",
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    date_to = forms.DateField(
        required=False,
        label="To Date",
        widget=forms.DateInput(attrs={'class': 'form-control', 'type': 'date'})
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and hasattr(user, 'parentguardian'):
            self.fields['student'].queryset = user.parentguardian.student.all()

