# core/templatetags/status_utils.py
from django import template
from decimal import Decimal

register = template.Library()

# Comprehensive status color mapping for all models
STATUS_COLOR_MAP = {
    # Financial statuses
    'draft': 'secondary',
    'issued': 'info',
    'unpaid': 'danger',
    'partial': 'warning',
    'paid': 'success',
    'overdue': 'dark',
    'cancelled': 'secondary',
    'refunded': 'info',
    
    # Assignment statuses
    'pending': 'secondary',
    'submitted': 'info',
    'late': 'warning',
    'graded': 'success',
    'draft': 'light',
    
    # Attendance statuses
    'present': 'success',
    'absent': 'danger',
    'late': 'warning',
    'excused': 'info',
    'sick': 'primary',
    'other': 'secondary',
    
    # General statuses
    'active': 'success',
    'inactive': 'secondary',
    'completed': 'success',
    'failed': 'danger',
    'processing': 'info',
    'ready': 'info',
    
    # Security/System statuses
    'online': 'success',
    'offline': 'danger',
    'secure': 'success',
    'insecure': 'danger',
    'locked': 'danger',
    'unlocked': 'success',
}

# Status display mapping (handles various models)
@register.filter
def status_display(status_code, model_type=None):
    """Get display name for status with optional model type"""
    if not status_code:
        return ''
    
    status_code = status_code.lower()
    
    # Financial-specific mappings
    if model_type in ['fee', 'bill', 'payment']:
        financial_map = {
            'draft': 'Draft',
            'issued': 'Issued',
            'unpaid': 'Unpaid',
            'partial': 'Part Payment',
            'paid': 'Paid',
            'overdue': 'Overdue',
            'cancelled': 'Cancelled',
            'refunded': 'Refunded',
        }
        return financial_map.get(status_code, status_code.title())
    
    # Assignment-specific mappings
    elif model_type in ['assignment', 'studentassignment']:
        assignment_map = {
            'pending': 'Pending',
            'submitted': 'Submitted',
            'late': 'Late',
            'graded': 'Graded',
            'draft': 'Draft',
        }
        return assignment_map.get(status_code, status_code.title())
    
    # Attendance-specific mappings
    elif model_type in ['attendance', 'studentattendance']:
        attendance_map = {
            'present': 'Present',
            'absent': 'Absent',
            'late': 'Late',
            'excused': 'Excused',
            'sick': 'Sick',
            'other': 'Other',
        }
        return attendance_map.get(status_code, status_code.title())
    
    # Default mapping
    default_map = {
        'active': 'Active',
        'inactive': 'Inactive',
        'completed': 'Completed',
        'failed': 'Failed',
        'processing': 'Processing',
        'ready': 'Ready',
        'online': 'Online',
        'offline': 'Offline',
        'secure': 'Secure',
        'insecure': 'Insecure',
        'locked': 'Locked',
        'unlocked': 'Unlocked',
    }
    
    return default_map.get(status_code, status_code.title())

@register.filter
def status_color(status_code, model_type=None):
    """Get Bootstrap color for status"""
    if not status_code:
        return 'secondary'
    
    status_code = status_code.lower()
    return STATUS_COLOR_MAP.get(status_code, 'secondary')

@register.filter
def status_color_css(status_code, model_type=None):
    """Get CSS class for status"""
    if not status_code:
        return 'status-unknown'
    return f"status-{status_code.lower().replace(' ', '-')}"

@register.filter
def currency_format(amount):
    """Format amount as currency"""
    try:
        if isinstance(amount, Decimal):
            return f"GH₵{amount:,.2f}"
        return f"GH₵{float(amount):,.2f}"
    except (ValueError, TypeError):
        return "GH₵0.00"

@register.filter
def is_overpaid(fee):
    """Check if fee has overpayment"""
    try:
        return fee.amount_paid > fee.amount_payable
    except:
        return False