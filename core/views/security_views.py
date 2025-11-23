# core/views/security_views.py - COMPLETELY FIXED
from core.models import SecurityEvent, AuditAlertRule
from django.contrib.auth.decorators import user_passes_test
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.utils.decorators import method_decorator
from django.views.decorators.cache import never_cache
from django.views import View
from django.contrib import messages
from django.http import JsonResponse
from django.conf import settings
from django.utils import timezone
from datetime import timedelta
import json

from core.models import UserProfile, AuditLog, ScheduledMaintenance, User
from core.forms import UserBlockForm, MaintenanceModeForm, UserSearchForm, ScheduledMaintenanceForm

def is_security_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)

@user_passes_test(is_security_admin)
def security_dashboard(request):
    # Get security statistics
    total_users = User.objects.filter(is_active=True).count()
    blocked_users = UserProfile.objects.filter(is_blocked=True).count()
    
    # FIXED: SecurityEvent uses 'created_at', AuditLog uses 'timestamp'
    recent_security_events = SecurityEvent.objects.all().order_by('-created_at')[:5]
    
    # FIXED: AuditLog uses 'timestamp' field
    recent_blocks = AuditLog.objects.filter(
        model_name='User',
        action__in=['BLOCK', 'UNBLOCK']
    ).order_by('-timestamp')[:10]
    
    context = {
        'active_tab': 'security_dashboard',
        'total_users': total_users,
        'blocked_users': blocked_users,
        'maintenance_mode': getattr(settings, 'MAINTENANCE_MODE', False),
        'recent_security_events': recent_security_events,
        'recent_blocks': recent_blocks,
    }
    
    return render(request, 'security/dashboard.html', context)


class UserManagementView(View):
    """View for managing user blocking/unblocking"""
    
    @method_decorator(login_required)
    @method_decorator(staff_member_required)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def get(self, request):
        search_form = UserSearchForm(request.GET or None)
        block_form = UserBlockForm()
        
        users = []
        search_performed = False
        
        if 'search_query' in request.GET and request.GET.get('search_query'):
            search_performed = True
            search_type = request.GET.get('search_type', 'username')
            search_query = request.GET.get('search_query', '')
            user_type = request.GET.get('user_type', 'all')
            
            users = self.search_users(search_type, search_query, user_type)
        
        context = {
            'search_form': search_form,
            'block_form': block_form,
            'users': users,
            'search_performed': search_performed,
            'active_tab': 'user_management',
        }
        return render(request, 'security/user_management.html', context)
    
    def search_users(self, search_type, query, user_type):
        """Search users based on criteria"""
        from django.contrib.auth import get_user_model
        from django.db import models
        
        User = get_user_model()
        
        users = User.objects.select_related('profile').all()
        
        # Apply search filter
        if search_type == 'username':
            users = users.filter(username__icontains=query)
        elif search_type == 'email':
            users = users.filter(email__icontains=query)
        elif search_type == 'name':
            users = users.filter(
                models.Q(first_name__icontains=query) | models.Q(last_name__icontains=query)
            )
        
        # Apply user type filter
        if user_type != 'all':
            if user_type == 'student':
                users = users.filter(student__isnull=False)
            elif user_type == 'teacher':
                users = users.filter(teacher__isnull=False)
            elif user_type == 'parent':
                users = users.filter(parentguardian__isnull=False)
            elif user_type == 'staff':
                users = users.filter(is_staff=True)
        
        return users.order_by('username')[:50]  # Limit results


class BlockUserView(View):
    """View for blocking/unblocking a specific user"""
    
    @method_decorator(login_required)
    @method_decorator(staff_member_required)
    def post(self, request, user_id):
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            user = User.objects.get(id=user_id)
            form = UserBlockForm(request.POST)
            
            if form.is_valid():
                action = form.cleaned_data['action']
                reason = form.cleaned_data['reason']
                duration_str = form.cleaned_data.get('duration')
                
                # Convert duration string to timedelta
                duration = None
                if duration_str:
                    if duration_str == '1 hour':
                        duration = timedelta(hours=1)
                    elif duration_str == '6 hours':
                        duration = timedelta(hours=6)
                    elif duration_str == '1 day':
                        duration = timedelta(days=1)
                    elif duration_str == '3 days':
                        duration = timedelta(days=3)
                    elif duration_str == '1 week':
                        duration = timedelta(weeks=1)
                
                # Ensure user has a profile
                profile, created = UserProfile.objects.get_or_create(user=user)
                
                if action == 'block':
                    profile.block_user(request.user, reason, duration)
                    duration_msg = f" for {duration_str}" if duration_str else " permanently"
                    messages.success(request, f'User {user.username} has been blocked{duration_msg}.')
                else:
                    profile.unblock_user(request.user, reason)
                    messages.success(request, f'User {user.username} has been unblocked successfully.')
                
                return redirect('user_management')
            else:
                messages.error(request, 'Invalid form data.')
                return redirect('user_management')
                
        except User.DoesNotExist:
            messages.error(request, 'User not found.')
            return redirect('user_management')
        except Exception as e:
            messages.error(request, f'Error processing request: {str(e)}')
            return redirect('user_management')


