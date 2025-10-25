from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
from django.apps import apps
import re
from datetime import date, timedelta
from decimal import Decimal
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator

from .models import (
    Student, Teacher, ParentGuardian, Subject, ClassAssignment,
    AcademicTerm, AttendancePeriod, StudentAttendance, AttendanceSummary,
    Grade, Assignment, AssignmentTemplate, StudentAssignment, FeeCategory, Fee, Bill, FeePayment,
    ReportCard, Announcement, TimeSlot, Timetable, TimetableEntry, SchoolConfiguration,
    CLASS_LEVEL_CHOICES, TERM_CHOICES
)

User = apps.get_model(settings.AUTH_USER_MODEL)

# ===== STUDENT FORMS =====

class StudentRegistrationForm(forms.ModelForm):
    password1 = forms.CharField(
        label='Password', 
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        min_length=8
    )
    password2 = forms.CharField(
        label='Confirm Password', 
        widget=forms.PasswordInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'student@example.com'})
    )
    phone_number = forms.CharField(
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
        model = Student
        fields = [
            'first_name', 'middle_name', 'last_name', 'date_of_birth', 'gender', 
            'nationality', 'ethnicity', 'religion', 'place_of_birth', 
            'residential_address', 'profile_picture', 'class_level', 'email', 'phone_number'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'residential_address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'nationality': forms.TextInput(attrs={'class': 'form-control'}),
            'ethnicity': forms.TextInput(attrs={'class': 'form-control'}),
            'religion': forms.TextInput(attrs={'class': 'form-control'}),
            'place_of_birth': forms.TextInput(attrs={'class': 'form-control'}),
            'class_level': forms.Select(attrs={'class': 'form-control'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def clean_date_of_birth(self):
        dob = self.cleaned_data['date_of_birth']
        today = date.today()
        age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
        if age < 4:
            raise ValidationError("Student must be at least 4 years old.")
        if age > 18:
            raise ValidationError("Student age seems too high. Please verify the date of birth.")
        return dob
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Remove any spaces or dashes
            phone_number = phone_number.replace(' ', '').replace('-', '')
            if len(phone_number) != 10 or not phone_number.startswith('0'):
                raise ValidationError("Phone number must be exactly 10 digits starting with 0")
        return phone_number
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        email = cleaned_data.get('email')
        
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords don't match")
        
        if email and User.objects.filter(email=email).exists():
            raise ValidationError("A user with this email already exists.")
        
        return cleaned_data
    
    def save(self, commit=True):
        student = super().save(commit=False)
        
        # Clean phone number
        if student.phone_number:
            student.phone_number = student.phone_number.replace(' ', '').replace('-', '')
        
        # Create user account
        email = self.cleaned_data['email']
        password = self.cleaned_data['password1']
        
        # Generate username from student data
        base_username = f"{self.cleaned_data['first_name'].lower()}.{self.cleaned_data['last_name'].lower()}"
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=self.cleaned_data['first_name'],
            last_name=self.cleaned_data['last_name'],
        )
        
        student.user = user
        if commit:
            student.save()
            
        return student


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
            
            # Check for duplicate name
            existing = Subject.objects.filter(name__iexact=name)
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise ValidationError("A subject with this name already exists.")
        
        return name
    
    def save(self, commit=True):
        # Ensure code is generated for new subjects
        if not self.instance.pk and not self.instance.code:
            self.instance.code = self.instance.generate_subject_code()
        return super().save(commit=commit)

class StudentProfileForm(forms.ModelForm):
    phone_number = forms.CharField(
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
        model = Student
        fields = [
            'first_name', 'middle_name', 'last_name', 'date_of_birth', 
            'gender', 'profile_picture', 'residential_address', 'nationality',
            'ethnicity', 'religion', 'place_of_birth', 'phone_number'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'residential_address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'first_name': forms.TextInput(attrs={'class': 'form-control'}),
            'middle_name': forms.TextInput(attrs={'class': 'form-control'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'nationality': forms.TextInput(attrs={'class': 'form-control'}),
            'ethnicity': forms.TextInput(attrs={'class': 'form-control'}),
            'religion': forms.TextInput(attrs={'class': 'form-control'}),
            'place_of_birth': forms.TextInput(attrs={'class': 'form-control'}),
            'profile_picture': forms.FileInput(attrs={'class': 'form-control'}),
        }
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Remove any spaces or dashes
            phone_number = phone_number.replace(' ', '').replace('-', '')
            if len(phone_number) != 10 or not phone_number.startswith('0'):
                raise ValidationError("Phone number must be exactly 10 digits starting with 0")
        return phone_number


# ===== TEACHER FORMS =====

class TeacherRegistrationForm(forms.ModelForm):
    username = forms.CharField(
        max_length=150, 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control'}), 
        required=True
    )
    first_name = forms.CharField(
        max_length=100, 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    last_name = forms.CharField(
        max_length=100, 
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    phone_number = forms.CharField(
        max_length=10,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': '0241234567',
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
        model = Teacher
        fields = [
            'date_of_birth', 'gender', 'phone_number', 'address', 'subjects', 
            'class_levels', 'qualification', 'date_of_joining', 'is_class_teacher', 'is_active'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_of_joining': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'gender': forms.Select(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'subjects': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'class_levels': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'P1,P2,P3'}),
            'qualification': forms.TextInput(attrs={'class': 'form-control'}),
            'is_class_teacher': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if self.instance and self.instance.pk:
            self.fields['username'].required = False
            self.fields['password'].required = False
            self.fields['first_name'].required = False
            self.fields['last_name'].required = False
            self.fields['email'].required = False

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Remove any spaces or dashes
            phone_number = phone_number.replace(' ', '').replace('-', '')
            if len(phone_number) != 10 or not phone_number.startswith('0'):
                raise ValidationError("Phone number must be exactly 10 digits starting with 0")
        return phone_number

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower()
            if not re.match(r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$', email):
                raise ValidationError("Please enter a valid email address.")
            
            if not (self.instance and self.instance.pk):
                if User.objects.filter(email=email).exists():
                    raise ValidationError("A teacher with this email already exists.")
        
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and not (self.instance and self.instance.pk):
            if User.objects.filter(username=username).exists():
                raise ValidationError("This username is already taken. Please choose a different one.")
        return username

    def save(self, commit=True):
        if not self.instance.pk:
            user_data = {
                'username': self.cleaned_data['username'],
                'first_name': self.cleaned_data['first_name'],
                'last_name': self.cleaned_data['last_name'],
                'email': self.cleaned_data['email'],
            }
            
            base_username = user_data['username']
            username = base_username
            counter = 1
            while User.objects.filter(username=username).exists():
                username = f"{base_username}{counter}"
                counter += 1
            
            user_data['username'] = username
            
            user = User.objects.create_user(**user_data)
            user.set_password(self.cleaned_data['password'])
            user.save()

            teacher = super().save(commit=False)
            teacher.user = user
        else:
            teacher = super().save(commit=False)
        
        # Clean phone number before saving
        if teacher.phone_number:
            teacher.phone_number = teacher.phone_number.replace(' ', '').replace('-', '')
        
        if commit:
            teacher.save()
            self.save_m2m()
        
        return teacher


class ClassAssignmentForm(forms.ModelForm):
    class Meta:
        model = ClassAssignment
        fields = ['class_level', 'subject', 'teacher', 'academic_year', 'is_active']
        widgets = {
            'academic_year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'YYYY/YYYY'
            }),
            'class_level': forms.Select(attrs={'class': 'form-select'}),
            'subject': forms.Select(attrs={'class': 'form-select'}),
            'teacher': forms.Select(attrs={'class': 'form-select'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'class_level': 'Class Level',
            'subject': 'Subject',
            'teacher': 'Teacher',
            'academic_year': 'Academic Year',
            'is_active': 'Is Active'
        }
        help_texts = {
            'academic_year': 'Format: YYYY/YYYY (e.g., 2024/2025)',
            'is_active': 'Uncheck to deactivate this assignment'
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # For teachers, limit the teacher field to themselves
        if self.request and hasattr(self.request.user, 'teacher'):
            self.fields['teacher'].queryset = Teacher.objects.filter(pk=self.request.user.teacher.pk)
            self.fields['teacher'].initial = self.request.user.teacher
            self.fields['teacher'].disabled = True
        
        # Set current academic year as default
        if not self.instance.pk:
            current_year = timezone.now().year
            self.initial['academic_year'] = f"{current_year}/{current_year + 1}"
    
    def clean_academic_year(self):
        academic_year = self.cleaned_data.get('academic_year')
        if academic_year:
            # Validate format
            if not re.match(r'^\d{4}/\d{4}$', academic_year):
                raise forms.ValidationError("Academic year must be in format YYYY/YYYY")
            
            # Validate consecutive years
            year1, year2 = map(int, academic_year.split('/'))
            if year2 != year1 + 1:
                raise forms.ValidationError("The second year should be exactly one year after the first year")
        
        return academic_year
    
    def clean(self):
        cleaned_data = super().clean()
        class_level = cleaned_data.get('class_level')
        subject = cleaned_data.get('subject')
        teacher = cleaned_data.get('teacher')
        academic_year = cleaned_data.get('academic_year')
        
        # Check for duplicate assignments
        if class_level and subject and teacher and academic_year:
            existing = ClassAssignment.objects.filter(
                class_level=class_level,
                subject=subject,
                teacher=teacher,
                academic_year=academic_year
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise forms.ValidationError(
                    "This teacher is already assigned to teach this subject for this class level and academic year"
                )
        
        # Validate that teacher can teach the subject
        if teacher and subject:
            if subject not in teacher.subjects.all():
                raise forms.ValidationError(
                    f"{teacher.get_full_name()} is not qualified to teach {subject.name}"
                )
        
        return cleaned_data


# ===== PARENT FORMS =====

class ParentGuardianAddForm(forms.ModelForm):
    full_name = forms.CharField(
        max_length=200, 
        required=True, 
        label="Full Name",
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., John Doe'})
    )
    phone_number = forms.CharField(
        max_length=10,
        required=True,
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': '0241234567',
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
        model = ParentGuardian
        fields = [
            'full_name', 'relationship', 'phone_number', 'email', 
            'occupation', 'address', 'is_emergency_contact', 'emergency_contact_priority'
        ]
        widgets = {
            'occupation': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Teacher, Engineer'}),
            'relationship': forms.Select(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'e.g., parent@example.com'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3, 'placeholder': 'Full residential address'}),
            'emergency_contact_priority': forms.NumberInput(attrs={'class': 'form-control', 'min': '1', 'max': '5'}),
            'is_emergency_contact': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.student_id = kwargs.pop('student_id', None)
        super().__init__(*args, **kwargs)
        
        self.fields['relationship'].required = True

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Remove any spaces or dashes
            phone_number = phone_number.replace(' ', '').replace('-', '')
            if len(phone_number) != 10 or not phone_number.startswith('0'):
                raise ValidationError("Phone number must be exactly 10 digits starting with 0")
        return phone_number

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower()
            if not re.match(r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$', email):
                raise ValidationError("Please enter a valid email address.")
        return email

    def save(self, commit=True):
        parent = super().save(commit=False)
        
        # Clean phone number
        if parent.phone_number:
            parent.phone_number = parent.phone_number.replace(' ', '').replace('-', '')
        
        full_name = self.cleaned_data['full_name'].strip()
        name_parts = full_name.split()
        
        if len(name_parts) >= 2:
            first_name = name_parts[0]
            last_name = ' '.join(name_parts[1:])
        else:
            first_name = full_name
            last_name = full_name
        
        username = self.generate_username()
        email = self.cleaned_data.get('email', '')
        
        user = User.objects.create_user(
            username=username,
            password='temp123',
            first_name=first_name,
            last_name=last_name,
            email=email
        )
        
        parent.user = user
        
        if commit:
            parent.save()
            
            if self.student_id:
                try:
                    student = Student.objects.get(pk=self.student_id)
                    parent.students.add(student)
                except Student.DoesNotExist:
                    pass
        
        return parent
    
    def generate_username(self):
        phone = self.cleaned_data.get('phone_number', '')
        clean_phone = ''.join(filter(str.isdigit, phone)) if phone else ''
        
        base_username = f"parent_{clean_phone}" if clean_phone else f"parent_{int(timezone.now().timestamp())}"
        
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}_{counter}"
            counter += 1
        
        return username


# ===== ATTENDANCE FORMS =====

class AcademicTermForm(forms.ModelForm):
    class Meta:
        model = AcademicTerm
        fields = ['term', 'academic_year', 'start_date', 'end_date', 'is_active']
        widgets = {
            'start_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'end_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'academic_year': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'YYYY/YYYY'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        help_texts = {
            'academic_year': 'Format: YYYY/YYYY (e.g., 2024/2025)',
            'is_active': 'Only one term can be active per academic year',
        }
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        academic_year = cleaned_data.get('academic_year')
        term = cleaned_data.get('term')
        
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError("End date must be after start date")
            
            delta = end_date - start_date
            if delta.days > 150:
                raise ValidationError("Term duration should not exceed 5 months")
            
            overlapping = AcademicTerm.objects.filter(
                Q(start_date__lte=end_date) & Q(end_date__gte=start_date)
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if overlapping.exists():
                raise ValidationError("This term overlaps with an existing term")
            
            if academic_year and term:
                existing = AcademicTerm.objects.filter(
                    term=term, academic_year=academic_year
                ).exclude(pk=self.instance.pk if self.instance else None)
                
                if existing.exists():
                    raise ValidationError(
                        f"A {AcademicTerm(term=term).get_term_display()} already exists for {academic_year}"
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
                    f"Date must be within {term} ({term.start_date} to {term.end_date})"
                )
            
            if period and not (period.start_date <= date <= period.end_date):
                raise ValidationError(
                    f"Date must be within {period} ({period.start_date} to {period.end_date})"
                )
            
            if period and period.is_locked:
                raise ValidationError("Cannot modify attendance for a locked period")
        
        return cleaned_data



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
        super().__init__(*args, **kwargs)
        # Set required=False for fields that can be blank
        self.fields['score'].required = False
        self.fields['feedback'].required = False
        
        # Set max score based on assignment
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

        # Validate that graded assignments have a score
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
        super().__init__(*args, **kwargs)
        
        # Set max score based on assignment
        if self.instance and self.instance.assignment:
            max_score = self.instance.assignment.max_score
            self.fields['score'].widget.attrs['max'] = max_score
            self.fields['score'].help_text = f'Maximum score: {max_score}'
            
            # Calculate percentage if score exists
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

        # Validate that graded assignments have a score
        if status == 'GRADED' and score is None:
            raise ValidationError(
                "A score is required for graded assignments"
            )

        # Validate submitted date for completed assignments
        if status in ['SUBMITTED', 'LATE', 'GRADED'] and not submitted_date:
            raise ValidationError(
                "Submission date is required for completed assignments"
            )

        # Validate that pending assignments don't have submission data
        if status == 'PENDING' and submitted_date:
            raise ValidationError(
                "Pending assignments shouldn't have a submission date"
            )

        return cleaned_data



class BulkAttendanceForm(forms.Form):
    term = forms.ModelChoiceField(
        queryset=AcademicTerm.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True,
        label="Academic Term"
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
                    f"Date must be within {term} ({term.start_date} to {term.end_date})"
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
        label="Academic Term"
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

# ===== GRADE FORMS =====

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

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        current_year = timezone.now().year
        self.initial['academic_year'] = f"{current_year}/{current_year + 1}"
        self.initial['term'] = 2
        
        if self.instance and self.instance.pk:
            self.initial['class_level'] = self.instance.student.class_level
        
        if user and hasattr(user, 'teacher'):
            teacher = user.teacher
            teacher_class_levels = ClassAssignment.objects.filter(
                teacher=teacher
            ).values_list('class_level', flat=True).distinct()
            
            self.fields['student'].queryset = Student.objects.filter(
                class_level__in=teacher_class_levels,
                is_active=True
            ).order_by('class_level', 'last_name', 'first_name')
            
            self.fields['subject'].queryset = teacher.subjects.all()
            
            self.fields['class_level'].choices = [
                (level, display) for level, display in CLASS_LEVEL_CHOICES 
                if level in teacher_class_levels
            ]
        else:
            self.fields['student'].queryset = Student.objects.filter(
                is_active=True
            ).order_by('class_level', 'last_name', 'first_name')
            self.fields['subject'].queryset = Subject.objects.all()

        self.fields['student'].widget.attrs.update({
            'class': 'form-select',
            'data-placeholder': 'Select a student'
        })
        self.fields['subject'].widget.attrs.update({
            'class': 'form-select', 
            'data-placeholder': 'Select a subject'
        })
        self.fields['academic_year'].widget.attrs.update({
            'class': 'form-control',
            'placeholder': 'YYYY/YYYY'
        })
        self.fields['term'].widget.attrs.update({
            'class': 'form-select'
        })

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        subject = cleaned_data.get('subject')
        class_level = cleaned_data.get('class_level')
        academic_year = cleaned_data.get('academic_year')
        term = cleaned_data.get('term')
        
        if not all([student, subject, class_level, academic_year, term]):
            return cleaned_data
        
        try:
            class_assignment = ClassAssignment.objects.get(
                class_level=class_level,
                subject=subject,
                academic_year=academic_year
            )
            self.instance.class_assignment = class_assignment
        except ClassAssignment.DoesNotExist:
            class_display = dict(CLASS_LEVEL_CHOICES).get(class_level, class_level)
            raise ValidationError(
                f"No class assignment found for {class_display} - {subject.name} in {academic_year}. "
                f"Please ensure the subject is assigned to this class."
            )
        
        if student and student.class_level != class_level:
            raise ValidationError({
                'class_level': f"Selected class level ({self.get_class_level_display(class_level)}) "
                              f"doesn't match student's actual class ({student.get_class_level_display()})"
            })
        
        existing_grade = Grade.objects.filter(
            student=student,
            subject=subject,
            academic_year=academic_year,
            term=term
        )
        if self.instance.pk:
            existing_grade = existing_grade.exclude(pk=self.instance.pk)
        if existing_grade.exists():
            raise ValidationError(
                "A grade already exists for this student, subject, term, and academic year."
            )
        
        return cleaned_data

    def get_class_level_display(self, class_level):
        return dict(CLASS_LEVEL_CHOICES).get(class_level, class_level)

    def save(self, commit=True):
        self.instance.calculate_total_score()
        self.instance.determine_ges_grade()
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
        # Helper function to check if user is admin
        def is_admin(user):
            return user.is_staff or user.is_superuser
        
        # Helper function to check if user is teacher
        def is_teacher(user):
            return hasattr(user, 'teacher')
        
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
            # Basic file validation
            if not file.name.endswith(('.csv', '.xlsx', '.xls')):
                raise ValidationError("Please upload a CSV or Excel file")
            
            # File size validation (5MB max)
            if file.size > 5 * 1024 * 1024:
                raise ValidationError("File size must be less than 5MB")
        
        return file

# ===== ASSIGNMENT FORMS =====

class AssignmentForm(forms.ModelForm):
    class_level = forms.ChoiceField(
        choices=[('', 'Select Class Level')] + list(CLASS_LEVEL_CHOICES),
        required=True,
        label="Class"
    )

    class Meta:
        model = Assignment
        fields = [
            'title', 'description', 'assignment_type', 'subject', 'class_level',
            'due_date', 'max_score', 'weight', 'attachment'
        ]
        widgets = {
            'due_date': forms.DateTimeInput(attrs={'type': 'datetime-local', 'class': 'form-control'}),
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'assignment_type': forms.Select(attrs={'class': 'form-control'}),
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'class_level': forms.Select(attrs={'class': 'form-control'}),
            'max_score': forms.NumberInput(attrs={'class': 'form-control'}),
            'weight': forms.NumberInput(attrs={'class': 'form-control'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        if 'class_assignment' in self.fields:
            del self.fields['class_assignment']
        
        self.fields['class_level'].choices = [('', 'Select Class')] + list(CLASS_LEVEL_CHOICES)
        self.fields['subject'].queryset = Subject.objects.all()

    def clean(self):
        cleaned_data = super().clean()
        class_level = cleaned_data.get('class_level')
        subject = cleaned_data.get('subject')
        
        if not class_level:
            self.add_error('class_level', "Class level is required.")
        
        if not subject:
            self.add_error('subject', "Subject is required.")
        
        if class_level and subject:
            current_year = timezone.now().year
            academic_year = f"{current_year}/{current_year + 1}"
            
            class_assignment = ClassAssignment.objects.filter(
                class_level=class_level,
                subject=subject
            ).first()
            
            if class_assignment:
                self.instance.class_assignment = class_assignment
            else:
                teachers = Teacher.objects.filter(subjects=subject)
                if teachers.exists():
                    teacher = teachers.first()
                    class_assignment = ClassAssignment.objects.create(
                        class_level=class_level,
                        subject=subject,
                        teacher=teacher,
                        academic_year=academic_year
                    )
                    self.instance.class_assignment = class_assignment
                else:
                    self.add_error(None, f"No teacher available to teach {subject.name}. Please assign a teacher to this subject first.")
        
        due_date = cleaned_data.get('due_date')
        if due_date and due_date <= timezone.now():
            self.add_error('due_date', 'Due date must be in the future')
        
        return cleaned_data


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
        
        # For teachers, limit subjects to what they teach
        if self.request and hasattr(self.request.user, 'teacher'):
            teacher = self.request.user.teacher
            self.fields['subject'].queryset = teacher.subjects.all()
            
            # Set class levels to what teacher teaches
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

class StudentAssignmentSubmissionForm(forms.ModelForm):
    class Meta:
        model = StudentAssignment
        fields = ['file', 'feedback']
        widgets = {
            'file': forms.FileInput(attrs={
                'class': 'form-control',
                'accept': '.pdf,.doc,.docx,.txt,.zip,.rar,.jpg,.jpeg,.png'
            }),
            'feedback': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Add any comments about your submission...'
            }),
        }
        labels = {
            'file': 'Upload Your Work',
            'feedback': 'Comments (Optional)'
        }
        help_texts = {
            'file': 'Supported formats: PDF, Word, Excel, Images (Max 10MB)',
        }

    def __init__(self, *args, **kwargs):
        self.assignment = kwargs.pop('assignment', None)
        super().__init__(*args, **kwargs)
        
        if not self.instance.pk or not self.instance.file:
            self.fields['file'].required = True

    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            max_size = 10 * 1024 * 1024
            if file.size > max_size:
                raise ValidationError("File size must be less than 10MB")
            
            allowed_types = ['pdf', 'doc', 'docx', 'txt', 'zip', 'rar', 'jpg', 'jpeg', 'png']
            ext = file.name.split('.')[-1].lower()
            if ext not in allowed_types:
                raise ValidationError(f"File type not allowed. Allowed types: {', '.join(allowed_types)}")
        
        return file

    def save(self, commit=True):
        student_assignment = super().save(commit=False)
        student_assignment.status = 'SUBMITTED'
        student_assignment.submitted_date = timezone.now()
        
        if commit:
            student_assignment.save()
        
        return student_assignment

# ===== FEE MANAGEMENT FORMS =====

class FeeCategoryForm(forms.ModelForm):
    class Meta:
        model = FeeCategory
        fields = [
            'name', 'description', 'default_amount', 'frequency', 
            'is_mandatory', 'is_active', 'class_levels'
        ]
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'default_amount': forms.NumberInput(attrs={
                'step': '0.01', 
                'min': '0',
                'class': 'form-control',
                'placeholder': '0.00'
            }),
            'frequency': forms.Select(attrs={'class': 'form-control'}),
            'is_mandatory': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'class_levels': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'P1,P2,P3 (leave blank for all classes)'
            }),
        }
        labels = {
            'default_amount': 'Default Amount (GH₵)',
            'class_levels': 'Applicable Class Levels',
        }
        help_texts = {
            'class_levels': 'Comma-separated list (e.g., P1,P2,P3) or leave blank for all classes',
            'frequency': 'How often this fee is charged to students',
        }
    
    def clean_default_amount(self):
        amount = self.cleaned_data.get('default_amount')
        if amount is not None and amount <= 0:
            raise forms.ValidationError("Amount must be greater than 0")
        return amount
    
    def clean_class_levels(self):
        class_levels = self.cleaned_data.get('class_levels', '')
        if class_levels:
            valid_levels = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'J1', 'J2', 'J3']
            levels = [level.strip() for level in class_levels.split(',')]
            invalid_levels = []
            
            for level in levels:
                if level and level not in valid_levels:
                    invalid_levels.append(level)
            
            if invalid_levels:
                raise forms.ValidationError(
                    f"Invalid class level(s): {', '.join(invalid_levels)}. "
                    f"Valid levels are: {', '.join(valid_levels)}"
                )
            
            unique_levels = list(set(levels))
            unique_levels = [level for level in unique_levels if level]
            return ','.join(unique_levels)
        
        return class_levels

class FeeForm(forms.ModelForm):
    academic_year = forms.CharField(
        help_text="Format: YYYY/YYYY or YYYY-YYYY",
        validators=[RegexValidator(r'^\d{4}[/-]\d{4}$', 'Enter a valid year in format YYYY/YYYY or YYYY-YYYY')],
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'YYYY/YYYY'})
    )
    
    payment_status = forms.ChoiceField(
        choices=[
            ('paid', 'Paid'),
            ('unpaid', 'Unpaid'),
            ('partial', 'Part Payment'),
            ('overdue', 'Overdue')
        ],
        initial='unpaid',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        model = Fee
        fields = [
            'student', 'category', 'academic_year', 'term', 'amount_payable', 
            'amount_paid', 'payment_status', 'payment_mode', 'payment_date', 
            'due_date', 'notes', 'bill'
        ]
        widgets = {
            'student': forms.HiddenInput(),
            'due_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'payment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'amount_payable': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'amount_paid': forms.NumberInput(attrs={'step': '0.01', 'class': 'form-control'}),
            'bill': forms.Select(attrs={'class': 'form-control'}),
            'category': forms.Select(attrs={'class': 'form-control'}),
            'term': forms.Select(attrs={'class': 'form-control'}),
            'payment_mode': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        student_id = kwargs.pop('student_id', None)
        super().__init__(*args, **kwargs)
        
        if student_id:
            try:
                student = Student.objects.get(pk=student_id)
                self.fields['student'].initial = student
                self.fields['student'].queryset = Student.objects.filter(pk=student_id)
                
                self.fields['category'].queryset = self.get_applicable_categories(student)
                self.fields['category'].empty_label = "--- Select Fee Type ---"
                
                self.fields['bill'].queryset = Bill.objects.filter(student=student)
                self.fields['bill'].empty_label = "--- Not linked to a bill ---"
                
            except Student.DoesNotExist:
                self.fields['student'].queryset = Student.objects.filter(is_active=True)
                self.fields['bill'].queryset = Bill.objects.all()
        else:
            self.fields['student'].queryset = Student.objects.filter(is_active=True)
            self.fields['bill'].queryset = Bill.objects.all()
        
        if not self.initial.get('academic_year'):
            current_year = timezone.now().year
            self.initial['academic_year'] = f"{current_year}/{current_year + 1}"
        
        self.fields['student'].required = True

    def get_applicable_categories(self, student):
        student_class = str(student.class_level)
        
        qs = FeeCategory.objects.filter(is_active=True)
        applicable_categories = []
        for category in qs:
            if category.class_levels:
                class_levels = [x.strip() for x in category.class_levels.split(',')]
                if student_class in class_levels:
                    applicable_categories.append(category)
            else:
                applicable_categories.append(category)
        
        return FeeCategory.objects.filter(id__in=[cat.id for cat in applicable_categories])
    
    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        category = cleaned_data.get('category')
        bill = cleaned_data.get('bill')
        
        if student and category:
            if category.class_levels:
                student_class = str(student.class_level)
                class_levels = [x.strip() for x in category.class_levels.split(',')] if category.class_levels else []
                if student_class not in class_levels:
                    raise forms.ValidationError(
                        f"The selected category '{category.name}' is not applicable to {student}'s class level ({student.get_class_level_display()})."
                    )
        
        if bill and student and bill.student != student:
            raise forms.ValidationError(
                "The selected bill does not belong to the chosen student."
            )
        
        amount_payable = cleaned_data.get('amount_payable', Decimal('0.00'))
        amount_paid = cleaned_data.get('amount_paid', Decimal('0.00'))
        payment_status = cleaned_data.get('payment_status')
        
        cleaned_data['balance'] = amount_payable - amount_paid
        
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
        academic_year = academic_year.replace('-', '/')
        
        try:
            year1, year2 = map(int, academic_year.split('/'))
            if year2 != year1 + 1:
                raise forms.ValidationError("The second year should be exactly one year after the first year.")
        except (ValueError, IndexError):
            raise forms.ValidationError("Invalid academic year format. Use YYYY/YYYY or YYYY-YYYY.")
        
        return academic_year

class FeePaymentForm(forms.ModelForm):
    class Meta:
        model = FeePayment
        fields = ['fee', 'amount', 'payment_mode', 'payment_date', 'receipt_number', 'notes', 'recorded_by']
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'class': 'form-control'}),
            'recorded_by': forms.HiddenInput(),
            'amount': forms.NumberInput(attrs={'class': 'form-control', 'step': '0.01', 'min': '0.01', 'placeholder': '0.00'}),
            'payment_mode': forms.Select(attrs={'class': 'form-select'}),
            'receipt_number': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Optional'}),
            'fee': forms.HiddenInput(),
        }
        labels = {
            'amount': 'Payment Amount (GH₵)',
            'payment_mode': 'Payment Method',
            'receipt_number': 'Receipt Number',
        }
        help_texts = {
            'receipt_number': 'Optional reference number for tracking',
            'notes': 'Optional notes about this payment',
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        fee_id = kwargs.pop('fee_id', None)
        super().__init__(*args, **kwargs)
        
        self.fields['payment_mode'].empty_label = 'Select Payment Method'
        
        if self.request and self.request.user.is_authenticated:
            self.fields['recorded_by'].initial = self.request.user
        
        if fee_id:
            try:
                fee = Fee.objects.get(pk=fee_id)
                self.fields['fee'].initial = fee
                
                max_amount = float(fee.balance)
                self.fields['amount'].widget.attrs['max'] = max_amount
                self.fields['amount'].help_text = f'Maximum payment: GH₵{fee.balance:.2f}'
                
                if fee.bill:
                    self.fields['bill'] = forms.ModelChoiceField(
                        queryset=Bill.objects.filter(pk=fee.bill.pk),
                        initial=fee.bill,
                        widget=forms.HiddenInput(),
                        required=False
                    )
            except Fee.DoesNotExist:
                self.fields['fee'].widget = forms.HiddenInput()
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        fee = self.cleaned_data.get('fee')
        
        if not fee:
            raise forms.ValidationError("Fee record is required.")
        
        if fee and amount:
            if amount <= 0:
                raise forms.ValidationError("Payment amount must be greater than zero.")
            
            if amount > fee.balance:
                raise forms.ValidationError(
                    f"Payment amount cannot exceed the remaining balance of GH₵{fee.balance:.2f}."
                )
        
        return amount
    
    def clean_payment_date(self):
        payment_date = self.cleaned_data.get('payment_date')
        if not payment_date:
            raise forms.ValidationError("Please select a payment date.")
        
        if hasattr(payment_date, 'date'):
            payment_date = payment_date.date()
        
        today = timezone.now().date()
        
        if payment_date > today:
            raise forms.ValidationError("Payment date cannot be in the future.")
        
        return payment_date

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
        self.user = kwargs.pop('user', None)
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

# ===== ANNOUNCEMENT FORMS =====

class AnnouncementForm(forms.ModelForm):
    class Meta:
        model = Announcement
        fields = [
            'title', 'message', 'priority', 'target_roles', 
            'target_class_levels', 'is_active', 'end_date'
        ]
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Enter announcement title'
            }),
            'message': forms.Textarea(attrs={
                'class': 'form-control',
                'placeholder': 'Enter announcement message',
                'rows': 4
            }),
            'priority': forms.Select(attrs={
                'class': 'form-control'
            }),
            'target_roles': forms.Select(attrs={
                'class': 'form-control'
            }),
            'target_class_levels': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'e.g., P1,P2,P3 (leave blank for all classes)'
            }),
            'end_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['end_date'].required = False
        
        self.fields['priority'].help_text = 'Select the priority level for this announcement'
        self.fields['target_roles'].help_text = 'Select which user roles should see this announcement'
        self.fields['target_class_levels'].help_text = 'Enter specific class levels (comma-separated) or leave blank for all classes'
        self.fields['end_date'].help_text = 'Optional: Set when this announcement should automatically expire'
    
    def clean_target_class_levels(self):
        class_levels = self.cleaned_data.get('target_class_levels', '')
        if class_levels:
            valid_levels = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'J1', 'J2', 'J3']
            levels = [level.strip() for level in class_levels.split(',')]
            invalid_levels = []
            
            for level in levels:
                if level and level not in valid_levels:
                    invalid_levels.append(level)
            
            if invalid_levels:
                raise forms.ValidationError(
                    f"Invalid class level(s): {', '.join(invalid_levels)}. "
                    f"Valid levels are: {', '.join(valid_levels)}"
                )
            
            unique_levels = list(set(levels))
            unique_levels = [level for level in unique_levels if level]
            return ','.join(unique_levels)
        
        return class_levels

# ===== FILTER FORMS =====

class FeeFilterForm(forms.Form):
    academic_year = forms.CharField(required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    term = forms.ChoiceField(
        choices=[('', 'All Terms')] + list(TERM_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    payment_status = forms.ChoiceField(
        choices=[('', 'All Statuses'), ('paid', 'Paid'), ('unpaid', 'Unpaid'), 
                ('partial', 'Partial Payment'), ('overdue', 'Overdue')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    category = forms.ModelChoiceField(
        queryset=FeeCategory.objects.all(),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        required=False,
        empty_label="All Students",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.data.get('academic_year'):
            current_year = timezone.now().year
            self.initial['academic_year'] = f"{current_year}/{current_year + 1}"


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
        label="Filter by User",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=False,
        label="Filter by Action",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    model_name = forms.CharField(
        required=False,
        label="Model Name",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., Student, Teacher, Fee'
        })
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="From Date"
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        label="To Date"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default date range to last 30 days
        self.fields['start_date'].initial = timezone.now().date() - timedelta(days=30)
        self.fields['end_date'].initial = timezone.now().date()
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise ValidationError("Start date cannot be after end date")
        
        return cleaned_data

class FeeStatusReportForm(forms.Form):
    REPORT_TYPE_CHOICES = [
        ('summary', 'Summary Report'),
        ('detailed', 'Detailed Report'),
        ('outstanding', 'Outstanding Fees'),
        ('paid', 'Paid Fees'),
        ('billed', 'Billed Fees'),
        ('unbilled', 'Unbilled Fees'),
    ]
    
    report_type = forms.ChoiceField(
        choices=REPORT_TYPE_CHOICES,
        required=True,
        label="Report Type",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    academic_year = forms.CharField(
        required=False,
        label="Academic Year",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2024/2025'
        })
    )
    
    term = forms.ChoiceField(
        choices=[('', 'All Terms')] + list(TERM_CHOICES),
        required=False,
        label="Term",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class_level = forms.ChoiceField(
        choices=[('', 'All Classes')] + list(CLASS_LEVEL_CHOICES),
        required=False,
        label="Class Level",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    payment_status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + [
            ('PAID', 'Paid'),
            ('UNPAID', 'Unpaid'),
            ('PARTIAL', 'Partial Payment'),
            ('OVERDUE', 'Overdue'),
        ],
        required=False,
        label="Payment Status",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    bill_status = forms.ChoiceField(
        choices=[('', 'All'), ('billed', 'Billed'), ('unbilled', 'Not Billed')],
        required=False,
        label="Bill Status",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    start_date = forms.DateField(
        required=False,
        label="Start Date",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    end_date = forms.DateField(
        required=False,
        label="End Date",
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set current academic year as default
        current_year = timezone.now().year
        self.fields['academic_year'].initial = f"{current_year}/{current_year + 1}"
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise ValidationError("Start date cannot be after end date")
        
        return cleaned_data


class ReportCardFilterForm(forms.Form):
    academic_year = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'YYYY-YYYY'
        }),
        validators=[RegexValidator(
            regex=r'^\d{4}-\d{4}$',
            message='Academic year must be in YYYY-YYYY format'
        )]
    )
    
    term = forms.ChoiceField(
        choices=[('', 'All Terms')] + [(i, f'Term {i}') for i in range(1, 4)],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class_level = forms.ChoiceField(
        choices=[('', 'All Classes')] + list(CLASS_LEVEL_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    student = forms.ModelChoiceField(
        queryset=Student.objects.filter(is_active=True),
        required=False,
        empty_label="All Students",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    is_published = forms.ChoiceField(
        choices=[
            ('', 'All Statuses'),
            ('true', 'Published'),
            ('false', 'Not Published')
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set current academic year as default
        current_year = timezone.now().year
        self.fields['academic_year'].initial = f"{current_year}-{current_year + 1}"
        
        # Role-based filtering
        if user and hasattr(user, 'teacher'):
            teacher_classes = ClassAssignment.objects.filter(
                teacher=user.teacher
            ).values_list('class_level', flat=True)
            
            self.fields['class_level'].choices = [
                (level, name) for level, name in CLASS_LEVEL_CHOICES
                if level in teacher_classes
            ]
            
            self.fields['student'].queryset = Student.objects.filter(
                class_level__in=teacher_classes,
                is_active=True
            )
        
        elif user and hasattr(user, 'parentguardian'):
            # Parents can only see their children's report cards
            parent = user.parentguardian
            self.fields['student'].queryset = parent.students.all()
            self.fields['class_level'].required = False
            self.fields['academic_year'].required = False
        
        elif user and hasattr(user, 'student'):
            # Students can only see their own report cards
            self.fields['student'].queryset = Student.objects.filter(pk=user.student.pk)
            self.fields['student'].initial = user.student
            self.fields['student'].widget = forms.HiddenInput()
            self.fields['class_level'].widget = forms.HiddenInput()
            self.fields['class_level'].initial = user.student.class_level
    
    def clean_academic_year(self):
        academic_year = self.cleaned_data.get('academic_year')
        if academic_year:
            # Convert to consistent format (replace - with /)
            academic_year = academic_year.replace('-', '/')
            
            # Validate the years are consecutive
            try:
                year1, year2 = map(int, academic_year.split('/'))
                if year2 != year1 + 1:
                    raise ValidationError("The second year should be exactly one year after the first year")
            except (ValueError, IndexError):
                raise ValidationError("Invalid academic year format. Use YYYY-YYYY or YYYY/YYYY")
        
        return academic_year

class AttendanceSummaryFilterForm(forms.Form):
    PERIOD_TYPE_CHOICES = [
        ('', 'All Period Types'),
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('custom', 'Custom'),
    ]
    
    term = forms.ModelChoiceField(
        queryset=AcademicTerm.objects.all(),
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=True,
        label="Academic Term"
    )
    
    period_type = forms.ChoiceField(
        choices=PERIOD_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-select'}),
        required=False,
        label="Period Type"
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
    
    min_attendance_rate = forms.IntegerField(
        required=False,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'min': '0',
            'max': '100',
            'placeholder': '0'
        }),
        label="Minimum Attendance Rate (%)",
        help_text="Filter students with attendance rate above this value"
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
        widget=forms.NumberInput(attrs={'class': 'form-control'}),
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    
    payment_method = forms.ChoiceField(
        label="Payment Method",
        choices=PAYMENT_METHODS,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    student = forms.ModelChoiceField(
        queryset=Student.objects.none(),
        widget=forms.HiddenInput(),
        required=True
    )
    
    bill = forms.ModelChoiceField(
        queryset=Bill.objects.none(),
        widget=forms.HiddenInput(),
        required=False
    )
    
    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        if user and hasattr(user, 'parentguardian'):
            parent = user.parentguardian
            # Set students to only the parent's children
            self.fields['student'].queryset = parent.students.all()
            
            # Set bills for the selected student
            if 'student' in self.data:
                try:
                    student_id = int(self.data.get('student'))
                    self.fields['bill'].queryset = Bill.objects.filter(
                        student_id=student_id,
                        status__in=['issued', 'partial', 'overdue']
                    )
                except (ValueError, TypeError):
                    self.fields['bill'].queryset = Bill.objects.none()
            elif self.initial.get('student'):
                self.fields['bill'].queryset = Bill.objects.filter(
                    student=self.initial['student'],
                    status__in=['issued', 'partial', 'overdue']
                )
            else:
                self.fields['bill'].queryset = Bill.objects.none()
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        student = self.cleaned_data.get('student')
        bill = self.cleaned_data.get('bill')
        
        if amount and student:
            if bill:
                # If paying a specific bill
                if amount > bill.balance:
                    raise ValidationError(
                        f"Payment amount cannot exceed the bill balance of GH₵{bill.balance:.2f}."
                    )
            else:
                # If paying general fees
                total_balance = Fee.objects.filter(
                    student=student,
                    payment_status__in=['unpaid', 'partial']
                ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
                
                if amount > total_balance:
                    raise ValidationError(
                        f"Payment amount cannot exceed the total outstanding balance of GH₵{total_balance:.2f}."
                    )
        
        return amount


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
            self.fields['student'].queryset = Student.objects.filter(
                parents__user=user
            )

# ===== BILL FORMS =====

class BillGenerationForm(forms.Form):
    academic_year = forms.CharField(
        max_length=9,
        required=True,
        validators=[RegexValidator(r'^\d{4}/\d{4}$', 'Enter a valid academic year in format YYYY/YYYY')],
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., 2024/2025'})
    )
    
    term = forms.ChoiceField(
        choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class_levels = forms.MultipleChoiceField(
        choices=CLASS_LEVEL_CHOICES,
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control', 'size': 6}),
        help_text="Select specific class levels (leave blank for all)"
    )
    
    due_date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        help_text="Due date for the generated bills"
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'class': 'form-control', 'placeholder': 'Optional notes for the bills'}),
        help_text="Optional notes that will be added to all generated bills"
    )
    
    skip_existing = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Skip students who already have bills for this term"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        current_year = timezone.now().year
        self.fields['academic_year'].initial = f"{current_year}/{current_year + 1}"
        
        default_due_date = timezone.now().date() + timedelta(days=30)
        self.fields['due_date'].initial = default_due_date
    
    def clean_academic_year(self):
        academic_year = self.cleaned_data['academic_year']
        try:
            year1, year2 = map(int, academic_year.split('/'))
            if year2 != year1 + 1:
                raise forms.ValidationError("The second year should be exactly one year after the first year")
        except (ValueError, IndexError):
            raise forms.ValidationError("Invalid academic year format. Use YYYY/YYYY")
        
        return academic_year
    
    def clean_due_date(self):
        due_date = self.cleaned_data['due_date']
        if due_date < timezone.now().date():
            raise forms.ValidationError("Due date cannot be in the past")
        return due_date

# ===== TIMETABLE FORMS =====

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
        super().__init__(*args, **kwargs)
        
        # Set current academic year as default
        current_year = timezone.now().year
        self.fields['academic_year'].initial = f"{current_year}/{current_year + 1}"
        
        # Set current term as default
        current_term = AcademicTerm.objects.filter(is_active=True).first()
        if current_term:
            self.fields['term'].initial = current_term.term
    
    def clean_academic_year(self):
        academic_year = self.cleaned_data.get('academic_year')
        if academic_year:
            # Convert to consistent format
            academic_year = academic_year.replace('-', '/')
            
            # Validate format
            if not re.match(r'^\d{4}/\d{4}$', academic_year):
                raise ValidationError("Academic year must be in format YYYY/YYYY")
            
            # Validate consecutive years
            try:
                year1, year2 = map(int, academic_year.split('/'))
                if year2 != year1 + 1:
                    raise ValidationError("The second year should be exactly one year after the first year")
            except (ValueError, IndexError):
                raise ValidationError("Invalid academic year format")
        
        return academic_year

# ===== SCHOOL CONFIGURATION FORMS =====

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
        model = SchoolConfiguration
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
    
    def clean_school_phone(self):
        phone_number = self.cleaned_data.get('school_phone')
        if phone_number:
            # Remove any spaces or dashes
            phone_number = phone_number.replace(' ', '').replace('-', '')
            if len(phone_number) != 10 or not phone_number.startswith('0'):
                raise ValidationError("Phone number must be exactly 10 digits starting with 0")
        return phone_number
    
    def clean_academic_year(self):
        academic_year = self.cleaned_data.get('academic_year')
        if academic_year:
            # Validate format
            if not re.match(r'^\d{4}/\d{4}$', academic_year):
                raise forms.ValidationError("Academic year must be in format YYYY/YYYY")
            
            # Validate consecutive years
            try:
                year1, year2 = map(int, academic_year.split('/'))
                if year2 != year1 + 1:
                    raise forms.ValidationError("The second year should be exactly one year after the first year")
            except (ValueError, IndexError):
                raise forms.ValidationError("Invalid academic year format")
        
        return academic_year