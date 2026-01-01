# core/services/fee_calculator.py
from decimal import Decimal, ROUND_HALF_UP
from django.utils import timezone
from datetime import timedelta
from core.models import FeeCategory, Student, AcademicTerm
from core.utils.financial import FinancialCalculator

class ProfessionalFeeCalculator:
    """Professional fee calculation service"""
    
    def __init__(self, student, academic_year, term):
        self.student = student
        self.academic_year = academic_year
        self.term = term
        self.calculator = FinancialCalculator()
    
    def calculate_term_fees(self, include_optional=False):
        """
        Calculate total fees for a student for a term
        Returns: {
            'mandatory_fees': [],
            'optional_fees': [],
            'subtotal': Decimal,
            'discounts': Decimal,
            'tax': Decimal,
            'total': Decimal,
            'breakdown': {}
        }
        """
        # Get applicable fee categories
        base_query = FeeCategory.objects.filter(is_active=True)
        
        mandatory_categories = base_query.filter(is_mandatory=True)
        optional_categories = base_query.filter(is_mandatory=False) if include_optional else []
        
        mandatory_fees = []
        optional_fees = []
        subtotal = Decimal('0.00')
        
        # Process mandatory fees
        for category in mandatory_categories:
            if category.is_applicable_to_class(self.student.class_level):
                amount = self.calculator.safe_decimal(category.default_amount)
                fee_item = {
                    'category': category,
                    'amount': amount,
                    'description': f"{category.get_name_display()} - Term {self.term}"
                }
                mandatory_fees.append(fee_item)
                subtotal += amount
        
        # Process optional fees
        for category in optional_categories:
            if category.is_applicable_to_class(self.student.class_level):
                amount = self.calculator.safe_decimal(category.default_amount)
                fee_item = {
                    'category': category,
                    'amount': amount,
                    'description': f"{category.get_name_display()} - Term {self.term} (Optional)"
                }
                optional_fees.append(fee_item)
        
        # Apply discounts (from StudentCredit model)
        discounts = self.calculate_discounts(subtotal)
        
        # Apply taxes (if applicable)
        tax_calculation = self.calculator.calculate_amount_with_tax(
            subtotal - discounts,
            tax_rate=0  # Adjust based on your tax requirements
        )
        
        total = tax_calculation['total']
        
        return {
            'mandatory_fees': mandatory_fees,
            'optional_fees': optional_fees,
            'subtotal': subtotal,
            'discounts': discounts,
            'tax': tax_calculation['tax_amount'],
            'total': total,
            'breakdown': {
                'mandatory_total': sum(f['amount'] for f in mandatory_fees),
                'optional_total': sum(f['amount'] for f in optional_fees),
                'tax_rate': tax_calculation['tax_rate'],
                'net_amount': subtotal - discounts
            }
        }
    
    def calculate_discounts(self, subtotal):
        """Calculate applicable discounts for student"""
        discounts = Decimal('0.00')
        
        # 1. Sibling discount (10% if has siblings in school)
        if self.has_siblings_in_school():
            discounts += subtotal * Decimal('0.10')
        
        # 2. Early payment discount (5% if paid before due date)
        # This would be calculated at payment time
        
        # 3. Apply any student credits
        credits = self.student.credits.filter(is_used=False).aggregate(
            total=Sum('credit_amount')
        )['total'] or Decimal('0.00')
        
        discounts += min(credits, subtotal)
        
        return min(discounts, subtotal)  # Can't discount more than total
    
    def has_siblings_in_school(self):
        """Check if student has siblings also enrolled"""
        # Implementation depends on your Student model
        # This is a placeholder
        return False
    
    def generate_payment_plan(self, total_amount, num_installments=3):
        """Generate installment payment plan"""
        if num_installments < 1 or num_installments > 6:
            raise ValueError("Number of installments must be between 1 and 6")
        
        installment_amount = (total_amount / num_installments).quantize(Decimal('0.01'))
        
        # Adjust last installment for rounding
        total_so_far = installment_amount * (num_installments - 1)
        last_installment = total_amount - total_so_far
        
        plan = []
        current_date = timezone.now().date()
        
        for i in range(num_installments):
            due_date = current_date + timedelta(days=30 * (i + 1))
            amount = last_installment if i == num_installments - 1 else installment_amount
            
            plan.append({
                'installment_number': i + 1,
                'amount': amount,
                'due_date': due_date,
                'percentage': (amount / total_amount * 100).quantize(Decimal('0.01'))
            })
        
        return plan