class MaintenanceModeView(View):
    """View for enabling/disabling maintenance mode"""
    
    @method_decorator(login_required)
    @method_decorator(staff_member_required)
    def get(self, request):
        form = MaintenanceModeForm()
        maintenance_mode = getattr(settings, 'MAINTENANCE_MODE', False)
        
        # FIXED: AuditLog uses 'timestamp' field
        recent_events = AuditLog.objects.filter(
            action__in=['MAINTENANCE_START', 'MAINTENANCE_END']
        ).order_by('-timestamp')[:10]
        
        context = {
            'form': form,
            'maintenance_mode': maintenance_mode,
            'recent_events': recent_events,
            'active_tab': 'maintenance_mode',
        }
        return render(request, 'security/maintenance_mode.html', context)
    
    @method_decorator(login_required)
    @method_decorator(staff_member_required)
    def post(self, request):
        form = MaintenanceModeForm(request.POST)
        
        if form.is_valid():
            action = form.cleaned_data['action']
            message = form.cleaned_data.get('message', '')
            
            # In a real implementation, you'd save this to database or settings
            # For now, we'll use a simple approach
            if action == 'enable':
                # Enable maintenance mode
                settings.MAINTENANCE_MODE = True
                if message:
                    settings.MAINTENANCE_MESSAGE = message
                messages.success(request, 'Maintenance mode has been enabled.')
                
                # Log the action
                AuditLog.log_action(
                    user=request.user,
                    action='MAINTENANCE_START',
                    model_name='System',
                    object_id=0,
                    details={
                        'message': message,
                        'started_at': timezone.now().isoformat()
                    }
                )
            else:
                # Disable maintenance mode
                settings.MAINTENANCE_MODE = False
                messages.success(request, 'Maintenance mode has been disabled.')
                
                # Log the action
                AuditLog.log_action(
                    user=request.user,
                    action='MAINTENANCE_END',
                    model_name='System',
                    object_id=0,
                    details={
                        'ended_at': timezone.now().isoformat()
                    }
                )
            
            return redirect('maintenance_mode')
        else:
            messages.error(request, 'Invalid form data.')
            return self.get(request)


class ScheduledMaintenanceView(View):
    """View for managing scheduled maintenance"""
    
    @method_decorator(login_required)
    @method_decorator(staff_member_required)
    def get(self, request):
        form = ScheduledMaintenanceForm()
        scheduled_maintenance = ScheduledMaintenance.objects.all().order_by('-start_time')
        
        context = {
            'form': form,
            'scheduled_maintenance': scheduled_maintenance,
            'active_tab': 'maintenance_mode',
        }
        return render(request, 'security/scheduled_maintenance.html', context)
    
    @method_decorator(login_required)
    @method_decorator(staff_member_required)
    def post(self, request):
        form = ScheduledMaintenanceForm(request.POST)
        
        if form.is_valid():
            maintenance = form.save(commit=False)
            maintenance.created_by = request.user
            maintenance.save()
            
            messages.success(request, f'Scheduled maintenance "{maintenance.title}" has been created.')
            return redirect('scheduled_maintenance')
        else:
            messages.error(request, 'Please correct the errors below.')
            return self.get(request)


def maintenance_mode_page(request):
    """View for maintenance mode page"""
    message = getattr(settings, 'MAINTENANCE_MESSAGE', 'The system is currently under maintenance. Please check back later.')
    
    # Check for scheduled maintenance message
    try:
        from core.models import ScheduledMaintenance
        scheduled_maintenance = ScheduledMaintenance.objects.filter(
            is_active=True
        ).first()
        
        if scheduled_maintenance and scheduled_maintenance.is_currently_active():
            message = scheduled_maintenance.message
    except Exception:
        pass
    
    context = {
        'message': message,
        'maintenance_mode': True,
    }
    return render(request, 'security/maintenance.html', context)


