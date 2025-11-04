from django import forms
import logging
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q
from django.conf import settings
from django.apps import apps

logger = logging.getLogger(__name__)

import re
from datetime import date, timedelta
from decimal import Decimal
from django.core.validators import RegexValidator, MinValueValidator, MaxValueValidator

from .models import (
    Student, Teacher, ParentGuardian, Subject, ClassAssignment,
    AcademicTerm, AttendancePeriod, StudentAttendance, AttendanceSummary,
    Grade, Assignment, AssignmentTemplate, StudentAssignment, FeeCategory, Fee, Bill, BillPayment, FeePayment,
    ReportCard, Announcement, TimeSlot, Timetable, TimetableEntry, SchoolConfiguration, Budget, Expense,
    FeeDiscount, FeeInstallment, Notification, AuditLog, SecurityEvent,
    CLASS_LEVEL_CHOICES, TERM_CHOICES
)

User = apps.get_model(settings.AUTH_USER_MODEL)


logger = logging.getLogger(__name__)


# ===== STUDENT FORMS =====


# forms.py - Updated StudentRegistrationForm
class StudentRegistrationForm(forms.ModelForm):
    username = forms.CharField(
        label='Username',
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'Choose a username',
            'required': 'required'
        }),
        min_length=3,
        max_length=150,
        help_text="Required. 150 characters or fewer. Letters, digits and @/./+/-/_ only."
    )
    password1 = forms.CharField(
        label='Password', 
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'required': 'required'
        }),
        min_length=8,
        help_text="Password must be at least 8 characters long."
    )
    password2 = forms.CharField(
        label='Confirm Password', 
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'required': 'required'
        }),
        help_text="Enter the same password as above for verification."
    )
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={
            'class': 'form-control', 
            'placeholder': 'student@example.com',
            'required': 'required'
        })
    )
    phone_number = forms.CharField(
        max_length=10,
        required=False,  # Made optional
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
            'residential_address', 'profile_picture', 'class_level', 'username', 'email', 'phone_number'
        ]
        widgets = {
            'date_of_birth': forms.DateInput(attrs={
                'type': 'date', 
                'class': 'form-control'
            }),
            'residential_address': forms.Textarea(attrs={
                'rows': 3, 
                'class': 'form-control', 
                'placeholder': 'Enter residential address'
            }),
            'first_name': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Enter first name'
            }),
            'middle_name': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Enter middle name'
            }),
            'last_name': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Enter last name'
            }),
            'gender': forms.Select(attrs={
                'class': 'form-control',
                'required': 'required'
            }),
            'nationality': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Enter nationality'
            }),
            'ethnicity': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Enter ethnicity'
            }),
            'religion': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Enter religion'
            }),
            'place_of_birth': forms.TextInput(attrs={
                'class': 'form-control', 
                'placeholder': 'Enter place of birth'
            }),
            'class_level': forms.Select(attrs={
                'class': 'form-control',
                'required': 'required'
            }),
            'profile_picture': forms.FileInput(attrs={
                'class': 'form-control'
            }),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make only essential fields required
        self.fields['first_name'].required = False  # Made optional
        self.fields['middle_name'].required = False  # Made optional
        self.fields['last_name'].required = False  # Made optional
        self.fields['date_of_birth'].required = False  # Made optional
        self.fields['gender'].required = True  # Keep required
        self.fields['nationality'].required = False  # Made optional
        self.fields['ethnicity'].required = False  # Made optional
        self.fields['religion'].required = False  # Made optional
        self.fields['place_of_birth'].required = False  # Made optional
        self.fields['residential_address'].required = False  # Made optional
        self.fields['class_level'].required = True  # Keep required
        self.fields['phone_number'].required = False  # Made optional
        self.fields['profile_picture'].required = False  # Made optional
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            # Check if username already exists
            if User.objects.filter(username=username).exists():
                raise ValidationError("A user with this username already exists.")
            
            # Validate username format
            if not re.match(r'^[\w.@+-]+\Z', username):
                raise ValidationError(
                    "Enter a valid username. This value may contain only letters, "
                    "numbers, and @/./+/-/_ characters."
                )
        return username
    
    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        # Remove age validation to accept any age
        if dob:
            today = date.today()
            if dob > today:
                raise ValidationError("Date of birth cannot be in the future.")
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
        
        # Clean phone number if provided
        if student.phone_number:
            student.phone_number = student.phone_number.replace(' ', '').replace('-', '')
        
        # Create user account
        username = self.cleaned_data['username']
        email = self.cleaned_data['email']
        password = self.cleaned_data['password1']
        
        # Use provided names or generate from username if not provided
        first_name = self.cleaned_data.get('first_name', '').strip()
        last_name = self.cleaned_data.get('last_name', '').strip()
        
        if not first_name:
            first_name = "Student"
        if not last_name:
            last_name = username
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,
            first_name=first_name,
            last_name=last_name,
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
            # Note: class_assignment is NOT included here - we'll handle it differently
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
        
        # Set current term
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
        if self.user and hasattr(self.user, 'teacher'):
            self.setup_teacher_form()
        else:
            self.setup_admin_form()

    def setup_teacher_form(self):
        """Setup form for teacher users"""
        teacher = self.user.teacher
        
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
        
        # Filter subjects to only those teacher teaches
        self.fields['subject'].queryset = Subject.objects.filter(
            classassignment__teacher=teacher,
            classassignment__is_active=True
        ).distinct().order_by('name')

    def setup_admin_form(self):
        """Setup form for admin users"""
        self.fields['student'].queryset = Student.objects.filter(
            is_active=True
        ).order_by('class_level', 'last_name', 'first_name')
        
        self.fields['subject'].queryset = Subject.objects.filter(
            is_active=True
        ).order_by('name')

    def clean_class_level(self):
        """Validate class level"""
        class_level = self.cleaned_data.get('class_level')
        student = self.cleaned_data.get('student')
        
        if student and class_level != student.class_level:
            class_display = dict(CLASS_LEVEL_CHOICES).get(class_level, class_level)
            student_class_display = student.get_class_level_display()
            raise ValidationError(
                f"Selected class level ({class_display}) doesn't match student's actual class ({student_class_display})"
            )
        
        return class_level

    def clean(self):
        """
        Comprehensive validation including class_assignment handling
        """
        cleaned_data = super().clean()
        
        # If there are already field errors, don't proceed with cross-field validation
        if self.errors:
            return cleaned_data
            
        student = cleaned_data.get('student')
        subject = cleaned_data.get('subject')
        class_level = cleaned_data.get('class_level')
        academic_year = cleaned_data.get('academic_year')
        term = cleaned_data.get('term')
        
        # Basic field validation
        if not all([student, subject, class_level, academic_year, term]):
            return cleaned_data
        
        # DEBUG: Log the values we're working with
        logger.info(f"Grade form data - Student: {student}, Subject: {subject}, Class Level: {class_level}, Academic Year: {academic_year}")
        
        # Handle class assignment - with enhanced error handling
        try:
            class_assignment = self.get_or_create_class_assignment(
                class_level, subject, academic_year
            )
            
            if class_assignment:
                # Set the class_assignment on the instance
                self.instance.class_assignment = class_assignment
                logger.info(f"Successfully assigned class_assignment: {class_assignment}")
            else:
                # Provide more detailed error information
                error_msg = self.get_detailed_class_assignment_error(class_level, subject, academic_year)
                raise ValidationError(error_msg)
                
        except Exception as e:
            logger.error(f"Error in class assignment handling: {str(e)}")
            raise ValidationError(f"Error setting up class assignment: {str(e)}")
        
        # Check for duplicate grades
        self.validate_no_duplicate_grade(student, subject, academic_year, term)
        
        # Validate scores don't exceed 100%
        self.validate_total_score(cleaned_data)
        
        return cleaned_data

    def get_detailed_class_assignment_error(self, class_level, subject, academic_year):
        """Provide detailed error information about why class assignment failed"""
        error_details = []
        
        # Check if subject exists and is active
        if not subject or not subject.is_active:
            error_details.append(f"Subject '{subject}' is not active or doesn't exist")
        
        # Check for existing class assignments
        existing_assignments = ClassAssignment.objects.filter(
            class_level=class_level,
            subject=subject,
            academic_year=academic_year
        )
        
        if existing_assignments.exists():
            error_details.append(f"Found {existing_assignments.count()} existing class assignments but none are active")
            inactive_assignments = existing_assignments.filter(is_active=False)
            if inactive_assignments.exists():
                error_details.append(f"{inactive_assignments.count()} assignments exist but are inactive")
        
        # Check for available teachers
        available_teachers = Teacher.objects.filter(
            subjects=subject,
            is_active=True
        )
        
        if not available_teachers.exists():
            error_details.append(f"No active teachers found who can teach {subject.name}")
        else:
            error_details.append(f"Found {available_teachers.count()} teachers who can teach {subject.name}")
            
            # Check if any teacher is assigned to this class level
            teachers_for_class = available_teachers.filter(
                classassignment__class_level=class_level
            ).distinct()
            if not teachers_for_class.exists():
                error_details.append(f"But no teachers are currently assigned to class level {class_level}")
        
        base_error = f"Unable to find or create class assignment for {subject.name} in {class_level} for {academic_year}."
        if error_details:
            base_error += " Details: " + "; ".join(error_details)
        
        return base_error

    def get_or_create_class_assignment(self, class_level, subject, academic_year):
        """
        Get or create class assignment for the given parameters with enhanced logic
        """
        try:
            logger.info(f"Looking for class assignment: {class_level}, {subject}, {academic_year}")
            
            # First try to find existing ACTIVE class assignment
            class_assignment = ClassAssignment.objects.filter(
                class_level=class_level,
                subject=subject,
                academic_year=academic_year,
                is_active=True
            ).first()
            
            if class_assignment:
                logger.info(f"Found existing active class assignment: {class_assignment}")
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
                logger.info(f"Reactivated existing class assignment: {existing_inactive}")
                return existing_inactive
            
            # If no existing assignment, create a new one
            logger.info("No existing class assignment found, creating new one")
            
            # Determine the teacher to assign
            teacher = None
            
            if self.user and hasattr(self.user, 'teacher'):
                # Try to use the current teacher if they're qualified
                current_teacher = self.user.teacher
                if (current_teacher.is_active and 
                    current_teacher.subjects.filter(id=subject.id).exists()):
                    teacher = current_teacher
                    logger.info(f"Using current teacher: {teacher}")
            
            # If current teacher not available or not qualified, find any available teacher
            if not teacher:
                teacher = Teacher.objects.filter(
                    subjects=subject,
                    is_active=True
                ).first()
                logger.info(f"Found available teacher: {teacher}")
            
            if not teacher:
                logger.error("No available teacher found for subject")
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
            logger.error(f"Error in get_or_create_class_assignment: {str(e)}")
            return None

    def validate_no_duplicate_grade(self, student, subject, academic_year, term):
        """
        Validate that no duplicate grade exists for this student, subject, term, and academic year
        """
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
                f"A grade already exists for {student.get_full_name()} in {subject.name} "
                f"for {academic_year} Term {term}. Please update the existing grade instead."
            )

    def validate_total_score(self, cleaned_data):
        """
        Validate that total score doesn't exceed 100%
        """
        classwork = cleaned_data.get('classwork_score', 0) or 0
        homework = cleaned_data.get('homework_score', 0) or 0
        test = cleaned_data.get('test_score', 0) or 0
        exam = cleaned_data.get('exam_score', 0) or 0
        
        total_score = classwork + homework + test + exam
        
        if total_score > 100:
            raise ValidationError(
                f"Total score cannot exceed 100%. Current total: {total_score}%"
            )

    def save(self, commit=True):
        """
        Save the grade with calculated fields
        """
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
    """Enhanced assignment form with better file handling"""
    
    # Add class_level as a form field (not a model field)
    class_level = forms.ChoiceField(
        choices=[('', 'Select Class Level')] + list(CLASS_LEVEL_CHOICES),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Select the class level for this assignment"
    )
    
    class Meta:
        model = Assignment
        fields = [
            'title', 'description', 'assignment_type', 'subject',
            'due_date', 'max_score', 'weight', 'attachment'
            # Note: 'class_level' is NOT included here since it's not a model field
        ]
        widgets = {
            'due_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local', 
                'class': 'form-control'
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
            'subject': forms.Select(attrs={'class': 'form-control'}),
            'max_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '100',
                'step': '1'
            }),
            'weight': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '1',
                'max': '100',
                'step': '1'
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
        super().__init__(*args, **kwargs)
        
        # Set current academic year
        current_year = timezone.now().year
        self.academic_year = f"{current_year}/{current_year + 1}"
        
        # Set up class level choices
        self.fields['class_level'].choices = [('', 'Select Class Level')] + list(CLASS_LEVEL_CHOICES)
        
        # For existing assignments, set the initial class_level value
        if self.instance and self.instance.pk and self.instance.class_assignment:
            self.fields['class_level'].initial = self.instance.class_assignment.class_level
        
        # Limit subjects based on user role and available class assignments
        if self.request and hasattr(self.request.user, 'teacher'):
            teacher = self.request.user.teacher
            # Only show subjects that the teacher teaches in active class assignments
            teacher_class_assignments = ClassAssignment.objects.filter(
                teacher=teacher,
                academic_year=self.academic_year,
                is_active=True
            )
            self.fields['subject'].queryset = Subject.objects.filter(
                classassignment__in=teacher_class_assignments
            ).distinct()
            
            # Also limit class_level choices to what the teacher actually teaches
            teacher_class_levels = teacher_class_assignments.values_list('class_level', flat=True).distinct()
            available_class_levels = [(level, name) for level, name in CLASS_LEVEL_CHOICES if level in teacher_class_levels]
            self.fields['class_level'].choices = [('', 'Select Class Level')] + available_class_levels
            
        else:
            # For admins, show all active subjects
            self.fields['subject'].queryset = Subject.objects.filter(is_active=True)
        
        # Set initial due date to 7 days from now for new assignments
        if not self.instance.pk:
            default_due_date = timezone.now() + timezone.timedelta(days=7)
            self.fields['due_date'].initial = default_due_date

    def clean(self):
        """Validate form data and handle class_assignment creation"""
        cleaned_data = super().clean()
        class_level = cleaned_data.get('class_level')
        subject = cleaned_data.get('subject')
        due_date = cleaned_data.get('due_date')
        weight = cleaned_data.get('weight')
        max_score = cleaned_data.get('max_score')
        
        # Validate required fields
        if not class_level:
            self.add_error('class_level', "Class level is required.")
        
        if not subject:
            self.add_error('subject', "Subject is required.")
        
        # Create or get class_assignment
        if class_level and subject and not self.errors:
            try:
                # First, try to find an existing class assignment
                class_assignment = ClassAssignment.objects.filter(
                    class_level=class_level,
                    subject=subject,
                    academic_year=self.academic_year,
                    is_active=True
                ).first()
                
                if class_assignment:
                    # Check if teacher is authorized for this class assignment
                    if (self.request and hasattr(self.request.user, 'teacher') and 
                        class_assignment.teacher != self.request.user.teacher):
                        self.add_error('class_level', 
                            f"You are not assigned to teach {subject.name} in {self.get_class_level_display(class_level)}."
                        )
                    else:
                        self.instance.class_assignment = class_assignment
                else:
                    # Create a new class assignment if none exists
                    if self.request and hasattr(self.request.user, 'teacher'):
                        teacher = self.request.user.teacher
                        # Check if teacher is qualified to teach this subject and class level
                        teacher_class_levels = [level.strip() for level in teacher.class_levels.split(',')] if teacher.class_levels else []
                        
                        if (subject in teacher.subjects.all() and 
                            class_level in teacher_class_levels):
                            
                            class_assignment = ClassAssignment.objects.create(
                                class_level=class_level,
                                subject=subject,
                                teacher=teacher,
                                academic_year=self.academic_year
                            )
                            self.instance.class_assignment = class_assignment
                        else:
                            self.add_error('class_level', 
                                f"You are not authorized to teach {subject.name} in {self.get_class_level_display(class_level)}. "
                                f"Please check your subject assignments and class levels."
                            )
                    else:
                        # For admins, find any available teacher
                        teacher = Teacher.objects.filter(
                            subjects=subject,
                            is_active=True
                        ).first()
                        
                        if teacher:
                            class_assignment = ClassAssignment.objects.create(
                                class_level=class_level,
                                subject=subject,
                                teacher=teacher,
                                academic_year=self.academic_year
                            )
                            self.instance.class_assignment = class_assignment
                        else:
                            self.add_error(None, 
                                f"No active teacher found for {subject.name} in {self.get_class_level_display(class_level)}. "
                                f"Please assign a teacher first."
                            )
                        
            except Exception as e:
                logger.error(f"Error in AssignmentForm.clean(): {str(e)}")
                self.add_error(None, f"Error creating assignment: {str(e)}")
        
        # Validate due date is in the future
        if due_date and due_date <= timezone.now():
            self.add_error('due_date', 'Due date must be in the future.')
        
        # Validate weight is reasonable
        if weight and (weight < 1 or weight > 100):
            self.add_error('weight', 'Weight must be between 1 and 100 percent.')
        
        # Validate max_score is reasonable
        if max_score and (max_score < 1 or max_score > 100):
            self.add_error('max_score', 'Maximum score must be between 1 and 100.')
        
        return cleaned_data

    def clean_attachment(self):
        attachment = self.cleaned_data.get('attachment')
        if attachment:
            max_size = 50 * 1024 * 1024  # 50MB for teacher uploads
            
            # Check file size
            if attachment.size > max_size:
                raise ValidationError(
                    f"File size must be less than 50MB. Your file is {attachment.size / (1024 * 1024):.1f}MB."
                )
            
            # Check file extension
            allowed_extensions = ['.pdf', '.doc', '.docx', '.txt', '.zip', '.jpg', '.jpeg', '.png', '.ppt', '.pptx']
            file_extension = os.path.splitext(attachment.name)[1].lower()
            
            if file_extension not in allowed_extensions:
                raise ValidationError(
                    f"File type '{file_extension}' is not allowed. "
                    f"Allowed types: {', '.join([ext for ext in allowed_extensions if ext])}"
                )
        
        return attachment

    def get_class_level_display(self, class_level):
        """Helper method to get display name for class level"""
        return dict(CLASS_LEVEL_CHOICES).get(class_level, class_level)

    def save(self, commit=True):
        """Save the assignment and create student assignments"""
        assignment = super().save(commit=False)
        
        # Ensure class_assignment is set before saving
        if not assignment.class_assignment and hasattr(self, 'cleaned_data'):
            class_level = self.cleaned_data.get('class_level')
            subject = self.cleaned_data.get('subject')
            
            if class_level and subject:
                # Try to find class assignment one more time
                class_assignment = ClassAssignment.objects.filter(
                    class_level=class_level,
                    subject=subject,
                    academic_year=self.academic_year,
                    is_active=True
                ).first()
                
                if class_assignment:
                    assignment.class_assignment = class_assignment
        
        if commit:
            assignment.save()
            
            # Create student assignments after saving
            try:
                assignment.create_student_assignments()
                
                # Send notifications to students about new assignment
                self.send_assignment_notifications(assignment)
                
            except Exception as e:
                logger.error(f"Error creating student assignments for assignment {assignment.id}: {str(e)}")
        
        return assignment

    def send_assignment_notifications(self, assignment):
        """Send notifications to students about the new assignment"""
        try:
            from django.urls import reverse
            
            # Get all students in the class level
            students = Student.objects.filter(
                class_level=assignment.class_assignment.class_level,
                is_active=True
            )
            
            for student in students:
                # Create notification for each student
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
        
        # If no new file is provided but there's an existing file, keep the existing one
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
        
        # Set submission date and update status
        student_assignment.submitted_date = timezone.now()
        
        # Check if submission is late
        if student_assignment.submitted_date > student_assignment.assignment.due_date:
            student_assignment.status = 'LATE'
        else:
            student_assignment.status = 'SUBMITTED'
        
        if commit:
            student_assignment.save()
            
            # Update assignment analytics
            try:
                student_assignment.assignment.update_analytics()
            except Exception as e:
                logger.error(f"Error updating analytics after submission: {str(e)}")
        
        return student_assignment

