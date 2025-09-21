# core/signals.py
from django.db.models.signals import post_save, post_delete
from django.dispatch import receiver
from django.db.models import Sum
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import logging
from django.utils import timezone
import geoip2.database
from django.conf import settings

logger = logging.getLogger(__name__)

def log_audit(action, instance, user, request=None):
    """
    Centralized audit logging function with geolocation capabilities
    """
    try:
        # Import locally to avoid circular imports
        from core.models import AuditLog
        
        # Create audit log instance
        audit_log = AuditLog(
            user=user,
            action=action,
            model=f"{instance._meta.app_label}.{instance._meta.model_name}",
            object_id=str(instance.pk),
            details={
                'fields': {field.name: getattr(instance, field.name) 
                         for field in instance._meta.fields},
                'repr': str(instance),
            }
        )
        
        # Add request metadata if available
        if request:
            audit_log.ip_address = request.META.get('REMOTE_ADDR')
            audit_log.user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
            
            # Add geolocation data if IP is available
            if audit_log.ip_address and hasattr(settings, 'GEOIP_PATH'):
                try:
                    with geoip2.database.Reader(settings.GEOIP_PATH) as reader:
                        response = reader.city(audit_log.ip_address)
                        audit_log.location = f"{response.city.name}, {response.country.name}"
                        audit_log.location_data = {
                            'city': response.city.name,
                            'country': response.country.name,
                            'latitude': response.location.latitude,
                            'longitude': response.location.longitude
                        }
                except Exception as ge:
                    logger.warning(f"Geolocation failed for IP {audit_log.ip_address}: {str(ge)}")
        
        audit_log.save()
        send_model_notification(action, instance, user)
        return True
        
    except Exception as e:
        logger.error(f"Audit logging failed: {str(e)}")
        return False

def send_model_notification(action, instance, user):
    """Send WebSocket notifications based on model changes"""
    try:
        model_name = instance._meta.model_name.lower()
        channel_layer = get_channel_layer()
        
        if model_name == 'grade' and action in ['CREATE', 'UPDATE']:
            recipient_id = instance.student.user.id
            notification_data = {
                'type': 'send_notification',
                'notification_type': 'GRADE',
                'title': 'Grade Updated' if action == 'UPDATE' else 'New Grade',
                'message': f'Your {instance.class_assignment.subject} grade is now {instance.grade}',
                'related_object_id': instance.class_assignment.id,
                'timestamp': str(timezone.now()),
                'action': action.lower()
            }
            
            async_to_sync(channel_layer.group_send)(
                f'notifications_{recipient_id}',
                notification_data
            )
            
            if user != instance.class_assignment.teacher.user:
                notify_third_party(user, instance.class_assignment.teacher.user, action, instance)
                
    except Exception as e:
        logger.error(f"Notification error for {instance}: {str(e)}")

def notify_third_party(user, target_user, action, instance):
    """Notify other interested parties about changes"""
    try:
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'notifications_{target_user.id}',
            {
                'type': 'send_notification',
                'notification_type': 'SYSTEM',
                'title': f'Grade {action.capitalize()}',
                'message': f'{user} modified grade for {instance.student}',
                'related_object_id': instance.id,
                'timestamp': str(timezone.now())
            }
        )
    except Exception as e:
        logger.error(f"Third-party notification failed: {str(e)}")

@receiver(post_save)
def post_save_audit(sender, instance, created, **kwargs):
    """Signal handler for post_save events"""
    # Skip Django built-in apps to avoid unnecessary logging
    if sender._meta.app_label in ['auth', 'admin', 'sessions', 'contenttypes']:
        return
    
    request = getattr(instance, '_request', None)
    user = getattr(instance, '_request_user', None) or (request.user if request and hasattr(request, 'user') else None)
    
    if user and user.is_authenticated:
        action = 'CREATE' if created else 'UPDATE'
        log_audit(action, instance, user, request)

@receiver(post_delete)
def post_delete_audit(sender, instance, **kwargs):
    """Signal handler for post_delete events"""
    # Skip Django built-in apps to avoid unnecessary logging
    if sender._meta.app_label in ['auth', 'admin', 'sessions', 'contenttypes']:
        return
    
    request = getattr(instance, '_request', None)
    user = getattr(instance, '_request_user', None) or (request.user if request and hasattr(request, 'user') else None)
    
    if user and user.is_authenticated:
        log_audit('DELETE', instance, user, request)

@receiver(post_save, sender='core.FeePayment')
def update_fee_status(sender, instance, **kwargs):
    """Update fee status when payment is saved"""
    try:
        fee = instance.fee
        fee.amount_paid = fee.payments.aggregate(Sum('amount'))['amount__sum'] or 0
        fee.update_payment_status()
    except Exception as e:
        logger.error(f"Error updating fee status: {str(e)}")

