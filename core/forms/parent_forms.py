from core.models import Student

from core.models import ParentGuardian

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



class ParentGuardianAddForm(forms.ModelForm):

    first_name = forms.CharField(

        max_length=100, 

        required=True, 

        label="First Name",

        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., John'})

    )

    

    last_name = forms.CharField(

        max_length=100, 

        required=True, 

        label="Last Name",

        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'e.g., Doe'})

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

            'relationship', 'phone_number', 'email', 

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

        

        if parent.phone_number:

            parent.phone_number = parent.phone_number.replace(' ', '').replace('-', '')

        

        first_name = self.cleaned_data['first_name'].strip()

        last_name = self.cleaned_data['last_name'].strip()

        email = self.cleaned_data.get('email', '')

        

        username = self.generate_username(first_name, last_name, email)

        

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

    

    def generate_username(self, first_name, last_name, email):

        base_username = f"{first_name.lower()}.{last_name.lower()}".replace(' ', '')

        

        username = base_username

        counter = 1

        while User.objects.filter(username=username).exists():

            username = f"{base_username}{counter}"

            counter += 1

        

        return username