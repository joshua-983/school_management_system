"""
Main forms module that imports all split forms for backward compatibility.
Use this file to maintain imports for existing code.
"""

# Import constants from models
from core.models import CLASS_LEVEL_CHOICES, TERM_CHOICES

# Import all forms from split modules
from .forms.student_forms import *
from .forms.teacher_forms import *
from .forms.parent_forms import *
from .forms.attendance_forms import *
from .forms.grade_forms import *
from .forms.assignment_forms import *
from .forms.fee_forms import *
from .forms.billing_forms import *
from .forms.report_card_forms import *
from .forms.announcement_forms import *
from .forms.timetable_forms import *
from .forms.school_config_forms import *
from .forms.security_forms import *
from .forms.bulk_operations_forms import *

# Re-export all forms for backward compatibility
__all__ = [
    # Constants
    'CLASS_LEVEL_CHOICES',
    'TERM_CHOICES',
    
    # Student forms
    'StudentRegistrationForm',
    'StudentProfileForm',
    'StudentParentAssignmentForm',
    
    # Teacher forms
    'TeacherRegistrationForm',
    'ClassAssignmentForm',
    
    # Parent forms
    'ParentGuardianAddForm',
    
    # Attendance forms
    'AcademicTermForm',
    'AttendancePeriodForm',
    'StudentAttendanceForm',
    'BulkAttendanceForm',
    'AttendanceRecordForm',
    'AttendanceFilterForm',
    'AttendanceSummaryFilterForm',
    
    # Grade forms
    'GradeEntryForm',
    'BulkGradeUploadForm',
    
    # Assignment forms
    'SubjectForm',
    'AssignmentForm',
    'AssignmentTemplateForm',
    'StudentAssignmentForm',
    'TeacherGradingForm',
    'StudentAssignmentSubmissionForm',
    
    # Fee forms
    'FeeCategoryForm',
    'FeeForm',
    'FeeDiscountForm',
    'FeeInstallmentForm',
    'FeeFilterForm',
    'FeeStatusReportForm',
    
    # Billing forms
    'BillGenerationForm',
    'BillPaymentForm',
    'BillFilterForm',
    'BillUpdateForm',
    'BulkBillActionForm',
    
    # Report card forms
    'ReportCardGenerationForm',
    'ReportCardSelectionForm',
    'ReportCardFilterForm',
    
    # Announcement forms
    'AnnouncementForm',
    
    # Timetable forms
    'TimeSlotForm',
    'TimetableForm',
    'TimetableEntryForm',
    'TimetableFilterForm',
    
    # School configuration forms
    'SchoolConfigurationForm',
    'BudgetForm',
    
    # Security forms
    'UserBlockForm',
    'MaintenanceModeForm',
    'UserSearchForm',
    'ScheduledMaintenanceForm',
    
    # Bulk operations forms
    'BulkFeeImportForm',
    'BulkFeeUpdateForm',
    'BulkFeeCreationForm',
    'DateRangeForm',
    'ParentFeePaymentForm',
    'ParentAttendanceFilterForm',
]
