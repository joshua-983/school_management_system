# core/validators/financial.py
from django.core.exceptions import ValidationError
from decimal import Decimal, InvalidOperation
import re
from django.utils import timezone

class FinancialValidator:
    """Validate all financial transactions"""
    
    @staticmethod
    def validate_amount(amount, field_name="Amount", min_value=Decimal('0.00'), max_value=Decimal('1000000.00')):
        """Validate amount is within acceptable range"""
        try:
            amount_decimal = Decimal(str(amount))
            if amount_decimal < min_value:
                raise ValidationError(f"{field_name} cannot be less than {min_value}")
            if amount_decimal > max_value:
                raise ValidationError(f"{field_name} cannot exceed {max_value}")
            return amount_decimal
        except (InvalidOperation, ValueError, TypeError):
            raise ValidationError(f"Invalid {field_name}")
    
    @staticmethod
    def validate_student_id(student_id):
        """Validate student ID format"""
        if not student_id or not isinstance(student_id, str):
            raise ValidationError("Invalid student ID")
        
        # Example: STU2024001 format
        pattern = r'^STU\d{7}$'
        if not re.match(pattern, student_id.upper()):
            raise ValidationError("Student ID must be in format STUYYYYNNN")
    
    @staticmethod
    def validate_academic_year(year):
        """Validate academic year format (2024/2025)"""
        pattern = r'^\d{4}/\d{4}$'
        if not re.match(pattern, year):
            raise ValidationError("Academic year must be in format YYYY/YYYY")
        
        # Ensure years are sequential
        year1, year2 = map(int, year.split('/'))
        if year2 != year1 + 1:
            raise ValidationError("Second year must be one year after first year")
    
    @staticmethod
    def detect_fraud_patterns(transaction_data):
        """
        Basic fraud detection patterns for school payments
        Returns: (is_suspicious, reasons)
        """
        suspicious = False
        reasons = []
        
        # 1. Unusually large amount for school fees
        if transaction_data.get('amount', 0) > Decimal('50000.00'):
            suspicious = True
            reasons.append("Amount exceeds typical school fee threshold")
        
        # 2. Multiple rapid transactions from same student
        # (Would need to check database in real implementation)
        
        # 3. Payment during unusual hours (outside school hours)
        current_hour = timezone.now().hour
        if current_hour < 6 or current_hour > 22:
            suspicious = True
            reasons.append("Payment made outside normal school hours")
        
        # 4. Round amount payments (common in fraud)
        amount = transaction_data.get('amount', 0)
        if isinstance(amount, Decimal):
            if amount % 1000 == 0:
                suspicious = True
                reasons.append("Suspicious round amount payment")
        
        return suspicious, reasons