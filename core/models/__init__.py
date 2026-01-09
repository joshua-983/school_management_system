# core/models/__init__.py - UPDATED VERSION
"""
Models package initialization - Updated version
"""

# Import base classes and constants FIRST
from .base import (
    GENDER_CHOICES,
    CLASS_LEVEL_CHOICES,
    TERM_CHOICES,
    ACADEMIC_PERIOD_SYSTEM_CHOICES,
    get_period_choices_for_system,
    get_period_display,
    get_current_academic_year,
    student_image_path,
    teacher_image_path,
    parent_image_path,
    GhanaEducationMixin,
    BaseModel,
    TimeStampedModel,
    StatusMixin,
)

# Import Academic Term models
from .academic_term import AcademicYear, AcademicTerm

# Import Subject and ClassAssignment from separate files
from .subject import Subject
from .class_assignment import ClassAssignment

# Import grades models
from .grades import Grade
from .report_card import ReportCard

# Import student models
from .student import Student

# Import teacher models
from .teacher import Teacher

# Import parent models
from .parent import (
    ParentGuardian,
    ParentAnnouncement,
    ParentMessage,
    ParentEvent,
)

# Import attendance models
from .attendance import (
    AttendancePeriod,
    StudentAttendance,
    AttendanceSummary,
)

# Import assignment models
from .assignments import (
    Assignment,
    StudentAssignment,
    AssignmentAnalytics,
    AssignmentTemplate,
)

# Import timetable models
from .timetable import (
    TimeSlot,
    Timetable,
    TimetableEntry,
)

# Import financial models
from .financial import (
    FeeCategory,
    Bill,
    BillItem,
    BillPayment,
    Fee,
    FeePayment,
    StudentCredit,
    FeeDiscount,
    FeeInstallment,
    PaymentGateway,
    OnlinePayment,
    PendingPayment,
    FeeGenerationBatch,
)

# Import communication models - ADD THIS IMPORT
from .communication import (
    Announcement,
    UserAnnouncementView,
    Notification,
)

# Import security models
from .security import (
    AuditAlertRule,
    SecurityEvent,
    AuditReport,
    DataRetentionPolicy,
    AuditLog,
    UserProfile,
)

# Import analytics models
from .analytics import (
    AnalyticsCache,
    GradeAnalytics,
    AttendanceAnalytics,
    Holiday,
)

# Import configuration models
from .configuration import (
    SchoolConfiguration,
    MaintenanceMode,
    ScheduledMaintenance,
    ReportCardConfiguration,
    PromotionConfiguration,
)

# Import budget models
from .budget_models import (
    Budget,
    Expense,
)

# Export all models for backward compatibility
__all__ = [
    # Base constants
    'GENDER_CHOICES',
    'CLASS_LEVEL_CHOICES',
    'TERM_CHOICES',
    'ACADEMIC_PERIOD_SYSTEM_CHOICES',
    'get_period_choices_for_system',
    'get_period_display',
    'get_current_academic_year',
    'student_image_path',
    'teacher_image_path',
    'parent_image_path',
    'GhanaEducationMixin',
    'BaseModel',
    'TimeStampedModel',
    'StatusMixin',
    
    # Academic Models
    'AcademicYear',
    'AcademicTerm',
    'Subject',
    'ClassAssignment',
    
    # Student
    'Student',
    
    # Parent
    'ParentGuardian',
    'ParentAnnouncement',
    'ParentMessage',
    'ParentEvent',
    
    # Teacher
    'Teacher',
    
    # Attendance
    'AttendancePeriod',
    'StudentAttendance',
    'AttendanceSummary',
    
    # Grades
    'Grade',
    'ReportCard',
    
    # Assignments
    'Assignment',
    'StudentAssignment',
    'AssignmentAnalytics',
    'AssignmentTemplate',
    
    # Timetable
    'TimeSlot',
    'Timetable',
    'TimetableEntry',
    
    # Financial
    'FeeCategory',
    'Bill',
    'BillItem',
    'BillPayment',
    'Fee',
    'FeePayment',
    'StudentCredit',
    'FeeDiscount',
    'FeeInstallment',
    'PaymentGateway',
    'OnlinePayment',
    'PendingPayment',
    'FeeGenerationBatch',
    
    # Communication - ADD THESE
    'Announcement',
    'UserAnnouncementView',
    'Notification',
    
    # Security
    'AuditAlertRule',
    'SecurityEvent',
    'AuditReport',
    'DataRetentionPolicy',
    'AuditLog',
    'UserProfile',
    
    # Analytics
    'AnalyticsCache',
    'GradeAnalytics',
    'AttendanceAnalytics',
    'Holiday',
    
    # Configuration
    'SchoolConfiguration',
    'MaintenanceMode',
    'ScheduledMaintenance',
    'ReportCardConfiguration',
    'PromotionConfiguration',
    
    # Budget Models
    'Budget',
    'Expense',
]

# Utility functions for backward compatibility
def get_current_academic_term():
    """Get current active academic term"""
    try:
        return AcademicTerm.get_current_term()
    except Exception:
        return None

def get_or_create_subject(name, code=None):
    """Get or create a subject"""
    try:
        if code:
            return Subject.objects.get_or_create(code=code, defaults={'name': name})
        else:
            # Find by name
            subject = Subject.objects.filter(name__iexact=name).first()
            if subject:
                return subject, False
            # Create new
            subject = Subject(name=name)
            subject.save()
            return subject, True
    except Exception as e:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Error getting/creating subject: {e}")
        return None, False