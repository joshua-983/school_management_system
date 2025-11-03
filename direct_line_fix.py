with open('templates/base.html', 'r') as f:
    lines = f.readlines()

# Replace line 446 directly
if len(lines) > 445:
    # Replace the problematic line with a conditional version
    lines[445] = '{% if user.student %}\\n'
    # Insert the original line after the conditional
    lines.insert(446, '    <a class="nav-link" href="{% url \\'report_card\\' student_id=user.student.pk %}">\\n')
    # Add the closing conditional after the menu item
    # Find where this menu item ends (look for closing </a> and the next item)
    for i in range(447, min(457, len(lines))):
        if '</a>' in lines[i] and i+1 < len(lines) and '<a class="nav-link"' in lines[i+1]:
            # Insert the rest of the conditions before the next menu item
            lines.insert(i+1, '{% elif user.parentguardian %}\\n')
            lines.insert(i+2, '    <a class="nav-link" href="{% url \\'parent_report_card_list\\' %}">\\n')
            lines.insert(i+3, '        <i class="bi bi-card-checklist"></i>\\n')
            lines.insert(i+4, '        <span>Report Cards</span>\\n')
            lines.insert(i+5, '    </a>\\n')
            lines.insert(i+6, '{% elif user.is_superuser or user.teacher %}\\n')
            lines.insert(i+7, '    <a class="nav-link" href="{% url \\'report_card_dashboard\\' %}">\\n')
            lines.insert(i+8, '        <i class="bi bi-card-checklist"></i>\\n')
            lines.insert(i+9, '        <span>Report Cards</span>\\n')
            lines.insert(i+10, '    </a>\\n')
            lines.insert(i+11, '{% endif %}\\n')
            break

with open('templates/base.html', 'w') as f:
    f.writelines(lines)

print("Direct line fix applied!")
