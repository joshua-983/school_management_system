"""
Fee management forms for handling student fees, discounts, and installments.
"""
from decimal import Decimal
import re
import logging
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from datetime import datetime, timedelta

from core.models import (
    FeeCategory, Fee, FeePayment, FeeDiscount, FeeInstallment,
    Student, CLASS_LEVEL_CHOICES, TERM_CHOICES, FeeGenerationBatch,
    AcademicTerm 
)

logger = logging.getLogger(__name__)

class FeeCategoryForm(forms.ModelForm):
    class Meta:
        model = FeeCategory
        fields = ['name', 'description', 'default_amount', 'frequency', 
                 'is_mandatory', 'is_active', 'applies_to_all', 'class_levels']
        widgets = {
            'name': forms.Select(attrs={
                'class': 'form-control',
                'placeholder': 'Select fee category type'
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Enter description...'
            }),
            'default_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'frequency': forms.Select(attrs={
                'class': 'form-control'
            }),
            'class_levels': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'P1,P2,P3 or leave blank for all'
            }),
        }
        labels = {
            'name': 'Category Type',
            'default_amount': 'Default Amount (GH₵)',
            'is_mandatory': 'Mandatory Fee',
            'applies_to_all': 'Applies to All Classes',
            'class_levels': 'Specific Class Levels',
        }

    def clean_default_amount(self):
        amount = self.cleaned_data.get('default_amount')
        if amount and amount < Decimal('0.01'):
            raise ValidationError("Default amount must be at least GH₵0.01")
        return amount

    def clean_class_levels(self):
        class_levels = self.cleaned_data.get('class_levels', '').strip()
        if class_levels:
            valid_levels = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'J1', 'J2', 'J3']
            levels_list = [level.strip() for level in class_levels.split(',')]
            for level in levels_list:
                if level not in valid_levels:
                    raise ValidationError(f"Invalid class level: {level}. Valid levels are: {', '.join(valid_levels)}")
        return class_levels


