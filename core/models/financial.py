"""
Financial management models: Fees, Bills, Payments, etc.
"""
import logging
from decimal import Decimal
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator, RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.db.models import Sum

from core.models.base import TERM_CHOICES
from core.models.student import Student
from core.models.academic import AcademicTerm

logger = logging.getLogger(__name__)
User = get_user_model()

# Import constants
from core.constants.financial import (
    BILL_STATUS_CHOICES,
    FEE_STATUS_CHOICES,
    PAYMENT_METHOD_CHOICES,
    FEE_CATEGORY_TYPES,
    FEE_FREQUENCY_CHOICES,
    PAYMENT_TOLERANCE,
    PAYMENT_GRACE_PERIOD,
)


class FeeCategory(models.Model):
    CATEGORY_TYPES = FEE_CATEGORY_TYPES
    FREQUENCY_CHOICES = FEE_FREQUENCY_CHOICES
    
    name = models.CharField(max_length=100, choices=CATEGORY_TYPES)
    description = models.TextField(blank=True)
    default_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='termly')
    is_mandatory = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    applies_to_all = models.BooleanField(default=True)
    class_levels = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Comma-separated list of class levels this applies to (leave blank for all)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Fee Categories"
        ordering = ['name']
        verbose_name = 'Fee Category'
    
    def __str__(self):
        return self.get_name_display()
    
    def get_frequency_display_with_icon(self):
        """Return frequency with appropriate icon for display"""
        icons = {
            'one_time': '💰',
            'termly': '📚',
            'monthly': '📅',
            'quarterly': '📊',
            'semester': '🎓',
            'annual': '📆',
            'custom': '⚙️',
        }
        return f"{icons.get(self.frequency, '📝')} {self.get_frequency_display()}"
    
    def get_applicable_class_levels(self):
        """Return list of applicable class levels"""
        if not self.class_levels:
            return []
        return [level.strip() for level in self.class_levels.split(',')]
    
    def is_applicable_to_class(self, class_level):
        """Check if this fee applies to a specific class level"""
        if self.applies_to_all or not self.class_levels:
            return True
        return class_level in self.get_applicable_class_levels()
    
    @classmethod
    def setup_default_categories(cls):
        """Create default professional fee categories"""
        categories = [
            {
                'name': 'TUITION',
                'description': 'Core academic instruction fees covering teachers salaries and classroom costs',
                'default_amount': 5000.00,
                'frequency': 'termly',
                'is_mandatory': True,
                'is_active': True,
                'applies_to_all': True,
            },
            {
                'name': 'ADMISSION',
                'description': 'One-time fee charged when a student is newly enrolled in the school',
                'default_amount': 500.00,
                'frequency': 'one_time',
                'is_mandatory': True,
                'is_active': True,
                'applies_to_all': True,
            },
            {
                'name': 'TRANSPORT',
                'description': 'School bus transportation services',
                'default_amount': 800.00,
                'frequency': 'termly',
                'is_mandatory': False,
                'is_active': True,
                'applies_to_all': True,
            },
            {
                'name': 'TECHNOLOGY',
                'description': 'Covers computer labs, software licenses, internet access and educational technology',
                'default_amount': 300.00,
                'frequency': 'termly',
                'is_mandatory': True,
                'is_active': True,
                'applies_to_all': True,
            },
            {
                'name': 'EXAMINATION',
                'description': 'Fees for internal and external examinations and certifications',
                'default_amount': 200.00,
                'frequency': 'termly',
                'is_mandatory': True,
                'is_active': True,
                'applies_to_all': True,
            },
            {
                'name': 'UNIFORM',
                'description': 'School uniform costs',
                'default_amount': 350.00,
                'frequency': 'one_time',
                'is_mandatory': True,
                'is_active': True,
                'applies_to_all': True,
            },
            {
                'name': 'PTA',
                'description': 'Parent-Teacher Association fees for school development projects',
                'default_amount': 100.00,
                'frequency': 'termly',
                'is_mandatory': True,
                'is_active': True,
                'applies_to_all': True,
            },
            {
                'name': 'EXTRA_CLASSES',
                'description': 'Additional tuition and special classes outside regular hours',
                'default_amount': 400.00,
                'frequency': 'termly',
                'is_mandatory': False,
                'is_active': True,
                'applies_to_all': True,
            }
        ]
        
        for category_data in categories:
            category, created = cls.objects.get_or_create(
                name=category_data['name'],
                defaults=category_data
            )
            if not created:
                # Update existing category
                for key, value in category_data.items():
                    if key != 'name':
                        setattr(category, key, value)
                category.save()
        
        return cls.objects.count()


