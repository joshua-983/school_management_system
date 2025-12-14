# core/constants/financial.py
"""
Financial Constants for the School Management System
Keeps all financial-related constants in one place to avoid circular imports
"""

from django.db import models
from decimal import Decimal

# ========== BILL STATUS ==========
BILL_STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('issued', 'Issued'),
    ('partial', 'Partially Paid'),
    ('paid', 'Paid'),
    ('overdue', 'Overdue'),
    ('cancelled', 'Cancelled'),
    ('refunded', 'Refunded'),
]

BILL_STATUS_DISPLAY = dict(BILL_STATUS_CHOICES)

# ========== FEE STATUS ==========
FEE_STATUS_CHOICES = [
    ('draft', 'Draft'),
    ('issued', 'Issued'),
    ('partial', 'Part Payment'),
    ('paid', 'Paid'),
    ('unpaid', 'Unpaid'),
    ('overdue', 'Overdue'),
    ('cancelled', 'Cancelled'),
    ('refunded', 'Refunded'),
]

FEE_STATUS_DISPLAY = dict(FEE_STATUS_CHOICES)

# ========== PAYMENT METHODS ==========
PAYMENT_METHOD_CHOICES = [
    ('cash', 'Cash'),
    ('mobile_money', 'Mobile Money'),
    ('bank_transfer', 'Bank Transfer'),
    ('cheque', 'Cheque'),
    ('credit_card', 'Credit Card'),
    ('debit_card', 'Debit Card'),
    ('online', 'Online Payment'),
    ('other', 'Other'),
]

PAYMENT_METHOD_DISPLAY = dict(PAYMENT_METHOD_CHOICES)

# ========== FEE CATEGORIES ==========
FEE_CATEGORY_TYPES = [
    ('TUITION', 'Tuition Fees'),
    ('ADMISSION', 'Admission Fees'),
    ('TRANSPORT', 'Transport Fees'),
    ('TECHNOLOGY', 'Technology Fee'),
    ('EXAMINATION', 'Examination Fees'),
    ('UNIFORM', 'Uniform Fees'),
    ('PTA', 'PTA Fees'),
    ('EXTRA_CLASSES', 'Extra Classes Fees'),
    ('LIBRARY', 'Library Fees'),
    ('SPORTS', 'Sports Fees'),
    ('MEDICAL', 'Medical Fees'),
    ('DEVELOPMENT', 'Development Levy'),
    ('OTHER', 'Other Fees'),
]

FEE_FREQUENCY_CHOICES = [
    ('one_time', 'One Time'),
    ('termly', 'Per Term'),
    ('monthly', 'Monthly'),
    ('quarterly', 'Quarterly'),
    ('semester', 'Per Semester'),
    ('annual', 'Annual'),
    ('custom', 'Custom'),
]

# ========== FINANCIAL SETTINGS ==========
DEFAULT_CURRENCY = 'GHS'
DEFAULT_CURRENCY_SYMBOL = 'GH₵'

# Payment tolerance for rounding errors
PAYMENT_TOLERANCE = Decimal('1.00')  # 1 unit tolerance

# Grace period for payments (in days)
PAYMENT_GRACE_PERIOD = 5

# ========== BUDGET CATEGORIES ==========
BUDGET_CATEGORY_CHOICES = [
    ('SALARIES', 'Salaries & Wages'),
    ('UTILITIES', 'Utilities'),
    ('MAINTENANCE', 'Maintenance & Repairs'),
    ('SUPPLIES', 'Teaching Supplies'),
    ('EQUIPMENT', 'Equipment & Furniture'),
    ('TRANSPORT', 'Transportation'),
    ('PROFESSIONAL', 'Professional Development'),
    ('ADMINISTRATION', 'Administrative Costs'),
    ('MARKETING', 'Marketing & Admissions'),
    ('OTHER', 'Other Expenses'),
]

# ========== DISCOUNT TYPES ==========
DISCOUNT_TYPES = [
    ('PERCENT', 'Percentage'),
    ('FIXED', 'Fixed Amount'),
]

# ========== INSTALLMENT STATUS ==========
INSTALLMENT_STATUS_CHOICES = [
    ('pending', 'Pending'),
    ('due', 'Due'),
    ('paid', 'Paid'),
    ('overdue', 'Overdue'),
    ('cancelled', 'Cancelled'),
]

# ========== FINANCIAL VALIDATION RULES ==========
FINANCIAL_VALIDATION_RULES = {
    'max_amount_per_transaction': Decimal('1000000.00'),  # 1 million
    'min_amount_per_transaction': Decimal('0.01'),
    'max_installments': 12,
    'min_days_between_installments': 7,
}