# core/utils/financial_utils.py
"""
Utility functions for financial operations
"""
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from .constants.financial import (
    BILL_STATUS_CHOICES, 
    FEE_STATUS_CHOICES, 
    PAYMENT_TOLERANCE,
    PAYMENT_GRACE_PERIOD
)


def calculate_payment_status(amount_payable, amount_paid, due_date, current_status=None):
    """
    Calculate payment status consistently for both fees and bills
    
    Args:
        amount_payable: Total amount due
        amount_paid: Amount already paid
        due_date: Due date for payment
        current_status: Current status (optional)
    
    Returns:
        str: Calculated status
    """
    # Don't change if already cancelled or refunded
    if current_status in ['cancelled', 'refunded']:
        return current_status
    
    # Calculate difference
    amount_payable = Decimal(str(amount_payable)) if amount_payable else Decimal('0.00')
    amount_paid = Decimal(str(amount_paid)) if amount_paid else Decimal('0.00')
    difference = amount_payable - amount_paid
    
    today = timezone.now().date()
    effective_due_date = due_date + timedelta(days=PAYMENT_GRACE_PERIOD)
    
    # Check if fully paid (within tolerance)
    if abs(difference) <= PAYMENT_TOLERANCE:
        return 'paid'
    
    # Check if partially paid
    elif amount_paid > Decimal('0.00'):
        return 'partial'
    
    # Check if overdue
    elif today > effective_due_date:
        return 'overdue'
    
    # Otherwise unpaid/issued
    else:
        return 'unpaid' if current_status == 'unpaid' else 'issued'


def get_status_display(status, model_type='fee'):
    """
    Get display name for status consistently
    
    Args:
        status: Status code
        model_type: 'fee' or 'bill'
    
    Returns:
        str: Display name
    """
    if model_type == 'fee':
        from .constants.financial import FEE_STATUS_DISPLAY
        return FEE_STATUS_DISPLAY.get(status, status)
    else:  # bill
        from .constants.financial import BILL_STATUS_DISPLAY
        return BILL_STATUS_DISPLAY.get(status, status)


def get_status_color(status):
    """
    Get Bootstrap color class for status
    
    Args:
        status: Status code
    
    Returns:
        str: Bootstrap color class
    """
    color_map = {
        'draft': 'secondary',
        'issued': 'info',
        'unpaid': 'warning',
        'partial': 'warning',
        'paid': 'success',
        'overdue': 'danger',
        'cancelled': 'dark',
        'refunded': 'info',
    }
    return color_map.get(status, 'secondary')