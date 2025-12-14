# core/templatetags/financial_utils.py
from django import template
from decimal import Decimal

register = template.Library()

# Define constants directly in the template tag (no imports needed)
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

# Status display mapping
STATUS_DISPLAY_MAP = {
    # Financial statuses
    'draft': 'Draft',
    'issued': 'Issued',
    'unpaid': 'Unpaid',
    'partial': 'Part Payment',
    'paid': 'Paid',
    'overdue': 'Overdue',
    'cancelled': 'Cancelled',
    'refunded': 'Refunded',
    
    # Assignment statuses
    'pending': 'Pending',
    'submitted': 'Submitted',
    'late': 'Late',
    'graded': 'Graded',
    
    # Attendance statuses
    'present': 'Present',
    'absent': 'Absent',
    'late': 'Late',
    'excused': 'Excused',
    'sick': 'Sick',
    'other': 'Other',
    
    # General statuses
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

@register.filter
def status_display(status_code, model_type=None):
    """Get display name for status"""
    if not status_code:
        return ''
    
    # Convert to lowercase for consistent lookup
    status_lower = str(status_code).lower()
    
    # Try to get from the map first
    display = STATUS_DISPLAY_MAP.get(status_lower)
    if display:
        return display
    
    # If not found, return capitalized version
    return str(status_code).title()

@register.filter
def status_color(status_code, model_type=None):
    """Get Bootstrap color for status"""
    if not status_code:
        return 'secondary'
    
    status_lower = str(status_code).lower()
    return STATUS_COLOR_MAP.get(status_lower, 'secondary')

@register.filter
def status_color_css(status_code):
    """Get CSS class for status"""
    if not status_code:
        return 'status-unknown'
    return f"status-{str(status_code).lower().replace(' ', '-')}"

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
    except (AttributeError, TypeError):
        return False

# You might also want to add this for bill statuses
@register.filter
def bill_status_display(status_code):
    """Specifically for bill status display"""
    return status_display(status_code, 'bill')

@register.filter
def fee_status_display(status_code):
    """Specifically for fee status display"""
    return status_display(status_code, 'fee')
    