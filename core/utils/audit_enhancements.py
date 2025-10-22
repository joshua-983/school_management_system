# core/utils/audit_enhancements.py
from django.core.mail import EmailMessage
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import json
import logging
from datetime import datetime, timedelta
import os

# Import models
from core.models import AuditLog
from core.models import SecurityEvent, AuditAlertRule, AuditReport, DataRetentionPolicy
from django.contrib.auth.models import User

logger = logging.getLogger(__name__)

class RealTimeSecurityMonitor:
    """Real-time security event detection and notification"""
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
    
    def check_security_rules(self, audit_log):
        """Check if audit log triggers any security rules"""
        try:
            active_rules = AuditAlertRule.objects.filter(is_active=True)
            
            for rule in active_rules:
                if self._evaluate_rule(rule, audit_log):
                    self._trigger_alert(rule, audit_log)
        except Exception as e:
            logger.error(f"Error checking security rules: {str(e)}")
    
    def _evaluate_rule(self, rule, audit_log):
        """Evaluate if audit log matches rule conditions"""
        condition_config = rule.condition_config
        
        if rule.condition_type == 'failed_logins':
            return self._check_failed_logins(condition_config, audit_log)
        elif rule.condition_type == 'bulk_operations':
            return self._check_bulk_operations(condition_config, audit_log)
        elif rule.condition_type == 'suspicious_ips':
            return self._check_suspicious_ips(condition_config, audit_log)
        elif rule.condition_type == 'data_exports':
            return self._check_data_exports(condition_config, audit_log)
        
        return False
    
    def _check_failed_logins(self, config, audit_log):
        """Check for failed login patterns"""
        if audit_log.action != 'LOGIN_FAILED':
            return False
        
        # Check recent failed logins from same IP/user
        time_window = config.get('time_window_minutes', 30)
        threshold = config.get('failed_attempts', 5)
        
        since_time = timezone.now() - timedelta(minutes=time_window)
        
        failed_count = AuditLog.objects.filter(
            action='LOGIN_FAILED',
            ip_address=audit_log.ip_address,
            timestamp__gte=since_time
        ).count()
        
        return failed_count >= threshold
    
    def _check_bulk_operations(self, config, audit_log):
        """Check for suspicious bulk operations"""
        if audit_log.action != 'DELETE':
            return False
        
        time_window = config.get('time_window_minutes', 10)
        threshold = config.get('delete_count', 10)
        
        since_time = timezone.now() - timedelta(minutes=time_window)
        
        delete_count = AuditLog.objects.filter(
            user=audit_log.user,
            action='DELETE',
            model_name=audit_log.model_name,
            timestamp__gte=since_time
        ).count()
        
        return delete_count >= threshold
    
    def _check_suspicious_ips(self, config, audit_log):
        """Check for suspicious IP activity"""
        suspicious_ips = config.get('suspicious_ips', [])
        return audit_log.ip_address in suspicious_ips
    
    def _check_data_exports(self, config, audit_log):
        """Check for large data exports"""
        if 'export' not in str(audit_log.details).lower():
            return False
        
        # You might need to parse export size from details
        export_size_threshold = config.get('export_size_mb', 10)
        # Implementation depends on how you track export sizes
        
        return True
    
    def _trigger_alert(self, rule, audit_log):
        """Create security event and send notifications"""
        try:
            # Create security event
            event = SecurityEvent.objects.create(
                rule=rule,
                event_type=self._map_rule_to_event_type(rule.condition_type),
                severity=rule.severity,
                title=f"Security Alert: {rule.name}",
                description=f"Rule triggered by user {audit_log.user.username if audit_log.user else 'Unknown'}",
                user=audit_log.user,
                ip_address=audit_log.ip_address,
                details={
                    'audit_log_id': audit_log.id,
                    'rule_condition': rule.condition_type,
                    'timestamp': audit_log.timestamp.isoformat()
                }
            )
            
            # Send real-time notification
            self._send_real_time_alert(event)
            
            # Send email if configured
            if rule.action in ['EMAIL', 'BOTH']:
                self._send_email_alert(event, rule)
            
            # Lock user account if critical
            if rule.action == 'LOCK' and rule.severity == 'CRITICAL':
                self._lock_user_account(audit_log.user)
                
        except Exception as e:
            logger.error(f"Error triggering alert: {str(e)}")
    
    def _map_rule_to_event_type(self, condition_type):
        """Map rule condition type to event type"""
        mapping = {
            'failed_logins': 'FAILED_LOGIN',
            'bulk_operations': 'BULK_DELETE',
            'suspicious_ips': 'SUSPICIOUS_IP',
            'data_exports': 'DATA_EXPORT',
            'unauthorized_access': 'UNAUTHORIZED_ACCESS'
        }
        return mapping.get(condition_type, 'SYSTEM_ERROR')
    
    def _send_real_time_alert(self, event):
        """Send real-time WebSocket notification"""
        try:
            async_to_sync(self.channel_layer.group_send)(
                'security_alerts',
                {
                    'type': 'security_alert',
                    'event': {
                        'id': event.id,
                        'title': event.title,
                        'severity': event.severity,
                        'timestamp': event.created_at.isoformat(),
                        'user': event.user.username if event.user else 'Unknown',
                    }
                }
            )
        except Exception as e:
            logger.error(f"Failed to send real-time alert: {str(e)}")
    
    def _send_email_alert(self, event, rule):
        """Send email notification for security event"""
        try:
            subject = f"Security Alert: {event.title}"
            context = {'event': event, 'rule': rule}
            html_message = render_to_string('core/emails/security_alert.html', context)
            
            email = EmailMessage(
                subject=subject,
                body=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=[admin[1] for admin in settings.ADMINS],
            )
            email.content_subtype = "html"
            email.send()
            
        except Exception as e:
            logger.error(f"Failed to send email alert: {str(e)}")
    
    def _lock_user_account(self, user):
        """Lock user account for critical security events"""
        if user:
            user.is_active = False
            user.save()
            logger.info(f"Locked user account: {user.username}")

