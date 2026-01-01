import sys

with open('core/views/fee_views.py', 'r') as file:
    lines = file.readlines()

# Find get_context_data method
for i, line in enumerate(lines):
    if 'def get_context_data(self' in line and '"""Get the fee object' in lines[i+1]:
        # Add debug after the try block starts
        for j in range(i, len(lines)):
            if 'try:' in lines[j] and j > i:
                # Insert debug after try:
                indent = ' ' * (len(lines[j]) - len(lines[j].lstrip()))
                debug_line = f'{indent}    print("DEBUG: Looking for fee_id =", fee_id)\n'
                lines.insert(j + 1, debug_line)
                
                # Also add debug in the except block
                for k in range(j, len(lines)):
                    if 'except Fee.DoesNotExist:' in lines[k]:
                        except_indent = ' ' * (len(lines[k]) - len(lines[k].lstrip()))
                        except_debug = f'{except_indent}    print("DEBUG: Fee.DoesNotExist exception caught for fee_id =", fee_id)\n'
                        lines.insert(k + 1, except_debug)
                        break
                break
        break

with open('core/views/fee_views.py', 'w') as file:
    file.writelines(lines)

print("✓ Added debug logging to get_context_data")
