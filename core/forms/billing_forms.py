"""
Billing forms for handling invoices, bills, and financial transactions.
"""
from datetime import timedelta
from decimal import Decimal
import re
import logging
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator
from django.utils import timezone

from core.models import (
    Bill, BillPayment, Student, FeeCategory, 
    CLASS_LEVEL_CHOICES, TERM_CHOICES
)

logger = logging.getLogger(__name__)


class BillGenerationForm(forms.Form):
    academic_year = forms.CharField(
        max_length=9,
        required=True,
        validators=[RegexValidator(r'^\d{4}/\d{4}$', 'Enter a valid academic year in format YYYY/YYYY')],
        widget=forms.TextInput(attrs={
            'class': 'form-control', 
            'placeholder': 'e.g., 2024/2025',
            'pattern': r'\d{4}/\d{4}',
            'title': 'Format: YYYY/YYYY'
        })
    )
    
    term = forms.ChoiceField(
        choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        required=True,
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    class_levels = forms.MultipleChoiceField(
        choices=CLASS_LEVEL_CHOICES,
        required=False,
        widget=forms.SelectMultiple(attrs={'class': 'form-select', 'size': '6'}),
        help_text="Select specific class levels (leave blank for all)"
    )
    
    due_date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
        help_text="Due date for the generated bills"
    )
    
    notes = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'rows': 2, 
            'class': 'form-control', 
            'placeholder': 'Optional notes for the bills'
        }),
        help_text="Optional notes that will be added to all generated bills"
    )
    
    skip_existing = forms.BooleanField(
        required=False,
        initial=True,
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Skip students who already have bills for this term"
    )
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
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


class BillPaymentForm(forms.ModelForm):
    class Meta:
        model = BillPayment
        fields = ['amount', 'payment_mode', 'payment_date', 'reference_number', 'notes']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'payment_mode': forms.Select(attrs={
                'class': 'form-select'
            }),
            'payment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'reference_number': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Optional transaction reference'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Payment notes...'
            }),
        }
        labels = {
            'amount': 'Payment Amount (GH₵)',
            'reference_number': 'Reference Number',
        }
    
    def __init__(self, *args, **kwargs):
        self.bill = kwargs.pop('bill', None)
        super().__init__(*args, **kwargs)
        
        self.fields['payment_date'].initial = timezone.now().date()
        
        if self.bill:
            balance_due = self.bill.get_balance_due
            self.fields['amount'].widget.attrs.update({
                'max': float(balance_due) if balance_due else None
            })
            self.fields['amount'].help_text = f'Maximum: GH₵{balance_due:.2f}'
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount:
            amount_decimal = Decimal(str(amount))
            if self.bill:
                balance_due = Decimal(str(self.bill.get_balance_due))
                if amount_decimal > balance_due:
                    raise forms.ValidationError(
                        f"Payment amount cannot exceed balance due of GH₵{balance_due:.2f}"
                    )
                if amount_decimal <= Decimal('0.00'):
                    raise forms.ValidationError("Payment amount must be greater than zero")
        return amount

    def clean_payment_date(self):
        payment_date = self.cleaned_data.get('payment_date')
        if payment_date and payment_date > timezone.now().date():
            raise forms.ValidationError("Payment date cannot be in the future")
        return payment_date


class BillFilterForm(forms.Form):
    """Form for filtering bills in the bill list view"""
    STATUS_CHOICES = [
        ('', 'All Statuses'),
        ('issued', 'Issued'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled'),
    ]
    
    academic_year = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2024/2025'
        })
    )
    
    term = forms.ChoiceField(
        choices=[('', 'All Terms')] + [(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    status = forms.ChoiceField(
        choices=STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    student = forms.ModelChoiceField(
        queryset=Student.objects.filter(is_active=True),
        required=False,
        empty_label="All Students",
        widget=forms.Select(attrs={
            'class': 'form-control select2',
            'data-placeholder': 'Select student...'
        })
    )
    
    class_level = forms.ChoiceField(
        choices=[('', 'All Classes')] + CLASS_LEVEL_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        current_year = timezone.now().year
        self.fields['academic_year'].initial = f"{current_year}/{current_year + 1}"


class BillUpdateForm(forms.ModelForm):
    """Form for updating existing bills (admin only)"""
    class Meta:
        model = Bill
        fields = ['due_date', 'notes', 'status']
        widgets = {
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Bill notes...'
            }),
            'status': forms.Select(attrs={'class': 'form-control'}),
        }
        labels = {
            'due_date': 'Due Date',
            'notes': 'Notes',
            'status': 'Status',
        }
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        # Don't allow changing status to paid if there's still balance
        if self.instance and self.instance.balance > 0:
            self.fields['status'].choices = [
                ('issued', 'Issued'),
                ('partial', 'Partially Paid'),
                ('overdue', 'Overdue'),
                ('cancelled', 'Cancelled'),
            ]
    
    def clean_status(self):
        status = self.cleaned_data.get('status')
        if status == 'paid' and self.instance.balance > 0:
            raise forms.ValidationError(
                "Cannot mark bill as paid when there is an outstanding balance"
            )
        return status
    
    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        if due_date and due_date < timezone.now().date():
            raise forms.ValidationError("Due date cannot be in the past")
        return due_date


class BulkBillActionForm(forms.Form):
    """Form for bulk actions on bills"""
    ACTION_CHOICES = [
        ('', 'Select Action'),
        ('send_reminders', 'Send Payment Reminders'),
        ('mark_overdue', 'Mark Selected as Overdue'),
        ('cancel', 'Cancel Selected Bills'),
        ('export', 'Export Selected Bills'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    bill_ids = forms.CharField(
        widget=forms.HiddenInput(),
        required=False
    )
    
    def clean_bill_ids(self):
        bill_ids = self.cleaned_data.get('bill_ids', '')
        if bill_ids:
            try:
                bill_id_list = [int(id.strip()) for id in bill_ids.split(',') if id.strip()]
                return bill_id_list
            except ValueError:
                raise forms.ValidationError("Invalid bill IDs provided")
        return []