# ===== FEE MANAGEMENT FORMS =====

# Constants for forms
CLASS_LEVEL_CHOICES = [
    ('P1', 'Primary 1'),
    ('P2', 'Primary 2'),
    ('P3', 'Primary 3'),
    ('P4', 'Primary 4'),
    ('P5', 'Primary 5'),
    ('P6', 'Primary 6'),
    ('J1', 'JHS 1'),
    ('J2', 'JHS 2'),
    ('J3', 'JHS 3'),
]

TERM_CHOICES = [
    (1, 'Term 1'),
    (2, 'Term 2'),
    (3, 'Term 3'),
]


# ===== FEE CATEGORY FORMS =====

class FeeCategoryForm(forms.ModelForm):
    class Meta:
        model = FeeCategory
        fields = ['name', 'description', 'default_amount', 'frequency', 
                 'is_mandatory', 'is_active', 'applies_to_all', 'class_levels']
        widgets = {
            'name': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'Select fee category type'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter description...'
            }),
            'default_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'frequency': forms.Select(attrs={
                'class': 'form-control'
            }),
            'class_levels': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'P1,P2,P3 or leave blank for all'
            }),
        }
        labels = {
            'name': 'Category Type',
            'default_amount': 'Default Amount (GH₵)',
            'is_mandatory': 'Mandatory Fee',
            'applies_to_all': 'Applies to All Classes',
            'class_levels': 'Specific Class Levels',
        }

    def clean_default_amount(self):
        amount = self.cleaned_data.get('default_amount')
        if amount and amount < Decimal('0.01'):
            raise ValidationError("Default amount must be at least GH₵0.01")
        return amount

    def clean_class_levels(self):
        class_levels = self.cleaned_data.get('class_levels', '').strip()
        if class_levels:
            # Validate class level format
            valid_levels = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'J1', 'J2', 'J3']
            levels_list = [level.strip() for level in class_levels.split(',')]
            for level in levels_list:
                if level not in valid_levels:
                    raise ValidationError(f"Invalid class level: {level}. Valid levels are: {', '.join(valid_levels)}")
        return class_levels


