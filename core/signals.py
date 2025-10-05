from django.db.models.signals import post_save, post_delete, pre_save, m2m_changed
from django.dispatch import receiver
from django.db.models import Sum
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging
from django.utils import timezone
from django.conf import settings
from django.db import transaction
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)

def get_client_ip(request):
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

def log_audit(action, instance, user, request=None):
    try:
        from core.models import AuditLog
        
        audit_log = AuditLog(
            user=user,
            action=action,
            model_name=f"{instance._meta.app_label}.{instance._meta.model_name}",
            object_id=str(instance.pk),
            details={
                'model': str(instance._meta),
                'repr': str(instance),
                'changes': getattr(instance, '_change_details', {}),
            }
        )
        
        if request:
            audit_log.ip_address = get_client_ip(request)
            audit_log.user_agent = request.META.get('HTTP_USER_AGENT', '')[:255]
        
        audit_log.save()
        logger.debug(f"Audit log created: {action} for {instance}")
        return True
        
    except Exception as e:
        logger.error(f"Audit logging failed: {str(e)}")
        return False

def send_websocket_notification(recipient_id, notification_type, title, message, related_object_id=None):
    try:
        channel_layer = get_channel_layer()
        notification_data = {
            'type': 'send_notification',
            'notification_type': notification_type,
            'title': title,
            'message': message,
            'related_object_id': related_object_id,
            'timestamp': str(timezone.now()),
        }
        
        async_to_sync(channel_layer.group_send)(
            f'notifications_{recipient_id}',
            notification_data
        )
        logger.debug(f"WebSocket notification sent to user {recipient_id}")
    except Exception as e:
        logger.error(f"WebSocket notification failed: {str(e)}")

@receiver(post_save, sender='core.Student')
def handle_student_save(sender, instance, created, **kwargs):
    try:
        from core.models import AuditLog
        
        request = getattr(instance, '_request', None)
        user = getattr(instance, '_request_user', None) or (request.user if request and hasattr(request, 'user') else None)
        
        if user and user.is_authenticated:
            action = 'CREATE' if created else 'UPDATE'
            log_audit(action, instance, user, request)
            
        if created and not instance.student_id:
            try:
                instance.save()
            except Exception as e:
                logger.error(f"Error generating student ID for {instance}: {str(e)}")
                
    except Exception as e:
        logger.error(f"Error in student save signal: {str(e)}")

@receiver(post_save, sender='core.Assignment')
def handle_assignment_creation(sender, instance, created, **kwargs):
    if created:
        try:
            logger.info(f"Processing new assignment: {instance.title}")
            
            from core.models import AssignmentAnalytics
            AssignmentAnalytics.objects.get_or_create(assignment=instance)
            logger.info(f"Created analytics for assignment: {instance.title}")
            
            def create_student_assignments():
                try:
                    from core.models import Student, StudentAssignment
                    
                    students = Student.objects.filter(
                        class_level=instance.class_assignment.class_level,
                        is_active=True
                    )
                    
                    assignments_to_create = []
                    for student in students:
                        if not StudentAssignment.objects.filter(
                            student=student, 
                            assignment=instance
                        ).exists():
                            assignments_to_create.append(
                                StudentAssignment(
                                    student=student,
                                    assignment=instance,
                                    status='PENDING'
                                )
                            )
                    
                    if assignments_to_create:
                        StudentAssignment.objects.bulk_create(assignments_to_create)
                        logger.info(f"Created {len(assignments_to_create)} student assignments for {instance.title}")
                    
                    for student in students:
                        send_websocket_notification(
                            student.user.id,
                            'ASSIGNMENT',
                            'New Assignment',
                            f'New assignment: {instance.title} for {instance.subject.name}',
                            instance.id
                        )
                        
                except Exception as e:
                    logger.error(f"Error creating student assignments: {str(e)}")
            
            transaction.on_commit(create_student_assignments)
            
        except Exception as e:
            logger.error(f"Error in assignment creation signal: {str(e)}")

@receiver(post_save, sender='core.StudentAssignment')
def handle_student_assignment_update(sender, instance, created, **kwargs):
    try:
        if hasattr(instance.assignment, 'analytics'):
            instance.assignment.analytics.calculate_analytics()
        
        if instance.status in ['SUBMITTED', 'LATE'] and instance.submitted_date:
            send_websocket_notification(
                instance.assignment.class_assignment.teacher.user.id,
                'SUBMISSION',
                'Assignment Submitted',
                f'{instance.student.get_full_name()} submitted {instance.assignment.title}',
                instance.id
            )
            
    except Exception as e:
        logger.error(f"Error in student assignment update signal: {str(e)}")

