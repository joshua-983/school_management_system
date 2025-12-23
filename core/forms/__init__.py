"""
Forms package initialization.
This file makes all forms available from the forms package directly.
"""

# Import all form modules for easy access
from .student_forms import *
from .teacher_forms import *
from .parent_forms import *
from .attendance_forms import *
from .grade_forms import (
    GradeEntryForm,
    GradeUpdateForm,
    BulkGradeUploadForm,
    QuickGradeEntryForm,
    GradeConfigurationForm,
    GradingSystemSelectorForm
)
from .assignment_forms import *
from .fee_forms import *
from .billing_forms import *
from .report_card_forms import *
from .announcement_forms import *
from .timetable_forms import *
from .school_config_forms import *
from .security_forms import *
from .bulk_operations_forms import *
from .budget_forms import *

# Re-export constants
from core.models import CLASS_LEVEL_CHOICES, TERM_CHOICES