# ===== FEE FORMS =====

class FeeForm(forms.ModelForm):
    student = forms.ModelChoiceField(
        queryset=Student.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-control select2',
            'data-placeholder': 'Select student...'
        })
    )
    
    class Meta:
        model = Fee
        fields = ['student', 'category', 'academic_year', 'term', 
                 'amount_payable', 'amount_paid', 'due_date', 'notes']
        widgets = {
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'academic_year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'YYYY/YYYY e.g., 2024/2025'
            }),
            'term': forms.Select(attrs={
                'class': 'form-control'
            }),
            'amount_payable': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'amount_paid': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional notes...'
            }),
        }
        labels = {
            'amount_payable': 'Amount Payable (GH₵)',
            'amount_paid': 'Amount Paid (GH₵)',
        }

    def __init__(self, *args, **kwargs):
        self.student_id = kwargs.pop('student_id', None)
        super().__init__(*args, **kwargs)
        
        # Set current academic year as default
        current_year = timezone.now().year
        next_year = current_year + 1
        self.fields['academic_year'].initial = f"{current_year}/{next_year}"
        
        # Filter categories to active ones only
        self.fields['category'].queryset = FeeCategory.objects.filter(is_active=True)
        
        # If student_id is provided, set the student field and make it read-only
        if self.student_id:
            try:
                student = Student.objects.get(pk=self.student_id)
                self.fields['student'].initial = student
                self.fields['student'].widget.attrs['readonly'] = True
                self.fields['student'].disabled = True
            except Student.DoesNotExist:
                pass

    def clean_academic_year(self):
        academic_year = self.cleaned_data.get('academic_year')
        if not re.match(r'^\d{4}/\d{4}$', academic_year):
            raise ValidationError("Academic year must be in format YYYY/YYYY (e.g., 2024/2025)")
        
        year1, year2 = map(int, academic_year.split('/'))
        if year2 != year1 + 1:
            raise ValidationError("The second year must be exactly one year after the first year")
            
        return academic_year

    def clean_amount_payable(self):
        amount = self.cleaned_data.get('amount_payable')
        if amount and amount < Decimal('0.01'):
            raise ValidationError("Amount payable must be at least GH₵0.01")
        return amount

    def clean_amount_paid(self):
        amount_paid = self.cleaned_data.get('amount_paid') or Decimal('0.00')
        amount_payable = self.cleaned_data.get('amount_payable')
        
        if amount_payable and amount_paid > amount_payable:
            # Allow overpayment but show warning
            self.cleaned_data['has_overpayment'] = True
        else:
            self.cleaned_data['has_overpayment'] = False
            
        return amount_paid

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        if due_date and due_date < timezone.now().date():
            if not self.instance.pk:  # Only for new records
                raise ValidationError("Due date cannot be in the past for new fees")
        return due_date

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        category = cleaned_data.get('category')
        academic_year = cleaned_data.get('academic_year')
        term = cleaned_data.get('term')

        # Check for duplicate fee records
        if student and category and academic_year and term:
            existing_fee = Fee.objects.filter(
                student=student,
                category=category,
                academic_year=academic_year,
                term=term
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing_fee.exists():
                raise ValidationError(
                    f"A fee record already exists for {student} - {category} "
                    f"for {academic_year} Term {term}"
                )

        return cleaned_data


# ===== FEE PAYMENT FORMS =====

class FeePaymentForm(forms.ModelForm):
    class Meta:
        model = FeePayment
        fields = ['amount', 'payment_mode', 'payment_date', 'receipt_number', 
                 'bank_reference', 'notes', 'recorded_by']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'payment_mode': forms.Select(attrs={
                'class': 'form-control'
            }),
            'payment_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'receipt_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Auto-generated if left blank'
            }),
            'bank_reference': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Reference number for bank/mobile money'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Payment notes...'
            }),
            'recorded_by': forms.Select(attrs={
                'class': 'form-control'
            }),
        }
        labels = {
            'amount': 'Payment Amount (GH₵)',
            'bank_reference': 'Transaction Reference',
        }

    def __init__(self, *args, **kwargs):
        self.fee_id = kwargs.pop('fee_id', None)
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Set current datetime as default
        self.fields['payment_date'].initial = timezone.now()
        
        # Set recorded_by to current user and make it read-only
        if self.request and self.request.user.is_authenticated:
            self.fields['recorded_by'].initial = self.request.user
            self.fields['recorded_by'].widget.attrs['readonly'] = True
            self.fields['recorded_by'].disabled = True
        
        # Filter recorded_by to staff users only
        self.fields['recorded_by'].queryset = User.objects.filter(
            is_staff=True
        ).order_by('username')

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount < Decimal('0.01'):
            raise ValidationError("Payment amount must be at least GH₵0.01")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        
        if self.fee_id and amount:
            try:
                fee = Fee.objects.get(pk=self.fee_id)
                
                # Check if payment exceeds remaining balance
                remaining_balance = fee.balance
                if amount > remaining_balance:
                    # Allow overpayment but show warning
                    overpayment = amount - remaining_balance
                    cleaned_data['overpayment_amount'] = overpayment
                    # Use Django messages for warning instead of form warning
                    from django.contrib import messages
                    if self.request:
                        messages.warning(self.request, f"Payment exceeds balance by GH₵{overpayment:.2f}. Overpayment will be credited to student account.")
                else:
                    cleaned_data['overpayment_amount'] = Decimal('0.00')
                    
            except Fee.DoesNotExist:
                raise ValidationError("Invalid fee record selected")

        return cleaned_data


