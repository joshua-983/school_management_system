from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, TemplateView
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.http import JsonResponse, HttpResponse
from django.core.exceptions import PermissionDenied
from django.db.models import Q, Count, Avg, Min, Max
from django.utils import timezone
from django.core.paginator import Paginator
from django.contrib import messages
from django.db import models
import json
from datetime import datetime, timedelta
import csv

# Import your models
from ..models import (
    AuditLog, Student, Grade, ClassAssignment, Assignment, 
    StudentAssignment, Fee, Teacher, ParentGuardian, User,
    Notification, AttendanceSummary, Bill, BillPayment
)

# Import your permission functions from base_views
from .base_views import is_admin, is_student, is_teacher

class AuditLogListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'core/analytics/audit_log_list.html'
    context_object_name = 'logs'
    paginate_by = 50
    model = AuditLog
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_queryset(self):
        queryset = AuditLog.objects.all().select_related('user').order_by('-timestamp')
        
        # Filtering
        action = self.request.GET.get('action')
        model_name = self.request.GET.get('model_name')
        user_id = self.request.GET.get('user_id')
        date_from = self.request.GET.get('date_from')
        date_to = self.request.GET.get('date_to')
        search = self.request.GET.get('search')
        
        if action and action != 'all':
            queryset = queryset.filter(action=action)
        
        if model_name and model_name != 'all':
            queryset = queryset.filter(model_name=model_name)
        
        if user_id and user_id != 'all':
            queryset = queryset.filter(user_id=user_id)
        
        if date_from:
            try:
                date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
                queryset = queryset.filter(timestamp__date__gte=date_from)
            except ValueError:
                pass
        
        if date_to:
            try:
                date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
                queryset = queryset.filter(timestamp__date__lte=date_to)
            except ValueError:
                pass
        
        if search:
            queryset = queryset.filter(
                Q(user__username__icontains=search) |
                Q(user__first_name__icontains=search) |
                Q(user__last_name__icontains=search) |
                Q(model_name__icontains=search) |
                Q(object_id__icontains=search) |
                Q(details__icontains=search)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add filter options to context
        context['actions'] = AuditLog.ACTION_CHOICES
        context['model_names'] = AuditLog.objects.values_list(
            'model_name', flat=True
        ).distinct().order_by('model_name')
        
        context['users'] = User.objects.filter(
            audit_logs__isnull=False
        ).distinct().order_by('username')
        
        # Add current filter values
        context['current_filters'] = {
            'action': self.request.GET.get('action', ''),
            'model_name': self.request.GET.get('model_name', ''),
            'user_id': self.request.GET.get('user_id', ''),
            'date_from': self.request.GET.get('date_from', ''),
            'date_to': self.request.GET.get('date_to', ''),
            'search': self.request.GET.get('search', ''),
        }
        
        # Add statistics
        context['total_logs'] = AuditLog.objects.count()
        context['today_logs'] = AuditLog.objects.filter(
            timestamp__date=timezone.now().date()
        ).count()
        context['unique_users'] = User.objects.filter(
            audit_logs__isnull=False
        ).distinct().count()
        
        return context

class AuditLogDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    template_name = 'core/analytics/audit_log_detail.html'
    context_object_name = 'log'
    model = AuditLog
    
    def test_func(self):
        return is_admin(self.request.user)

class AuditDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/analytics/audit_dashboard.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Time periods for filtering
        today = timezone.now().date()
        week_ago = today - timedelta(days=7)
        month_ago = today - timedelta(days=30)
        
        # Basic statistics
        context['total_actions'] = AuditLog.objects.count()
        context['today_actions'] = AuditLog.objects.filter(
            timestamp__date=today
        ).count()
        context['week_actions'] = AuditLog.objects.filter(
            timestamp__date__gte=week_ago
        ).count()
        context['month_actions'] = AuditLog.objects.filter(
            timestamp__date__gte=month_ago
        ).count()
        
        # Action type distribution
        action_stats = AuditLog.objects.values('action').annotate(
            count=Count('id')
        ).order_by('-count')
        context['action_stats'] = list(action_stats)
        
        # Model distribution
        model_stats = AuditLog.objects.values('model_name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        context['model_stats'] = list(model_stats)
        
        # Top users by activity
        user_stats = AuditLog.objects.values(
            'user__username', 'user__first_name', 'user__last_name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        context['user_stats'] = list(user_stats)
        
        # Recent suspicious activity (multiple failed logins, bulk deletes, etc.)
        suspicious_logins = AuditLog.objects.filter(
            action='LOGIN',
            timestamp__date__gte=week_ago
        ).values('user__username', 'ip_address').annotate(
            count=Count('id')
        ).filter(count__gt=10)  # More than 10 logins from same IP/user
        
        context['suspicious_activity'] = list(suspicious_logins)
        
        # Daily activity for chart
        daily_activity = AuditLog.objects.filter(
            timestamp__date__gte=month_ago
        ).extra(
            {'date': "date(timestamp)"}
        ).values('date').annotate(
            count=Count('id')
        ).order_by('date')
        
        context['daily_activity'] = list(daily_activity)
        
        return context

@login_required
def audit_export_csv(request):
    """Export audit logs as CSV"""
    if not is_admin(request.user):
        raise PermissionDenied
    
    # Create the HttpResponse object with CSV header
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = 'attachment; filename="audit_logs_export.csv"'
    
    writer = csv.writer(response)
    writer.writerow([
        'Timestamp', 'User', 'Action', 'Model', 'Object ID', 
        'IP Address', 'Details'
    ])
    
    # Apply same filters as list view
    queryset = AuditLog.objects.all().select_related('user').order_by('-timestamp')
    
    # Filtering logic (same as list view)
    action = request.GET.get('action')
    model_name = request.GET.get('model_name')
    user_id = request.GET.get('user_id')
    date_from = request.GET.get('date_from')
    date_to = request.GET.get('date_to')
    
    if action and action != 'all':
        queryset = queryset.filter(action=action)
    
    if model_name and model_name != 'all':
        queryset = queryset.filter(model_name=model_name)
    
    if user_id and user_id != 'all':
        queryset = queryset.filter(user_id=user_id)
    
    if date_from:
        try:
            date_from = datetime.strptime(date_from, '%Y-%m-%d').date()
            queryset = queryset.filter(timestamp__date__gte=date_from)
        except ValueError:
            pass
    
    if date_to:
        try:
            date_to = datetime.strptime(date_to, '%Y-%m-%d').date()
            queryset = queryset.filter(timestamp__date__lte=date_to)
        except ValueError:
            pass
    
    for log in queryset:
        writer.writerow([
            log.timestamp.strftime('%Y-%m-%d %H:%M:%S'),
            log.user.username if log.user else 'System',
            log.get_action_display(),
            log.model_name,
            log.object_id or '',
            log.ip_address or '',
            json.dumps(log.details) if log.details else ''
        ])
    
    return response

@login_required
def audit_statistics_api(request):
    """API endpoint for audit statistics (for charts)"""
    if not is_admin(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    period = request.GET.get('period', 'week')
    
    if period == 'week':
        start_date = timezone.now().date() - timedelta(days=7)
    elif period == 'month':
        start_date = timezone.now().date() - timedelta(days=30)
    else:  # year
        start_date = timezone.now().date() - timedelta(days=365)
    
    # Daily activity data
    daily_data = AuditLog.objects.filter(
        timestamp__date__gte=start_date
    ).extra(
        {'date': "date(timestamp)"}
    ).values('date').annotate(
        count=Count('id')
    ).order_by('date')
    
    # Action type distribution
    action_data = AuditLog.objects.filter(
        timestamp__date__gte=start_date
    ).values('action').annotate(
        count=Count('id')
    ).order_by('-count')
    
    # Model distribution
    model_data = AuditLog.objects.filter(
        timestamp__date__gte=start_date
    ).values('model_name').annotate(
        count=Count('id')
    ).order_by('-count')[:10]
    
    return JsonResponse({
        'daily_activity': list(daily_data),
        'action_distribution': list(action_data),
        'model_distribution': list(model_data),
    })

@login_required
def user_activity_report(request, user_id):
    """Generate detailed activity report for a specific user"""
    if not is_admin(request.user):
        raise PermissionDenied
    
    user = get_object_or_404(User, id=user_id)
    
    # Get user's audit logs
    user_logs = AuditLog.objects.filter(user=user).order_by('-timestamp')
    
    # Statistics
    total_actions = user_logs.count()
    actions_by_type = user_logs.values('action').annotate(count=Count('id'))
    actions_by_model = user_logs.values('model_name').annotate(count=Count('id'))
    
    # Recent activity
    recent_activity = user_logs[:20]
    
    # Login patterns
    login_logs = user_logs.filter(action='LOGIN')
    unique_ips = login_logs.values('ip_address').distinct().count()
    last_login = login_logs.first()
    
    context = {
        'target_user': user,
        'total_actions': total_actions,
        'actions_by_type': actions_by_type,
        'actions_by_model': actions_by_model,
        'recent_activity': recent_activity,
        'unique_ips': unique_ips,
        'last_login': last_login,
    }
    
    return render(request, 'core/analytics/user_activity_report.html', context)

@login_required
def system_health_check(request):
    """System health check with audit insights"""
    if not is_admin(request.user):
        raise PermissionDenied
    
    # Check for unusual patterns
    today = timezone.now().date()
    week_ago = today - timedelta(days=7)
    
    # High frequency actions
    high_frequency_users = AuditLog.objects.filter(
        timestamp__date__gte=week_ago
    ).values('user__username').annotate(
        count=Count('id')
    ).filter(count__gt=100)  # More than 100 actions in a week
    
    # Failed logins
    failed_logins = AuditLog.objects.filter(
        action='LOGIN',
        timestamp__date__gte=week_ago,
        details__icontains='failed'  # Assuming failed logins are recorded in details
    ).count()
    
    # Bulk deletions
    bulk_deletions = AuditLog.objects.filter(
        action='DELETE',
        timestamp__date__gte=week_ago
    ).values('model_name').annotate(
        count=Count('id')
    ).filter(count__gt=10)  # More than 10 deletions of same model type
    
    context = {
        'high_frequency_users': list(high_frequency_users),
        'failed_logins': failed_logins,
        'bulk_deletions': list(bulk_deletions),
        'total_logs_today': AuditLog.objects.filter(timestamp__date=today).count(),
    }
    
    return render(request, 'core/analytics/system_health.html', context)

# Existing functions from your original file (kept for compatibility)
@login_required
def student_progress_chart(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    
    # Check permissions
    if is_student(request.user) and request.user.student != student:
        raise PermissionDenied
    elif is_teacher(request.user):
        # Check if teacher teaches this student
        if not ClassAssignment.objects.filter(
            class_level=student.class_level,
            teacher=request.user.teacher
        ).exists():
            raise PermissionDenied
    
    grades = Grade.objects.filter(student=student).order_by('subject')
    
    subjects = [grade.subject.name for grade in grades]
    scores = [float(grade.total_score) for grade in grades]
    
    data = {
        'subjects': subjects,
        'scores': scores,
    }
    
    return JsonResponse(data)

@login_required
def class_performance_chart(request, class_level):
    # Check permissions
    if is_student(request.user):
        raise PermissionDenied
    elif is_teacher(request.user):
        # Check if teacher teaches this class
        if not ClassAssignment.objects.filter(
            class_level=class_level,
            teacher=request.user.teacher
        ).exists():
            raise PermissionDenied
    
    grades = Grade.objects.filter(
        class_assignment__class_level=class_level
    ).values('subject__name').annotate(
        average_score=Avg('total_score')
    ).order_by('subject__name')
    
    subjects = [grade['subject__name'] for grade in grades]
    averages = [float(grade['average_score']) for grade in grades]
    
    data = {
        'subjects': subjects,
        'averages': averages,
    }
    
    return JsonResponse(data)

