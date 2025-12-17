"""
Bulk operations forms for handling mass imports and exports.
"""
from datetime import timedelta
from decimal import Decimal
import re
import logging
from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.utils import timezone

from core.models import (
    Student, FeeCategory, Fee, Bill, Assignment,
    AttendancePeriod, AcademicTerm, ClassAssignment,
    CLASS_LEVEL_CHOICES, TERM_CHOICES
)

logger = logging.getLogger(__name__)


class BulkFeeImportForm(forms.Form):
    FILE_TYPE_CHOICES = [
        ('excel', 'Excel File (.xlsx, .xls)'),
        ('csv', 'CSV File (.csv)'),
    ]
    
    file = forms.FileField(
        label="Upload File",
        help_text="Upload Excel or CSV file with fee data",
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.csv,.xlsx,.xls',
            'required': 'required'
        })
    )
    
    file_type = forms.ChoiceField(
        choices=FILE_TYPE_CHOICES,
        initial='excel',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    academic_year = forms.CharField(
        max_length=9,
        required=True,
        validators=[RegexValidator(r'^\d{4}/\d{4}$', 'Enter a valid academic year in format YYYY/YYYY')],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2024/2025',
            'pattern': r'\d{4}/\d{4}'
        })
    )
    
    term = forms.ChoiceField(
        choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        label="Update existing fees",
        help_text="Update fees that already exist for students",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        current_year = timezone.now().year
        self.fields['academic_year'].initial = f"{current_year}/{current_year + 1}"
    
    def clean_file(self):
        file = self.cleaned_data.get('file')
        if file:
            file_type = self.cleaned_data.get('file_type', 'excel')
            if file_type == 'excel' and not file.name.endswith(('.xlsx', '.xls')):
                raise ValidationError("Please upload an Excel file (.xlsx or .xls)")
            elif file_type == 'csv' and not file.name.endswith('.csv'):
                raise ValidationError("Please upload a CSV file (.csv)")
            
            if file.size > 10 * 1024 * 1024:
                raise ValidationError("File size must be less than 10MB")
        
        return file
    
    def clean_academic_year(self):
        academic_year = self.cleaned_data.get('academic_year')
        if academic_year:
            try:
                year1, year2 = map(int, academic_year.split('/'))
                if year2 != year1 + 1:
                    raise ValidationError("The second year should be exactly one year after the first year")
            except (ValueError, IndexError):
                raise ValidationError("Invalid academic year format. Use YYYY/YYYY")
        
        return academic_year


class BulkFeeUpdateForm(forms.Form):
    ACTION_CHOICES = [
        ('update_status', 'Update Payment Status'),
        ('update_due_date', 'Update Due Date'),
        ('adjust_amount', 'Adjust Amount'),
        ('mark_paid', 'Mark as Paid'),
        ('mark_overdue', 'Mark as Overdue'),
        ('add_payment', 'Add Payment'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('unpaid', 'Unpaid'),
        ('partial', 'Partial Payment'),
        ('overdue', 'Overdue'),
    ]
    
    ADJUSTMENT_TYPE_CHOICES = [
        ('increase', 'Increase Amount'),
        ('decrease', 'Decrease Amount'),
        ('set', 'Set Specific Amount'),
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        required=True,
        widget=forms.Select(attrs={
            'class': 'form-control',
            'id': 'id_action'
        })
    )
    
    fee_ids = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter fee IDs separated by commas or one per line...'
        }),
        help_text="Enter fee IDs (comma-separated or one per line)"
    )
    
    new_status = forms.ChoiceField(
        choices=PAYMENT_STATUS_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    new_due_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    amount_adjustment = forms.DecimalField(
        required=False,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0.01'
        }),
        help_text="Amount to adjust by or set to"
    )
    
    adjustment_type = forms.ChoiceField(
        choices=ADJUSTMENT_TYPE_CHOICES,
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        self.fields['new_due_date'].initial = timezone.now().date() + timedelta(days=30)
    
    def clean_fee_ids(self):
        fee_ids = self.cleaned_data.get('fee_ids', '').strip()
        if not fee_ids:
            raise ValidationError("Please enter at least one fee ID")
        
        fee_id_list = []
        for line in fee_ids.split('\n'):
            for fee_id in line.split(','):
                fee_id = fee_id.strip()
                if fee_id and fee_id.isdigit():
                    fee_id_list.append(int(fee_id))
        
        if not fee_id_list:
            raise ValidationError("No valid fee IDs found. Please enter numeric fee IDs.")
        
        existing_fees = Fee.objects.filter(id__in=fee_id_list)
        if existing_fees.count() != len(fee_id_list):
            found_ids = set(existing_fees.values_list('id', flat=True))
            missing_ids = set(fee_id_list) - found_ids
            raise ValidationError(f"Some fee IDs not found: {', '.join(map(str, missing_ids))}")
        
        return fee_id_list
    
    def clean(self):
        cleaned_data = super().clean()
        action = cleaned_data.get('action')
        new_status = cleaned_data.get('new_status')
        new_due_date = cleaned_data.get('new_due_date')
        amount_adjustment = cleaned_data.get('amount_adjustment')
        adjustment_type = cleaned_data.get('adjustment_type')
        
        if action == 'update_status' and not new_status:
            self.add_error('new_status', 'This field is required for status updates')
        
        elif action == 'update_due_date' and not new_due_date:
            self.add_error('new_due_date', 'This field is required for due date updates')
        
        elif action == 'adjust_amount':
            if not amount_adjustment:
                self.add_error('amount_adjustment', 'This field is required for amount adjustments')
            if not adjustment_type:
                self.add_error('adjustment_type', 'This field is required for amount adjustments')
            elif amount_adjustment and amount_adjustment <= 0:
                self.add_error('amount_adjustment', 'Amount must be greater than 0')
        
        elif action == 'add_payment' and not amount_adjustment:
            self.add_error('amount_adjustment', 'Payment amount is required')
        
        return cleaned_data


class BulkFeeCreationForm(forms.Form):
    student_ids = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Enter student IDs separated by commas or one per line...'
        }),
        help_text="Enter student IDs (comma-separated or one per line)"
    )
    
    category = forms.ModelChoiceField(
        queryset=FeeCategory.objects.filter(is_active=True),
        required=True,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    amount_payable = forms.DecimalField(
        required=True,
        max_digits=10,
        decimal_places=2,
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'min': '0.01'
        }),
        help_text="Amount payable for each student"
    )
    
    academic_year = forms.CharField(
        max_length=9,
        required=True,
        validators=[RegexValidator(r'^\d{4}/\d{4}$', 'Enter a valid academic year in format YYYY/YYYY')],
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2024/2025'
        })
    )
    
    term = forms.ChoiceField(
        choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')],
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    due_date = forms.DateField(
        required=True,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Optional description for the fees...'
        })
    )
    
    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        current_year = timezone.now().year
        self.fields['academic_year'].initial = f"{current_year}/{current_year + 1}"
        self.fields['due_date'].initial = timezone.now().date() + timedelta(days=30)
    
    def clean_student_ids(self):
        student_ids = self.cleaned_data.get('student_ids', '').strip()
        if not student_ids:
            raise ValidationError("Please enter at least one student ID")
        
        student_id_list = []
        for line in student_ids.split('\n'):
            for student_id in line.split(','):
                student_id = student_id.strip()
                if student_id:
                    student_id_list.append(student_id)
        
        if not student_id_list:
            raise ValidationError("No valid student IDs found")
        
        existing_students = Student.objects.filter(
            student_id__in=student_id_list, 
            is_active=True
        )
        
        if existing_students.count() != len(student_id_list):
            found_ids = set(existing_students.values_list('student_id', flat=True))
            missing_ids = set(student_id_list) - found_ids
            raise ValidationError(f"Some student IDs not found or inactive: {', '.join(missing_ids)}")
        
        return student_id_list
    
    def clean_amount_payable(self):
        amount = self.cleaned_data.get('amount_payable')
        if amount and amount <= 0:
            raise ValidationError("Amount payable must be greater than 0")
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
        widget=forms.TextInput(attrs={'class': 'form-control'})
    )
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
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
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
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        current_year = timezone.now().year
        self.fields['academic_year'].initial = f"{current_year}/{current_year + 1}"
    
    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date and start_date > end_date:
            raise ValidationError("Start date cannot be after end date")
        
        return cleaned_data


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
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        self.fields['start_date'].initial = timezone.now().date() - timedelta(days=30)
        self.fields['end_date'].initial = timezone.now().date()

    def clean(self):
        cleaned_data = super().clean()
        start_date = cleaned_data.get('start_date')
        end_date = cleaned_data.get('end_date')
        
        if start_date and end_date:
            if start_date > end_date:
                raise ValidationError("Start date cannot be after end date")
            
            if (end_date - start_date).days > 365:
                raise ValidationError("Date range cannot exceed 1 year")
                
        return cleaned_data


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
            self.fields['student'].queryset = parent.students.all()
            
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
                if amount > bill.balance:
                    raise ValidationError(
                        f"Payment amount cannot exceed the bill balance of GH₵{bill.balance:.2f}."
                    )
            else:
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