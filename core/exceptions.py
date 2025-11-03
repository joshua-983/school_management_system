# core/exceptions.py
"""
Custom exception classes for the School Management System.
These exceptions provide more specific error handling for different scenarios.
"""

import logging

logger = logging.getLogger(__name__)


class SchoolManagementException(Exception):
    """Base exception for school management system"""
    
    def __init__(self, message=None, details=None, user=None):
        self.message = message or "An error occurred in the school management system"
        self.details = details
        self.user = user
        super().__init__(self.message)
        
        # Log the exception
        logger.error(
            f"SchoolManagementException: {self.message} - "
            f"User: {getattr(user, 'username', 'Anonymous')}, "
            f"Details: {details}"
        )


class GradeValidationError(SchoolManagementException):
    """Raised when grade validation fails"""
    
    def __init__(self, message="Grade validation failed", field_errors=None, **kwargs):
        self.field_errors = field_errors or {}
        super().__init__(message, **kwargs)
        
        logger.warning(
            f"GradeValidationError: {message} - "
            f"Field Errors: {field_errors}"
        )


class BulkUploadError(SchoolManagementException):
    """Raised when bulk upload operations fail"""
    
    def __init__(self, message="Bulk upload failed", row_errors=None, **kwargs):
        self.row_errors = row_errors or []
        super().__init__(message, **kwargs)
        
        logger.error(
            f"BulkUploadError: {message} - "
            f"Row Errors: {len(self.row_errors)} errors"
        )


class PermissionDeniedError(SchoolManagementException):
    """Raised when user lacks required permissions"""
    
    def __init__(self, message="Permission denied", required_permission=None, **kwargs):
        self.required_permission = required_permission
        super().__init__(message, **kwargs)
        
        logger.warning(
            f"PermissionDeniedError: {message} - "
            f"Required: {required_permission}"
        )


class DataValidationError(SchoolManagementException):
    """Raised when data validation fails"""
    
    def __init__(self, message="Data validation failed", validation_errors=None, **kwargs):
        self.validation_errors = validation_errors or {}
        super().__init__(message, **kwargs)


class NotificationException(SchoolManagementException):
    """Raised when notification operations fail"""
    
    def __init__(self, message="Notification operation failed", **kwargs):
        super().__init__(message, **kwargs)


class CacheOperationException(SchoolManagementException):
    """Raised when cache operations fail"""
    
    def __init__(self, message="Cache operation failed", **kwargs):
        super().__init__(message, **kwargs)


class DatabaseOperationException(SchoolManagementException):
    """Raised when database operations fail"""
    
    def __init__(self, message="Database operation failed", **kwargs):
        super().__init__(message, **kwargs)


class GradingSystemException(SchoolManagementException):
    """Raised when grading system operations fail"""
    
    def __init__(self, message="Grading system operation failed", **kwargs):
        super().__init__(message, **kwargs)


class AcademicTermException(SchoolManagementException):
    """Raised when academic term operations fail"""
    
    def __init__(self, message="Academic term operation failed", **kwargs):
        super().__init__(message, **kwargs)


class StudentManagementException(SchoolManagementException):
    """Raised when student management operations fail"""
    
    def __init__(self, message="Student management operation failed", **kwargs):
        super().__init__(message, **kwargs)


class TeacherManagementException(SchoolManagementException):
    """Raised when teacher management operations fail"""
    
    def __init__(self, message="Teacher management operation failed", **kwargs):
        super().__init__(message, **kwargs)


class AttendanceException(SchoolManagementException):
    """Raised when attendance operations fail"""
    
    def __init__(self, message="Attendance operation failed", **kwargs):
        super().__init__(message, **kwargs)


class FeeManagementException(SchoolManagementException):
    """Raised when fee management operations fail"""
    
    def __init__(self, message="Fee management operation failed", **kwargs):
        super().__init__(message, **kwargs)