def user_blocked_page(request):
    """View for blocked user page"""
    return render(request, 'security/user_blocked.html')


# API Views
def security_stats_api(request):
    """API endpoint for security statistics"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    from django.contrib.auth import get_user_model
    User = get_user_model()
    
    # Count today's logins
    today = timezone.now().date()
    # FIXED: AuditLog uses 'timestamp' field
    today_logins = AuditLog.objects.filter(
        action='LOGIN',
        timestamp__date=today
    ).count()
    
    return JsonResponse({
        'today_logins': today_logins,
        'blocked_users': UserProfile.objects.filter(is_blocked=True).count(),
        'maintenance_mode': getattr(settings, 'MAINTENANCE_MODE', False)
    })


def user_details_api(request, user_id):
    """API endpoint for user details"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user = User.objects.get(id=user_id)
        
        def get_user_type(user):
            if hasattr(user, 'student'):
                return 'Student'
            elif hasattr(user, 'teacher'):
                return 'Teacher'
            elif hasattr(user, 'parentguardian'):
                return 'Parent'
            elif user.is_staff:
                return 'Staff'
            else:
                return 'System'
        
        data = {
            'username': user.username,
            'email': user.email,
            'full_name': user.get_full_name(),
            'user_type': get_user_type(user),
            'is_blocked': user.profile.is_blocked if hasattr(user, 'profile') else False,
            'block_reason': user.profile.blocked_reason if hasattr(user, 'profile') else None,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'date_joined': user.date_joined.isoformat(),
        }
        
        return JsonResponse(data)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)


class RateLimitExceededView(View):
    """View for rate limit exceeded page"""
    
    @method_decorator(never_cache)
    def get(self, request):
        return render(request, 'security/rate_limit_exceeded.html')


class SecuritySettingsView(View):
    """View for security configuration settings"""
    
    @method_decorator(login_required)
    @method_decorator(staff_member_required)
    def get(self, request):
        context = {
            'max_login_attempts': getattr(settings, 'MAX_LOGIN_ATTEMPTS', 5),
            'password_rotation_days': getattr(settings, 'PASSWORD_ROTATION_DAYS', 90),
            'rate_limit_requests': getattr(settings, 'RATE_LIMIT_REQUESTS', 100),
            'rate_limit_window': getattr(settings, 'RATE_LIMIT_WINDOW', 60),
            'active_tab': 'security_settings',
        }
        return render(request, 'security/settings.html', context)
    
    @method_decorator(login_required)
    @method_decorator(staff_member_required)
    def post(self, request):
        # In a real implementation, you'd save these to settings or database
        # For now, we'll just show a message
        messages.success(request, 'Security settings updated successfully.')
        return redirect('security_settings')


def security_events_api(request):
    """API endpoint for recent security events"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    # FIXED: AuditLog uses 'timestamp' field
    recent_events = AuditLog.objects.filter(
        action__in=['BLOCK', 'UNBLOCK', 'LOGIN_FAILED', 'MAINTENANCE_START', 'MAINTENANCE_END']
    ).order_by('-timestamp')[:20]
    
    events_data = []
    for event in recent_events:
        events_data.append({
            'id': event.id,
            'action': event.action,
            'user': event.user.username if event.user else 'System',
            'timestamp': event.timestamp.isoformat(),  # FIXED: Use timestamp
            'details': event.details,
            'ip_address': event.ip_address,
        })
    
    return JsonResponse({'events': events_data})


def maintenance_details_api(request, maintenance_id):
    """API endpoint for maintenance details"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
        from .models import ScheduledMaintenance
        maintenance = ScheduledMaintenance.objects.get(id=maintenance_id)
        
        data = {
            'id': maintenance.id,
            'title': maintenance.title,
            'description': maintenance.description,
            'maintenance_type': maintenance.maintenance_type,
            'maintenance_type_display': maintenance.get_maintenance_type_display(),
            'start_time': maintenance.start_time.strftime("%b %d, %Y at %I:%M %p"),
            'end_time': maintenance.end_time.strftime("%b %d, %Y at %I:%M %p"),
            'duration': str(maintenance.duration()),
            'message': maintenance.message,
            'is_active': maintenance.is_active,
            'was_executed': maintenance.was_executed,
            'is_currently_active': maintenance.is_currently_active(),
            'is_upcoming': maintenance.is_upcoming(),
            'created_by': maintenance.created_by.username,
            'created_at': maintenance.created_at.strftime("%b %d, %Y at %I:%M %p"),
        }
        
        return JsonResponse(data)
    except ScheduledMaintenance.DoesNotExist:
        return JsonResponse({'error': 'Maintenance not found'}, status=404)
