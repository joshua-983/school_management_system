import re

# Read the file
with open('core/views/base_views.py', 'r') as f:
    lines = f.readlines()

# We know context is at line 216 (0-indexed: 215)
context_line = 215  # Python uses 0-index

# Check if 'user' is already in the next few lines
has_user = False
for i in range(context_line, min(context_line + 30, len(lines))):
    if "'user'" in lines[i] or '"user"' in lines[i]:
        has_user = True
        print(f"Found existing 'user' at line {i+1}: {lines[i].strip()}")
        break
    if '}' in lines[i] and lines[i].strip().startswith('}'):
        break

if has_user:
    print("✅ 'user' is already in context - no fix needed")
else:
    # Get the indentation from the context line
    indent = len(lines[context_line]) - len(lines[context_line].lstrip())
    
    # Create the user line with proper indentation (4 spaces more than context line)
    user_line = ' ' * (indent + 4) + "'user': request.user,\n"
    
    # Insert after the context line
    lines.insert(context_line + 1, user_line)
    
    # Write back
    with open('core/views/base_views.py', 'w') as f:
        f.writelines(lines)
    
    print(f"✅ Added 'user': request.user at line {context_line + 2}")
    
    # Show the fix
    print("\n=== APPLIED FIX ===")
    for i in range(context_line - 2, min(context_line + 8, len(lines))):
        line_num = i + 1
        if i == context_line:
            print(f"{line_num:3d}: {lines[i].rstrip()}  <-- context line")
        elif i == context_line + 1:
            print(f"{line_num:3d}: {lines[i].rstrip()}  <-- ADDED THIS LINE")
        else:
            print(f"{line_num:3d}: {lines[i].rstrip()}")
