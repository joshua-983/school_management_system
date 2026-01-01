# core/utils/financial.py
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
import logging

logger = logging.getLogger(__name__)

class FinancialCalculator:
    """Secure financial calculations for school system"""
    
    # Ghanaian currency settings
    CURRENCY = 'GHS'
    DECIMAL_PLACES = 2
    ROUNDING = ROUND_HALF_UP
    
    @staticmethod
    def safe_decimal(value, default=Decimal('0.00')):
        """
        Safely convert any value to Decimal for financial operations
        Returns default value on any error
        """
        if value is None:
            return default
        
        try:
            if isinstance(value, Decimal):
                return value.quantize(Decimal('0.01'))
            if isinstance(value, (int, float)):
                return Decimal(str(value)).quantize(Decimal('0.01'))
            if isinstance(value, str):
                # Remove any currency symbols and whitespace
                cleaned = value.strip().replace('GH₵', '').replace('GHS', '').replace('$', '').replace(',', '')
                return Decimal(cleaned).quantize(Decimal('0.01'))
        except (InvalidOperation, ValueError, TypeError) as e:
            logger.warning(f"Failed to convert value to Decimal: {value}, error: {e}")
            return default
        
        return default
    
    @staticmethod
    def calculate_amount_with_tax(amount, tax_rate=0):
        """Calculate amount with tax (VAT/NHIL)"""
        amount_decimal = FinancialCalculator.safe_decimal(amount)
        tax_rate_decimal = FinancialCalculator.safe_decimal(tax_rate)
        
        tax_amount = (amount_decimal * tax_rate_decimal / 100).quantize(Decimal('0.01'))
        total = amount_decimal + tax_amount
        
        return {
            'subtotal': amount_decimal,
            'tax_rate': tax_rate_decimal,
            'tax_amount': tax_amount,
            'total': total
        }
    
    @staticmethod
    def calculate_discount(amount, discount_percent=0, discount_fixed=0):
        """Calculate discounted amount"""
        amount_decimal = FinancialCalculator.safe_decimal(amount)
        discount_percent_decimal = FinancialCalculator.safe_decimal(discount_percent)
        discount_fixed_decimal = FinancialCalculator.safe_decimal(discount_fixed)
        
        # Apply percentage discount first
        if discount_percent_decimal > 0:
            discount_amount = (amount_decimal * discount_percent_decimal / 100).quantize(Decimal('0.01'))
            amount_after_percent = max(Decimal('0.00'), amount_decimal - discount_amount)
        else:
            amount_after_percent = amount_decimal
        
        # Apply fixed discount
        discounted_amount = max(Decimal('0.00'), amount_after_percent - discount_fixed_decimal)
        
        return {
            'original': amount_decimal,
            'discount_percent': discount_percent_decimal,
            'discount_fixed': discount_fixed_decimal,
            'discounted_amount': discounted_amount,
            'total_discount': amount_decimal - discounted_amount
        }
    
    @staticmethod
    def validate_payment_amount(amount_payable, amount_paid, tolerance=Decimal('0.01')):
        """
        Validate payment amount with tolerance for rounding
        Returns: (is_valid, message, overpayment_amount)
        """
        payable = FinancialCalculator.safe_decimal(amount_payable)
        paid = FinancialCalculator.safe_decimal(amount_paid)
        
        if paid < Decimal('0.00'):
            return False, 'Payment amount cannot be negative', Decimal('0.00')
        
        if payable <= Decimal('0.00'):
            return False, 'Payable amount must be positive', Decimal('0.00')
        
        difference = payable - paid
        abs_difference = abs(difference)
        
        # Check if payment is within tolerance
        if abs_difference <= tolerance:
            return True, 'Payment complete (within tolerance)', Decimal('0.00')
        
        # Check for overpayment
        if paid > payable:
            overpayment = paid - payable
            return True, f'Payment complete with overpayment of GH₵{overpayment:.2f}', overpayment
        
        # Underpayment
        return False, f'Payment incomplete. Balance: GH₵{difference:.2f}', Decimal('0.00')