import re

# Read the current parents_views.py
with open('core/views/parents_views.py', 'r') as file:
    content = file.read()

# Find the models import line and add Announcement
import_pattern = r'from \.\.models import \('

if import_pattern in content:
    # Add Announcement to the imports
    content = content.replace(
        'from ..models import (',
        'from ..models import (\\n    # Announcement models\\n    Announcement, UserAnnouncementView,'
    )
    print("✅ Added Announcement import")
else:
    # Check for alternative import format
    alt_pattern = r'from \.\.models import'
    if alt_pattern in content:
        # Add Announcement to existing imports
        content = content.replace(
            'from ..models import',
            'from ..models import Announcement, UserAnnouncementView,'
        )
        print("✅ Added Announcement import (alternative format)")
    else:
        print("❌ Could not find models import to update")

# Write the updated content back
with open('core/views/parents_views.py', 'w') as file:
    file.write(content)