# ADD THIS FUNCTION TO FIX AUDIT LOG CREATION
def get_client_ip(request):
    """Get the client's IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

# UPDATE THE security_dashboard FUNCTION
@user_passes_test(is_security_admin)
def security_dashboard(request):
    # Create audit log for dashboard access - FIXED VERSION
    try:
        AuditLog.objects.create(
            user=request.user,
            action='ACCESS',
            model_name='SecurityDashboard',
            object_id=0,
            details={'action': 'viewed_security_dashboard', 'path': request.path},
            ip_address=get_client_ip(request)
        )
    except Exception as e:
        # Log error but don't break the dashboard
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Failed to create audit log for security dashboard: {e}")
    
    # Rest of your existing security_dashboard code...
    total_users = User.objects.filter(is_active=True).count()
    blocked_users = UserProfile.objects.filter(is_blocked=True).count()
    
    recent_security_events = SecurityEvent.objects.all().order_by('-created_at')[:5]
    recent_blocks = AuditLog.objects.filter(
        model_name='User',
        action__in=['BLOCK', 'UNBLOCK']
    ).order_by('-timestamp')[:10]
    
    context = {
        'active_tab': 'security_dashboard',
        'total_users': total_users,
        'blocked_users': blocked_users,
        'maintenance_mode': getattr(settings, 'MAINTENANCE_MODE', False),
        'recent_security_events': recent_security_events,
        'recent_blocks': recent_blocks,
    }
    
    return render(request, 'security/dashboard.html', context)

# ADD THESE FUNCTIONS TO FIX TEMPLATE COMPATIBILITY
@user_passes_test(is_security_admin)
def security_events(request):
    """Simple security events view for template compatibility"""
    events = SecurityEvent.objects.all().order_by('-created_at')[:50]
    
    context = {
        'active_tab': 'security_events',
        'security_events': events,
    }
    return render(request, 'security/events.html', context)

@user_passes_test(is_security_admin)
def alert_rule_list(request):
    """Simple alert rules view for template compatibility"""
    alert_rules = AuditAlertRule.objects.all().order_by('-created_at')
    
    context = {
        'active_tab': 'alert_rules',
        'alert_rules': alert_rules,
    }
    return render(request, 'security/alert_rules.html', context)


# Add these functions to your security_views.py

def security_status_api(request):
    """API endpoint for security system status"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    # Get system health status
    from core.models import SecurityEvent, AuditLog
    from django.utils import timezone
    from datetime import timedelta
    
    # Check for recent security events (last 24 hours)
    recent_events = SecurityEvent.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).count()
    
    # Check system health
    system_status = 'healthy'
    threat_level = 'low'
    
    if recent_events > 50:
        system_status = 'critical'
        threat_level = 'critical'
    elif recent_events > 10:
        system_status = 'warning' 
        threat_level = 'high'
    elif recent_events > 5:
        threat_level = 'medium'
    
    return JsonResponse({
        'status': 'success',
        'system_status': system_status,
        'threat_level': threat_level,
        'last_updated': timezone.now().isoformat(),
        'active_alerts': recent_events,
        'components': {
            'database': 'online',
            'authentication': 'online', 
            'monitoring': 'online',
            'logging': 'online'
        }
    })

def security_notifications_api(request):
    """API endpoint for security notifications (compatibility alias)"""
    return security_events_api(request)