class FeeForm(forms.ModelForm):
    
    class Meta:
        model = Fee
        fields = ['student', 'category', 'academic_year', 'term', 'academic_term',
                 'amount_payable', 'amount_paid', 'payment_status', 'payment_mode',
                 'payment_date', 'due_date', 'notes', 'generation_status',
                 'generation_batch', 'bill']  # ADDED generation_status, generation_batch
        widgets = {
            'student': forms.Select(attrs={
                'class': 'form-control',
                'data-placeholder': 'Select student...'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_category',
                'required': True
            }),
            'academic_year': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'YYYY/YYYY e.g., 2024/2025'
            }),
            'term': forms.Select(attrs={
                'class': 'form-control'
            }),
            'academic_term': forms.Select(attrs={
                'class': 'form-control'
            }),
            'amount_payable': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0.01'
            }),
            'amount_paid': forms.NumberInput(attrs={
                'class': 'form-control',
                'placeholder': '0.00',
                'step': '0.01',
                'min': '0'
            }),
            'payment_status': forms.Select(attrs={
                'class': 'form-control',
                'id': 'id_payment_status'
            }),
            'payment_mode': forms.Select(attrs={
                'class': 'form-control'
            }),
            'payment_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Additional notes...'
            }),
            'generation_status': forms.Select(attrs={
                'class': 'form-control'
            }),
            'generation_batch': forms.Select(attrs={
                'class': 'form-control'
            }),
            'bill': forms.Select(attrs={
                'class': 'form-control'
            }),
        }
        labels = {
            'amount_payable': 'Amount Payable (GH₵)',
            'amount_paid': 'Amount Paid (GH₵)',
            'payment_mode': 'Payment Method',
            'payment_date': 'Payment Date',
            'generation_status': 'Generation Status',
            'generation_batch': 'Generation Batch',
        }

    def __init__(self, *args, **kwargs):
        self.student_id = kwargs.pop('student_id', None)
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        
        logger.info(f"FeeForm initialized with student_id: {self.student_id}")
        
        if 'category' in self.fields:
            active_categories = FeeCategory.objects.filter(is_active=True).order_by('name')
            self.fields['category'].queryset = active_categories
            self.fields['category'].empty_label = "--------- Select Fee Category ---------"
            
            logger.info(f"FeeForm: Available categories: {active_categories.count()}")
            for cat in active_categories:
                logger.info(f"  - {cat.get_name_display()} (ID: {cat.id})")
        
        if 'student' in self.fields:
            self.fields['student'].queryset = Student.objects.filter(is_active=True)
        
        # Generation batch field setup
        if 'generation_batch' in self.fields:
            self.fields['generation_batch'].queryset = FeeGenerationBatch.objects.all().order_by('-generated_at')
            self.fields['generation_batch'].required = False
            self.fields['generation_batch'].empty_label = "--------- No Batch ---------"
        
        # Academic term field setup
        if 'academic_term' in self.fields:
            self.fields['academic_term'].queryset = AcademicTerm.objects.all().order_by('-start_date')
            self.fields['academic_term'].required = False
            self.fields['academic_term'].empty_label = "--------- Select Term ---------"
        
        current_year = timezone.now().year
        next_year = current_year + 1
        self.fields['academic_year'].initial = f"{current_year}/{next_year}"
        
        self.fields['term'].initial = 1
        
        if not self.instance.pk:
            self.fields['payment_date'].initial = None
        else:
            self.fields['payment_date'].initial = timezone.now().date()
        
        if not self.instance.pk:
            self.fields['due_date'].initial = timezone.now().date() + timezone.timedelta(days=30)
        
        self.fields['payment_status'].initial = 'unpaid'
        
        # Set default generation status for new fees
        if not self.instance.pk:
            self.fields['generation_status'].initial = 'DRAFT'
        
        # For existing fees, make generation status read-only if LOCKED
        if self.instance.pk and self.instance.generation_status == 'LOCKED':
            self.fields['generation_status'].widget.attrs['readonly'] = True
            self.fields['generation_status'].widget.attrs['disabled'] = True
            self.fields['generation_status'].help_text = "Cannot change status of LOCKED fees"
        
        if self.student_id:
            try:
                student = Student.objects.get(pk=self.student_id)
                self.initial['student'] = student
                self.fields['student'].initial = student
                self.fields['student'].widget.attrs['readonly'] = True
                self.fields['student'].disabled = True
                self.fields['student'].widget = forms.HiddenInput()
                
            except Student.DoesNotExist:
                self.add_error(None, f"Student with ID {self.student_id} not found")
        
        self.fields['_categories_loaded'] = forms.BooleanField(
            initial=True, 
            required=False,
            widget=forms.HiddenInput()
        )

    def clean_academic_year(self):
        academic_year = self.cleaned_data.get('academic_year')
        if not academic_year:
            raise ValidationError("Academic year is required")
        
        if not re.match(r'^\d{4}/\d{4}$', academic_year):
            raise ValidationError("Academic year must be in format YYYY/YYYY (e.g., 2024/2025)")
        
        year1, year2 = map(int, academic_year.split('/'))
        if year2 != year1 + 1:
            raise ValidationError("The second year must be exactly one year after the first year")
            
        return academic_year

    def clean_amount_payable(self):
        amount = self.cleaned_data.get('amount_payable')
        if amount and amount < Decimal('0.01'):
            raise ValidationError("Amount payable must be at least GH₵0.01")
        return amount

    def clean_amount_paid(self):
        amount_paid = self.cleaned_data.get('amount_paid') or Decimal('0.00')
        amount_payable = self.cleaned_data.get('amount_payable')
        
        if amount_payable and amount_paid > amount_payable:
            self.cleaned_data['has_overpayment'] = True
        else:
            self.cleaned_data['has_overpayment'] = False
            
        return amount_paid

    def clean_payment_date(self):
        payment_date = self.cleaned_data.get('payment_date')
        if payment_date and payment_date > timezone.now().date():
            raise ValidationError("Payment date cannot be in the future")
        return payment_date

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        generation_status = self.cleaned_data.get('generation_status', self.instance.generation_status if self.instance else 'DRAFT')
        
        # For DRAFT and GENERATED fees, allow far future dates
        if generation_status in ['DRAFT', 'GENERATED']:
            return due_date  # No validation for draft fees
        
        # For non-draft fees, validate due date
        if due_date and due_date < timezone.now().date():
            if not self.instance.pk:
                raise ValidationError("Due date cannot be in the past for new non-draft fees")
        return due_date
    
    def clean_generation_status(self):
        generation_status = self.cleaned_data.get('generation_status')
        current_status = self.instance.generation_status if self.instance else 'DRAFT'
        
        # Validate status transitions
        valid_transitions = {
            'DRAFT': ['GENERATED', 'VERIFIED', 'CANCELLED'],
            'GENERATED': ['DRAFT', 'VERIFIED', 'CANCELLED'],
            'VERIFIED': ['LOCKED', 'DRAFT', 'CANCELLED'],
            'LOCKED': [],  # Cannot change from LOCKED
            'CANCELLED': ['DRAFT'],
        }
        
        if current_status == 'LOCKED' and generation_status != 'LOCKED':
            raise ValidationError("Cannot change status of a LOCKED fee")
        
        if generation_status not in valid_transitions.get(current_status, []):
            raise ValidationError(
                f"Cannot transition from {current_status} to {generation_status}"
            )
        
        return generation_status

    def clean(self):
        cleaned_data = super().clean()
        
        student = cleaned_data.get('student')
        category = cleaned_data.get('category')
        academic_year = cleaned_data.get('academic_year')
        term = cleaned_data.get('term')
        amount_paid = cleaned_data.get('amount_paid', Decimal('0.00'))
        payment_mode = cleaned_data.get('payment_mode')
        payment_date = cleaned_data.get('payment_date')
        payment_status = cleaned_data.get('payment_status', 'unpaid')
        generation_status = cleaned_data.get('generation_status', 'DRAFT')

        if not category:
            self.add_error('category', 'Please select a fee category')
        
        if student and category and academic_year and term:
            existing_fee = Fee.objects.filter(
                student=student,
                category=category,
                academic_year=academic_year,
                term=term
            ).exclude(pk=self.instance.pk if self.instance else None)
            
            if existing_fee.exists():
                self.add_error(
                    None,
                    f"A fee record already exists for {student} - {category} "
                    f"for {academic_year} Term {term}"
                )

        if payment_status == 'paid':
            if not payment_mode:
                self.add_error('payment_mode', 'Payment method is required for paid status')
            if not payment_date:
                self.add_error('payment_date', 'Payment date is required for paid status')
        elif amount_paid and amount_paid > Decimal('0.00'):
            if not payment_mode:
                self.add_error('payment_mode', 'Payment method is required when an amount is paid')
            if not payment_date:
                self.add_error('payment_date', 'Payment date is required when an amount is paid')
        
        # Additional validation for LOCKED fees
        if generation_status == 'LOCKED':
            if not cleaned_data.get('due_date'):
                self.add_error('due_date', 'Due date is required for LOCKED fees')
            elif cleaned_data.get('due_date') and cleaned_data['due_date'] < timezone.now().date():
                self.add_error('due_date', 'Due date cannot be in the past for LOCKED fees')

        return cleaned_data


