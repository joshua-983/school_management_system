# core/utils.py
from django.apps import apps
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
from django.contrib.auth.models import Group
from django.core.mail import send_mail
from django.conf import settings
from django.template.loader import render_to_string
from django.utils.html import strip_tags

def send_email(subject, message, recipient, html_message=None, from_email=None):
    """
    Send an email using Django's email backend
    
    Args:
        subject: Email subject
        message: Plain text message
        recipient: Email recipient or list of recipients
        html_message: Optional HTML content
        from_email: Optional sender email (uses DEFAULT_FROM_EMAIL if not provided)
    """
    try:
        if from_email is None:
            from_email = settings.DEFAULT_FROM_EMAIL
        
        send_mail(
            subject=subject,
            message=message,
            from_email=from_email,
            recipient_list=[recipient] if isinstance(recipient, str) else recipient,
            html_message=html_message,
            fail_silently=False,
        )
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        # You might want to log this error in production
        return False

def send_email_template(subject, template_name, context, recipient, from_email=None):
    """
    Send an email using a Django template
    
    Args:
        subject: Email subject
        template_name: Path to the template (e.g., 'emails/payment_reminder.html')
        context: Context data for the template
        recipient: Email recipient
        from_email: Optional sender email
    """
    try:
        # Render HTML content from template
        html_message = render_to_string(template_name, context)
        # Create plain text version by stripping HTML tags
        plain_message = strip_tags(html_message)
        
        return send_email(
            subject=subject,
            message=plain_message,
            recipient=recipient,
            html_message=html_message,
            from_email=from_email
        )
    except Exception as e:
        print(f"Error sending template email: {e}")
        return False

def send_notification(recipient, notification_type, title, message, related_object=None):
    """
    Create and send a notification
    Args:
        recipient: User object
        notification_type: One of 'GRADE', 'FEE', 'ASSIGNMENT', 'GENERAL'
        title: Notification title
        message: Notification message
        related_object: Optional related object for linking
    """
    # Create notification
    notification = Notification.objects.create(
        recipient=recipient,
        notification_type=notification_type,
        title=title,
        message=message,
        related_object_id=related_object.id if related_object else None,
        related_content_type=related_object.__class__.__name__ if related_object else ''
    )
    
    # Send via WebSocket
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f'notifications_{recipient.id}',
        {
            'type': 'send_notification',
            'notification_type': notification_type,
            'title': title,
            'message': message,
            'notification_id': notification.id
        }
    )
    
    return notification

def is_admin(user):
    return user.is_authenticated and (user.is_superuser or hasattr(user, 'admin'))

def is_teacher(user):
    return user.is_authenticated and hasattr(user, 'teacher')

def is_student(user):
    return user.is_authenticated and hasattr(user, 'student_profile')

def is_parent(user):
    return user.is_authenticated and hasattr(user, 'parentguardian')

