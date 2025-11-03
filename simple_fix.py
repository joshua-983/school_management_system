with open('templates/base.html', 'r') as f:
    lines = f.readlines()

# Simply comment out line 446
if len(lines) > 445:
    lines[445] = "<!-- TEMPORARY FIX: " + lines[445].rstrip() + " -->\\n"

with open('templates/base.html', 'w') as f:
    f.writelines(lines)

print("Line 446 commented out successfully!")
