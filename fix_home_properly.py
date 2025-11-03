with open('templates/core/home.html', 'r') as f:
    content = f.read()

# Fix line 36 - student report card
old_student_line = '<a href="{% url \'report_card\' student_id=user.student.pk %}"'
new_student_section = '''{% if user.student %}
<a href="{% url 'report_card' student_id=user.student.pk %}" 
class="btn btn-outline-primary btn-lg px-4">
<i class="bi bi-card-checklist me-2"></i>View Report Card
</a>
{% endif %}'''

content = content.replace(old_student_line, new_student_section)

# Fix line 101 - parent report card
old_parent_line = '<a href="{% url \'parent_report_card_detail\' student_id=child.pk %}" class="btn btn-sm btn-outline-success">'
new_parent_section = '''{% if child.pk %}
<a href="{% url 'parent_report_card_detail' student_id=child.pk %}" class="btn btn-sm btn-outline-success">
    <i class="bi bi-card-checklist"></i> Report
</a>
{% else %}
<span class="btn btn-sm btn-outline-secondary disabled">
    <i class="bi bi-card-checklist"></i> No Report
</span>
{% endif %}'''

content = content.replace(old_parent_line, new_parent_section)

with open('templates/core/home.html', 'w') as f:
    f.write(content)

print("Home.html fixed properly!")
