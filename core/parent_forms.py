# core/parent_forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q
import re

from .models import ParentGuardian, Student

User = get_user_model()

class ParentRegistrationForm(forms.ModelForm):
    """Form for parent registration with user account creation"""
    
    # Add first_name and last_name as form fields (not model fields)
    first_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="First Name"
    )
    
    last_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="Last Name"
    )
    
    password1 = forms.CharField(
        label='Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Create a password'
        }),
        min_length=8,
        help_text="Password must be at least 8 characters long."
    )
    
    password2 = forms.CharField(
        label='Confirm Password',
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Confirm your password'
        }),
        help_text="Enter the same password as above for verification."
    )
    
    # Student selection
    student_ids = forms.CharField(
        required=True,
        widget=forms.HiddenInput(),
        help_text="Select students to associate with this parent"
    )
    
    class Meta:
        model = ParentGuardian
        fields = [
            'email', 'phone_number', 'relationship', 'occupation', 
            'address', 'is_emergency_contact', 'emergency_contact_priority'
        ]  # Removed first_name and last_name from here
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'relationship': forms.Select(attrs={'class': 'form-control'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_emergency_contact': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'emergency_contact_priority': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        # Make email required for account creation
        self.fields['email'].required = True
        
        # Populate first_name and last_name from user if available
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            # Check if email is already used by another parent
            if ParentGuardian.objects.filter(email=email).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise ValidationError("This email is already registered with another parent account.")
            
            # Check if email is already used by a user
            if User.objects.filter(email=email).exists():
                raise ValidationError("This email is already associated with an existing user account.")
        
        return email
    
    def clean_phone_number(self):
        phone_number = self.cleaned_data.get('phone_number')
        if phone_number:
            # Remove any spaces or dashes
            phone_number = phone_number.replace(' ', '').replace('-', '')
            if len(phone_number) != 10 or not phone_number.startswith('0'):
                raise ValidationError("Phone number must be exactly 10 digits starting with 0")
        return phone_number
    
    def clean_password2(self):
        password1 = self.cleaned_data.get('password1')
        password2 = self.cleaned_data.get('password2')
        
        if password1 and password2 and password1 != password2:
            raise ValidationError("Passwords don't match")
        
        return password2
    
    def clean_student_ids(self):
        student_ids = self.cleaned_data.get('student_ids', '')
        if not student_ids:
            raise ValidationError("At least one student must be selected")
        
        # Parse student IDs
        try:
            student_id_list = [sid.strip() for sid in student_ids.split(',') if sid.strip()]
            students = Student.objects.filter(student_id__in=student_id_list, is_active=True)
            
            if students.count() != len(student_id_list):
                found_ids = set(students.values_list('student_id', flat=True))
                missing_ids = set(student_id_list) - found_ids
                raise ValidationError(f"Some student IDs not found: {', '.join(missing_ids)}")
            
            return students
        except Exception as e:
            raise ValidationError("Invalid student IDs provided")
    
    def save(self, commit=True):
        parent = super().save(commit=False)
        
        # Get first_name and last_name from form data
        first_name = self.cleaned_data['first_name']
        last_name = self.cleaned_data['last_name']
        
        # Create user account if it doesn't exist
        if not parent.user:
            password = self.cleaned_data['password1']
            email = self.cleaned_data['email']
            
            # Generate username
            username = self.generate_username(email, first_name, last_name)
            
            # Create user
            user = User.objects.create_user(
                username=username,
                email=email,
                password=password,
                first_name=first_name,
                last_name=last_name
            )
            parent.user = user
        else:
            # Update existing user's name
            parent.user.first_name = first_name
            parent.user.last_name = last_name
            parent.user.save()
        
        if commit:
            parent.save()
            
            # Add students
            students = self.cleaned_data.get('student_ids')
            if students:
                parent.students.set(students)
        
        return parent
    
    def generate_username(self, email, first_name, last_name):
        """Generate a unique username for the parent"""
        base_username = f"{first_name.lower()}.{last_name.lower()}".replace(' ', '')
        
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        return username


class ParentLoginForm(AuthenticationForm):
    """Custom login form for parents"""
    
    username = forms.CharField(
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Email or Username'
        })
    )
    
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={
            'class': 'form-control',
            'placeholder': 'Password'
        })
    )
    
    def clean(self):
        cleaned_data = super().clean()
        username = cleaned_data.get('username')
        
        if username:
            # Check if the user is a parent
            try:
                user = User.objects.get(
                    Q(username=username) | Q(email=username)
                )
                if not hasattr(user, 'parentguardian'):
                    raise ValidationError("This account is not registered as a parent.")
                
                parent = user.parentguardian
                if parent.account_status != 'active':
                    raise ValidationError("Your parent account is not active. Please contact administration.")
                    
            except User.DoesNotExist:
                raise ValidationError("Invalid login credentials.")
        
        return cleaned_data