class Bill(models.Model):
    """Represents an invoice sent to a student for specific fees"""
    bill_number = models.CharField(max_length=20, unique=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='bills')
    issue_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    academic_year = models.CharField(max_length=9)
    term = models.PositiveSmallIntegerField(choices=TERM_CHOICES)
    
    status = models.CharField(
        max_length=20,
        choices=BILL_STATUS_CHOICES,
        default='issued'
    )
    
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='recorded_bills')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-issue_date']
        verbose_name = 'Bill'
        verbose_name_plural = 'Bills'
        indexes = [
            models.Index(fields=['student', 'academic_year', 'term']),
            models.Index(fields=['status']),
            models.Index(fields=['due_date']),
        ]
    
    def __str__(self):
        return f"Bill #{self.bill_number} - {self.student.get_full_name()}"
    
    def save(self, *args, **kwargs):
        if not self.bill_number:
            self.bill_number = self.generate_bill_number()
        
        # Use Decimal for calculations
        total_amount = Decimal(str(self.total_amount)) if self.total_amount else Decimal('0.00')
        amount_paid = Decimal(str(self.amount_paid)) if self.amount_paid else Decimal('0.00')
        
        # Calculate balance
        self.balance = total_amount - amount_paid
        
        # Auto-update status based on payments and due date
        self.update_status()
        
        super().save(*args, **kwargs)
    
    def generate_bill_number(self):
        """Generate unique bill number"""
        current_year = str(timezone.now().year)
        last_bill = Bill.objects.filter(
            bill_number__startswith=f'BILL{current_year}'
        ).order_by('-bill_number').first()
        
        if last_bill:
            try:
                last_sequence = int(last_bill.bill_number[-6:])
                new_sequence = last_sequence + 1
            except ValueError:
                new_sequence = 1
        else:
            new_sequence = 1
            
        return f"BILL{current_year}{new_sequence:06d}"
    
    def update_status(self):
        """Update bill status based on payments and due date"""
        tolerance = PAYMENT_TOLERANCE
        
        # Get total payments for this bill
        total_payments = self.bill_payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        self.amount_paid = total_payments
        self.balance = self.total_amount - self.amount_paid
        
        # Don't update status if cancelled or refunded
        if self.status in ['cancelled', 'refunded']:
            return
        
        # Determine new status
        if abs(self.amount_paid - self.total_amount) <= tolerance:
            self.status = 'paid'
        elif self.amount_paid > 0:
            self.status = 'partial'
        elif timezone.now().date() > self.due_date:
            self.status = 'overdue'
        else:
            self.status = 'issued'
    
    def get_payment_progress(self):
        """Get payment progress percentage"""
        if self.total_amount > 0:
            return (self.amount_paid / self.total_amount) * 100
        return 0
    
    def get_remaining_days(self):
        """Get remaining days until due date"""
        today = timezone.now().date()
        remaining = (self.due_date - today).days
        
        if remaining < 0:
            return f"{abs(remaining)} days overdue"
        elif remaining == 0:
            return "Due today"
        else:
            return f"{remaining} days remaining"
    
    @property
    def is_overdue(self):
        """Check if bill is overdue"""
        return self.status == 'overdue' or (self.due_date < timezone.now().date() and self.status != 'paid')
    
    def can_accept_payment(self):
        """Check if bill can accept additional payments"""
        return self.balance > 0 and self.status != 'cancelled'


