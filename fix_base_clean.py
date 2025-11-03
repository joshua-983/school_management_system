# Read the entire file
with open('templates/base.html', 'r') as f:
    content = f.read()

# Find the messed up section and replace it with clean code
import re

# Pattern to find the duplicated section
pattern = r'<!-- Report Cards - Show to students, parents, teachers and admin -->\s+{% if user\.student %}\s+{% if user\.student %}.*?{% endif %}'

# Clean replacement
replacement = '''<!-- Report Cards - Show to students, parents, teachers and admin -->
{% if user.student %}
    <a class="nav-link" href="{% url 'report_card' student_id=user.student.pk %}">
        <i class="bi bi-card-checklist"></i>
        <span>Report Card</span>
    </a>
{% elif user.parentguardian %}
    <a class="nav-link" href="{% url 'parent_report_card_list' %}">
        <i class="bi bi-card-checklist"></i>
        <span>Report Cards</span>
    </a>
{% elif user.is_superuser or user.teacher %}
    <a class="nav-link" href="{% url 'report_card_dashboard' %}">
        <i class="bi bi-card-checklist"></i>
        <span>Report Cards</span>
    </a>
{% endif %}'''

# Replace using regex
content = re.sub(pattern, replacement, content, flags=re.DOTALL)

# Write back
with open('templates/base.html', 'w') as f:
    f.write(content)

print("Cleaned up base.html successfully!")
