with open('templates/base.html', 'r') as f:
    lines = f.readlines()

# Fix line 448 - replace comment with proper menu
lines[447] = '    <a class="nav-link" href="{% url "\''report_card"\'" student_id=user.student.pk %}">\n'

# Fix line 451 - correct the parent URL  
lines[450] = '    <a class="nav-link" href="{% url "\''parent_report_card_list"\'" %}">\n'
lines[453] = '        <span>Report Cards</span>\n'

with open('templates/base.html', 'w') as f:
    f.writelines(lines)

print("Line-by-line fix completed!")
