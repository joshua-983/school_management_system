# core/services/automation.py
import logging
from datetime import datetime, timedelta
from decimal import Decimal
from django.utils import timezone
from django.db import transaction
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string

from core.models import Fee, Bill, Student, FeePayment, AcademicTerm
from core.models.audit import FinancialAuditTrail
from core.utils.financial import FinancialCalculator

logger = logging.getLogger(__name__)


class FinancialAutomationService:
    """Automate financial processes"""
    
    def __init__(self):
        self.calculator = FinancialCalculator()
    
    def generate_term_fees_automatically(self):
        """Automatically generate fees for new term"""
        try:
            current_term = AcademicTerm.objects.filter(is_active=True).first()
            if not current_term:
                logger.warning("No active academic term found")
                return 0
            
            # Get all active students
            students = Student.objects.filter(is_active=True)
            
            # Get mandatory fee categories
            categories = FeeCategory.objects.filter(
                is_active=True,
                is_mandatory=True
            )
            
            created_count = 0
            errors = []
            
            with transaction.atomic():
                for student in students:
                    try:
                        for category in categories:
                            # Check if category applies to student's class
                            if not category.is_applicable_to_class(student.class_level):
                                continue
                            
                            # Check if fee already exists
                            if Fee.objects.filter(
                                student=student,
                                category=category,
                                academic_year=current_term.academic_year,
                                term=current_term.term
                            ).exists():
                                continue
                            
                            # Calculate due date (e.g., 2 weeks after term starts)
                            due_date = current_term.start_date + timedelta(days=14)
                            
                            # Create the fee
                            fee = Fee.objects.create(
                                student=student,
                                category=category,
                                academic_year=current_term.academic_year,
                                term=current_term.term,
                                amount_payable=category.default_amount,
                                due_date=due_date,
                                recorded_by=None,  # System action
                                payment_status='unpaid'
                            )
                            
                            # Log automation
                            FinancialAuditTrail.log_action(
                                action='CREATE',
                                model_name='Fee',
                                object_id=fee.id,
                                user=None,
                                notes=f'Auto-generated fee for {student.get_full_name()} - {category.get_name_display()}'
                            )
                            
                            created_count += 1
                            
                    except Exception as e:
                        errors.append(f"Student {student.student_id}: {str(e)}")
                        logger.error(f"Error generating fee for student {student.student_id}: {str(e)}")
                        continue
            
            logger.info(f"Auto-generated {created_count} fee records")
            
            # Send notification if many errors
            if errors and len(errors) > 10:
                self._send_automation_alert(
                    "Fee Generation Errors",
                    f"Encountered {len(errors)} errors during fee generation"
                )
            
            return created_count
            
        except Exception as e:
            logger.error(f"Error in auto fee generation: {str(e)}")
            return 0
    
    def send_payment_reminders(self, days_before=7):
        """Send payment reminders for upcoming due dates"""
        try:
            reminder_date = timezone.now().date() + timedelta(days=days_before)
            
            # Find fees due on reminder date
            due_fees = Fee.objects.filter(
                due_date=reminder_date,
                payment_status__in=['unpaid', 'partial']
            ).select_related('student', 'category')
            
            reminder_count = 0
            
            for fee in due_fees:
                try:
                    # Check if reminder already sent today
                    if self._reminder_already_sent_today(fee):
                        continue
                    
                    # Send reminder
                    self._send_fee_reminder(fee, days_before)
                    
                    # Log reminder
                    FinancialAuditTrail.log_action(
                        action='REMINDER',
                        model_name='Fee',
                        object_id=fee.id,
                        user=None,
                        notes=f'Payment reminder sent for {fee.student.get_full_name()} - Due in {days_before} days'
                    )
                    
                    reminder_count += 1
                    
                except Exception as e:
                    logger.error(f"Error sending reminder for fee {fee.id}: {str(e)}")
                    continue
            
            logger.info(f"Sent {reminder_count} payment reminders")
            return reminder_count
            
        except Exception as e:
            logger.error(f"Error in payment reminders: {str(e)}")
            return 0
    
    def send_overdue_notifications(self):
        """Send notifications for overdue payments"""
        try:
            overdue_fees = Fee.objects.filter(
                payment_status='overdue',
                due_date__lt=timezone.now().date()
            ).select_related('student', 'category')
            
            notification_count = 0
            
            for fee in overdue_fees:
                try:
                    # Check last notification date
                    if self._overdue_notification_recent(fee):
                        continue
                    
                    # Send overdue notification
                    self._send_overdue_notification(fee)
                    
                    # Log notification
                    FinancialAuditTrail.log_action(
                        action='OVERDUE_NOTIFICATION',
                        model_name='Fee',
                        object_id=fee.id,
                        user=None,
                        notes=f'Overdue notification sent for {fee.student.get_full_name()}'
                    )
                    
                    notification_count += 1
                    
                except Exception as e:
                    logger.error(f"Error sending overdue notification for fee {fee.id}: {str(e)}")
                    continue
            
            # Also check for overdue bills
            overdue_bills = Bill.objects.filter(
                status='overdue',
                due_date__lt=timezone.now().date()
            ).select_related('student')
            
            for bill in overdue_bills:
                try:
                    self._send_bill_overdue_notification(bill)
                    notification_count += 1
                except Exception as e:
                    logger.error(f"Error sending overdue notification for bill {bill.id}: {str(e)}")
                    continue
            
            logger.info(f"Sent {notification_count} overdue notifications")
            return notification_count
            
        except Exception as e:
            logger.error(f"Error in overdue notifications: {str(e)}")
            return 0
    
    def update_overdue_statuses(self):
        """Update status of overdue fees and bills"""
        try:
            current_date = timezone.now().date()
            
            # Update overdue fees
            overdue_fees = Fee.objects.filter(
                due_date__lt=current_date,
                payment_status__in=['unpaid', 'partial']
            )
            
            updated_fee_count = overdue_fees.update(payment_status='overdue')
            
            # Update overdue bills
            overdue_bills = Bill.objects.filter(
                due_date__lt=current_date,
                status__in=['issued', 'partial']
            )
            
            updated_bill_count = overdue_bills.update(status='overdue')
            
            if updated_fee_count > 0 or updated_bill_count > 0:
                logger.info(f"Updated {updated_fee_count} fees and {updated_bill_count} bills to overdue")
                
                # Log bulk update
                FinancialAuditTrail.log_action(
                    action='BULK_UPDATE',
                    model_name='System',
                    object_id='overdue_update',
                    user=None,
                    notes=f'Auto-updated {updated_fee_count} fees and {updated_bill_count} bills to overdue status'
                )
            
            return updated_fee_count + updated_bill_count
            
        except Exception as e:
            logger.error(f"Error updating overdue statuses: {str(e)}")
            return 0
    
    def generate_monthly_financial_report(self):
        """Generate and send monthly financial report"""
        try:
            # Calculate date range
            today = timezone.now().date()
            first_day_of_month = today.replace(day=1)
            last_day_of_prev_month = first_day_of_month - timedelta(days=1)
            first_day_of_prev_month = last_day_of_prev_month.replace(day=1)
            
            # Generate report data
            from core.services.financial_reports import FinancialReportGenerator
            
            report_generator = FinancialReportGenerator()
            income_statement = report_generator.generate_income_statement(
                first_day_of_prev_month, last_day_of_prev_month
            )
            
            cash_flow = report_generator.generate_cash_flow_statement(
                first_day_of_prev_month, last_day_of_prev_month
            )
            
            arrears_report = report_generator.generate_student_arrears_report()
            
            # Prepare report
            report_data = {
                'month': last_day_of_prev_month.strftime('%B %Y'),
                'period': f"{first_day_of_prev_month.strftime('%d/%m/%Y')} - {last_day_of_prev_month.strftime('%d/%m/%Y')}",
                'income_statement': income_statement,
                'cash_flow': cash_flow,
                'arrears_summary': {
                    'total_students': arrears_report['total_students'],
                    'total_amount': arrears_report['total_arrears'],
                    'top_5_students': arrears_report['students'][:5]
                },
                'key_metrics': self._calculate_monthly_metrics(income_statement, cash_flow, arrears_report)
            }
            
            # Send report to administrators
            self._send_monthly_report(report_data)
            
            # Log report generation
            FinancialAuditTrail.log_action(
                action='REPORT',
                model_name='FinancialReport',
                object_id=f"monthly_{last_day_of_prev_month.strftime('%Y%m')}",
                user=None,
                notes=f'Monthly financial report generated for {last_day_of_prev_month.strftime("%B %Y")}'
            )
            
            logger.info(f"Generated monthly financial report for {last_day_of_prev_month.strftime('%B %Y')}")
            return True
            
        except Exception as e:
            logger.error(f"Error generating monthly report: {str(e)}")
            return False
    
    # Helper methods
    def _send_fee_reminder(self, fee, days_before):
        """Send fee payment reminder"""
        student = fee.student
        parent_email = student.parent_email
        
        if not parent_email:
            logger.warning(f"No parent email for student {student.student_id}")
            return
        
        # Prepare email content
        context = {
            'student': student,
            'fee': fee,
            'days_before': days_before,
            'due_date': fee.due_date,
            'amount': fee.balance,
            'school_name': getattr(settings, 'SCHOOL_NAME', 'Our School'),
            'contact_email': getattr(settings, 'SCHOOL_EMAIL', 'accounts@school.edu.gh')
        }
        
        subject = f"Payment Reminder: {fee.category.get_name_display()} - Due in {days_before} days"
        html_message = render_to_string('core/emails/fee_reminder.html', context)
        plain_message = render_to_string('core/emails/fee_reminder.txt', context)
        
        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'noreply@school.edu.gh'),
                recipient_list=[parent_email],
                html_message=html_message,
                fail_silently=False
            )
            
            logger.info(f"Sent reminder to {parent_email} for fee {fee.id}")
            
        except Exception as e:
            logger.error(f"Error sending reminder email: {str(e)}")
            raise
    
    def _send_overdue_notification(self, fee):
        """Send overdue payment notification"""
        student = fee.student
        parent_email = student.parent_email
        
        if not parent_email:
            return
        
        # Calculate days overdue
        days_overdue = (timezone.now().date() - fee.due_date).days
        
        context = {
            'student': student,
            'fee': fee,
            'days_overdue': days_overdue,
            'amount': fee.balance,
            'late_fee': self._calculate_late_fee(fee.balance, days_overdue),
            'school_name': getattr(settings, 'SCHOOL_NAME', 'Our School'),
            'contact_phone': getattr(settings, 'SCHOOL_PHONE', ''),
            'payment_options': self._get_payment_options()
        }
        
        subject = f"URGENT: Overdue Payment - {fee.category.get_name_display()}"
        html_message = render_to_string('core/emails/overdue_notification.html', context)
        plain_message = render_to_string('core/emails/overdue_notification.txt', context)
        
        try:
            send_mail(
                subject=subject,
                message=plain_message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL'),
                recipient_list=[parent_email],
                html_message=html_message,
                fail_silently=False
            )
            
        except Exception as e:
            logger.error(f"Error sending overdue notification: {str(e)}")
            raise
    
    def _calculate_late_fee(self, balance, days_overdue):
        """Calculate late fee penalty"""
        # Example: 1% per month or GH₵50 minimum
        if days_overdue > 30:
            months_overdue = days_overdue // 30
            late_fee = balance * Decimal('0.01') * months_overdue
            return max(late_fee, Decimal('50.00'))
        return Decimal('0.00')
    
    def _reminder_already_sent_today(self, fee):
        """Check if reminder was already sent today"""
        # Check in audit trail
        today = timezone.now().date()
        
        from core.models.audit import FinancialAuditTrail
        return FinancialAuditTrail.objects.filter(
            model_name='Fee',
            object_id=fee.id,
            action='REMINDER',
            timestamp__date=today
        ).exists()
    
    def _overdue_notification_recent(self, fee):
        """Check if overdue notification was sent recently (within 7 days)"""
        seven_days_ago = timezone.now() - timedelta(days=7)
        
        from core.models.audit import FinancialAuditTrail
        return FinancialAuditTrail.objects.filter(
            model_name='Fee',
            object_id=fee.id,
            action='OVERDUE_NOTIFICATION',
            timestamp__gte=seven_days_ago
        ).exists()
    
    def _send_automation_alert(self, subject, message):
        """Send alert about automation issues"""
        admin_emails = getattr(settings, 'ADMIN_EMAILS', [])
        
        if admin_emails:
            try:
                send_mail(
                    subject=f"[AUTOMATION ALERT] {subject}",
                    message=message,
                    from_email=getattr(settings, 'DEFAULT_FROM_EMAIL'),
                    recipient_list=admin_emails,
                    fail_silently=True
                )
            except Exception as e:
                logger.error(f"Error sending automation alert: {str(e)}")