with open('templates/base.html', 'r') as f:
    content = f.read()

# Replace the specific line with conditional wrapper
old_line = '    <a class="nav-link" href="{% url \'report_card\' student_id=user.student.pk %}">'
new_section = '''{% if user.student %}
    <a class="nav-link" href="{% url 'report_card' student_id=user.student.pk %}">
        <i class="bi bi-card-checklist"></i>
        <span>Report Card</span>
    </a>
{% endif %}'''

content = content.replace(old_line, new_section)

with open('templates/base.html', 'w') as f:
    f.write(content)

print("Base.html fixed properly!")