class FeeDiscountForm(forms.ModelForm):
    class Meta:
        model = FeeDiscount
        fields = ['student', 'category', 'discount_type', 'amount', 
                 'reason', 'start_date', 'end_date']
        widgets = {
            'student': forms.Select(attrs={
                'class': 'form-control select2',
                'data-placeholder': 'Select student...'
            }),
            'category': forms.Select(attrs={
                'class': 'form-control'
            }),
            'discount_type': forms.Select(attrs={
                'class': 'form-control'
            }),
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'reason': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Reason for discount...'
            }),
            'start_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
            'end_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }

    def __init__(self, *args, **kwargs):
        self.request = kwargs.pop('request', None)
        super().__init__(*args, **kwargs)
        # Set default dates
        self.fields['start_date'].initial = timezone.now().date()
        self.fields['end_date'].initial = timezone.now().date() + timezone.timedelta(days=30)
        
        # Filter to active students and categories
        self.fields['student'].queryset = Student.objects.filter(is_active=True)
        self.fields['category'].queryset = FeeCategory.objects.filter(is_active=True)

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        discount_type = self.cleaned_data.get('discount_type')
        
        if discount_type == 'PERCENT' and amount > 100:
            raise ValidationError("Percentage discount cannot exceed 100%")
        elif amount <= 0:
            raise ValidationError("Discount amount must be greater than 0")
            
        return amount

    def clean_end_date(self):
        start_date = self.cleaned_data.get('start_date')
        end_date = self.cleaned_data.get('end_date')
        
        if start_date and end_date and end_date < start_date:
            raise ValidationError("End date must be after start date")
            
        return end_date