class AdvancedAuditAnalytics:
    """Machine learning and advanced analytics for audit data"""
    
    def detect_anomalies(self, days=30):
        """Use Isolation Forest to detect anomalous user behavior"""
        try:
            # Get recent audit data
            since_date = timezone.now() - timedelta(days=days)
            audit_data = AuditLog.objects.filter(timestamp__gte=since_date)
            
            # For now, return empty list - implement ML later
            # This is a placeholder for actual ML implementation
            return []
            
        except Exception as e:
            logger.error(f"Error in anomaly detection: {str(e)}")
            return []
    
    def predict_risk_scores(self, users):
        """Predict risk scores for users based on behavior patterns"""
        risk_scores = {}
        
        for user in users:
            # Calculate risk score based on various factors
            score = self._calculate_user_risk_score(user)
            risk_scores[user.id] = score
        
        return risk_scores
    
    def _calculate_user_risk_score(self, user):
        """Calculate comprehensive risk score for a user"""
        score = 0
        
        try:
            # Factor 1: Failed login attempts
            failed_logins = AuditLog.objects.filter(
                user=user, action='LOGIN_FAILED',
                timestamp__gte=timezone.now() - timedelta(days=7)
            ).count()
            score += min(failed_logins * 10, 50)  # Max 50 points
            
            # Factor 2: Bulk operations
            bulk_deletes = AuditLog.objects.filter(
                user=user, action='DELETE',
                timestamp__gte=timezone.now() - timedelta(days=1)
            ).count()
            if bulk_deletes > 10:
                score += 30
            
            # Factor 3: Unusual access times
            unusual_hours = AuditLog.objects.filter(
                user=user,
                timestamp__hour__in=[0, 1, 2, 3, 4, 5],  # Late night hours
                timestamp__gte=timezone.now() - timedelta(days=30)
            ).count()
            if unusual_hours > 5:
                score += 20
                
        except Exception as e:
            logger.error(f"Error calculating risk score for user {user.id}: {str(e)}")
        
        return min(score, 100)  # Cap at 100

