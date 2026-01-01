import sys

with open('core/views/fee_views.py', 'r') as file:
    lines = file.readlines()

# Find get_context_data method in SecureFeePaymentCreateView
for i in range(len(lines)):
    if 'class SecureFeePaymentCreateView' in lines[i]:
        # Find get_context_data within this class
        for j in range(i, len(lines)):
            if 'def get_context_data(self' in lines[j]:
                # Replace the entire try block with better debugging
                for k in range(j, len(lines)):
                    if 'try:' in lines[k]:
                        # Find the end of the try block (where except starts)
                        for l in range(k, len(lines)):
                            if 'except Fee.DoesNotExist:' in lines[l]:
                                # Replace from try: to except: with better debug
                                new_code = '''        # ===== DEBUG =====
        print("\\n" + "="*60)
        print("DEBUG get_context_data in SecureFeePaymentCreateView")
        print(f"  View: {self.__class__.__name__}")
        print(f"  URL kwargs: {self.kwargs}")
        print(f"  fee_id parameter: {fee_id}")
        print(f"  User: {self.request.user.username}")
        print("="*60 + "\\n")
        
        try:
            print(f"DEBUG: Attempting to get Fee with id={fee_id}")
            fee = Fee.objects.get(id=fee_id)
            print(f"DEBUG: SUCCESS - Found fee: {fee.id} for {fee.student}")
            print(f"DEBUG: Fee balance: ${fee.balance}")
            context['fee'] = fee
            context['student'] = fee.student
            context['remaining_balance'] = fee.balance
        except Fee.DoesNotExist as e:
            print(f"DEBUG: FAILED - Fee.DoesNotExist: {e}")
            print(f"DEBUG: Available fee IDs: {list(Fee.objects.all().values_list('id', flat=True)[:10])}")
            # Fee not found - this is what's causing your error
            context['error'] = "Fee Record Not Found"
            context['fee'] = None
        except Exception as e:
            print(f"DEBUG: UNEXPECTED ERROR: {type(e).__name__}: {e}")
            import traceback
            traceback.print_exc()
            context['error'] = f"Error: {str(e)}"
            context['fee'] = None'''
                                
                                # Replace lines k through l-1
                                indent = ' ' * (len(lines[k]) - len(lines[k].lstrip()))
                                lines[k:l] = [indent + line + '\\n' for line in new_code.split('\\n')]
                                break
                        break
                break
        break

with open('core/views/fee_views.py', 'w') as file:
    file.writelines(lines)

print("✓ Added comprehensive debug to get_context_data")
