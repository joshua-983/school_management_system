# core/utils/error_handling.py
"""
Utility functions for comprehensive error handling across the application.
"""

import logging
from functools import wraps
from django.contrib import messages
from django.shortcuts import redirect
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404, JsonResponse
from django.db import DatabaseError

from ..exceptions import (
    SchoolManagementException,
    GradeValidationError,
    BulkUploadError,
    PermissionDeniedError,
    DataValidationError,
    NotificationException
)

logger = logging.getLogger(__name__)


def handle_view_exception(view_func):
    """
    Decorator to handle exceptions in views with comprehensive error handling.
    
    Usage:
    @handle_view_exception
    def my_view(request):
        # your view logic
    """
    @wraps(view_func)
    def wrapper(request, *args, **kwargs):
        try:
            return view_func(request, *args, **kwargs)
            
        except PermissionDeniedError as e:
            logger.warning(
                f"Permission denied for user {request.user}: {e.message}",
                extra={'user': request.user, 'details': e.details}
            )
            messages.error(
                request, 
                e.message or "You don't have permission to perform this action."
            )
            return redirect('home')
            
        except GradeValidationError as e:
            logger.error(
                f"Grade validation error: {e.message}",
                extra={'user': request.user, 'field_errors': e.field_errors}
            )
            
            # Add field-specific errors to messages
            for field, error in e.field_errors.items():
                messages.error(request, f"{field}: {error}")
                
            if not e.field_errors:
                messages.error(request, e.message or "Grade validation failed.")
                
            return redirect(request.META.get('HTTP_REFERER', 'grade_list'))
            
        except BulkUploadError as e:
            logger.error(
                f"Bulk upload error: {e.message}",
                extra={'user': request.user, 'row_errors_count': len(e.row_errors)}
            )
            
            messages.error(request, e.message or "Bulk upload failed.")
            
            # Show first few row errors
            for i, row_error in enumerate(e.row_errors[:3]):
                messages.warning(request, f"Row {i+1}: {row_error}")
                
            if len(e.row_errors) > 3:
                messages.warning(request, f"... and {len(e.row_errors) - 3} more errors")
                
            return redirect(request.META.get('HTTP_REFERER', 'bulk_upload'))
            
        except DataValidationError as e:
            logger.error(
                f"Data validation error: {e.message}",
                extra={'user': request.user, 'validation_errors': e.validation_errors}
            )
            
            messages.error(request, e.message or "Data validation failed.")
            return redirect(request.META.get('HTTP_REFERER', 'home'))
            
        except NotificationException as e:
            logger.error(
                f"Notification error: {e.message}",
                extra={'user': request.user}
            )
            # Don't show notification errors to users, just log them
            return view_func(request, *args, **kwargs)
            
        except Http404:
            logger.warning(
                f"Resource not found - User: {request.user}, Path: {request.path}"
            )
            messages.error(request, "The requested resource was not found.")
            return redirect('home')
            
        except ValidationError as e:
            logger.error(
                f"Django validation error: {e}",
                extra={'user': request.user}
            )
            messages.error(request, "Invalid data provided. Please check your input.")
            return redirect(request.META.get('HTTP_REFERER', 'home'))
            
        except DatabaseError as e:
            logger.error(
                f"Database error in {view_func.__name__}: {e}",
                extra={'user': request.user},
                exc_info=True
            )
            messages.error(
                request, 
                "A database error occurred. Please try again or contact support."
            )
            return redirect('home')
            
        except SchoolManagementException as e:
            logger.error(
                f"School management error in {view_func.__name__}: {e.message}",
                extra={'user': request.user, 'details': e.details},
                exc_info=True
            )
            messages.error(request, e.message or "An application error occurred.")
            return redirect('home')
            
        except Exception as e:
            logger.error(
                f"Unexpected error in {view_func.__name__}: {str(e)}",
                extra={'user': request.user, 'path': request.path},
                exc_info=True
            )
            messages.error(
                request, 
                "An unexpected error occurred. Please try again or contact support."
            )
            return redirect('home')
            
    return wrapper