@receiver(post_delete, sender='core.FeePayment')
def update_fee_status_on_delete(sender, instance, **kwargs):
    """Update fee status when payment is deleted"""
    try:
        fee = instance.fee
        fee.amount_paid = fee.payments.aggregate(Sum('amount'))['amount__sum'] or 0
        fee.update_payment_status()
    except Exception as e:
        logger.error(f"Error updating fee status on delete: {str(e)}")

def get_location(ip_address):
    """Utility function to get location from IP"""
    if not hasattr(settings, 'GEOIP_PATH'):
        return None
        
    try:
        with geoip2.database.Reader(settings.GEOIP_PATH) as reader:
            response = reader.city(ip_address)
            return {
                'city': response.city.name,
                'country': response.country.name,
                'coordinates': (response.location.latitude, response.location.longitude)
            }
    except Exception as e:
        logger.warning(f"Geolocation failed for {ip_address}: {str(e)}")
        return None

# Add signal for new message notifications
@receiver(post_save, sender='core.ParentMessage')
def notify_parent_message(sender, instance, created, **kwargs):
    if created:
        try:
            # Import Notification locally to avoid circular imports
            from core.models import Notification
            
            # Send notification to receiver
            Notification.objects.create(
                recipient=instance.receiver,
                notification_type='MESSAGE',
                title='New Message',
                message=f'You have a new message from {instance.sender.get_full_name()}',
                related_object_id=instance.id,
                related_content_type='parentmessage'
            )
        except Exception as e:
            logger.error(f"Error creating parent message notification: {str(e)}")

# ASSIGNMENT-RELATED SIGNALS (using string references to avoid circular imports)
@receiver(post_save, sender='core.Assignment')
def create_assignment_analytics(sender, instance, created, **kwargs):
    """
    Automatically create analytics record when assignment is created
    """
    if created:
        try:
            # Import locally to avoid circular imports
            from core.models import AssignmentAnalytics
            AssignmentAnalytics.objects.create(assignment=instance)
            logger.info(f"Created analytics for new assignment: {instance.title}")
        except Exception as e:
            logger.error(f"Failed to create analytics for assignment {instance.id}: {str(e)}")

@receiver(post_save, sender='core.StudentAssignment')
def update_assignment_analytics_on_change(sender, instance, **kwargs):
    """
    Update analytics when student assignments are created or updated
    """
    try:
        # Import locally to avoid circular imports
        from core.models import AssignmentAnalytics
        
        # Get or create analytics for the assignment
        analytics, created = AssignmentAnalytics.objects.get_or_create(
            assignment=instance.assignment
        )
        # Recalculate analytics
        analytics.calculate_analytics()
        logger.debug(f"Updated analytics for assignment: {instance.assignment.title}")
    except Exception as e:
        logger.error(f"Error updating assignment analytics: {str(e)}")

@receiver(post_delete, sender='core.StudentAssignment')
def update_assignment_analytics_on_delete(sender, instance, **kwargs):
    """
    Update analytics when student assignments are deleted
    """
    try:
        if hasattr(instance.assignment, 'analytics'):
            instance.assignment.analytics.calculate_analytics()
            logger.debug(f"Updated analytics after deletion for assignment: {instance.assignment.title}")
    except Exception as e:
        logger.error(f"Error updating analytics after deletion: {str(e)}")

@receiver(post_save, sender='core.Assignment')
def audit_assignment_changes(sender, instance, created, **kwargs):
    """Audit log for assignment changes"""
    if sender._meta.app_label == 'core':
        request = getattr(instance, '_request', None)
        user = getattr(instance, '_request_user', None) or (request.user if request and hasattr(request, 'user') else None)
        
        if user and user.is_authenticated:
            action = 'CREATE' if created else 'UPDATE'
            log_audit(action, instance, user, request)

@receiver(post_save, sender='core.StudentAssignment')
def audit_student_assignment_changes(sender, instance, created, **kwargs):
    """Audit log for student assignment changes"""
    if sender._meta.app_label == 'core':
        request = getattr(instance, '_request', None)
        user = getattr(instance, '_request_user', None) or (request.user if request and hasattr(request, 'user') else None)
        
        if user and user.is_authenticated:
            action = 'CREATE' if created else 'UPDATE'
            log_audit(action, instance, user, request)

@receiver(post_save, sender='core.Assignment')
def notify_new_assignment(sender, instance, created, **kwargs):
    """Send notifications when new assignments are created"""
    if created:
        try:
            from core.models import Notification
            from django.contrib.auth.models import User
            
            # Get all students in the class
            students = User.objects.filter(
                student__class_level=instance.class_assignment.class_level,
                student__is_active=True
            )
            
            for student in students:
                Notification.objects.create(
                    recipient=student,
                    notification_type='ASSIGNMENT',
                    title='New Assignment',
                    message=f'New assignment: {instance.title} for {instance.subject.name}',
                    related_object_id=instance.id,
                    related_content_type='assignment'
                )
                
            logger.info(f"Created notifications for new assignment: {instance.title}")
            
        except Exception as e:
            logger.error(f"Failed to create assignment notifications: {str(e)}")