class BillItem(models.Model):
    """Individual fee items on a bill"""
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='items')
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Bill Item'
        verbose_name_plural = 'Bill Items'
    
    def __str__(self):
        return f"{self.fee_category.name} - GH₵{self.amount}"


class BillPayment(models.Model):
    PAYMENT_MODES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('cheque', 'Cheque'),
        ('other', 'Other'),
    ]
    
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='bill_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default='cash')
    payment_date = models.DateField(default=timezone.now)
    reference_number = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date']
        verbose_name = 'Bill Payment'
        verbose_name_plural = 'Bill Payments'
        indexes = [
            models.Index(fields=['bill', 'payment_date']),
        ]

    def __str__(self):
        return f"Payment of GH₵{self.amount:.2f} for Bill #{self.bill.bill_number}"

    def save(self, *args, **kwargs):
        # Update the bill's paid amount when a payment is saved
        super().save(*args, **kwargs)
        self.bill.update_status()


class Fee(models.Model):
    PAYMENT_STATUS_CHOICES = FEE_STATUS_CHOICES
    PAYMENT_MODE_CHOICES = PAYMENT_METHOD_CHOICES

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='fees')
    category = models.ForeignKey(FeeCategory, on_delete=models.PROTECT, related_name='fees')
    academic_year = models.CharField(max_length=9)
    term = models.PositiveSmallIntegerField(choices=TERM_CHOICES)
    
    amount_payable = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])
    
    payment_status = models.CharField(
        max_length=20, 
        choices=FEE_STATUS_CHOICES, 
        default='unpaid'
    )
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_METHOD_CHOICES, blank=True, null=True)
    payment_date = models.DateField(blank=True, null=True)
    due_date = models.DateField()
    
    bill = models.ForeignKey(Bill, on_delete=models.SET_NULL, null=True, blank=True, related_name='fees')
    
    receipt_number = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    
    recorded_by = models.ForeignKey(User, on_delete=models.PROTECT, related_name='recorded_fees')
    date_recorded = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_recorded']
        verbose_name_plural = 'Fees'
        verbose_name = 'Fee'
        indexes = [
            models.Index(fields=['student']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['due_date']),
        ]

    def __str__(self):
        return f"{self.student} - {self.category} ({self.academic_year} Term {self.term})"

    def update_payment_status(self):
        """Update payment status with proper overpayment handling"""
        tolerance = PAYMENT_TOLERANCE
        grace_period = PAYMENT_GRACE_PERIOD
        today = timezone.now().date()
        effective_due_date = self.due_date + timedelta(days=grace_period)
        
        # Don't update if status is cancelled or refunded
        if self.payment_status in ['cancelled', 'refunded']:
            return
        
        # Calculate the actual difference
        difference = self.amount_payable - self.amount_paid
        
        # Handle full payment with tolerance
        if abs(difference) <= tolerance:
            self.payment_status = 'paid'
            if not self.payment_date:
                self.payment_date = today
        elif self.amount_paid > Decimal('0.00'):
            self.payment_status = 'partial'
        elif today > effective_due_date:
            self.payment_status = 'overdue'
        else:
            self.payment_status = 'unpaid'

    @property
    def overpayment_amount(self):
        """Calculate overpayment amount"""
        if self.amount_paid > self.amount_payable:
            return self.amount_paid - self.amount_payable
        return Decimal('0.00')

    @property
    def has_overpayment(self):
        """Check if there's an overpayment"""
        return self.amount_paid > self.amount_payable

    def clean(self):
        """Validate the fee data with overpayment handling"""
        # Allow overpayment but track it
        if self.payment_status == 'paid' and self.amount_paid < self.amount_payable:
            raise ValidationError({
                'payment_status': 'Cannot mark as paid when amount paid is less than payable'
            })
        
        if not self.pk and self.due_date < timezone.now().date():
            raise ValidationError({
                'due_date': 'Due date cannot be in the past for new fees'
            })

    def save(self, *args, **kwargs):
        """Auto-calculate balance and update payment status before saving"""
        # Calculate balance (can be negative for overpayment)
        self.balance = self.amount_payable - self.amount_paid
        
        self.update_payment_status()
        
        if self.payment_status == 'paid' and not self.payment_date:
            self.payment_date = timezone.now().date()
        elif self.payment_status != 'paid' and self.payment_date:
            self.payment_date = None
            
        super().save(*args, **kwargs)

    def get_payment_status_html(self):
        """Get HTML badge for payment status with overpayment indicator"""
        status_display = self.get_payment_status_display()
        if self.has_overpayment:
            status_display += " (Credit)"
            
        color_map = {
            'paid': 'success',
            'unpaid': 'danger',
            'partial': 'warning',
            'overdue': 'dark'
        }
        color = color_map.get(self.payment_status, 'primary')
        return mark_safe(f'<span class="badge bg-{color}">{status_display}</span>')
    
    def can_accept_payment(self):
        """Check if this fee can accept additional payments"""
        return self.balance > 0 and self.payment_status != 'paid'
    
    def get_remaining_days(self):
        """Get remaining days until due date"""
        if not self.due_date:
            return None
        
        today = timezone.now().date()
        remaining = (self.due_date - today).days
        
        if remaining < 0:
            return f"{abs(remaining)} days overdue"
        elif remaining == 0:
            return "Due today"
        else:
            return f"{remaining} days remaining"


