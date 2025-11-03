with open('templates/base.html', 'r') as f:
    lines = f.readlines()

# Find and replace the specific lines
for i in range(len(lines)):
    if '<!-- Report Card menu temporarily disabled for admin users -->' in lines[i]:
        # Replace the comment with the proper menu item
        lines[i] = '    <a class="nav-link" href="{% url \\'report_card\\' student_id=user.student.pk %}">\\n'
        # Make sure the indentation matches
        lines[i+1] = '        <i class="bi bi-card-checklist"></i>\\n'
        lines[i+2] = '        <span>Report Card</span>\\n'
        lines[i+3] = '    </a>\\n'
        break

with open('templates/base.html', 'w') as f:
    f.writelines(lines)

print("Report card menu properly restored!")