class FeeInstallmentForm(forms.ModelForm):
    class Meta:
        model = FeeInstallment
        fields = ['amount', 'due_date']
        widgets = {
            'amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'step': '0.01',
                'min': '0.01'
            }),
            'due_date': forms.DateInput(attrs={
                'class': 'form-control',
                'type': 'date'
            }),
        }

    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount and amount < Decimal('0.01'):
            raise ValidationError("Installment amount must be at least GH₵0.01")
        return amount

    def clean_due_date(self):
        due_date = self.cleaned_data.get('due_date')
        if due_date and due_date < timezone.now().date():
            raise ValidationError("Due date cannot be in the past")
        return due_date


class PaymentForm(forms.ModelForm):
    """Form for recording payments against a specific fee (FeePayment model)"""
    class Meta:
        model = FeePayment
        fields = ['amount', 'payment_mode', 'payment_date', 'notes', 'bank_reference']
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
            'notes': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 3,
                'placeholder': 'Payment notes...'
            }),
            'bank_reference': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Bank transaction reference...'
            }),
        }
        labels = {
            'amount': 'Payment Amount (GH₵)',
            'bank_reference': 'Transaction Reference',
        }
    
    def __init__(self, *args, **kwargs):
        # Extract fee_id and request from kwargs
        self.fee_id = kwargs.pop('fee_id', None)
        self.fee = kwargs.pop('fee', None)
        self.request = kwargs.pop('request', None)  # Store but don't pass to parent
        super().__init__(*args, **kwargs)
        
        # Set initial payment date to today
        self.fields['payment_date'].initial = timezone.now().date()
        
        # Get fee object if we have fee_id
        fee_obj = self.fee
        if not fee_obj and self.fee_id:
            try:
                fee_obj = Fee.objects.get(id=self.fee_id)
            except Fee.DoesNotExist:
                pass
        
        # Set max amount based on fee balance
        if fee_obj and hasattr(fee_obj, 'balance'):
            balance = fee_obj.balance
            self.fields['amount'].widget.attrs.update({
                'max': float(balance) if balance > 0 else None
            })
            if balance > 0:
                self.fields['amount'].help_text = f'Maximum: GH₵{balance:.2f}'
            else:
                self.fields['amount'].help_text = 'Fee is already fully paid'
    
    def clean_amount(self):
        amount = self.cleaned_data.get('amount')
        if amount:
            amount_decimal = Decimal(str(amount))
            
            # Validate against fee balance
            if hasattr(self, 'fee') and self.fee:
                balance = self.fee.balance
                if amount_decimal > balance:
                    raise forms.ValidationError(
                        f"Payment amount cannot exceed balance due of GH₵{balance:.2f}"
                    )
            
            if amount_decimal <= Decimal('0.00'):
                raise forms.ValidationError("Payment amount must be greater than zero")
        
        return amount
    
    def clean_payment_date(self):
        from datetime import datetime  # Add this import
        payment_date = self.cleaned_data.get('payment_date')
        if payment_date:
            # Convert to date if it's a datetime
            if isinstance(payment_date, datetime):
                payment_date = payment_date.date()
            
            # Now compare with today's date
            if payment_date > timezone.now().date():
                raise forms.ValidationError("Payment date cannot be in the future")
        return payment_date


# Add this to core/forms/fee_forms.py

