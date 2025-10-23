# Read the current parents_views.py
with open('core/views/parents_views.py', 'r') as file:
    content = file.read()

# Find the models import section starting at line 30
lines = content.split('\n')

# Look for the models import block
in_models_import = False
models_import_end = -1
announcement_added = False

for i, line in enumerate(lines):
    if 'from ..models import (' in line:
        in_models_import = True
        continue
    
    if in_models_import and ')' in line:
        models_import_end = i
        break
    
    if in_models_import and 'ParentEvent' in line and not announcement_added:
        # Add Announcement imports after ParentEvent line
        lines.insert(i + 1, '    # Announcement models')
        lines.insert(i + 2, '    Announcement, UserAnnouncementView,')
        announcement_added = True
        break

# If we didn't find ParentEvent, add at the end of the import block
if not announcement_added and models_import_end > 0:
    lines.insert(models_import_end, '    # Announcement models')
    lines.insert(models_import_end + 1, '    Announcement, UserAnnouncementView,')
    announcement_added = True

# Write the updated content back
with open('core/views/parents_views.py', 'w') as file:
    file.write('\n'.join(lines))

if announcement_added:
    print("✅ Announcement import added successfully!")
else:
    print("❌ Could not add Announcement import")