#audit_enhancements
class RealTimeSecurityMonitor:
    """Real-time security event detection and notification"""
    
    def __init__(self):
        self.channel_layer = get_channel_layer()
    
    def check_security_rules(self, audit_log):
        """Check if audit log triggers any security rules"""
        active_rules = AuditAlertRule.objects.filter(is_active=True)
        
        for rule in active_rules:
            if self._evaluate_rule(rule, audit_log):
                self._trigger_alert(rule, audit_log)
    
    def _evaluate_rule(self, rule, audit_log):
        """Evaluate if audit log matches rule conditions"""
        condition_config = rule.condition_config
        
        if rule.condition_type == 'failed_logins':
            return self._check_failed_logins(condition_config, audit_log)
        elif rule.condition_type == 'bulk_operations':
            return self._check_bulk_operations(condition_config, audit_log)
        elif rule.condition_type == 'suspicious_ips':
            return self._check_suspicious_ips(condition_config, audit_log)
        elif rule.condition_type == 'data_export':
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
        if 'export' not in audit_log.details.lower():
            return False
        
        # You might need to parse export size from details
        export_size_threshold = config.get('export_size_mb', 10)
        # Implementation depends on how you track export sizes
        
        return True
    
    def _trigger_alert(self, rule, audit_log):
        """Create security event and send notifications"""
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
        # Get recent audit data
        since_date = timezone.now() - timedelta(days=days)
        audit_data = AuditLog.objects.filter(timestamp__gte=since_date)
        
        # Prepare features for ML
        features = self._prepare_features(audit_data)
        
        if len(features) < 10:  # Need minimum data
            return []
        
        # Train Isolation Forest model
        clf = IsolationForest(contamination=0.1, random_state=42)
        predictions = clf.fit_predict(features)
        
        # Get anomalous records
        anomalies = [i for i, pred in enumerate(predictions) if pred == -1]
        
        return anomalies
    
    def _prepare_features(self, audit_data):
        """Prepare features for machine learning"""
        # This is a simplified example - you'd want more sophisticated features
        features = []
        
        for log in audit_data:
            feature_vector = [
                log.user.id if log.user else 0,
                self._action_to_numeric(log.action),
                len(log.details) if log.details else 0,
                log.timestamp.hour,  # Time-based feature
            ]
            features.append(feature_vector)
        
        return np.array(features)
    
    def _action_to_numeric(self, action):
        """Convert action string to numeric value"""
        action_map = {'CREATE': 1, 'UPDATE': 2, 'DELETE': 3, 'LOGIN': 4, 'LOGIN_FAILED': 5}
        return action_map.get(action, 0)
    
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
        
        return min(score, 100)  # Cap at 100

class AuditReportGenerator:
    """Generate automated PDF and email reports"""
    
    def generate_daily_report(self):
        """Generate daily security report"""
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
    
    def _generate_pdf_report(self, report_type, data):
        """Generate PDF report using ReportLab"""
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import letter
            from reportlab.lib.units import inch
            import os
            
            # Create reports directory
            reports_dir = os.path.join(settings.MEDIA_ROOT, 'reports')
            os.makedirs(reports_dir, exist_ok=True)
            
            filename = f"{report_type}_report_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            filepath = os.path.join(reports_dir, filename)
            
            # Create PDF
            c = canvas.Canvas(filepath, pagesize=letter)
            width, height = letter
            
            # Add content
            c.setFont("Helvetica-Bold", 16)
            c.drawString(1*inch, height-1*inch, f"Security Audit Report")
            c.setFont("Helvetica", 12)
            c.drawString(1*inch, height-1.5*inch, f"Date: {data['date']}")
            c.drawString(1*inch, height-2*inch, f"Total Actions: {data['total_actions']}")
            c.drawString(1*inch, height-2.5*inch, f"Security Events: {data['security_events']}")
            
            c.save()
            
            return filepath
            
        except ImportError:
            logger.error("ReportLab not installed for PDF generation")
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
        cutoff_date = timezone.now() - timedelta(days=policy.retention_days)
        
        # Get the actual model class
        try:
            from django.apps import apps
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
        policy.save()
        
        logger.info(f"Applied retention policy {policy.name}: deleted {deleted_count} records")
    
    def _archive_records(self, model_class, cutoff_date, policy):
        """Archive records before deletion"""
        try:
            import pandas as pd
            import os
            
            # Get records to archive
            records = model_class.objects.filter(created_at__lt=cutoff_date)
            
            if records.exists():
                # Convert to DataFrame for easy storage
                data = list(records.values())
                df = pd.DataFrame(data)
                
                # Create archive directory
                archive_dir = os.path.join(settings.MEDIA_ROOT, 'archive')
                os.makedirs(archive_dir, exist_ok=True)
                
                # Save as Parquet (efficient for large datasets)
                filename = f"{policy.model_name}_archive_{timezone.now().strftime('%Y%m%d')}.parquet"
                filepath = os.path.join(archive_dir, filename)
                
                df.to_parquet(filepath)
                
                logger.info(f"Archived {len(records)} records to {filepath}")
                
        except Exception as e:
            logger.error(f"Failed to archive records: {str(e)}")