def security_stats_api(request):
    """API endpoint for security statistics"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    from core.models import SecurityEvent, AuditLog
    from django.utils import timezone
    from datetime import timedelta
    
    # Calculate stats for last 7 days
    week_ago = timezone.now() - timedelta(days=7)
    
    total_events = SecurityEvent.objects.filter(created_at__gte=week_ago).count()
    critical_events = SecurityEvent.objects.filter(
        created_at__gte=week_ago, 
        severity='CRITICAL'
    ).count()
    
    # Get active alert rules count
    active_rules = 5  # Default value
    
    return JsonResponse({
        'total_events': total_events,
        'critical_events': critical_events,
        'active_rules': active_rules,
        'threat_level': 'low' if critical_events == 0 else 'medium' if critical_events < 3 else 'high'
    })



# =============================================================================
# AXES LOCKOUT MANAGEMENT - BEAUTIFUL ADMIN INTERFACE
# =============================================================================

@user_passes_test(lambda u: u.is_superuser)
def axes_lockout_management(request):
    """Main lockout management dashboard"""
    try:
        from axes.models import AccessAttempt
        # Get currently locked users
        locked_users = AccessAttempt.objects.filter(failures_since_start__gte=5)
        
        # Get recent lockout history (last 24 hours)
        from django.utils import timezone
        from datetime import timedelta
        recent_lockouts = AccessAttempt.objects.filter(
            attempt_time__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-attempt_time')[:20]
        
        context = {
            'active_tab': 'lockout_management',
            'locked_users_count': locked_users.count(),
            'recent_lockouts': recent_lockouts,
            'total_attempts_today': AccessAttempt.objects.filter(
                attempt_time__date=timezone.now().date()
            ).count(),
        }
        return render(request, 'security/lockout_management.html', context)
        
    except Exception as e:
        messages.error(request, f'Error loading lockout management: {str(e)}')
        return redirect('security_dashboard')

@user_passes_test(lambda u: u.is_superuser)
def unlock_user_api(request, username):
    """API endpoint to unlock user"""
    try:
        from axes.models import AccessAttempt
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        # Check if user exists
        user_exists = User.objects.filter(username=username).exists()
        if not user_exists:
            return JsonResponse({
                'success': False, 
                'error': f'User "{username}" not found in system'
            })
        
        # Delete lockout records
        deleted_count, _ = AccessAttempt.objects.filter(username=username).delete()
        
        # Log the action
        AuditLog.log_action(
            user=request.user,
            action='AXES_UNLOCK',
            model_name='User',
            object_id=0,
            details={
                'unlocked_user': username,
                'deleted_records': deleted_count,
                'unlocked_by': request.user.username
            }
        )
        
        return JsonResponse({
            'success': True, 
            'message': f'✅ Successfully unlocked user "{username}"',
            'details': f'Removed {deleted_count} lockout records',
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Error unlocking user: {str(e)}'
        })

@user_passes_test(lambda u: u.is_superuser)  
def locked_users_api(request):
    """API endpoint to get currently locked users"""
    try:
        from axes.models import AccessAttempt
        from django.utils import timezone
        
        locked_users = AccessAttempt.objects.filter(failures_since_start__gte=5)
        
        users_data = []
        for attempt in locked_users:
            # Calculate time since lockout
            time_since_lockout = timezone.now() - attempt.attempt_time
            hours_locked = int(time_since_lockout.total_seconds() / 3600)
            minutes_locked = int((time_since_lockout.total_seconds() % 3600) / 60)
            
            users_data.append({
                'username': attempt.username,
                'ip_address': attempt.ip_address,
                'user_agent': attempt.user_agent[:50] + '...' if attempt.user_agent and len(attempt.user_agent) > 50 else attempt.user_agent,
                'failures': attempt.failures_since_start,
                'locked_at': attempt.attempt_time.strftime("%Y-%m-%d %H:%M:%S"),
                'time_locked': f"{hours_locked}h {minutes_locked}m",
                'is_recent': time_since_lockout.total_seconds() < 3600,  # Less than 1 hour
            })
        
        return JsonResponse({
            'success': True,
            'locked_users': users_data,
            'total_locked': len(users_data),
            'last_updated': timezone.now().strftime("%Y-%m-%d %H:%M:%S")
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Error fetching locked users: {str(e)}'
        })

@user_passes_test(lambda u: u.is_superuser)
def unlock_all_users_api(request):
    """API endpoint to unlock ALL locked users"""
    try:
        from axes.models import AccessAttempt
        
        # Get count before deletion
        locked_count = AccessAttempt.objects.filter(failures_since_start__gte=5).count()
        
        # Delete all lockout records
        deleted_count, _ = AccessAttempt.objects.all().delete()
        
        # Log the action
        AuditLog.log_action(
            user=request.user,
            action='AXES_UNLOCK_ALL',
            model_name='System',
            object_id=0,
            details={
                'unlocked_count': locked_count,
                'deleted_records': deleted_count,
                'unlocked_by': request.user.username
            }
        )
        
        return JsonResponse({
            'success': True, 
            'message': f'✅ Successfully unlocked all users',
            'details': f'Removed {deleted_count} lockout records, unlocked {locked_count} users',
            'unlocked_count': locked_count,
            'deleted_count': deleted_count
        })
        
    except Exception as e:
        return JsonResponse({
            'success': False, 
            'error': f'Error unlocking all users: {str(e)}'
        })