# ===== BILL PAYMENT FORM =====

class BillPaymentForm(forms.ModelForm):
    class Meta:
        model = BillPayment
        fields = ['amount', 'payment_mode', 'payment_date', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'payment_mode': forms.Select(attrs={
                'class': 'form-control'
            }),
            'payment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Payment notes...'
            }),
        }
        labels = {
            'amount': 'Payment Amount (GH₵)',
        }

    def __init__(self, *args, **kwargs):
        self.bill_id = kwargs.pop('bill_id', None)
        super().__init__(*args, **kwargs)
        
        # Set current date as default
        self.fields['payment_date'].initial = timezone.now().date()

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount < Decimal('0.01'):
            raise ValidationError("Payment amount must be at least GH₵0.01")
        return amount

    def clean(self):
        cleaned_data = super().clean()
        amount = cleaned_data.get('amount')
        
        if self.bill_id and amount:
            try:
                bill = Bill.objects.get(pk=self.bill_id)
                
                # Check if payment exceeds bill balance
                if amount > bill.balance:
                    raise ValidationError(
                        f"Payment amount (GH₵{amount:.2f}) exceeds bill balance (GH₵{bill.balance:.2f})"
                    )
                    
            except Bill.DoesNotExist:
                raise ValidationError("Invalid bill selected")

        return cleaned_data