class ParentProfileForm(forms.ModelForm):
    """Form for parents to update their profile"""
    
    # Add first_name and last_name as form fields
    first_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="First Name"
    )
    
    last_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="Last Name"
    )
    
    class Meta:
        model = ParentGuardian
        fields = [
            'phone_number', 'occupation', 'address', 'relationship'
        ]  # Removed first_name and last_name from here
        widgets = {
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'relationship': forms.Select(attrs={'class': 'form-control'}),
        }
        
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        # Populate with user data if available
        if self.instance and self.instance.user:
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
    
    def save(self, commit=True):
        parent = super().save(commit=False)
        
        # Update user information
        if parent.user:
            parent.user.first_name = self.cleaned_data['first_name']
            parent.user.last_name = self.cleaned_data['last_name']
            parent.user.save()
        
        if commit:
            parent.save()
        
        return parent


class ParentAccountActivationForm(forms.Form):
    """Form for activating parent accounts"""
    
    email = forms.EmailField(
        widget=forms.EmailInput(attrs={'class': 'form-control'})
    )
    
    activation_code = forms.CharField(
        max_length=6,
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
    
    def clean(self):
        cleaned_data = super().clean()
        email = cleaned_data.get('email')
        activation_code = cleaned_data.get('activation_code')
        
        if email and activation_code:
            try:
                parent = ParentGuardian.objects.get(
                    email=email,
                    account_status='pending'
                )
                # Here you would validate the activation code
                # For now, we'll just activate the account
                parent.account_status = 'active'
                parent.save()
            except ParentGuardian.DoesNotExist:
                raise ValidationError("Invalid activation code or email.")
        
        return cleaned_data


# FIXED: AdminParentRegistrationForm without first_name and last_name fields
class AdminParentRegistrationForm(forms.ModelForm):
    """Enhanced parent registration form for admin use - FIXED VERSION"""
    
    # Student selection
    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.filter(is_active=True),
        required=True,
        widget=forms.SelectMultiple(attrs={
            'class': 'form-control select2-multiple',
            'data-placeholder': 'Select students for this parent'
        }),
        help_text="Select students to associate with this parent"
    )
    
    # Account creation options
    create_user_account = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Create user account for parent login"
    )
    
    send_activation_email = forms.BooleanField(
        initial=True,
        required=False,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Send activation email to parent"
    )
    
    # User account fields (these will be used to create the User model)
    username = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        help_text="Leave blank to auto-generate from email"
    )
    
    first_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="First Name"
    )
    
    last_name = forms.CharField(
        max_length=100,
        required=True,
        widget=forms.TextInput(attrs={'class': 'form-control'}),
        label="Last Name"
    )
    
    password = forms.CharField(
        required=False,
        widget=forms.PasswordInput(attrs={'class': 'form-control'}),
        help_text="Leave blank to auto-generate a random password"
    )
    
    class Meta:
        model = ParentGuardian
        fields = [
            'email', 'phone_number', 'relationship', 'occupation', 
            'address', 'is_emergency_contact', 'emergency_contact_priority'
        ]
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'relationship': forms.Select(attrs={'class': 'form-control'}),
            'occupation': forms.TextInput(attrs={'class': 'form-control'}),
            'address': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'is_emergency_contact': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'emergency_contact_priority': forms.NumberInput(attrs={'class': 'form-control'}),
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['email'].required = True
        self.fields['phone_number'].required = True
        
        # If editing existing parent, populate user fields
        if self.instance and self.instance.user:
            self.fields['username'].initial = self.instance.user.username
            self.fields['first_name'].initial = self.instance.user.first_name
            self.fields['last_name'].initial = self.instance.user.last_name
            self.fields['create_user_account'].initial = True
            self.fields['create_user_account'].disabled = True
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email:
            if ParentGuardian.objects.filter(email=email).exclude(pk=self.instance.pk if self.instance else None).exists():
                raise ValidationError("This email is already registered with another parent.")
        return email
    
    def clean_username(self):
        username = self.cleaned_data.get('username')
        if username:
            if User.objects.filter(username=username).exclude(pk=self.instance.user.pk if self.instance and self.instance.user else None).exists():
                raise ValidationError("This username is already taken.")
        return username
    
    def clean(self):
        cleaned_data = super().clean()
        create_user_account = cleaned_data.get('create_user_account')
        
        if create_user_account and not cleaned_data.get('email'):
            raise ValidationError("Email is required to create a user account.")
        
        return cleaned_data
    
    def save(self, commit=True):
        parent = super().save(commit=False)
        
        create_user_account = self.cleaned_data.get('create_user_account')
        first_name = self.cleaned_data.get('first_name')
        last_name = self.cleaned_data.get('last_name')
        email = self.cleaned_data.get('email')
        
        # Create or update user account if requested
        if create_user_account:
            if not parent.user:
                # Create new user
                username = self.cleaned_data.get('username') or self.generate_username(email, first_name, last_name)
                password = self.cleaned_data.get('password') or User.objects.make_random_password()
                
                user = User.objects.create_user(
                    username=username,
                    email=email,
                    password=password,
                    first_name=first_name,
                    last_name=last_name
                )
                parent.user = user
            else:
                # Update existing user
                parent.user.first_name = first_name
                parent.user.last_name = last_name
                parent.user.email = email
                if self.cleaned_data.get('username'):
                    parent.user.username = self.cleaned_data['username']
                parent.user.save()
            
            parent.account_status = 'active'
        
        if commit:
            parent.save()
            # Add students
            students = self.cleaned_data.get('students')
            if students:
                parent.students.set(students)
        
        return parent
    
    def generate_username(self, email, first_name, last_name):
        """Generate a unique username for the parent"""
        base_username = f"{first_name.lower()}.{last_name.lower()}".replace(' ', '')
        
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        return username