class FeeFilterForm(forms.Form):
    """Form for filtering fees"""
    academic_year = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2024/2025'
        })
    )
    term = forms.ChoiceField(
        choices=[('', 'All Terms')] + list(TERM_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    payment_status = forms.ChoiceField(
        choices=[('', 'All Statuses'), ('paid', 'Paid'), ('unpaid', 'Unpaid'), 
                ('partial', 'Partial'), ('overdue', 'Overdue')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # ADDED generation_status filter
    generation_status = forms.ChoiceField(
        choices=[('', 'All Statuses'), ('DRAFT', 'Draft'), ('GENERATED', 'Generated'), 
                ('VERIFIED', 'Verified'), ('LOCKED', 'Locked'), ('CANCELLED', 'Cancelled')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    category = forms.ModelChoiceField(
        queryset=FeeCategory.objects.filter(is_active=True),
        required=False,
        empty_label="All Categories",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    student = forms.ModelChoiceField(
        queryset=Student.objects.filter(is_active=True),
        required=False,
        empty_label="All Students",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    has_bill = forms.ChoiceField(
        choices=[('', 'All'), ('yes', 'Has Bill'), ('no', 'No Bill')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


# Add these additional forms to your fee_forms.py file

class FeeStatusReportForm(forms.Form):
    """Form for fee status reporting"""
    REPORT_TYPE_CHOICES = [
        ('summary', 'Summary Report'),
        ('detailed', 'Detailed Report'),
        ('overdue', 'Overdue Fees Report'),
        ('unbilled', 'Unbilled Fees Report'),
    ]
    
    report_type = forms.ChoiceField(
        choices=REPORT_TYPE_CHOICES,
        initial='summary',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    academic_year = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2024/2025'
        })
    )
    term = forms.ChoiceField(
        choices=[('', 'All Terms')] + list(TERM_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    class_level = forms.ChoiceField(
        choices=[('', 'All Classes')] + list(CLASS_LEVEL_CHOICES),
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    payment_status = forms.ChoiceField(
        choices=[('', 'All Statuses'), ('paid', 'Paid'), ('unpaid', 'Unpaid'), 
                ('partial', 'Partial'), ('overdue', 'Overdue')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # ADDED generation_status filter for reports
    generation_status = forms.ChoiceField(
        choices=[('', 'All Statuses'), ('DRAFT', 'Draft'), ('GENERATED', 'Generated'), 
                ('VERIFIED', 'Verified'), ('LOCKED', 'Locked')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    bill_status = forms.ChoiceField(
        choices=[('', 'All'), ('billed', 'Billed'), ('unbilled', 'Unbilled')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )


class BulkFeeImportForm(forms.Form):
    """Form for bulk fee import"""
    file = forms.FileField(
        label='Select file',
        widget=forms.FileInput(attrs={
            'class': 'form-control',
            'accept': '.xlsx,.xls,.csv'
        })
    )
    file_type = forms.ChoiceField(
        choices=[('excel', 'Excel (.xlsx, .xls)'), ('csv', 'CSV (.csv)')],
        initial='excel',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    academic_year = forms.CharField(
        required=True,
        initial=f"{timezone.now().year}/{timezone.now().year + 1}",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2024/2025'
        })
    )
    term = forms.ChoiceField(
        choices=TERM_CHOICES,
        initial=1,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # ADDED generation_status field for bulk imports
    generation_status = forms.ChoiceField(
        choices=[('DRAFT', 'Draft'), ('GENERATED', 'Generated'), ('VERIFIED', 'Verified')],
        initial='DRAFT',
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    update_existing = forms.BooleanField(
        required=False,
        initial=False,
        label='Update existing fees',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )


class BulkFeeUpdateForm(forms.Form):
    """Form for bulk fee updates"""
    ACTION_CHOICES = [
        ('update_status', 'Update Payment Status'),
        ('update_due_date', 'Update Due Date'),
        ('adjust_amount', 'Adjust Amount'),
        ('mark_paid', 'Mark as Paid'),
        ('mark_overdue', 'Mark as Overdue'),
        ('add_payment', 'Add Payment'),
        ('update_generation_status', 'Update Generation Status'),  # ADDED new action
    ]
    
    action = forms.ChoiceField(
        choices=ACTION_CHOICES,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    fee_ids = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter fee IDs separated by commas (e.g., 1,2,3,4)'
        }),
        help_text='Enter fee IDs separated by commas'
    )
    new_status = forms.ChoiceField(
        choices=[('', 'Select Status'), ('paid', 'Paid'), ('unpaid', 'Unpaid'), 
                ('partial', 'Partial'), ('overdue', 'Overdue')],
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
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': '0.00'
        })
    )
    adjustment_type = forms.ChoiceField(
        choices=[('', 'Select Type'), ('increase', 'Increase'), ('decrease', 'Decrease'), ('set', 'Set to Amount')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    # ADDED generation status update field
    new_generation_status = forms.ChoiceField(
        choices=[('', 'Select Generation Status'), ('DRAFT', 'Draft'), ('GENERATED', 'Generated'), 
                ('VERIFIED', 'Verified'), ('LOCKED', 'Locked')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )


class BulkFeeCreationForm(forms.Form):
    """Form for bulk fee creation"""
    student_ids = forms.CharField(
        required=True,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 3,
            'placeholder': 'Enter student IDs separated by commas (e.g., STU001,STU002,STU003)'
        }),
        help_text='Enter student IDs separated by commas or one per line'
    )
    category = forms.ModelChoiceField(
        queryset=FeeCategory.objects.filter(is_active=True),
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    amount_payable = forms.DecimalField(
        required=True,
        max_digits=10,
        decimal_places=2,
        min_value=Decimal('0.01'),
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'step': '0.01',
            'placeholder': '0.00'
        })
    )
    academic_year = forms.CharField(
        required=True,
        initial=f"{timezone.now().year}/{timezone.now().year + 1}",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'e.g., 2024/2025'
        })
    )
    term = forms.ChoiceField(
        choices=TERM_CHOICES,
        initial=1,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    due_date = forms.DateField(
        required=True,
        initial=timezone.now().date() + timedelta(days=30),
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        })
    )
    
    # ADDED generation_status field for bulk creation
    generation_status = forms.ChoiceField(
        choices=[('DRAFT', 'Draft'), ('GENERATED', 'Generated'), ('VERIFIED', 'Verified')],
        initial='DRAFT',
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    description = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 2,
            'placeholder': 'Optional description...'
        })
    )


# NEW FORM: For generating term fees
class GenerateTermFeesForm(forms.Form):
    """Form for generating term fees"""
    academic_term = forms.ModelChoiceField(
        queryset=AcademicTerm.objects.all().order_by('-start_date'),
        widget=forms.Select(attrs={'class': 'form-control'}),
        label="Academic Term",
        help_text="Select the term for which to generate fees"
    )
    
    include_optional = forms.BooleanField(
        required=False,
        initial=False,
        label='Include optional fee categories',
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'}),
        help_text="Check to include non-mandatory fee categories"
    )
    
    def clean_academic_term(self):
        academic_term = self.cleaned_data.get('academic_term')
        
        # Check if fees already exist for this term
        existing_fees = Fee.objects.filter(academic_term=academic_term).exists()
        if existing_fees:
            raise ValidationError(
                "Fees already exist for this academic term. "
                "Please review existing fees before generating new ones."
            )
        
        return academic_term


# NEW FORM: For batch management
class FeeBatchFilterForm(forms.Form):
    """Form for filtering fee batches"""
    status = forms.ChoiceField(
        choices=[('', 'All Statuses'), ('DRAFT', 'Draft'), ('GENERATED', 'Generated'), 
                ('VERIFIED', 'Verified'), ('LOCKED', 'Locked'), ('CANCELLED', 'Cancelled')],
        required=False,
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    academic_term = forms.ModelChoiceField(
        queryset=AcademicTerm.objects.all().order_by('-start_date'),
        required=False,
        empty_label="All Terms",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    generated_by = forms.ModelChoiceField(
        queryset=None,  # Will be set in __init__
        required=False,
        empty_label="All Users",
        widget=forms.Select(attrs={'class': 'form-control'})
    )
    
    start_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Generated After"
    )
    
    end_date = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={
            'class': 'form-control',
            'type': 'date'
        }),
        label="Generated Before"
    )
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Set the generated_by queryset to users who have generated batches
        from django.contrib.auth import get_user_model
        User = get_user_model()
        self.fields['generated_by'].queryset = User.objects.filter(
            fee_batches__isnull=False
        ).distinct().order_by('username')