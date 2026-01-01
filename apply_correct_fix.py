import re

with open('templates/core/admin/admin_dashboard.html', 'r') as f:
    content = f.read()

# Fix line 454: Use safe access pattern
# From: {{ log.user.get_full_name|default:log.user.username|slice:":1"|upper }}
# To: {{ log.user.get_full_name|default:log.user.username|default:""|slice:":1"|upper }}
# But actually better: {% if log.user %}...{% else %}...{% endif %}

# Actually, let's use a different approach - add a default for when user is None
# Replace the entire problematic section with a safer version

# First, let's make a simple fix by adding default:"" before slice
pattern1 = r'\{\{\s*log\.user\.get_full_name\|\s*default:log\.user\.username\s*(\|.*?)\}\}'
def replace1(match):
    filters = match.group(1)
    return f'{{{{ log.user.get_full_name|default:log.user.username|default:""{filters }}}}'

content = re.sub(pattern1, replace1, content, flags=re.DOTALL)

# Also fix similar patterns
pattern2 = r'\{\{\s*log\.user\.email\|\s*default:""'
# This one is already safe with |default:""

# Write back
with open('templates/core/admin/admin_dashboard.html', 'w') as f:
    f.write(content)

print("✅ Applied fix for default filter issue")
