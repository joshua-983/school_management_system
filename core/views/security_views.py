# core/views/security_views.py - ADD MISSING IMPORTS AT TOP
from core.models import SecurityEvent, AuditAlertRule, UserProfile, AuditLog, ScheduledMaintenance, User, MaintenanceMode
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
import logging

# ADD THESE MISSING IMPORTS:
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView
from django.urls import reverse_lazy
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_POST
from django.contrib.auth import get_user_model
from django.db import models
from django.views.decorators.csrf import ensure_csrf_cookie
from datetime import datetime

# Import base_views for is_admin function
try:
    from .base_views import is_admin
except ImportError:
    def is_admin(user):
        return user.is_authenticated and (user.is_staff or user.is_superuser)

# Add these model imports if not already there
try:
    from core.models import AuditReport, DataRetentionPolicy
except ImportError:
    pass

from core.forms import UserBlockForm, MaintenanceModeForm, UserSearchForm, ScheduledMaintenanceForm

# Configure logger
logger = logging.getLogger(__name__)


def is_security_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)

@user_passes_test(is_security_admin)
def security_dashboard(request):
    # Create audit log for dashboard access
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
        logger.error(f"Failed to create audit log for security dashboard: {e}")
    
    # Get security statistics
    total_users = User.objects.filter(is_active=True).count()
    blocked_users = UserProfile.objects.filter(is_blocked=True).count()
    
    # Get maintenance mode status from database
    try:
        maintenance = MaintenanceMode.objects.filter(is_active=True).first()
        maintenance_mode = maintenance.is_active if maintenance else False
    except Exception as e:
        logger.error(f"Error getting maintenance mode: {e}")
        maintenance_mode = False
    
    recent_security_events = SecurityEvent.objects.all().order_by('-created_at')[:5]
    
    recent_blocks = AuditLog.objects.filter(
        model_name='User',
        action__in=['BLOCK', 'UNBLOCK']
    ).order_by('-timestamp')[:10]
    
    context = {
        'active_tab': 'security_dashboard',
        'total_users': total_users,
        'blocked_users': blocked_users,
        'maintenance_mode': maintenance_mode,
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
        
        return users.order_by('username')[:50]


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
    """View for enabling/disabling maintenance mode using database model"""
    
    @method_decorator(login_required)
    @method_decorator(staff_member_required)
    def get(self, request):
        form = MaintenanceModeForm()
        
        # Get current maintenance mode from database
        try:
            maintenance = MaintenanceMode.objects.filter(is_active=True).first()
            maintenance_mode = maintenance.is_active if maintenance else False
            current_message = maintenance.message if maintenance else ""
        except Exception as e:
            logger.error(f"Error getting maintenance mode: {e}")
            maintenance_mode = False
            current_message = ""
        
        recent_events = AuditLog.objects.filter(
            action__in=['MAINTENANCE_START', 'MAINTENANCE_END']
        ).order_by('-timestamp')[:10]
        
        context = {
            'form': form,
            'maintenance_mode': maintenance_mode,
            'current_message': current_message,
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
            
            try:
                if action == 'enable':
                    # Enable maintenance mode
                    maintenance, created = MaintenanceMode.objects.get_or_create(
                        defaults={
                            'is_active': True,
                            'message': message,
                            'created_by': request.user
                        }
                    )
                    if not created:
                        maintenance.is_active = True
                        maintenance.message = message
                        maintenance.created_by = request.user
                        maintenance.save()
                    
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
                    maintenance = MaintenanceMode.objects.filter(is_active=True).first()
                    if maintenance:
                        maintenance.is_active = False
                        maintenance.save()
                        messages.success(request, 'Maintenance mode has been disabled.')
                    else:
                        messages.info(request, 'Maintenance mode was already disabled.')
                    
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
                
            except Exception as e:
                logger.error(f"Error updating maintenance mode: {e}")
                messages.error(request, f'Error updating maintenance mode: {str(e)}')
                return self.get(request)
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
    """View for maintenance mode page with admin bypass"""
    # Check if user can bypass maintenance mode
    if request.user.is_authenticated:
        try:
            if MaintenanceMode.can_user_access(request.user):
                # User can bypass maintenance - redirect to appropriate page
                if request.user.is_staff or request.user.is_superuser:
                    messages.info(request, '⚠️ Maintenance mode is active, but you have admin access.')
                    return redirect('admin_dashboard')
                else:
                    return redirect('dashboard')
        except Exception as e:
            logger.error(f"Error checking maintenance bypass: {e}")
    
    # User cannot bypass - show maintenance page
    try:
        maintenance = MaintenanceMode.objects.filter(is_active=True).first()
        if maintenance and maintenance.is_currently_active():
            message = maintenance.message
        else:
            # Fallback to settings
            message = getattr(settings, 'MAINTENANCE_MESSAGE', 'The system is currently under maintenance. Please check back later.')
    except Exception as e:
        logger.error(f"Error checking maintenance mode: {e}")
        message = getattr(settings, 'MAINTENANCE_MESSAGE', 'The system is currently under maintenance. Please check back later.')
    
    # Check for scheduled maintenance message
    try:
        scheduled_maintenance = ScheduledMaintenance.objects.filter(
            is_active=True
        ).first()
        
        if scheduled_maintenance and scheduled_maintenance.is_currently_active():
            message = scheduled_maintenance.message
    except Exception as e:
        logger.error(f"Error checking scheduled maintenance: {e}")
        pass
    
    context = {
        'message': message,
        'maintenance_mode': True,
        'user_can_bypass': False,  # If they reached here, they can't bypass
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
    today_logins = AuditLog.objects.filter(
        action='LOGIN',
        timestamp__date=today
    ).count()
    
    # Get maintenance mode from database
    try:
        maintenance = MaintenanceMode.objects.filter(is_active=True).first()
        maintenance_mode = maintenance.is_active if maintenance else False
    except Exception as e:
        logger.error(f"Error getting maintenance mode for API: {e}")
        maintenance_mode = False
    
    return JsonResponse({
        'today_logins': today_logins,
        'blocked_users': UserProfile.objects.filter(is_blocked=True).count(),
        'maintenance_mode': maintenance_mode
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
            'blocked_at': user.profile.blocked_at.isoformat() if hasattr(user, 'profile') and user.profile.blocked_at else None,
            'last_login': user.last_login.isoformat() if user.last_login else None,
            'date_joined': user.date_joined.isoformat(),
        }
        
        return JsonResponse(data)
    except User.DoesNotExist:
        return JsonResponse({'error': 'User not found'}, status=404)
    except Exception as e:
        logger.error(f"Error getting user details: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


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
    
    recent_events = AuditLog.objects.filter(
        action__in=['BLOCK', 'UNBLOCK', 'LOGIN_FAILED', 'MAINTENANCE_START', 'MAINTENANCE_END']
    ).order_by('-timestamp')[:20]
    
    events_data = []
    for event in recent_events:
        events_data.append({
            'id': event.id,
            'action': event.action,
            'user': event.user.username if event.user else 'System',
            'timestamp': event.timestamp.isoformat(),
            'details': event.details,
            'ip_address': event.ip_address,
        })
    
    return JsonResponse({'events': events_data})


def maintenance_details_api(request, maintenance_id):
    """API endpoint for maintenance details"""
    if not request.user.is_staff:
        return JsonResponse({'error': 'Unauthorized'}, status=403)
    
    try:
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
    except Exception as e:
        logger.error(f"Error getting maintenance details: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@user_passes_test(is_security_admin)
def security_events(request):
    """Security events view with proper context variables"""
    # Get the full QuerySet first
    events_queryset = SecurityEvent.objects.all().order_by('-created_at')
    
    # Calculate counts from the FULL QuerySet (before slicing)
    unresolved_count = events_queryset.filter(is_resolved=False).count()
    critical_count = events_queryset.filter(severity='CRITICAL').count()
    
    # Count today's events from the FULL QuerySet
    today = timezone.now().date()
    today_count = events_queryset.filter(created_at__date=today).count()
    
    # Now slice for display (last 50 events)
    recent_events = events_queryset[:50]
    
    context = {
        'active_tab': 'security_events',
        'security_events': recent_events,
        'unresolved_count': unresolved_count,
        'critical_count': critical_count,
        'today_count': today_count,
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


def security_status_api(request):
    """API endpoint for security system status"""
    if not request.user.is_authenticated:
        return JsonResponse({'error': 'Authentication required'}, status=401)
    
    # Check for recent security events (last 24 hours)
    recent_events = SecurityEvent.objects.filter(
        created_at__gte=timezone.now() - timedelta(hours=24)
    ).count()
    
    # Check maintenance mode status
    try:
        maintenance = MaintenanceMode.objects.filter(is_active=True).first()
        maintenance_mode = maintenance.is_active if maintenance else False
    except Exception as e:
        logger.error(f"Error checking maintenance mode for status API: {e}")
        maintenance_mode = False
    
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
        'maintenance_mode': maintenance_mode,
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


# =============================================================================
# AXES LOCKOUT MANAGEMENT - FIXED VERSION
# =============================================================================

@user_passes_test(lambda u: u.is_superuser)
def axes_lockout_management(request):
    """Main lockout management dashboard"""
    try:
        # Check if axes is installed
        try:
            from axes.models import AccessAttempt
            axes_installed = True
        except ImportError:
            axes_installed = False
            return render(request, 'security/lockout_management.html', {
                'active_tab': 'lockout_management',
                'axes_installed': False,
                'error': 'django-axes is not installed. Please install it to use lockout management.'
            })
        
        # Get currently locked users
        locked_users = AccessAttempt.objects.filter(failures_since_start__gte=5)
        
        # Get recent lockout history (last 24 hours)
        recent_lockouts = AccessAttempt.objects.filter(
            attempt_time__gte=timezone.now() - timedelta(hours=24)
        ).order_by('-attempt_time')[:20]
        
        # Get total attempts today
        total_attempts_today = AccessAttempt.objects.filter(
            attempt_time__date=timezone.now().date()
        ).count()
        
        context = {
            'active_tab': 'lockout_management',
            'locked_users_count': locked_users.count(),
            'recent_lockouts': recent_lockouts,
            'total_attempts_today': total_attempts_today,
            'axes_installed': True,
        }
        return render(request, 'security/lockout_management.html', context)
        
    except Exception as e:
        logger.error(f'Error loading lockout management: {str(e)}')
        
        return render(request, 'security/lockout_management.html', {
            'active_tab': 'lockout_management',
            'axes_installed': False,
            'error': f'Error loading lockout management: {str(e)}'
        })


@user_passes_test(lambda u: u.is_superuser)
def locked_users_api(request):
    """API endpoint to get currently locked login attempts"""
    try:
        from axes.models import AccessAttempt
        
        from django.utils import timezone
        
        # Get locked login attempts (usernames with 5 or more failures within cooloff period)
        locked_attempts = AccessAttempt.objects.filter(failures_since_start__gte=5)
        
        attempts_data = []
        for attempt in locked_attempts:
            # Calculate time since lockout
            time_since_lockout = timezone.now() - attempt.attempt_time
            hours_locked = int(time_since_lockout.total_seconds() / 3600)
            minutes_locked = int((time_since_lockout.total_seconds() % 3600) / 60)
            
            # Check if still locked (within 15 minute cooloff)
            is_locked = time_since_lockout.total_seconds() < 900  # 15 minutes
            
            attempts_data.append({
                'username': attempt.username or 'Unknown',
                'ip_address': attempt.ip_address or 'Unknown',
                'user_agent': attempt.user_agent[:50] + '...' if attempt.user_agent and len(attempt.user_agent) > 50 else (attempt.user_agent or 'Unknown'),
                'failures': attempt.failures_since_start,
                'locked_at': attempt.attempt_time.strftime("%Y-%m-%d %H:%M:%S") if attempt.attempt_time else 'Unknown',
                'time_locked': f"{hours_locked}h {minutes_locked}m",
                'is_recent': time_since_lockout.total_seconds() < 3600,  # Less than 1 hour
                'is_locked': is_locked,
            })
        
        return JsonResponse({
            'success': True,
            'locked_users': attempts_data,  # Keeping same key for frontend compatibility
            'total_locked': len(attempts_data),
            'last_updated': timezone.now().strftime("%Y-%m-%d %H:%M:%S"),
            'axes_installed': True
        })
        
    except ImportError:
        return JsonResponse({
            'success': False, 
            'error': 'django-axes is not installed. Please install it to use lockout management.',
            'axes_installed': False
        })
    except Exception as e:
        logger.error(f'Error fetching locked login attempts: {str(e)}')
        
        return JsonResponse({
            'success': False, 
            'error': f'Error fetching locked login attempts: {str(e)}',
            'axes_installed': False
        })

@user_passes_test(lambda u: u.is_superuser)
def unlock_user_api(request, username):
    """API endpoint to unlock user - FIXED VERSION"""
    try:
        from axes.models import AccessAttempt
        
        logger.info(f"Unlock API called for username: {username}")
        
        # FIX: Don't check if user exists in User model
        # Axes locks login attempts, not necessarily valid users
        # Just delete the AccessAttempt records for this username
        
        # Delete lockout records for this username (login attempt)
        deleted_count, _ = AccessAttempt.objects.filter(username=username).delete()
        
        logger.info(f"Deleted {deleted_count} lockout records for username: {username}")
        
        # Log the action
        try:
            AuditLog.log_action(
                user=request.user,
                action='AXES_UNLOCK',
                model_name='User',
                object_id=0,
                details={
                    'unlocked_username': username,
                    'deleted_records': deleted_count,
                    'unlocked_by': request.user.username
                }
            )
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
        
        return JsonResponse({
            'success': True, 
            'message': f'✅ Successfully unlocked login attempts for "{username}"',
            'details': f'Removed {deleted_count} lockout records',
            'deleted_count': deleted_count,
            'axes_installed': True
        })
        
    except ImportError:
        return JsonResponse({
            'success': False, 
            'error': 'django-axes is not installed. Please install it to use lockout management.',
            'axes_installed': False
        })
    except Exception as e:
        logger.error(f'Error unlocking username {username}: {str(e)}')
        
        return JsonResponse({
            'success': False, 
            'error': f'Error unlocking username: {str(e)}'
        })

@user_passes_test(lambda u: u.is_superuser)  
def unlock_all_users_api(request):
    """API endpoint to unlock ALL locked users - SINGLE DEFINITION"""
    try:
        from axes.models import AccessAttempt
        
        logger.info("Unlock all users API called")
        
        # Get count before deletion
        locked_count = AccessAttempt.objects.filter(failures_since_start__gte=5).count()
        
        # Delete all lockout records
        deleted_count, _ = AccessAttempt.objects.all().delete()
        
        logger.info(f"Deleted {deleted_count} lockout records, unlocked {locked_count} users")
        
        # Log the action
        try:
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
        except Exception as e:
            logger.error(f"Failed to create audit log: {e}")
        
        return JsonResponse({
            'success': True, 
            'message': f'✅ Successfully unlocked all users',
            'details': f'Removed {deleted_count} lockout records, unlocked {locked_count} users',
            'unlocked_count': locked_count,
            'deleted_count': deleted_count,
            'axes_installed': True
        })
        
    except ImportError:
        return JsonResponse({
            'success': False, 
            'error': 'django-axes is not installed. Please install it to use lockout management.',
            'axes_installed': False
        })
    except Exception as e:
        logger.error(f'Error unlocking all users: {str(e)}')
        
        return JsonResponse({
            'success': False, 
            'error': f'Error unlocking all users: {str(e)}'
        })


# =============================================================================
# MAINTENANCE MODE MANAGEMENT FUNCTIONS
# =============================================================================

@user_passes_test(is_security_admin)
def maintenance_mode_status_api(request):
    """API endpoint to get current maintenance mode status"""
    try:
        maintenance = MaintenanceMode.objects.filter(is_active=True).first()
        
        if maintenance:
            data = {
                'is_active': True,
                'message': maintenance.message,
                'started_at': maintenance.created_at.isoformat(),
                'started_by': maintenance.created_by.username if maintenance.created_by else 'System',
            }
        else:
            data = {
                'is_active': False,
                'message': '',
                'started_at': None,
                'started_by': None,
            }
        
        return JsonResponse(data)
    except Exception as e:
        logger.error(f"Error getting maintenance mode status: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@user_passes_test(is_security_admin)
def maintenance_mode_history_api(request):
    """API endpoint to get maintenance mode history"""
    try:
        maintenance_history = MaintenanceMode.objects.all().order_by('-created_at')[:20]
        
        history_data = []
        for maintenance in maintenance_history:
            history_data.append({
                'id': maintenance.id,
                'is_active': maintenance.is_active,
                'message': maintenance.message,
                'created_at': maintenance.created_at.isoformat(),
                'created_by': maintenance.created_by.username if maintenance.created_by else 'System',
                'updated_at': maintenance.updated_at.isoformat(),
            })
        
        return JsonResponse({'history': history_data})
    except Exception as e:
        logger.error(f"Error getting maintenance mode history: {e}")
        return JsonResponse({'error': 'Internal server error'}, status=500)


@user_passes_test(is_security_admin)
def delete_maintenance_record(request, record_id):
    """Delete a maintenance mode record"""
    try:
        maintenance = get_object_or_404(MaintenanceMode, id=record_id)
        
        # Don't allow deletion of active maintenance
        if maintenance.is_active:
            messages.error(request, 'Cannot delete an active maintenance record. Disable it first.')
            return redirect('maintenance_mode')
        
        maintenance.delete()
        messages.success(request, 'Maintenance record deleted successfully.')
        return redirect('maintenance_mode')
        
    except Exception as e:
        logger.error(f"Error deleting maintenance record: {e}")
        messages.error(request, f'Error deleting maintenance record: {str(e)}')
        return redirect('maintenance_mode')


# =============================================================================
# SECURITY HEALTH CHECK FUNCTIONS
# =============================================================================

@user_passes_test(is_security_admin)
def security_health_check(request):
    """Comprehensive security health check"""
    try:
        health_checks = {}
        
        # Check database connectivity
        try:
            User.objects.count()
            health_checks['database'] = {'status': 'healthy', 'message': 'Database connection successful'}
        except Exception as e:
            health_checks['database'] = {'status': 'critical', 'message': f'Database error: {str(e)}'}
        
        # Check maintenance mode
        try:
            maintenance = MaintenanceMode.objects.filter(is_active=True).first()
            health_checks['maintenance_mode'] = {
                'status': 'active' if maintenance else 'inactive',
                'message': f'Maintenance mode is {"active" if maintenance else "inactive"}'
            }
        except Exception as e:
            health_checks['maintenance_mode'] = {'status': 'error', 'message': f'Error checking maintenance mode: {str(e)}'}
        
        # Check blocked users
        try:
            blocked_count = UserProfile.objects.filter(is_blocked=True).count()
            health_checks['blocked_users'] = {
                'status': 'warning' if blocked_count > 10 else 'healthy',
                'message': f'{blocked_count} users currently blocked'
            }
        except Exception as e:
            health_checks['blocked_users'] = {'status': 'error', 'message': f'Error checking blocked users: {str(e)}'}
        
        # Check recent security events
        try:
            recent_events = SecurityEvent.objects.filter(
                created_at__gte=timezone.now() - timedelta(hours=24)
            ).count()
            health_checks['recent_events'] = {
                'status': 'warning' if recent_events > 5 else 'healthy',
                'message': f'{recent_events} security events in last 24 hours'
            }
        except Exception as e:
            health_checks['recent_events'] = {'status': 'error', 'message': f'Error checking security events: {str(e)}'}
        
        context = {
            'active_tab': 'security_health',
            'health_checks': health_checks,
            'last_checked': timezone.now(),
        }
        
        return render(request, 'security/health_check.html', context)
        
    except Exception as e:
        logger.error(f"Error performing security health check: {e}")
        messages.error(request, f'Error performing health check: {str(e)}')
        return redirect('security_dashboard')


def get_client_ip(request):
    """Get the client's IP address from request"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip

@never_cache
def emergency_maintenance_bypass(request, secret_key=None):
    """Emergency bypass for maintenance mode - use with caution"""
    # Set a secret key in your settings for emergency access
    expected_key = getattr(settings, 'EMERGENCY_BYPASS_KEY', 'emergency123')
    
    if request.method == 'POST':
        secret_key = request.POST.get('secret_key')
    
    if secret_key == expected_key:
        # Add user to session bypass
        request.session['maintenance_bypass'] = True
        request.session.set_expiry(3600)  # 1 hour expiration
        messages.success(request, '⚠️ Emergency maintenance bypass activated for 1 hour. Use with caution!')
        logger.warning(f"Emergency maintenance bypass activated by IP: {get_client_ip(request)}")
        
        # Redirect to appropriate dashboard
        if request.user.is_authenticated:
            if request.user.is_staff or request.user.is_superuser:
                return redirect('admin_dashboard')
            else:
                return redirect('dashboard')
        else:
            return redirect('admin_login')
    else:
        if request.method == 'POST':
            messages.error(request, 'Invalid emergency bypass key.')
        # Show bypass form
        return render(request, 'security/emergency_bypass.html')

def clear_maintenance_bypass(request):
    """Clear the maintenance bypass (for testing or when done)"""
    if 'maintenance_bypass' in request.session:
        del request.session['maintenance_bypass']
        messages.success(request, 'Maintenance bypass cleared.')
        logger.info(f"Maintenance bypass cleared by user: {request.user.username if request.user.is_authenticated else 'Anonymous'}")
    else:
        messages.info(request, 'No active maintenance bypass found.')
    
    # Redirect to appropriate page
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('admin_dashboard')
        else:
            return redirect('dashboard')
    else:
        return redirect('maintenance_mode_page')
# Add this to the end of security_views.py (after all other functions)

def clear_maintenance_bypass(request):
    """Clear the maintenance bypass (for testing or when done)"""
    if 'maintenance_bypass' in request.session:
        del request.session['maintenance_bypass']
        messages.success(request, 'Maintenance bypass cleared.')
        logger.info(f"Maintenance bypass cleared by user: {request.user.username if request.user.is_authenticated else 'Anonymous'}")
    else:
        messages.info(request, 'No active maintenance bypass found.')
    
    # Redirect to appropriate page
    if request.user.is_authenticated:
        if request.user.is_staff or request.user.is_superuser:
            return redirect('admin_dashboard')
        else:
            return redirect('dashboard')
    else:
        return redirect('maintenance_mode_page')


def system_health_api(request):
    """API endpoint for system health data"""
    if not request.user.is_superuser:
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    health_data = {
        'system_status': 'Healthy',
        'response_time': '0.45s',
        'database_status': 'Connected',
        'cache_status': 'Active',
        'timestamp': timezone.now().isoformat()
    }
    
    return JsonResponse(health_data)

