# core/utils/logger.py
"""
Centralized logging utility for better error handling
"""
import logging
import functools
from django.contrib.auth import get_user_model

User = get_user_model()

# Create loggers for different components
parent_logger = logging.getLogger('core.parents')
audit_logger = logging.getLogger('core.parents.audit')
error_logger = logging.getLogger('core.parents.errors')

def setup_logging():
    """Configure logging for parent portal"""
    logging.config.dictConfig({
        'version': 1,
        'disable_existing_loggers': False,
        'formatters': {
            'detailed': {
                'format': '%(asctime)s %(name)-12s %(levelname)-8s %(message)s'
            },
            'simple': {
                'format': '%(levelname)s %(message)s'
            },
            'audit': {
                'format': '%(asctime)s | USER:%(user_id)s | ROLE:%(user_role)s | ACTION:%(action)s | STATUS:%(status)s'
            }
        },
        'handlers': {
            'console': {
                'class': 'logging.StreamHandler',
                'formatter': 'simple',
                'level': 'INFO',
            },
            'parent_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': 'logs/parent_portal.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'formatter': 'detailed',
                'level': 'INFO',
            },
            'error_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': 'logs/parent_errors.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 5,
                'formatter': 'detailed',
                'level': 'ERROR',
            },
            'audit_file': {
                'class': 'logging.handlers.RotatingFileHandler',
                'filename': 'logs/parent_audit.log',
                'maxBytes': 10485760,  # 10MB
                'backupCount': 10,
                'formatter': 'audit',
                'level': 'INFO',
            },
        },
        'loggers': {
            'core.parents': {
                'handlers': ['console', 'parent_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'core.parents.audit': {
                'handlers': ['audit_file'],
                'level': 'INFO',
                'propagate': False,
            },
            'core.parents.errors': {
                'handlers': ['error_file', 'console'],
                'level': 'ERROR',
                'propagate': False,
            },
        },
    })

def log_parent_action(action, user=None, status='success', extra=None):
    """Log parent actions for audit trail"""
    log_data = {
        'action': action,
        'status': status,
        'user_id': user.id if user else 'anonymous',
        'user_role': 'parent' if user and hasattr(user, 'parentguardian') else 'unknown',
    }
    
    if extra:
        log_data.update(extra)
    
    audit_logger.info(action, extra=log_data)

def log_parent_error(error_message, user=None, exc_info=False, extra=None):
    """Log parent-related errors"""
    log_data = {
        'user_id': user.id if user else 'anonymous',
        'username': user.username if user else 'anonymous',
    }
    
    if extra:
        log_data.update(extra)
    
    error_logger.error(error_message, exc_info=exc_info, extra=log_data)

def log_view_exception(view_name):
    """
    Decorator to log exceptions in views
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(request, *args, **kwargs):
            try:
                return func(request, *args, **kwargs)
            except Exception as e:
                log_parent_error(
                    f"Error in {view_name}: {str(e)}",
                    user=request.user if hasattr(request, 'user') else None,
                    exc_info=True,
                    extra={'view': view_name}
                )
                raise
        return wrapper
    return decorator

def log_database_queries(func):
    """
    Decorator to log database query count and time
    """
    @functools.wraps(func)
    def wrapper(request, *args, **kwargs):
        from django.db import connection
        from time import time
        
        start_time = time()
        start_queries = len(connection.queries)
        
        response = func(request, *args, **kwargs)
        
        end_time = time()
        end_queries = len(connection.queries)
        
        query_count = end_queries - start_queries
        execution_time = end_time - start_time
        
        if query_count > 50:  # Log if too many queries
            log_parent_error(
                f"High query count: {query_count} queries in {execution_time:.2f}s",
                user=request.user,
                extra={
                    'view': func.__name__,
                    'query_count': query_count,
                    'execution_time': execution_time
                }
            )
        
        return response
    return wrapper