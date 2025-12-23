"""
COMPREHENSIVE VIEWS BRIDGE - BACKWARD COMPATIBILITY

Imports all views from split modules for seamless backward compatibility.
New code should import directly from core.views.* modules.
"""

import warnings
warnings.warn(
    "Importing from core.views is deprecated. Use direct imports from core.views.* modules.",
    DeprecationWarning,
    stacklevel=2
)

# Import ALL view modules for comprehensive backward compatibility
from .views.analytics_views import *
from .views.announcement_views import *
from .views.api import *
from .views.assignment_views import *
from .views.attendance_views import *
from .views.audit_views import *
from .views.base_views import *
from .views.bill_views import *
from .views.budget_views import *
from .views.class_assignments import *
from .views.fee_views import *
from .views.grade_views import *
from .views.network_views import *
from .views.notifications_views import *
from .views.parents_views import *
from .views.report_card_views import *
from .views.SecurityEvent_views import *
from .views.security_views import *
from .views.student_views import *
from .views.subjects_views import *
from .views.teacher_views import *
from .views.timetable_views import *

# Also import from backup/simple versions if needed (optional)
try:
    from .views.attendance_views_backup import *
    from .views.audit_enhancements import *
    from .views.base_views_simple import *
    from .views.misc import *
except ImportError:
    pass  # These are optional

# Import the CSRF failure view from views/__init__.py
from .views import csrf_failure

# Re-export for backward compatibility
__all__ = [
    'csrf_failure',
    # All other imports will be included automatically
]