# ===== FEE DISCOUNT FORM =====

class FeeDiscountForm(forms.ModelForm):
    class Meta:
        model = FeeDiscount
        fields = ['student', 'category', 'discount_type', 'amount', 
                 'reason', 'start_date', 'end_date']
        widgets = {
            'student': forms.Select(attrs={
                'class': 'form-control select2',
                'data-placeholder': 'Select student...'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'discount_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Reason for discount...'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default dates
        self.fields['start_date'].initial = timezone.now().date()
        self.fields['end_date'].initial = timezone.now().date() + timezone.timedelta(days=30)
        
        # Filter to active students and categories
        self.fields['student'].queryset = Student.objects.filter(is_active=True)
        self.fields['category'].queryset = FeeCategory.objects.filter(is_active=True)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        discount_type = self.cleaned_data.get('discount_type')
        
        if discount_type == 'PERCENT' and amount > 100:
            raise ValidationError("Percentage discount cannot exceed 100%")
        elif amount <= 0:
            raise ValidationError("Discount amount must be greater than 0")
            
        return amount

    def clean_end_date(self):
        start_date = self.cleaned_data.get('start_date')
        end_date = self.cleaned_data.get('end_date')
        
        if start_date and end_date and end_date < start_date:
            raise ValidationError("End date must be after start date")
            
        return end_date


# ===== FEE INSTALLMENT FORM =====

class FeeInstallmentForm(forms.ModelForm):
    class Meta:
        model = FeeInstallment
        fields = ['amount', 'due_date']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount < Decimal('0.01'):
            raise ValidationError("Installment amount must be at least GH₵0.01")
        return amount

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        if due_date and due_date < timezone.now().date():
            raise ValidationError("Due date cannot be in the past")
        return due_date


# ===== FILTER FORMS =====

class FeeFilterForm(forms.Form):
    academic_year = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2024/2025'
        })
    )
    term = forms.ChoiceField(
        required=False,
        choices=[('', 'All Terms')] + [(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    payment_status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Statuses')] + [
            ('paid', 'Paid'),
            ('unpaid', 'Unpaid'), 
            ('partial', 'Partial Payment'),
            ('overdue', 'Overdue')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    category = forms.ModelChoiceField(
        required=False,
        queryset=FeeCategory.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    student = forms.ModelChoiceField(
        required=False,
        queryset=Student.objects.filter(is_active=True),
        widget=forms.Select(attrs={
            'class': 'form-control select2',
            'data-placeholder': 'Select student...'
        })
    )
    has_bill = forms.ChoiceField(
        required=False,
        choices=[('', 'All'), ('yes', 'Has Bill'), ('no', 'No Bill')],
        widget=forms.Select(attrs={'class': 'form-control'}),
        label='Bill Status'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set current academic year as default
        current_year = timezone.now().year
        next_year = current_year + 1
        self.fields['academic_year'].initial = f"{current_year}/{next_year}"


class FeeStatusReportForm(forms.Form):
    REPORT_TYPE_CHOICES = [
        ('summary', 'Summary Report'),
        ('detailed', 'Detailed Report'),
        ('outstanding', 'Outstanding Fees'),
        ('collection', 'Collection Report'),
    ]
    
    report_type = forms.ChoiceField(
        choices=REPORT_TYPE_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'}),
        initial='summary'
    )
    academic_year = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2024/2025'
        })
    )
    term = forms.ChoiceField(
        required=False,
        choices=[('', 'All Terms')] + [(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    class_level = forms.ChoiceField(
        required=False,
        choices=[('', 'All Classes')] + CLASS_LEVEL_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    payment_status = forms.ChoiceField(
        required=False,
        choices=[('', 'All Statuses')] + [
            ('paid', 'Paid'),
            ('unpaid', 'Unpaid'),
            ('partial', 'Partial Payment'),
            ('overdue', 'Overdue')
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    bill_status = forms.ChoiceField(
        required=False,
        choices=[('', 'All'), ('billed', 'Billed'), ('unbilled', 'Not Billed')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default date range to current term
        self.fields['start_date'].initial = timezone.now().date().replace(day=1)
        self.fields['end_date'].initial = timezone.now().date()
        
        # Set current academic year
        current_year = timezone.now().year
        next_year = current_year + 1
        self.fields['academic_year'].initial = f"{current_year}/{next_year}"

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise ValidationError("Start date cannot be after end date")
            
        return cleaned_data


# ===== BULK FEE GENERATION FORM =====

class BulkFeeGenerationForm(forms.Form):
    academic_year = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'YYYY/YYYY e.g., 2024/2025'
        })
    )
    term = forms.ChoiceField(
        choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    class_levels = forms.MultipleChoiceField(
        choices=CLASS_LEVEL_CHOICES,
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2'}),
        required=False,
        help_text="Select specific classes or leave blank for all classes"
    )
    categories = forms.ModelMultipleChoiceField(
        queryset=FeeCategory.objects.filter(is_active=True, is_mandatory=True),
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2'}),
        help_text="Select fee categories to generate"
    )
    due_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        help_text="Due date for generated fees"
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default values
        current_year = timezone.now().year
        next_year = current_year + 1
        self.fields['academic_year'].initial = f"{current_year}/{next_year}"
        
        # Set due date to 30 days from now
        self.fields['due_date'].initial = timezone.now().date() + timezone.timedelta(days=30)

    def clean_academic_year(self):
        academic_year = self.cleaned_data.get('academic_year')
        if not re.match(r'^\d{4}/\d{4}$', academic_year):
            raise ValidationError("Academic year must be in format YYYY/YYYY (e.g., 2024/2025)")
        return academic_year

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        if due_date and due_date < timezone.now().date():
            raise ValidationError("Due date cannot be in the past")
        return due_date


# ===== DATE RANGE FILTER FORM =====

class DateRangeForm(forms.Form):
    start_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='From Date'
    )
    end_date = forms.DateField(
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label='To Date'
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default date range (last 30 days)
        self.fields['start_date'].initial = timezone.now().date() - timezone.timedelta(days=30)
        self.fields['end_date'].initial = timezone.now().date()

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError("Start date cannot be after end date")
            
            # Limit date range to 1 year maximum
            if (end_date - start_date).days > 365:
                raise ValidationError("Date range cannot exceed 1 year")
                
        return cleaned_data



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
    # Add class level choices as a form field
    target_class_levels = forms.MultipleChoiceField(
        choices=CLASS_LEVEL_CHOICES,
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-select',
            'size': '6'
        }),
        help_text="Select specific class levels (hold Ctrl/Cmd to select multiple)"
    )
    
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
            'end_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        }
        labels = {
            'target_class_levels': 'Target Class Levels',
            'target_roles': 'Target Audience Type'
        }
        help_texts = {
            'target_class_levels': 'Select specific classes or leave empty for all classes',
            'target_roles': 'Choose which user roles should see this announcement'
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Set initial values for target_class_levels from the instance
        if self.instance and self.instance.pk:
            if self.instance.target_class_levels:
                self.initial['target_class_levels'] = self.instance.get_target_class_levels()
        
        # Make end_date not required
        self.fields['end_date'].required = False
        
    def clean_target_class_levels(self):
        """Clean and validate target class levels"""
        class_levels = self.cleaned_data.get('target_class_levels', [])
        if class_levels:
            # Convert list to comma-separated string
            return ','.join(class_levels)
        return ''
    
    def clean(self):
        cleaned_data = super().clean()
        target_roles = cleaned_data.get('target_roles')
        target_class_levels = cleaned_data.get('target_class_levels')
        
        # If targeting specific classes, ensure class levels are selected
        if target_roles == 'CLASS' and not target_class_levels:
            raise forms.ValidationError({
                'target_class_levels': 'Please select at least one class level when targeting specific classes.'
            })
        
        # Validate end date is after start date
        end_date = cleaned_data.get('end_date')
        if end_date and end_date < timezone.now():
            raise forms.ValidationError({
                'end_date': 'End date cannot be in the past.'
            })
        
        return cleaned_data


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