@receiver(post_save, sender='core.StudentAssignment')
def handle_student_assignment_graded(sender, instance, **kwargs):
    try:
        if instance.status == 'GRADED' and instance.score is not None:
            send_websocket_notification(
                instance.student.user.id,
                'GRADE',
                'Assignment Graded',
                f'Your assignment "{instance.assignment.title}" has been graded',
                instance.id
            )
    except Exception as e:
        logger.error(f"Error in student assignment graded signal: {str(e)}")

@receiver(post_save, sender='core.Grade')
def handle_grade_update(sender, instance, created, **kwargs):
    try:
        from core.models import Notification
        
        action = 'created' if created else 'updated'
        
        Notification.objects.create(
            recipient=instance.student.user,
            notification_type='GRADE',
            title=f'Grade {action.capitalize()}',
            message=f'Your {instance.subject.name} grade has been {action}',
            related_object_id=instance.id,
            related_content_type='grade'
        )
        
        send_websocket_notification(
            instance.student.user.id,
            'GRADE',
            f'Grade {action.capitalize()}',
            f'Your {instance.subject.name} grade is now {instance.total_score}',
            instance.id
        )
        
        logger.info(f"Grade notification sent for {instance.student}")
        
    except Exception as e:
        logger.error(f"Error in grade update signal: {str(e)}")

@receiver(post_save, sender='core.FeePayment')
def update_fee_after_payment(sender, instance, created, **kwargs):
    try:
        fee = instance.fee
        total_paid = fee.payments.aggregate(Sum('amount'))['amount__sum'] or 0
        fee.amount_paid = total_paid
        fee.balance = fee.amount_payable - total_paid
        
        old_status = fee.payment_status
        fee.update_payment_status()
        
        fee.save(update_fields=['amount_paid', 'balance', 'payment_status', 'last_updated'])
        
        if old_status != fee.payment_status:
            send_websocket_notification(
                fee.student.user.id,
                'FEE',
                'Fee Status Updated',
                f'Your fee status is now {fee.get_payment_status_display()}',
                fee.id
            )
            
        logger.info(f"Updated fee status for {fee.student}: {fee.payment_status}")
        
    except Exception as e:
        logger.error(f"Error updating fee status: {str(e)}")

@receiver(post_delete, sender='core.FeePayment')
def update_fee_after_payment_delete(sender, instance, **kwargs):
    try:
        fee = instance.fee
        total_paid = fee.payments.aggregate(Sum('amount'))['amount__sum'] or 0
        fee.amount_paid = total_paid
        fee.balance = fee.amount_payable - total_paid
        fee.update_payment_status()
        fee.save(update_fields=['amount_paid', 'balance', 'payment_status', 'last_updated'])
        
        logger.info(f"Updated fee status after payment deletion for {fee.student}")
        
    except Exception as e:
        logger.error(f"Error updating fee status on delete: {str(e)}")

@receiver(post_save, sender='core.BillPayment')
def update_bill_status(sender, instance, created, **kwargs):
    try:
        bill = instance.bill
        bill.update_status()
        
        if bill.status == 'paid':
            send_websocket_notification(
                bill.student.user.id,
                'FEE',
                'Bill Paid',
                f'Your bill #{bill.bill_number} has been fully paid',
                bill.id
            )
            
    except Exception as e:
        logger.error(f"Error updating bill status: {str(e)}")

@receiver(post_save, sender='core.StudentAttendance')
def handle_attendance_update(sender, instance, created, **kwargs):
    try:
        if instance.status == 'absent':
            from core.models import ParentGuardian
            parents = ParentGuardian.objects.filter(students=instance.student)
            
            for parent in parents:
                if parent.user:
                    send_websocket_notification(
                        parent.user.id,
                        'ATTENDANCE',
                        'Student Absent',
                        f'{instance.student.get_full_name()} was absent on {instance.date}',
                        instance.id
                    )
                    
    except Exception as e:
        logger.error(f"Error in attendance update signal: {str(e)}")

