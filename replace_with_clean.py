import sys

with open('core/views/fee_views.py', 'r') as file:
    lines = file.readlines()

# Find the original SecureFeePaymentCreateView
for i, line in enumerate(lines):
    if 'class SecureFeePaymentCreateView' in line:
        start_line = i
        # Find where this class ends (next class or end of file)
        for j in range(i + 1, len(lines)):
            if lines[j].strip() and not lines[j].startswith(' ') and not lines[j].startswith('\t'):
                if 'class ' in lines[j] and ':' in lines[j]:
                    end_line = j
                    break
        else:
            end_line = len(lines)
        
        # Create clean version
        clean_view = '''class SecureFeePaymentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = FeePayment
    form_class = PaymentForm
    template_name = 'core/finance/fees/fee_payment_form.html'

    def test_func(self):
        # ADD ADDITIONAL CHECKS
        if not is_admin(self.request.user) and not is_teacher(self.request.user):
            return False

        # Check if user has financial permissions
        if hasattr(self.request.user, 'profile'):
            return self.request.user.profile.has_financial_access
        return True

    def get_context_data(self, **kwargs):
        """Get the fee object and add it to context"""
        context = super().get_context_data(**kwargs)
        fee_id = self.kwargs.get('fee_id')

        print(f"DEBUG: get_context_data - fee_id = {fee_id}")

        try:
            fee = Fee.objects.get(id=fee_id)
            print(f"DEBUG: Found fee {fee.id}")
            context['fee'] = fee
            context['student'] = fee.student
            context['remaining_balance'] = fee.balance
        except Fee.DoesNotExist:
            print(f"DEBUG: Fee {fee_id} not found")
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

        return super().form_valid(form)

    def get_success_url(self):
        """Redirect to fee detail page after payment"""
        if hasattr(self.object, 'fee') and self.object.fee:
            return reverse_lazy('fee_detail', kwargs={'pk': self.object.fee.pk})
        return reverse_lazy('fee_list')'''
        
        # Replace the class
        lines[start_line:end_line] = [line + '\n' for line in clean_view.split('\n')]
        break

with open('core/views/fee_views.py', 'w') as file:
    file.writelines(lines)

print("✓ Replaced with clean SecureFeePaymentCreateView")
