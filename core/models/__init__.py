"""
Models package initialization.
Exports all models for backward compatibility.
"""

# Import base classes and constants
from .base import (
    GENDER_CHOICES,
    CLASS_LEVEL_CHOICES,
    TERM_CHOICES,
    CLASS_LEVEL_DISPLAY_MAP,
    student_image_path,
    teacher_image_path,
    parent_image_path,
    GhanaEducationMixin,
)

# Import academic models
from .academic import (
    Subject,
    AcademicTerm,
    ClassAssignment,
)

# Import student models
from .student import Student

# Import parent models
from .parent import (
    ParentGuardian,
    ParentAnnouncement,
    ParentMessage,
    ParentEvent,
)

# Import teacher models
from .teacher import Teacher

# Import attendance models
from .attendance import (
    AttendancePeriod,
    StudentAttendance,
    AttendanceSummary,
)

# Import grade models
from .grades import (
    Grade,
    ReportCard,
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
)

# Import communication models
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

# Import analytics models (REMOVE Budget and Expense from here)
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
)

# Import budget models (ADD THIS - these are the correct Budget and Expense models)
from .budget_models import (
    Budget,
    Expense,
)

# Export all models for backward compatibility
__all__ = [
    # Base
    'GENDER_CHOICES',
    'CLASS_LEVEL_CHOICES',
    'TERM_CHOICES',
    'GhanaEducationMixin',
    
    # Academic
    'Subject',
    'AcademicTerm',
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
    
    # Communication
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
    # 'Budget',  # REMOVE FROM HERE
    # 'Expense',  # REMOVE FROM HERE
    
    # Configuration
    'SchoolConfiguration',
    'MaintenanceMode',
    'ScheduledMaintenance',
    
    # Budget Models (ADD THESE)
    'Budget',
    'Expense',
]

# Utility function for backward compatibility
def get_unread_count(user):
    """
    Get count of unread notifications for a user
    """
    from .communication import Notification
    return Notification.get_unread_count_for_user(user)

def create_notification(recipient, title, message, notification_type="GENERAL", link=None, related_object=None):
    """Utility function to create notifications"""
    from .communication import Notification
    return Notification.create_notification(
        recipient=recipient,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link,
        related_object=related_object
    )

def is_admin(user):
    """Check if user is admin"""
    return user.is_staff or user.is_superuser

def is_student(user):
    """Check if user is a student"""
    return hasattr(user, 'student')

def is_teacher(user):
    """Check if user is a teacher"""
    return hasattr(user, 'teacher')

def is_parent(user):
    """Check if user is a parent"""
    return hasattr(user, 'parentguardian')