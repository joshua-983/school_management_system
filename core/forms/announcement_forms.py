from core.models import Announcement, CLASS_LEVEL_CHOICES
from django import forms
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone
import logging
import re



logger = logging.getLogger(__name__)

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
    
    # Make target_roles required with proper validation
    target_roles = forms.ChoiceField(
        choices=Announcement.TARGET_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control'
        }),
        help_text="Select which user roles should see this announcement"
    )
    
    class Meta:
        model = Announcement
        fields = [
            'title', 'message', 'priority', 'target_roles', 
            'is_active', 'start_date', 'end_date', 'attachment'
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
            'start_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'end_date': forms.DateTimeInput(attrs={
                'class': 'form-control',
                'type': 'datetime-local'
            }),
            'is_active': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'attachment': forms.FileInput(attrs={'class': 'form-control'}),
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
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        
        # Set initial values for target_class_levels from the instance
        if self.instance and self.instance.pk and self.instance.target_class_levels:
            self.initial['target_class_levels'] = self.instance.get_target_class_levels()
        
        # Set default start date to current time if not set
        if not self.instance.pk and not self.data.get('start_date'):
            self.initial['start_date'] = timezone.now().strftime('%Y-%m-%dT%H:%M')
        
        # Set default target_roles if not set
        if not self.instance.pk and not self.data.get('target_roles'):
            self.initial['target_roles'] = 'ALL'
        
        # Make end_date not required
        self.fields['end_date'].required = False
        
        # Ensure target_roles is marked as required in the template
        self.fields['target_roles'].required = True
        
    def clean_target_roles(self):
        """Clean and validate target_roles field"""
        target_roles = self.cleaned_data.get('target_roles')
        if not target_roles:
            raise ValidationError("This field is required.")
        return target_roles
        
    def clean_target_class_levels(self):
        """Clean and validate target class levels"""
        class_levels = self.cleaned_data.get('target_class_levels', [])
        # Return as list, we'll handle the conversion in save()
        return class_levels
    
    def clean(self):
        cleaned_data = super().clean()
        target_roles = cleaned_data.get('target_roles')
        target_class_levels = cleaned_data.get('target_class_levels')
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        # Ensure target_roles is present
        if not target_roles:
            self.add_error('target_roles', 'This field is required.')
        
        # If targeting specific classes, ensure class levels are selected
        if target_roles == 'CLASS' and not target_class_levels:
            raise forms.ValidationError({
                'target_class_levels': 'Please select at least one class level when targeting specific classes.'
            })
        
        # Validate end date is after start date
        if start_date and end_date and end_date <= start_date:
            raise forms.ValidationError({
                'end_date': 'End date must be after start date.'
            })
        
        # Validate end date is not in the past
        if end_date and end_date < timezone.now():
            raise forms.ValidationError({
                'end_date': 'End date cannot be in the past.'
            })
        
        return cleaned_data
    
    def save(self, commit=True):
        instance = super().save(commit=False)
        
        # Handle target class levels - convert list to comma-separated string
        target_class_levels = self.cleaned_data.get('target_class_levels', [])
        if target_class_levels:
            instance.target_class_levels = ','.join(target_class_levels)
        else:
            instance.target_class_levels = ''
        
        if commit:
            instance.save()
        
        return instance