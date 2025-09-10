from datetime import date, timedelta
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm, PasswordChangeForm
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import date
from django.core.validators import RegexValidator
from decimal import Decimal
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.conf import settings
from django.apps import apps
import re
from .models import (
    ParentMessage, Announcement, ReportCard, Fee, FeeCategory, Student, StudentAttendance, 
    ClassAssignment, ParentGuardian, FeePayment, Bill, Subject, BillPayment,  # Added comma here
    Teacher, Grade, StudentAssignment, AcademicTerm, AttendancePeriod, Assignment, TimeSlot,  # Added comma after Grade
    Timetable, TimetableEntry
)
from .models import CLASS_LEVEL_CHOICES, TERM_CHOICES

User = apps.get_model(settings.AUTH_USER_MODEL)

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
        model = ParentGuardian  # Import this from models, not define here
        fields = ['user', 'students', 'occupation', 'relationship', 'phone_number', 'email', 'address', 
                 'is_emergency_contact', 'emergency_contact_priority']
        widgets = {
            'students': forms.SelectMultiple(attrs={'class': 'form-control'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'relationship': forms.Select(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'emergency_contact_priority': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make user field optional for existing instances
        if self.instance and self.instance.pk:
            self.fields['user'].required = False

class FeeCategoryForm(forms.ModelForm):
    class Meta:
        model = FeeCategory
        fields = ['name', 'description', 'default_amount', 'frequency', 'is_mandatory', 'is_active', 'class_levels']
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
            # Validate class levels format
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
            
            # Remove duplicates and empty strings, then rejoin
            unique_levels = list(set(levels))
            unique_levels = [level for level in unique_levels if level]  # Remove empty strings
            return ','.join(unique_levels)
        
        return class_levels
class FeeForm(forms.ModelForm):
    academic_year = forms.CharField(
        help_text="Format: YYYY/YYYY or YYYY-YYYY",
        validators=[RegexValidator(r'^\d{4}[/-]\d{4}$', 'Enter a valid year in format YYYY/YYYY or YYYY-YYYY')]
    )
    
    payment_status = forms.ChoiceField(
        choices=[
            ('PAID', 'Paid'),
            ('UNPAID', 'Unpaid'),
            ('PARTIAL', 'Part Payment'),
            ('OVERDUE', 'Overdue')
        ],
        initial='UNPAID'
    )
    
    class Meta:
        model = Fee
        fields = ['student', 'category', 'academic_year', 'term', 'amount_payable', 
                 'amount_paid', 'payment_status', 'payment_mode', 'payment_date', 
                 'due_date', 'notes', 'bill']
        widgets = {
            'student': forms.HiddenInput(),
            'due_date': forms.DateInput(attrs={'type': 'date'}),
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
            'amount_payable': forms.NumberInput(attrs={'step': '0.01'}),
            'amount_paid': forms.NumberInput(attrs={'step': '0.01'}),
            'bill': forms.Select(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        student_id = kwargs.pop('student_id', None)
        super().__init__(*args, **kwargs)
        
        # Set up the student field
        if student_id:
            try:
                student = Student.objects.get(pk=student_id)
                self.fields['student'].initial = student
                self.fields['student'].queryset = Student.objects.filter(pk=student_id)
                
                # Set up category field with applicable categories
                self.fields['category'].queryset = self.get_applicable_categories(student)
                self.fields['category'].empty_label = "--- Select Fee Type ---"
                
                # Set up bill field with student's bills
                self.fields['bill'].queryset = Bill.objects.filter(student=student)
                self.fields['bill'].empty_label = "--- Not linked to a bill ---"
                
            except Student.DoesNotExist:
                # If student doesn't exist, show all students (for admin)
                self.fields['student'].queryset = Student.objects.filter(is_active=True)
                self.fields['bill'].queryset = Bill.objects.all()
        else:
            # If no student_id provided, show all active students
            self.fields['student'].queryset = Student.objects.filter(is_active=True)
            self.fields['bill'].queryset = Bill.objects.all()
        
        # Set default academic year if not already set
        if not self.initial.get('academic_year'):
            current_year = timezone.now().year
            self.initial['academic_year'] = f"{current_year}/{current_year + 1}"
        
        # Make student field required
        self.fields['student'].required = True

    def get_applicable_categories(self, student):
        """Get categories that apply to this student's class level"""
        student_class = str(student.class_level)
        
        # Categories that apply to all classes
        qs = FeeCategory.objects.filter(is_active=True)
        
        # Filter categories that either apply to all or specifically to this class
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
        
        # Validate that category is applicable to student's class
        if student and category:
            if category.class_levels:
                student_class = str(student.class_level)
                class_levels = [x.strip() for x in category.class_levels.split(',')] if category.class_levels else []
                if student_class not in class_levels:
                    raise forms.ValidationError(
                        f"The selected category '{category.name}' is not applicable to {student}'s class level ({student.get_class_level_display()})."
                    )
        
        # Validate bill belongs to the correct student
        if bill and student and bill.student != student:
            raise forms.ValidationError(
                "The selected bill does not belong to the chosen student."
            )
        
        amount_payable = cleaned_data.get('amount_payable', Decimal('0.00'))
        amount_paid = cleaned_data.get('amount_paid', Decimal('0.00'))
        payment_status = cleaned_data.get('payment_status')
        
        # Calculate and set balance
        cleaned_data['balance'] = amount_payable - amount_paid
        
        # Validate payment status consistency
        if payment_status == 'PAID' and amount_paid != amount_payable:
            raise forms.ValidationError(
                "For 'Paid' status, amount paid must equal amount payable."
            )
        elif payment_status == 'UNPAID' and amount_paid > 0:
            raise forms.ValidationError(
                "For 'Unpaid' status, amount paid must be zero."
            )
        elif payment_status == 'PARTIAL' and (amount_paid <= 0 or amount_paid >= amount_payable):
            raise forms.ValidationError(
                "For 'Part Payment' status, amount paid must be between 0 and the payable amount."
            )
        elif payment_status == 'OVERDUE' and amount_paid >= amount_payable:
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
            
            # If fee is linked to a bill, show bill information
            if fee.bill:
                self.fields['bill'] = forms.ModelChoiceField(
                    queryset=Bill.objects.filter(pk=fee.bill.pk),
                    initial=fee.bill,
                    widget=forms.HiddenInput(),
                    required=False
                )
    
    class Meta:
        model = FeePayment
        fields = ['fee', 'amount', 'payment_mode', 'payment_date', 'notes', 'recorded_by']
        widgets = {
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2}),
            'recorded_by': forms.HiddenInput(),
        }
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        fee = self.cleaned_data.get('fee')
        
        if fee and amount:
            if amount <= 0:
                raise forms.ValidationError("Payment amount must be greater than zero.")
            
            if amount > fee.balance:
                raise forms.ValidationError(
                    f"Payment amount cannot exceed the remaining balance of GH₵{fee.balance:.2f}."
                )
        
        return amount
    
    def clean(self):
        cleaned_data = super().clean()
        fee = cleaned_data.get('fee')
        amount = cleaned_data.get('amount')
        
        if fee and amount:
            # Check if payment would make the fee overpaid
            new_total_paid = fee.amount_paid + amount
            if new_total_paid > fee.amount_payable:
                raise forms.ValidationError(
                    f"This payment would result in overpayment. Maximum allowed is GH₵{fee.balance:.2f}."
                )
        
        return cleaned_data
class FeeFilterForm(forms.Form):
    academic_year = forms.CharField(required=False)
    term = forms.ChoiceField(
        choices=[('', 'All Terms'), (1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        required=False
    )
    payment_status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + Fee.PAYMENT_STATUS_CHOICES,
        required=False
    )
    category = forms.ModelChoiceField(
        queryset=FeeCategory.objects.all(),
        required=False,
        empty_label="All Categories"
    )
    student = forms.ModelChoiceField(
        queryset=Student.objects.all(),
        required=False,
        empty_label="All Students"
    )
    has_bill = forms.ChoiceField(
        choices=[('', 'All'), ('yes', 'With Bill'), ('no', 'Without Bill')],
        required=False,
        label="Bill Status"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set current academic year as default if not provided
        if not self.data.get('academic_year'):
            current_year = timezone.now().year
            self.initial['academic_year'] = f"{current_year}/{current_year + 1}"

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
        label="Report Type"
    )
    
    academic_year = forms.CharField(
        required=False,
        label="Academic Year",
        widget=forms.TextInput(attrs={'placeholder': 'e.g., 2024/2025'})
    )
    
    term = forms.ChoiceField(
        choices=[('', 'All Terms')] + list(TERM_CHOICES),
        required=False,
        label="Term"
    )
    
    class_level = forms.ChoiceField(
        choices=[('', 'All Classes')] + list(CLASS_LEVEL_CHOICES),
        required=False,
        label="Class Level"
    )
    
    payment_status = forms.ChoiceField(
        choices=[('', 'All Statuses')] + [
            ('PAID', 'Paid'),
            ('UNPAID', 'Unpaid'),
            ('PARTIAL', 'Partial Payment'),
            ('OVERDUE', 'Overdue'),
        ],
        required=False,
        label="Payment Status"
    )
    
    bill_status = forms.ChoiceField(
        choices=[('', 'All'), ('billed', 'Billed'), ('unbilled', 'Not Billed')],
        required=False,
        label="Bill Status"
    )
    
    start_date = forms.DateField(
        required=False,
        label="Start Date",
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    end_date = forms.DateField(
        required=False,
        label="End Date",
        widget=forms.DateInput(attrs={'type': 'date'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise forms.ValidationError("Start date cannot be after end date")
        
        return cleaned_data

class SubjectForm(forms.ModelForm):
    class Meta:
        model = Subject
        fields = ['name', 'code', 'description']
        widgets = {
            'description': forms.Textarea(attrs={'rows': 3}),
        }

class TeacherRegistrationForm(forms.ModelForm):
    username = forms.CharField(max_length=150, required=True)
    password = forms.CharField(widget=forms.PasswordInput, required=True)
    first_name = forms.CharField(max_length=100, required=True)
    last_name = forms.CharField(max_length=100, required=True)
    email = forms.EmailField(required=True)

    class Meta:
        model = Teacher
        fields = ['date_of_birth', 'gender', 'phone_number', 'address', 'subjects', 'class_levels', 
                 'qualification', 'date_of_joining', 'is_class_teacher', 'is_active']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'date_of_joining': forms.DateInput(attrs={'type': 'date'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # If editing an existing teacher, make user fields optional
        if self.instance and self.instance.pk:
            self.fields['username'].required = False
            self.fields['password'].required = False
            self.fields['first_name'].required = False
            self.fields['last_name'].required = False
            self.fields['email'].required = False

    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            if not phone_number.isdigit() or len(phone_number) != 10:
                raise ValidationError("Phone number must be exactly 10 digits.")
        return phone_number

    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Convert to lowercase and validate format
            email = email.lower()
            if not re.match(r'^[a-z0-9._%+-]+@[a-z00.-]+\.[a-z]{2,}$', email):
                raise ValidationError("Email must be in valid format with @ symbol.")
            
            # Check if email already exists in the system (only for new teachers)
            if not (self.instance and self.instance.pk):
                User = apps.get_model(settings.AUTH_USER_MODEL)
                if User.objects.filter(email=email).exists():
                    raise ValidationError("A teacher with this email already exists.")
        
        return email

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username and not (self.instance and self.instance.pk):
            User = apps.get_model(settings.AUTH_USER_MODEL)
            if User.objects.filter(username=username).exists():
                raise ValidationError("This username is already taken. Please choose a different one.")
        return username

    def clean(self):
        cleaned_data = super().clean()
        
        # Only validate user fields for new teachers
        if not (self.instance and self.instance.pk):
            for field_name in ['username', 'password', 'first_name', 'last_name', 'email']:
                if self.fields[field_name].required and not cleaned_data.get(field_name):
                    self.add_error(field_name, "This field is required.")
        
        return cleaned_data

    def save(self, commit=True):
        # For new teachers, create user
        if not self.instance.pk:
            User = apps.get_model(settings.AUTH_USER_MODEL)
            
            user_data = {
                'username': self.cleaned_data['username'],
                'first_name': self.cleaned_data['first_name'],
                'last_name': self.cleaned_data['last_name'],
                'email': self.cleaned_data['email'],
            }
            
            # Check if username already exists and generate a unique one
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
            
            # Auto-generate employee_id if not set
            if not teacher.employee_id:
                last_teacher = Teacher.objects.order_by('-id').first()
                if last_teacher and last_teacher.employee_id and last_teacher.employee_id.startswith('T'):
                    try:
                        last_number = int(last_teacher.employee_id[1:])
                        new_number = last_number + 1
                    except ValueError:
                        new_number = 1
                else:
                    new_number = 1
                teacher.employee_id = f"T{new_number:03d}"
        else:
            # For existing teachers, just save normally
            teacher = super().save(commit=False)
        
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
        fields = ['subject', 'class_level', 'academic_year', 'teacher']
        
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        if self.request and hasattr(self.request.user, 'teacher'):
            self.fields['subject'].queryset = Subject.objects.filter(
                teachers=self.request.user.teacher
            )
            # For teachers, set the teacher field to their own account and make it read-only
            self.fields['teacher'].initial = self.request.user.teacher
            self.fields['teacher'].widget.attrs['readonly'] = True
            self.fields['teacher'].disabled = True
        else:
            # For admins, show all active teachers
            self.fields['teacher'].queryset = Teacher.objects.filter(is_active=True)

    def clean(self):
        cleaned_data = super().clean()
        subject = cleaned_data.get('subject')
        class_level = cleaned_data.get('class_level')
        academic_year = cleaned_data.get('academic_year')
        teacher = cleaned_data.get('teacher')
        
        # For teachers, automatically set the teacher to themselves
        if self.request and hasattr(self.request.user, 'teacher') and not teacher:
            cleaned_data['teacher'] = self.request.user.teacher
            teacher = self.request.user.teacher
        
        if subject and class_level and academic_year and teacher:
            # Check if this subject-class combination already exists
            existing_assignment = ClassAssignment.objects.filter(
                subject=subject,
                class_level=class_level,
                academic_year=academic_year
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing_assignment.exists():
                raise ValidationError(
                    f"This subject ({subject}) is already assigned to another teacher "
                    f"in {class_level} for academic year {academic_year}."
                )
        
        return cleaned_data

class GradeForm(forms.ModelForm):
    class Meta:
        model = Grade
        fields = ['student', 'subject', 'class_assignment', 'academic_year', 'term',
                 'classwork_score', 'homework_score', 'test_score', 'exam_score', 'remarks']
        widgets = {
            'academic_year': forms.TextInput(attrs={
                'placeholder': 'YYYY/YYYY',
                'class': 'form-control'
            }),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'classwork_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '30',
                'step': '0.1'
            }),
            'homework_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '10',
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
                'max': '50',
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
            
            # Get subjects and class assignments taught by this teacher
            self.fields['subject'].queryset = teacher.subjects.all()
            self.fields['class_assignment'].queryset = ClassAssignment.objects.filter(
                teacher=teacher
            )
        else:
            # Admin sees all students and subjects
            self.fields['student'].queryset = Student.objects.all().order_by(
                'class_level', 'last_name', 'first_name'
            )
            self.fields['subject'].queryset = Subject.objects.all()
            self.fields['class_assignment'].queryset = ClassAssignment.objects.all()

    def clean_academic_year(self):
        academic_year = self.cleaned_data['academic_year']
        # Validate format (YYYY/YYYY or YYYY-YYYY)
        if not re.match(r'^\d{4}[/-]\d{4}$', academic_year):
            raise ValidationError("Academic year must be in YYYY/YYYY or YYYY-YYYY format")
        
        # Convert to consistent format
        academic_year = academic_year.replace('-', '/')
        
        # Validate the years are consecutive
        year1, year2 = map(int, academic_year.split('/'))
        if year2 != year1 + 1:
            raise ValidationError("The second year should be exactly one year after the first year")
        
        return academic_year

    def clean(self):
        cleaned_data = super().clean()
        
        # Validate class assignment matches student and subject
        student = cleaned_data.get('student')
        subject = cleaned_data.get('subject')
        class_assignment = cleaned_data.get('class_assignment')
        
        if student and subject and class_assignment:
            if (class_assignment.class_level != student.class_level or 
                class_assignment.subject != subject):
                raise ValidationError(
                    "Class assignment doesn't match the selected student and subject"
                )
        
        return cleaned_data

class GradeEntryForm(forms.ModelForm):
    class Meta:
        model = Grade
        fields = ['student', 'subject', 'class_assignment', 'academic_year', 'term',
                 'classwork_score', 'homework_score', 'test_score', 'exam_score', 'remarks']
        
        widgets = {
            'academic_year': forms.TextInput(attrs={
                'placeholder': 'YYYY/YYYY',
                'class': 'form-control'
            }),
            'term': forms.Select(attrs={'class': 'form-select'}),
            'classwork_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '30',
                'step': '0.1'
            }),
            'homework_score': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': '0',
                'max': '10',
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
                'max': '50',
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
            self.fields['class_assignment'].queryset = ClassAssignment.objects.filter(
                teacher=teacher
            )
        else:
            # Admin sees all students and subjects
            self.fields['student'].queryset = Student.objects.all().order_by(
                'class_level', 'last_name', 'first_name'
            )
            self.fields['subject'].queryset = Subject.objects.all()
            self.fields['class_assignment'].queryset = ClassAssignment.objects.all()

    def clean(self):
        cleaned_data = super().clean()
        student = cleaned_data.get('student')
        class_assignment = cleaned_data.get('class_assignment')
        
        # Validate class assignment matches student's class level
        if student and class_assignment and student.class_level != class_assignment.class_level:
            raise ValidationError(
                "The selected class assignment doesn't match the student's class level"
            )
        
        return cleaned_data

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
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Get the custom user model in the __init__ method
        User = apps.get_model(settings.AUTH_USER_MODEL)
        self.fields['user'].queryset = User.objects.all()
    
    user = forms.ModelChoiceField(
        queryset=None,
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
            if delta.days > 120:
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
        choices=CLASS_LEVEL_CHOICES,  # ← FIXED
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
                (level, name) for level, name in CLASS_LEVEL_CHOICES  # ← FIXED
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
        choices=[('', 'All Classes')] + list(CLASS_LEVEL_CHOICES),  # ← FIXED (1st instance)
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
                (level, name) for level, name in CLASS_LEVEL_CHOICES  # ← FIXED (2nd instance)
                if level in class_levels
            ]
            self.fields['student'].queryset = Student.objects.filter(
                class_level__in=class_levels
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
            self.fields['student'].queryset = Student.objects.filter(
                parents__user=user
            )

class ReportCardForm(forms.ModelForm):
    class Meta:
        model = ReportCard
        fields = ['student', 'academic_year', 'term', 'is_published']
        widgets = {
            'academic_year': forms.Select(choices=[
                ('', 'Select Academic Year'),
                ('2023/2024', '2023/2024'),
                ('2024/2025', '2024/2025'),
            ]),
            'term': forms.Select(choices=[
                ('', 'Select Term'),
                (1, 'Term 1'),
                (2, 'Term 2'),
                (3, 'Term 3'),
            ]),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['student'].queryset = Student.objects.all().order_by('first_name', 'last_name')

class TimeSlotForm(forms.ModelForm):
    class Meta:
        model = TimeSlot
        fields = ['period_number', 'start_time', 'end_time', 'is_break', 'break_name']
        widgets = {
            'start_time': forms.TimeInput(attrs={'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'type': 'time'}),
        }

class TimetableForm(forms.ModelForm):
    class Meta:
        model = Timetable
        fields = ['class_level', 'day_of_week', 'academic_year', 'term', 'is_active']
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set current academic year as default
        current_year = timezone.now().year
        next_year = current_year + 1
        self.fields['academic_year'].initial = f"{current_year}/{next_year}"

class TimetableEntryForm(forms.ModelForm):
    class Meta:
        model = TimetableEntry
        fields = ['time_slot', 'subject', 'teacher', 'classroom', 'is_break']
    
    def __init__(self, *args, **kwargs):
        timetable = kwargs.pop('timetable', None)
        super().__init__(*args, **kwargs)
        
        if timetable:
            # Filter teachers who teach this class level
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
        choices=[('', 'All Classes')] + list(CLASS_LEVEL_CHOICES),  # ← FIXED
        required=False
    )
    academic_year = forms.CharField(required=False)
    term = forms.ChoiceField(
        choices=[('', 'All Terms')] + list(TERM_CHOICES),  # Also fixed TERM_CHOICES
        required=False
    )
    day_of_week = forms.ChoiceField(
        choices=[('', 'All Days')] + list(Timetable.DAYS_OF_WEEK),
        required=False
    )

#bills
class BillGenerationForm(forms.Form):
    academic_year = forms.CharField(
        max_length=9,
        required=True,
        validators=[RegexValidator(r'^\d{4}/\d{4}$', 'Enter a valid academic year in format YYYY/YYYY')],
        widget=forms.TextInput(attrs={'placeholder': 'e.g., 2024/2025'})
    )
    
    term = forms.ChoiceField(
        choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        required=True
    )
    
    class_levels = forms.MultipleChoiceField(
        choices=CLASS_LEVEL_CHOICES,
        required=False,
        widget=forms.SelectMultiple(attrs={'size': 6}),
        help_text="Select specific class levels (leave blank for all)"
    )
    
    due_date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'type': 'date'}),
        help_text="Due date for the generated bills"
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional notes for the bills'}),
        help_text="Optional notes that will be added to all generated bills"
    )
    
    skip_existing = forms.BooleanField(
        required=False,
        initial=True,
        help_text="Skip students who already have bills for this term"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set default academic year
        current_year = timezone.now().year
        self.fields['academic_year'].initial = f"{current_year}/{current_year + 1}"
        
        # Set default due date (30 days from now)
        default_due_date = timezone.now().date() + timedelta(days=30)
        self.fields['due_date'].initial = default_due_date
    
    def clean_academic_year(self):
        academic_year = self.cleaned_data['academic_year']
        # Validate the years are consecutive
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
    
    def clean(self):
        cleaned_data = super().clean()
        academic_year = cleaned_data.get('academic_year')
        term = cleaned_data.get('term')
        
        # Check if bills already exist for this term
        if academic_year and term and cleaned_data.get('skip_existing'):
            existing_bills_count = Bill.objects.filter(
                academic_year=academic_year,
                term=term
            ).count()
            
            if existing_bills_count > 0:
                self.add_error(
                    None,
                    f"Warning: {existing_bills_count} bills already exist for {academic_year} Term {term}. "
                    f"They will be skipped if 'Skip existing' is checked."
                )
        
        return cleaned_data

class BillPaymentForm(forms.ModelForm):
    class Meta:
        model = BillPayment
        fields = ['bill', 'amount', 'payment_mode', 'payment_date', 'notes', 'recorded_by']
        widgets = {
            'bill': forms.HiddenInput(),
            'payment_date': forms.DateInput(attrs={'type': 'date'}),
            'notes': forms.Textarea(attrs={'rows': 2, 'placeholder': 'Optional payment notes'}),
            'recorded_by': forms.HiddenInput(),
        }
    
    def __init__(self, *args, **kwargs):
        bill_id = kwargs.pop('bill_id', None)
        super().__init__(*args, **kwargs)
        
        if bill_id:
            bill = get_object_or_404(Bill, pk=bill_id)
            self.fields['bill'].initial = bill
            self.fields['bill'].widget = forms.HiddenInput()
            
            # Set max payment amount as the remaining balance
            remaining_balance = bill.total_amount - bill.amount_paid
            self.fields['amount'].widget.attrs['max'] = remaining_balance
            self.fields['amount'].help_text = f"Remaining balance: GH₵{remaining_balance:.2f}"
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        bill = self.cleaned_data.get('bill')
        
        if bill and amount:
            if amount <= 0:
                raise forms.ValidationError("Payment amount must be greater than zero.")
            
            remaining_balance = bill.total_amount - bill.amount_paid
            if amount > remaining_balance:
                raise forms.ValidationError(
                    f"Payment amount cannot exceed the remaining balance of GH₵{remaining_balance:.2f}."
                )
        
        return amount
    
    def clean(self):
        cleaned_data = super().clean()
        bill = cleaned_data.get('bill')
        amount = cleaned_data.get('amount')
        
        if bill and amount:
            # Check if payment would make the bill overpaid
            new_total_paid = bill.amount_paid + amount
            if new_total_paid > bill.total_amount:
                raise forms.ValidationError(
                    f"This payment would result in overpayment. Maximum allowed is GH₵{bill.total_amount - bill.amount_paid:.2f}."
                )
        
        return cleaned_data


class StudentProfileForm(forms.ModelForm):
    class Meta:
        model = Student
        fields = ['first_name', 'middle_name', 'last_name', 'date_of_birth', 
                 'gender', 'profile_picture', 'residential_address']
        widgets = {
            'date_of_birth': forms.DateInput(attrs={'type': 'date'}),
            'residential_address': forms.Textarea(attrs={'rows': 3}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Make some fields read-only if needed
        self.fields['first_name'].disabled = True
        self.fields['last_name'].disabled = True



class ParentMessageForm(forms.ModelForm):
    class Meta:
        model = ParentMessage
        fields = ['receiver', 'subject', 'message']
        widgets = {
            'message': forms.Textarea(attrs={'rows': 4}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Limit receiver choices to teachers and staff
        from django.contrib.auth.models import User
        self.fields['receiver'].queryset = User.objects.filter(
            Q(is_staff=True) | Q(teacher__isnull=False)
        )