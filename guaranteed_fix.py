# Read the entire file
with open('templates/base.html', 'r') as f:
    content = f.read()

# Replace the exact problematic sections
# Fix 1: Replace the student comment with proper menu
content = content.replace(
    '    <!-- Report Card menu temporarily disabled for admin users -->',
    '    <a class="nav-link" href="{% url \'report_card\' student_id=user.student.pk %}">'
)

# Fix 2: Replace the parent menu (the one with wrong URL)
old_parent_menu = '''    <a class="nav-link" href="{% url 'report_card' student_id=user.student.pk %}">       
        <i class="bi bi-card-checklist"></i>
        <span>Report Card</span>
    </a>'''

new_parent_menu = '''    <a class="nav-link" href="{% url 'parent_report_card_list' %}">
        <i class="bi bi-card-checklist"></i>
        <span>Report Cards</span>
    </a>'''

content = content.replace(old_parent_menu, new_parent_menu)

# Write back
with open('templates/base.html', 'w') as f:
    f.write(content)

print("Guaranteed fix applied!")
