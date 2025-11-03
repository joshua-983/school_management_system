# Read the entire file
with open('templates/base.html', 'r') as f:
    content = f.read()

# Replace the entire report cards section with correct code
old_section = '''<!-- Report Cards - Show to students, parents, teachers and admin -->
{% if user.student %}
    <a class="nav-link" href="{% url 'report_card' student_id=user.student.pk %}">
{% elif user.parentguardian %}
    <a class="nav-link" href="{% url 'report_card' student_id=user.student.pk %}">
        <i class="bi bi-card-checklist"></i>
        <span>Report Card</span>
    </a>
{% elif user.is_superuser or user.teacher %}
    <a class="nav-link" href="{% url 'report_card_dashboard' %}">
        <i class="bi bi-card-checklist"></i>
        <span>Report Cards</span>
    </a>
{% endif %}'''

new_section = '''<!-- Report Cards - Show to students, parents, teachers and admin -->
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

content = content.replace(old_section, new_section)

# Write back
with open('templates/base.html', 'w') as f:
    f.write(content)

print("Complete final fix applied!")
