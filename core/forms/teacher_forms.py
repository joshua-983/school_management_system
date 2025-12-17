from core.models import Teacher, Subject, CLASS_LEVEL_CHOICES
from decimal import Decimal
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.db import models
from django.utils import timezone
import logging
import re


logger = logging.getLogger(__name__)
User = get_user_model()

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
        self.request = kwargs.pop('request', None)
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
        
        if teacher.phone_number:
            teacher.phone_number = teacher.phone_number.replace(' ', '').replace('-', '')
        
        if commit:
            teacher.save()
            self.save_m2m()
        
        return teacher

class ClassAssignmentForm(forms.ModelForm):
    add_qualification = forms.BooleanField(
        required=False,
        initial=True,
        label="Add subject to teacher's qualifications if needed",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    class Meta:
        # Meta without model - will be set in __new__
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
    
    def __new__(cls, *args, **kwargs):
        # Resolve the model when creating form instances
        from django.apps import apps
        cls._meta.model = apps.get_model('core', 'ClassAssignment')
        return super().__new__(cls, *args, **kwargs)
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        if self.request and hasattr(self.request.user, 'teacher'):
            self.fields['teacher'].queryset = Teacher.objects.filter(pk=self.request.user.teacher.pk)
            self.fields['teacher'].initial = self.request.user.teacher
            self.fields['teacher'].disabled = True
        
        if not self.instance.pk:
            current_year = timezone.now().year
            self.initial['academic_year'] = f"{current_year}/{current_year + 1}"
            
        if self.request and hasattr(self.request.user, 'teacher'):
            self.fields['add_qualification'].widget = forms.HiddenInput()

    def clean(self):
        cleaned_data = super().clean()
        class_level = cleaned_data.get('class_level')
        subject = cleaned_data.get('subject')
        teacher = cleaned_data.get('teacher')
        academic_year = cleaned_data.get('academic_year')
        add_qualification = cleaned_data.get('add_qualification', False)
        
        if class_level and subject and teacher and academic_year:
            # Get model from self._meta
            existing = self._meta.model.objects.filter(
                class_level=class_level,
                subject=subject,
                teacher=teacher,
                academic_year=academic_year
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing.exists():
                raise forms.ValidationError(
                    "This teacher is already assigned to teach this subject for this class level and academic year"
                )
        
        if teacher and subject:
            if subject not in teacher.subjects.all():
                self.qualification_warning = True
                self.unqualified_subject = subject
                self.unqualified_teacher = teacher
                
                if add_qualification:
                    teacher.subjects.add(subject)
                    teacher.save()
                    self.qualification_warning = False
        
        return cleaned_data