class FeePayment(models.Model):
    PAYMENT_MODE_CHOICES = [
        ('cash', 'Cash'),
        ('check', 'Check'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('other', 'Other'),
    ]
    
    fee = models.ForeignKey(Fee, on_delete=models.CASCADE, related_name='payments')
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='fee_payments', null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_date = models.DateTimeField(default=timezone.now)
    payment_mode = models.CharField(max_length=15, choices=PAYMENT_MODE_CHOICES)
    receipt_number = models.CharField(max_length=20, unique=True, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='recorded_payments')
    notes = models.TextField(blank=True)
    bank_reference = models.CharField(max_length=50, blank=True)
    is_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-payment_date']
        verbose_name = 'Fee Payment'
        verbose_name_plural = 'Fee Payments'
    
    def __str__(self):
        return f"Payment of {self.amount} for {self.fee}"
    
    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
        
        if self.bill:
            self.bill.update_status()
            
        super().save(*args, **kwargs)
    
    @classmethod
    def generate_receipt_number(cls):
        from django.utils.crypto import get_random_string
        while True:
            receipt_number = f"RCPT-{get_random_string(10, '0123456789')}"
            if not cls.objects.filter(receipt_number=receipt_number).exists():
                return receipt_number


class StudentCredit(models.Model):
    """Track student credit balances from overpayments"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='credits')
    source_fee = models.ForeignKey(Fee, on_delete=models.CASCADE, null=True, blank=True)
    credit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=200, default='Overpayment')
    created_date = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    used_date = models.DateTimeField(null=True, blank=True)
    used_for_fee = models.ForeignKey(Fee, on_delete=models.SET_NULL, null=True, blank=True, related_name='applied_credits')
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Student Credit'
        verbose_name_plural = 'Student Credits'
        ordering = ['-created_date']
    
    def __str__(self):
        return f"{self.student} - GH₵{self.credit_amount} Credit"


class FeeDiscount(models.Model):
    DISCOUNT_TYPES = [
        ('PERCENT', 'Percentage'),
        ('FIXED', 'Fixed Amount'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='discounts')
    category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES)
    amount = models.DecimalField(max_digits=5, decimal_places=2)
    reason = models.TextField()
    approved_by = models.ForeignKey(User, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Fee Discount'
        verbose_name_plural = 'Fee Discounts'
    
    def apply_discount(self, fee_amount):
        if self.discount_type == 'PERCENT':
            return fee_amount * (self.amount / 100)
        return min(fee_amount, self.amount)


class FeeInstallment(models.Model):
    fee = models.ForeignKey(Fee, on_delete=models.CASCADE, related_name='installments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    is_paid = models.BooleanField(default=False)
    payment_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['due_date']
        verbose_name = 'Fee Installment'
        verbose_name_plural = 'Fee Installments'
        
    def __str__(self):
        return f"Installment of {self.amount} due {self.due_date}"