# core/__init__.py
"""
Core application for School Management System.
"""

default_app_config = 'core.apps.CoreConfig'

# Export exceptions for easy importing
from .exceptions import (
    SchoolManagementException,
    GradeValidationError,
    BulkUploadError,
    PermissionDeniedError,
    DataValidationError,
    NotificationException,
    GradingSystemException
)