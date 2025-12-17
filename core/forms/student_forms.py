from core.models import Student, ParentGuardian
from core.utils import is_teacher
from datetime import date
from decimal import Decimal
from django import forms
from django.apps import apps
from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.db.models import Q
from django.utils import timezone
import logging
import re



logger = logging.getLogger(__name__)
User = apps.get_model(settings.AUTH_USER_MODEL)

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
    
    parents = forms.ModelMultipleChoiceField(
        queryset=ParentGuardian.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control select2-multiple',
            'data-placeholder': 'Select existing parents (optional)',
            'style': 'width: 100%'
        }),
        help_text="Optional: Assign existing parents to this student"
    )
    
    create_parent_account = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'create_parent_account'
        }),
        label="Create parent account for guardians"
    )
    
    class Meta:
        model = Student
        fields = [
            'first_name', 'middle_name', 'last_name', 'date_of_birth', 'gender', 
            'nationality', 'ethnicity', 'religion', 'place_of_birth', 
            'residential_address', 'profile_picture', 'class_level', 
            'username', 'email', 'phone_number', 'parents', 'create_parent_account'
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
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Make only essential fields required
        self.fields['first_name'].required = False
        self.fields['middle_name'].required = False
        self.fields['last_name'].required = False
        self.fields['date_of_birth'].required = False
        self.fields['gender'].required = True
        self.fields['nationality'].required = False
        self.fields['ethnicity'].required = False
        self.fields['religion'].required = False
        self.fields['place_of_birth'].required = False
        self.fields['residential_address'].required = False
        self.fields['class_level'].required = True
        self.fields['phone_number'].required = False
        self.fields['profile_picture'].required = False
        
        # Setup parents field
        self.fields['parents'].queryset = ParentGuardian.objects.filter(
            user__is_active=True
        ).select_related('user').order_by('user__last_name', 'user__first_name')
        
        # Set initial parents for existing students
        if self.instance and self.instance.pk:
            try:
                if hasattr(self.instance, 'parents'):
                    self.fields['parents'].initial = self.instance.parents.all()
                elif hasattr(self.instance, 'parentguardian_set'):
                    self.fields['parents'].initial = self.instance.parentguardian_set.all()
                elif hasattr(self.instance, 'guardians'):
                    self.fields['parents'].initial = self.instance.guardians.all()
                else:
                    parents = ParentGuardian.objects.filter(students=self.instance)
                    self.fields['parents'].initial = parents
            except Exception as e:
                logger.warning(f"Error setting initial parents for student {self.instance.pk}: {e}")
                self.fields['parents'].initial = ParentGuardian.objects.none()
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            query = User.objects.filter(username=username)
            if self.instance and self.instance.pk and hasattr(self.instance, 'user'):
                query = query.exclude(pk=self.instance.user.pk)
            
            if query.exists():
                raise ValidationError("A user with this username already exists.")
            
            if not re.match(r'^[\w.@+-]+\Z', username):
                raise ValidationError(
                    "Enter a valid username. This value may contain only letters, "
                    "numbers, and @/./+/-/_ characters."
                )
        return username
    
    def clean_date_of_birth(self):
        dob = self.cleaned_data.get('date_of_birth')
        if dob:
            today = date.today()
            if dob > today:
                raise ValidationError("Date of birth cannot be in the future.")
            
            min_age = 4
            max_age = 25
            age = today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))
            
            if age < min_age:
                raise ValidationError(f"Student must be at least {min_age} years old.")
            if age > max_age:
                raise ValidationError(f"Student age cannot exceed {max_age} years.")
                
        return dob
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            phone_number = phone_number.replace(' ', '').replace('-', '')
            if len(phone_number) != 10 or not phone_number.startswith('0'):
                raise ValidationError("Phone number must be exactly 10 digits starting with 0")
            
            if self.instance and self.instance.pk:
                existing = Student.objects.filter(phone_number=phone_number).exclude(pk=self.instance.pk)
            else:
                existing = Student.objects.filter(phone_number=phone_number)
                
            if existing.exists():
                raise ValidationError("This phone number is already associated with another student.")
        return phone_number
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            email = email.lower().strip()
            
            query = User.objects.filter(email=email)
            if self.instance and self.instance.pk and hasattr(self.instance, 'user'):
                query = query.exclude(pk=self.instance.user.pk)
            
            if query.exists():
                raise ValidationError("A user with this email already exists.")
        return email
    
    def clean(self):
        cleaned_data = super().clean()
        password1 = cleaned_data.get('password1')
        password2 = cleaned_data.get('password2')
        email = cleaned_data.get('email')
        create_parent_account = cleaned_data.get('create_parent_account')
        
        if password1 and password2:
            if password1 != password2:
                self.add_error('password2', "Passwords don't match")
            
            if len(password1) < 8:
                self.add_error('password1', "Password must be at least 8 characters long.")
            if not any(char.isdigit() for char in password1):
                self.add_error('password1', "Password must contain at least one number.")
            if not any(char.isalpha() for char in password1):
                self.add_error('password1', "Password must contain at least one letter.")
        
        if not email:
            self.add_error('email', "Email address is required.")
        
        first_name = cleaned_data.get('first_name', '').strip()
        last_name = cleaned_data.get('last_name', '').strip()
        
        if not first_name and not last_name:
            self.add_error('first_name', "Either first name or last name is required.")
            self.add_error('last_name', "Either first name or last name is required.")
        
        if create_parent_account:
            pass
        
        return cleaned_data
    
    def save(self, commit=True):
        student = super().save(commit=False)
        
        if student.phone_number:
            student.phone_number = student.phone_number.replace(' ', '').replace('-', '')
        
        is_new_student = not student.pk
        
        if is_new_student:
            username = self.cleaned_data['username']
            email = self.cleaned_data['email']
            password = self.cleaned_data['password1']
            
            first_name = self.cleaned_data.get('first_name', '').strip()
            last_name = self.cleaned_data.get('last_name', '').strip()
            
            if not first_name:
                first_name = "Student"
            if not last_name:
                last_name = username
            
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name,
            )
            student.user = user
        else:
            if hasattr(student, 'user') and student.user:
                user = student.user
                if 'email' in self.cleaned_data:
                    user.email = self.cleaned_data['email']
                if 'first_name' in self.cleaned_data:
                    user.first_name = self.cleaned_data.get('first_name', user.first_name)
                if 'last_name' in self.cleaned_data:
                    user.last_name = self.cleaned_data.get('last_name', user.last_name)
                
                if 'password1' in self.cleaned_data and self.cleaned_data['password1']:
                    user.set_password(self.cleaned_data['password1'])
                
                user.save()
        
        if commit:
            student.save()
            self.save_m2m()
            
            if 'parents' in self.cleaned_data:
                try:
                    if hasattr(student, 'parents'):
                        student.parents.set(self.cleaned_data['parents'])
                    else:
                        for parent in self.cleaned_data['parents']:
                            parent.students.add(student)
                except Exception as e:
                    logger.error(f"Error assigning parents to student {student.pk}: {e}")
        
        return student

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
    
    current_parents = forms.ModelMultipleChoiceField(
        queryset=ParentGuardian.objects.none(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control',
            'disabled': 'disabled',
            'size': '3'
        }),
        label="Current Parents/Guardians",
        help_text="Parents/guardians assigned to you (contact admin to modify)"
    )
    
    class Meta:
        model = Student
        fields = [
            'first_name', 'middle_name', 'last_name', 'date_of_birth', 
            'gender', 'profile_picture', 'residential_address', 'nationality',
            'ethnicity', 'religion', 'place_of_birth', 'phone_number',
            'current_parents'
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
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        if self.instance and self.instance.pk:
            parents = self.instance.parentguardian_set.all()
            self.fields['current_parents'].queryset = parents
            self.fields['current_parents'].initial = parents
            
            parent_choices = []
            for parent in parents:
                display_name = f"{parent.user.get_full_name()} ({parent.get_relationship_display()})"
                if parent.phone_number:
                    display_name += f" - {parent.phone_number}"
                parent_choices.append((parent.id, display_name))
            
            self.fields['current_parents'].choices = parent_choices
        
        self.fields['current_parents'].widget.attrs['readonly'] = True
        self.fields['current_parents'].widget.attrs['class'] += ' bg-light'
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            phone_number = phone_number.replace(' ', '').replace('-', '')
            if len(phone_number) != 10 or not phone_number.startswith('0'):
                raise ValidationError("Phone number must be exactly 10 digits starting with 0")
        return phone_number

class StudentParentAssignmentForm(forms.Form):
    """Form for assigning parents to students"""
    
    parents = forms.ModelMultipleChoiceField(
        queryset=ParentGuardian.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control select2-multiple',
            'data-placeholder': 'Select parents to assign...',
            'style': 'width: 100%'
        }),
        help_text="Select existing parents to assign to this student"
    )
    
    create_new_parent = forms.BooleanField(
        required=False,
        initial=False,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input',
            'id': 'create_new_parent_toggle'
        }),
        label="Create new parent/guardian"
    )
    
    new_parent_first_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'First name'
        }),
        label="First Name"
    )
    
    new_parent_last_name = forms.CharField(
        max_length=100,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Last name'
        }),
        label="Last Name"
    )
    
    new_parent_relationship = forms.ChoiceField(
        choices=ParentGuardian.RELATIONSHIP_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Relationship"
    )
    
    new_parent_phone = forms.CharField(
        max_length=10,
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': '0241234567',
            'pattern': r'0\d{9}'
        }),
        label="Phone Number",
        help_text="10-digit number starting with 0"
    )
    
    new_parent_email = forms.EmailField(
        required=False,
        widget=forms.EmailInput(attrs={
            'class': 'form-control',
            'placeholder': 'parent@example.com'
        }),
        label="Email Address"
    )

    def __init__(self, *args, **kwargs):
        self.student = kwargs.pop('student', None)
        super().__init__(*args, **kwargs)
        
        self.fields['parents'].queryset = ParentGuardian.objects.filter(
            user__is_active=True
        ).select_related('user').order_by('user__last_name', 'user__first_name')
        
        if self.student:
            self.fields['parents'].initial = self.student.parents.all()

    def clean_new_parent_phone(self):
        phone = self.cleaned_data.get('new_parent_phone')
        if phone:
            phone = phone.replace(' ', '').replace('-', '')
            if len(phone) != 10 or not phone.startswith('0'):
                raise ValidationError("Phone number must be exactly 10 digits starting with 0")
            
            if ParentGuardian.objects.filter(phone_number=phone).exists():
                raise ValidationError("A parent with this phone number already exists")
        
        return phone

    def clean_new_parent_email(self):
        email = self.cleaned_data.get('new_parent_email')
        if email:
            email = email.lower()
            if not re.match(r'^[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}$', email):
                raise ValidationError("Please enter a valid email address.")
            
            if User.objects.filter(email=email).exists():
                raise ValidationError("This email is already associated with an existing user account.")
        
        return email

    def clean(self):
        cleaned_data = super().clean()
        create_new = cleaned_data.get('create_new_parent')
        new_parent_first_name = cleaned_data.get('new_parent_first_name')
        new_parent_last_name = cleaned_data.get('new_parent_last_name')
        new_parent_phone = cleaned_data.get('new_parent_phone')
        new_parent_relationship = cleaned_data.get('new_parent_relationship')
        
        if create_new:
            if not new_parent_first_name:
                self.add_error('new_parent_first_name', 'First name is required when creating a new parent')
            
            if not new_parent_last_name:
                self.add_error('new_parent_last_name', 'Last name is required when creating a new parent')
            
            if not new_parent_phone:
                self.add_error('new_parent_phone', 'Phone number is required when creating a new parent')
            
            if not new_parent_relationship:
                self.add_error('new_parent_relationship', 'Relationship is required when creating a new parent')
            
            selected_parents = cleaned_data.get('parents', [])
            if not selected_parents and not (new_parent_first_name and new_parent_last_name and new_parent_phone):
                raise ValidationError("Please either select existing parents or create a new parent.")
        
        return cleaned_data

    def save(self):
        if not self.student:
            return None
            
        selected_parents = self.cleaned_data.get('parents', [])
        self.student.parents.set(selected_parents)
        
        if self.cleaned_data.get('create_new_parent'):
            try:
                first_name = self.cleaned_data['new_parent_first_name'].strip()
                last_name = self.cleaned_data['new_parent_last_name'].strip()
                clean_phone = self.cleaned_data['new_parent_phone'].replace(' ', '').replace('-', '')
                relationship = self.cleaned_data['new_parent_relationship']
                email = self.cleaned_data.get('new_parent_email', '').strip()
                
                base_username = f"{first_name.lower()}.{last_name.lower()}".replace(' ', '')
                
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                user = User.objects.create_user(
                    username=username,
                    password='temp123',
                    first_name=first_name,
                    last_name=last_name,
                    email=email
                )
                
                new_parent = ParentGuardian.objects.create(
                    user=user,
                    relationship=relationship,
                    phone_number=clean_phone,
                    email=email,
                    account_status='active'
                )
                
                new_parent.students.add(self.student)
                
                logger.info(f"Created new parent {new_parent} for student {self.student}")
                
            except Exception as e:
                logger.error(f"Error creating new parent for student {self.student}: {str(e)}")
                raise ValidationError(f"Error creating new parent: {str(e)}")
        
        return self.student