import sys

# Read the file
with open('core/views/fee_views.py', 'r') as file:
    lines = file.readlines()

# Find the class and where to insert
insert_line = None
for i, line in enumerate(lines):
    if 'class SecureFeePaymentCreateView' in line:
        # Find the test_func method end
        for j in range(i, len(lines)):
            if 'def post(self, request' in lines[j]:
                insert_line = j
                break
        break

if insert_line:
    # Methods to insert
    methods_to_insert = '''
    def get_context_data(self, **kwargs):
        """Get the fee object and add it to context"""
        context = super().get_context_data(**kwargs)
        fee_id = self.kwargs.get('fee_id')
        
        try:
            fee = Fee.objects.get(id=fee_id)
            context['fee'] = fee
            context['student'] = fee.student
            context['remaining_balance'] = fee.balance
        except Fee.DoesNotExist:
            # Fee not found - this is what's causing your error
            context['error'] = "Fee Record Not Found"
            context['fee'] = None
        
        return context
    
    def get_initial(self):
        """Set initial form values"""
        initial = super().get_initial()
        fee_id = self.kwargs.get('fee_id')
        
        try:
            fee = Fee.objects.get(id=fee_id)
            initial['fee'] = fee
            # Set default amount to the remaining balance
            if fee.balance > 0:
                initial['amount'] = fee.balance
            else:
                initial['amount'] = fee.amount_payable
        except Fee.DoesNotExist:
            pass
        
        return initial
    
    def form_valid(self, form):
        """Set the fee before saving"""
        fee_id = self.kwargs.get('fee_id')
        
        try:
            fee = Fee.objects.get(id=fee_id)
            form.instance.fee = fee
        except Fee.DoesNotExist:
            form.add_error(None, "Fee record not found")
            return self.form_invalid(form)
        
        # ADD AMOUNT VALIDATION
        amount = form.cleaned_data.get('amount')
        
        # Validate amount doesn't exceed system limits
        from core.utils.financial import FinancialCalculator
        calculator = FinancialCalculator()
        
        max_amount = Decimal('100000.00')  # System limit
        validated_amount = calculator.safe_decimal(amount)
        
        if validated_amount > max_amount:
            form.add_error('amount', f'Amount cannot exceed GH₵{max_amount:,.2f}')
            return self.form_invalid(form)
        
        # Check for suspicious patterns
        if validated_amount % 1000 == 0 and validated_amount > Decimal('5000.00'):
            # Round large amounts might be suspicious
            logger.warning(f"Large round payment detected: {validated_amount}")
        
        return super().form_valid(form)
    
    def get_success_url(self):
        """Redirect to fee detail page after payment"""
        if hasattr(self.object, 'fee') and self.object.fee:
            return reverse_lazy('fee_detail', kwargs={'pk': self.object.fee.pk})
        return reverse_lazy('fee_list')
'''
    
    # Insert the methods
    lines.insert(insert_line, methods_to_insert)
    
    # Write back to file
    with open('core/views/fee_views.py', 'w') as file:
        file.writelines(lines)
    
    print(f"✓ Added missing methods at line {insert_line}")
else:
    print("✗ Could not find insertion point")