def handle_api_exception(api_func):
    """
    Decorator to handle exceptions in API views with JSON responses.
    
    Usage:
    @handle_api_exception
    def my_api_view(request):
        # your API logic
    """
    @wraps(api_func)
    def wrapper(request, *args, **kwargs):
        try:
            return api_func(request, *args, **kwargs)
            
        except PermissionDeniedError as e:
            logger.warning(f"API permission denied: {e.message}")
            return JsonResponse({
                'error': 'Permission denied',
                'message': e.message,
                'code': 'permission_denied'
            }, status=403)
            
        except (GradeValidationError, DataValidationError) as e:
            logger.error(f"API validation error: {e.message}")
            return JsonResponse({
                'error': 'Validation failed',
                'message': e.message,
                'details': getattr(e, 'field_errors', {}) or getattr(e, 'validation_errors', {}),
                'code': 'validation_error'
            }, status=400)
            
        except BulkUploadError as e:
            logger.error(f"API bulk upload error: {e.message}")
            return JsonResponse({
                'error': 'Bulk upload failed',
                'message': e.message,
                'row_errors': e.row_errors,
                'code': 'bulk_upload_error'
            }, status=400)
            
        except Http404:
            logger.warning(f"API resource not found: {request.path}")
            return JsonResponse({
                'error': 'Resource not found',
                'message': 'The requested resource was not found.',
                'code': 'not_found'
            }, status=404)
            
        except SchoolManagementException as e:
            logger.error(f"API business error: {e.message}")
            return JsonResponse({
                'error': 'Business logic error',
                'message': e.message,
                'code': 'business_error'
            }, status=400)
            
        except Exception as e:
            logger.error(
                f"API unexpected error in {api_func.__name__}: {str(e)}",
                exc_info=True
            )
            return JsonResponse({
                'error': 'Internal server error',
                'message': 'An unexpected error occurred.',
                'code': 'internal_error'
            }, status=500)
            
    return wrapper


def safe_database_operation(func):
    """
    Decorator for safe database operations with automatic transaction handling.
    
    Usage:
    @safe_database_operation
    def my_database_operation():
        # your database logic
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        from django.db import transaction, DatabaseError
        
        try:
            with transaction.atomic():
                return func(*args, **kwargs)
                
        except DatabaseError as e:
            logger.error(
                f"Database operation failed in {func.__name__}: {str(e)}",
                exc_info=True
            )
            raise DatabaseOperationException(
                f"Database operation failed: {str(e)}",
                details={'function': func.__name__}
            )
        except Exception as e:
            logger.error(
                f"Unexpected error in database operation {func.__name__}: {str(e)}",
                exc_info=True
            )
            raise SchoolManagementException(
                f"Operation failed: {str(e)}",
                details={'function': func.__name__}
            )
            
    return wrapper


class ErrorHandler:
    """
    Utility class for comprehensive error handling across the application.
    """
    
    @staticmethod
    def handle_grade_validation(student, subject, scores, user=None):
        """
        Handle grade validation with proper error reporting.
        """
        errors = {}
        
        # Validate score ranges
        max_scores = {
            'classwork_score': 30,
            'homework_score': 10,
            'test_score': 10,
            'exam_score': 50
        }
        
        for score_field, max_score in max_scores.items():
            score = scores.get(score_field, 0)
            if score < 0:
                errors[score_field] = f"Score cannot be negative"
            elif score > max_score:
                errors[score_field] = f"Score cannot exceed {max_score}"
        
        # Validate total score
        total_score = sum(scores.get(field, 0) for field in max_scores.keys())
        if total_score > 100:
            errors['__all__'] = f"Total score cannot exceed 100%. Current: {total_score}%"
        
        if errors:
            raise GradeValidationError(
                message="Grade validation failed",
                field_errors=errors,
                user=user,
                details={
                    'student_id': getattr(student, 'id', None),
                    'subject_id': getattr(subject, 'id', None),
                    'scores': scores
                }
            )
        
        return True
    
    @staticmethod
    def handle_permission_check(user, required_permission, resource=None):
        """
        Handle permission checks with detailed error reporting.
        """
        from ..utils import is_admin, is_teacher, is_student
        
        has_permission = False
        
        if required_permission == 'admin_access':
            has_permission = is_admin(user)
        elif required_permission == 'teacher_access':
            has_permission = is_teacher(user)
        elif required_permission == 'student_access':
            has_permission = is_student(user)
        else:
            # Custom permission logic
            has_permission = getattr(user, f'has_{required_permission}', lambda: False)()
        
        if not has_permission:
            raise PermissionDeniedError(
                message=f"Permission denied for {required_permission}",
                required_permission=required_permission,
                user=user,
                details={'resource': resource}
            )
        
        return True
    
    @staticmethod
    def log_security_event(user, event_type, details=None):
        """
        Log security-related events for monitoring and auditing.
        """
        security_logger = logging.getLogger('security')
        
        log_data = {
            'event_type': event_type,
            'user': getattr(user, 'username', 'Anonymous'),
            'user_id': getattr(user, 'id', None),
            'details': details or {}
        }
        
        if event_type in ['login_failed', 'permission_denied', 'suspicious_activity']:
            security_logger.warning(f"Security event: {event_type}", extra=log_data)
        else:
            security_logger.info(f"Security event: {event_type}", extra=log_data)