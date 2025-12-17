"""
Budget forms for financial planning and management.
"""
from decimal import Decimal
import re
import logging
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone

logger = logging.getLogger(__name__)


class BudgetForm(forms.ModelForm):
    # Define category choices for the form
    CATEGORY_CHOICES = [
        ('TUITION', 'Tuition Fees'),
        ('EXAMINATION', 'Examination Fees'),
        ('LIBRARY', 'Library Fees'),
        ('SPORTS', 'Sports & Games'),
        ('SCIENCE', 'Science Lab'),
        ('ICT', 'ICT Lab'),
        ('MAINTENANCE', 'Maintenance'),
        ('UTILITIES', 'Utilities'),
        ('SALARIES', 'Salaries'),
        ('OTHER', 'Other Expenses'),
    ]
    
    category = forms.ChoiceField(
        choices=CATEGORY_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    class Meta:
        from core.models import Budget
        model = Budget
        fields = ['category', 'allocated_amount', 'academic_year', 'notes']
        widgets = {
            'academic_year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'YYYY/YYYY'
            }),
            'allocated_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Budget notes...'
            }),
        }
        labels = {
            'allocated_amount': 'Budget Amount (GH₵)',
            'academic_year': 'Academic Year',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        
        current_year = timezone.now().year
        self.fields['academic_year'].initial = f"{current_year}/{current_year + 1}"
    
    def clean_academic_year(self):
        academic_year = self.cleaned_data.get('academic_year')
        if academic_year and not re.match(r'^\d{4}/\d{4}$', academic_year):
            raise ValidationError("Academic year must be in format YYYY/YYYY (e.g., 2024/2025)")
        return academic_year
    
    def clean_allocated_amount(self):
        amount = self.cleaned_data.get('allocated_amount')
        if amount and amount < Decimal('0.01'):
            raise ValidationError("Budget amount must be at least GH₵0.01")
        return amount


class BudgetFilterForm(forms.Form):
    """Form for filtering budgets"""
    academic_year = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'YYYY/YYYY'
        })
    )
    
    category = forms.ChoiceField(
        choices=[('', 'All Categories')] + BudgetForm.CATEGORY_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        current_year = timezone.now().year
        self.fields['academic_year'].initial = f"{current_year}/{current_year + 1}"
    
    def clean_academic_year(self):
        academic_year = self.cleaned_data.get('academic_year')
        if academic_year and not re.match(r'^\d{4}/\d{4}$', academic_year):
            raise ValidationError("Academic year must be in format YYYY/YYYY")
        return academic_year


class ExpenseForm(forms.ModelForm):
    """Form for recording expenses"""
    class Meta:
        from core.models import Expense
        model = Expense
        fields = ['category', 'amount', 'date', 'description', 'receipt_number']
        widgets = {
            'category': forms.Select(attrs={'class': 'form-control'}),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Expense description...'
            }),
            'receipt_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Receipt/Invoice number'
            }),
        }
        labels = {
            'amount': 'Amount (GH₵)',
            'receipt_number': 'Reference Number',
        }
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['date'].initial = timezone.now().date()
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount < Decimal('0.01'):
            raise ValidationError("Amount must be at least GH₵0.01")
        return amount