class AuditReportGenerator:
    """Generate automated PDF and email reports"""
    
    def generate_daily_report(self):
        """Generate daily security report"""
        try:
            today = timezone.now().date()
            
            report_data = {
                'date': today,
                'total_actions': AuditLog.objects.filter(timestamp__date=today).count(),
                'security_events': SecurityEvent.objects.filter(created_at__date=today).count(),
                'failed_logins': AuditLog.objects.filter(
                    action='LOGIN_FAILED', timestamp__date=today
                ).count(),
                'top_users': self._get_top_users(today),
                'suspicious_activity': self._get_suspicious_activity(today),
            }
            
            # Generate PDF
            pdf_path = self._generate_pdf_report('daily', report_data)
            
            # Save report record
            report = AuditReport.objects.create(
                name=f"Daily Security Report - {today}",
                report_type='DAILY',
                parameters=report_data,
                generated_by=User.objects.filter(is_superuser=True).first(),
                file_path=pdf_path,
                is_scheduled=True,
                email_recipients=','.join([admin[1] for admin in settings.ADMINS])
            )
            
            # Send email
            self._send_report_email(report, pdf_path)
            
            return report
            
        except Exception as e:
            logger.error(f"Error generating daily report: {str(e)}")
            return None
    
    def _get_top_users(self, date):
        """Get top users by activity for the day"""
        from django.db.models import Count
        return list(AuditLog.objects.filter(
            timestamp__date=date
        ).values('user__username').annotate(
            count=Count('id')
        ).order_by('-count')[:10])
    
    def _get_suspicious_activity(self, date):
        """Get suspicious activity for the day"""
        return {
            'failed_logins': AuditLog.objects.filter(
                action='LOGIN_FAILED', timestamp__date=date
            ).count(),
            'bulk_deletes': AuditLog.objects.filter(
                action='DELETE', timestamp__date=date
            ).count(),
        }
    
    def _generate_pdf_report(self, report_type, data):
        """Generate PDF report - placeholder implementation"""
        # For now, return None - implement PDF generation later
        return None
    
    def _send_report_email(self, report, attachment_path):
        """Send report via email"""
        try:
            subject = f"Automated Report: {report.name}"
            context = {'report': report}
            html_message = render_to_string('core/emails/automated_report.html', context)
            
            email = EmailMessage(
                subject=subject,
                body=html_message,
                from_email=settings.DEFAULT_FROM_EMAIL,
                to=report.email_recipients.split(','),
            )
            
            # Attach PDF if generated
            if attachment_path and os.path.exists(attachment_path):
                email.attach_file(attachment_path)
            
            email.content_subtype = "html"
            email.send()
            
        except Exception as e:
            logger.error(f"Failed to send report email: {str(e)}")

class DataRetentionManager:
    """Manage data retention policies and archiving"""
    
    def apply_retention_policies(self):
        """Apply all active data retention policies"""
        policies = DataRetentionPolicy.objects.filter(is_active=True)
        
        for policy in policies:
            self._apply_policy(policy)
    
    def _apply_policy(self, policy):
        """Apply a specific retention policy"""
        try:
            if policy.retention_days == 0:  # Never delete
                return
                
            cutoff_date = timezone.now() - timedelta(days=policy.retention_days)
            
            # Get the actual model class
            from django.apps import apps
            try:
                model_class = apps.get_model('core', policy.model_name)
            except LookupError:
                logger.error(f"Model not found: {policy.model_name}")
                return
            
            # Archive records if configured
            if policy.archive_before_delete:
                self._archive_records(model_class, cutoff_date, policy)
            
            # Delete old records
            deleted_count = model_class.objects.filter(
                created_at__lt=cutoff_date
            ).delete()[0]
            
            # Update policy last run
            policy.last_run = timezone.now()
            policy.records_deleted += deleted_count
            policy.save()
            
            logger.info(f"Applied retention policy {policy.name}: deleted {deleted_count} records")
            
        except Exception as e:
            logger.error(f"Error applying retention policy {policy.name}: {str(e)}")
    
    def _archive_records(self, model_class, cutoff_date, policy):
        """Archive records before deletion - placeholder implementation"""
        try:
            # This is a placeholder - implement actual archiving logic
            records = model_class.objects.filter(created_at__lt=cutoff_date)
            logger.info(f"Would archive {records.count()} records for {policy.model_name}")
            
        except Exception as e:
            logger.error(f"Failed to archive records: {str(e)}")