@receiver(post_save, sender='core.ParentMessage')
def notify_new_parent_message(sender, instance, created, **kwargs):
    if created:
        try:
            from core.models import Notification
            
            Notification.objects.create(
                recipient=instance.receiver,
                notification_type='MESSAGE',
                title='New Message',
                message=f'You have a new message from {instance.sender.get_full_name()}',
                related_object_id=instance.id,
                related_content_type='parentmessage'
            )
            
            send_websocket_notification(
                instance.receiver.id,
                'MESSAGE',
                'New Message',
                f'New message from {instance.sender.get_full_name()}',
                instance.id
            )
            
        except Exception as e:
            logger.error(f"Error creating parent message notification: {str(e)}")

@receiver(post_save, sender='core.Announcement')
def notify_new_announcement(sender, instance, created, **kwargs):
    if created:
        try:
            from core.models import Notification
            from django.contrib.auth import get_user_model
            
            User = get_user_model()
            
            if instance.target_roles == 'ALL':
                users = User.objects.filter(is_active=True)
            elif instance.target_roles == 'STUDENTS':
                users = User.objects.filter(student__isnull=False, is_active=True)
            elif instance.target_roles == 'TEACHERS':
                users = User.objects.filter(teacher__isnull=False, is_active=True)
            elif instance.target_roles == 'ADMINS':
                users = User.objects.filter(is_staff=True, is_active=True)
            else:
                users = User.objects.none()
            
            for user in users:
                Notification.objects.create(
                    recipient=user,
                    notification_type='ANNOUNCEMENT',
                    title='New Announcement',
                    message=instance.title,
                    related_object_id=instance.id,
                    related_content_type='announcement'
                )
                
                send_websocket_notification(
                    user.id,
                    'ANNOUNCEMENT',
                    'New Announcement',
                    instance.title,
                    instance.id
                )
                
            logger.info(f"Created notifications for announcement: {instance.title}")
            
        except Exception as e:
            logger.error(f"Failed to create announcement notifications: {str(e)}")

@receiver(post_save, sender='core.Teacher')
def handle_teacher_save(sender, instance, created, **kwargs):
    try:
        from core.models import AuditLog
        
        request = getattr(instance, '_request', None)
        user = getattr(instance, '_request_user', None) or (request.user if request and hasattr(request, 'user') else None)
        
        if user and user.is_authenticated:
            action = 'CREATE' if created else 'UPDATE'
            log_audit(action, instance, user, request)
            
    except Exception as e:
        logger.error(f"Error in teacher save signal: {str(e)}")

# REMOVED PROBLEMATIC M2M SIGNALS - THEY'RE CAUSING THE ERROR
# @receiver(m2m_changed, sender='core.Teacher.subjects.through')
# def teacher_subjects_changed(sender, instance, action, **kwargs):
#     pass

# @receiver(m2m_changed, sender='core.ParentGuardian.students.through')
# def parent_students_changed(sender, instance, action, **kwargs):
#     pass

@receiver(post_save)
def general_post_save_audit(sender, instance, created, **kwargs):
    if sender._meta.app_label in ['auth', 'admin', 'sessions', 'contenttypes']:
        return
    
    if sender._meta.model_name in ['notification', 'auditlog', 'studentassignment', 'assignment']:
        return
    
    try:
        request = getattr(instance, '_request', None)
        user = getattr(instance, '_request_user', None) or (request.user if request and hasattr(request, 'user') else None)
        
        if user and user.is_authenticated:
            action = 'CREATE' if created else 'UPDATE'
            log_audit(action, instance, user, request)
    except Exception as e:
        logger.debug(f"Audit logging skipped for {sender._meta.model_name}: {str(e)}")

@receiver(post_delete)
def general_post_delete_audit(sender, instance, **kwargs):
    if sender._meta.app_label in ['auth', 'admin', 'sessions', 'contenttypes']:
        return
    
    try:
        request = getattr(instance, '_request', None)
        user = getattr(instance, '_request_user', None) or (request.user if request and hasattr(request, 'user') else None)
        
        if user and user.is_authenticated:
            log_audit('DELETE', instance, user, request)
    except Exception as e:
        logger.debug(f"Delete audit logging skipped for {sender._meta.model_name}: {str(e)}")


def initialize_signals():
    try:
        logger.info("✅ School Management System signals initialized successfully")
    except Exception as e:
        logger.error(f"❌ Error initializing signals: {str(e)}")