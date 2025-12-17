"""
Security forms for managing user access, maintenance, and security settings.
"""
import re
import logging
from django import forms
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models import ScheduledMaintenance

logger = logging.getLogger(__name__)
User = get_user_model()


class UserBlockForm(forms.Form):
    """Form for blocking/unblocking users"""
    BLOCK_CHOICES = [
        ('block', 'Block User'),
        ('unblock', 'Unblock User'),
    ]
    
    DURATION_CHOICES = [
        ('', 'Permanent'),
        ('1 hour', '1 Hour'),
        ('6 hours', '6 Hours'), 
        ('1 day', '1 Day'),
        ('3 days', '3 Days'),
        ('1 week', '1 Week'),
    ]
    
    action = forms.ChoiceField(
        choices=BLOCK_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    duration = forms.ChoiceField(
        choices=DURATION_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'}),
        help_text="Select duration for temporary block (leave empty for permanent)"
    )
    reason = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter reason for blocking/unblocking this user...'
        }),
        help_text="Please provide a reason for this action"
    )
    
    def clean_reason(self):
        reason = self.cleaned_data.get('reason', '').strip()
        if not reason:
            raise ValidationError("Reason is required for blocking/unblocking users")
        return reason


class MaintenanceModeForm(forms.Form):
    """Form for enabling/disabling maintenance mode with admin bypass options"""
    MAINTENANCE_CHOICES = [
        ('enable', 'Enable Maintenance Mode'),
        ('disable', 'Disable Maintenance Mode'),
    ]
    
    action = forms.ChoiceField(
        choices=MAINTENANCE_CHOICES,
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    message = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Custom maintenance message (optional)...'
        }),
        help_text="Optional custom message to display during maintenance"
    )
    allow_staff_access = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Allow all staff users to access the system during maintenance"
    )
    allow_superuser_access = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={
            'class': 'form-check-input'
        }),
        help_text="Allow all superusers to access the system during maintenance"
    )


class UserSearchForm(forms.Form):
    """Form for searching users to block/unblock"""
    search_type = forms.ChoiceField(
        choices=[
            ('username', 'Username'),
            ('email', 'Email'),
            ('name', 'Full Name'),
        ],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    search_query = forms.CharField(
        max_length=255,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Enter search term...'
        })
    )
    user_type = forms.ChoiceField(
        choices=[
            ('all', 'All Users'),
            ('student', 'Students Only'),
            ('teacher', 'Teachers Only'),
            ('parent', 'Parents Only'),
            ('staff', 'Staff Only'),
        ],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class ScheduledMaintenanceForm(forms.ModelForm):
    class Meta:
        model = ScheduledMaintenance
        fields = ['title', 'description', 'maintenance_type', 'start_time', 'end_time', 'message']
        widgets = {
            'title': forms.TextInput(attrs={'class': 'form-control'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'maintenance_type': forms.Select(attrs={'class': 'form-control'}),
            'start_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'end_time': forms.DateTimeInput(attrs={'class': 'form-control', 'type': 'datetime-local'}),
            'message': forms.Textarea(attrs={'class': 'form-control', 'rows': 4}),
        }