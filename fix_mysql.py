import re

with open('school_mgt_system/settings.py', 'r') as f:
    content = f.read()

# Remove or modify the init_command that's causing the privilege issue
content = re.sub(
    r"'init_command': \"SET sql_mode='STRICT_TRANS_TABLES', innodb_strict_mode=1\",",
    "'init_command': \"SET sql_mode='STRICT_TRANS_TABLES'\",",
    content
)

with open('school_mgt_system/settings.py', 'w') as f:
    f.write(content)

print("✅ Fixed MySQL settings")