class ParentCreationForm(forms.ModelForm):
    """Simplified form for creating parents without user account"""
    
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
    
    students = forms.ModelMultipleChoiceField(
        queryset=Student.objects.all(),
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-control select2'})
    )
    
    class Meta:
        model = ParentGuardian
        fields = ['email', 'phone_number', 'relationship', 'students']
        widgets = {
            'email': forms.EmailInput(attrs={'class': 'form-control'}),
            'phone_number': forms.TextInput(attrs={'class': 'form-control'}),
            'relationship': forms.Select(attrs={'class': 'form-control'}),
        }
    
    def clean_email(self):
        email = self.cleaned_data.get('email')
        if email and ParentGuardian.objects.filter(email=email).exists():
            raise ValidationError("A parent with that email already exists.")
        return email
    
    def save(self, commit=True):
        # This form only creates ParentGuardian records without User accounts
        # The User account can be created later via the admin interface
        parent = super().save(commit=False)
        
        if commit:
            parent.save()
            self.save_m2m()  # Save many-to-many relationships (students)
        
        return parent


class BulkParentForm(forms.Form):
    csv_file = forms.FileField(
        label='CSV File',
        help_text='Upload a CSV file with parent data. Template available for download.',
        widget=forms.FileInput(attrs={'class': 'form-control'})
    )
    
    send_invites = forms.BooleanField(
        required=False,
        initial=True,
        help_text='Send invitation emails to new parents',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class ParentMessageForm(forms.Form):
    subject = forms.CharField(
        max_length=200, 
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Message subject'})
    )
    
    message = forms.CharField(
        widget=forms.Textarea(attrs={'class': 'form-control', 'rows': 5, 'placeholder': 'Type your message here...'})
    )
    
    message_type = forms.ChoiceField(
        choices=[('email', 'Email'), ('sms', 'SMS'), ('internal', 'Internal Message')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )