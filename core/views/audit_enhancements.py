# core/views/audit_enhancements.py
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, CreateView, UpdateView, DetailView, TemplateView
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.utils import timezone
from django.core.exceptions import PermissionDenied
from django.views.decorators.http import require_POST
from django.contrib.auth.decorators import login_required
import json

from core.models import (
    AuditAlertRule, SecurityEvent, AuditReport, DataRetentionPolicy
)
from core.utils.audit_enhancements import (
    RealTimeSecurityMonitor, AdvancedAuditAnalytics, 
    AuditReportGenerator, DataRetentionManager
)
from .base_views import is_admin

# Real-time Security Monitoring Views
class SecurityEventListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = SecurityEvent
    template_name = 'core/analytics/security_events.html'
    context_object_name = 'events'
    paginate_by = 20
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_queryset(self):
        queryset = SecurityEvent.objects.all().select_related('user', 'rule')
        
        # Filter by severity
        severity = self.request.GET.get('severity')
        if severity:
            queryset = queryset.filter(severity=severity)
        
        # Filter by resolved status
        resolved = self.request.GET.get('resolved')
        if resolved == 'true':
            queryset = queryset.filter(is_resolved=True)
        elif resolved == 'false':
            queryset = queryset.filter(is_resolved=False)
        
        return queryset.order_by('-created_at')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['severity_choices'] = AuditAlertRule.SEVERITY_CHOICES
        return context

class AuditAlertRuleListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = AuditAlertRule
    template_name = 'core/analytics/alert_rules.html'
    context_object_name = 'rules'
    
    def test_func(self):
        return is_admin(self.request.user)

class AuditAlertRuleCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = AuditAlertRule
    template_name = 'core/analytics/alert_rule_form.html'
    fields = ['name', 'description', 'condition_type', 'condition_config', 
              'severity', 'action', 'is_active']
    success_url = reverse_lazy('alert_rule_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        messages.success(self.request, 'Alert rule created successfully!')
        return super().form_valid(form)

# Advanced Analytics Views
class AdvancedAnalyticsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/analytics/advanced_analytics.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        analytics = AdvancedAuditAnalytics()
        
        # Get risk scores for active users
        users = User.objects.filter(is_active=True)[:50]  # Limit for performance
        risk_scores = analytics.predict_risk_scores(users)
        
        context['risk_scores'] = risk_scores
        context['users'] = users
        
        # Get anomaly detection results
        anomalies = analytics.detect_anomalies()
        context['anomaly_count'] = len(anomalies)
        
        return context

@login_required
@require_POST
def run_anomaly_detection(request):
    """API endpoint to run anomaly detection"""
    if not is_admin(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        analytics = AdvancedAuditAnalytics()
        anomalies = analytics.detect_anomalies()
        
        return JsonResponse({
            'success': True,
            'anomaly_count': len(anomalies),
            'anomalies': anomalies[:10]  # Return first 10 for preview
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# Automated Reporting Views
class AuditReportListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = AuditReport
    template_name = 'core/analytics/audit_reports.html'
    context_object_name = 'reports'
    paginate_by = 10
    
    def test_func(self):
        return is_admin(self.request.user)

@login_required
@require_POST
def generate_custom_report(request):
    """Generate custom audit report"""
    if not is_admin(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        report_type = request.POST.get('report_type', 'CUSTOM')
        parameters = json.loads(request.POST.get('parameters', '{}'))
        
        generator = AuditReportGenerator()
        
        if report_type == 'DAILY':
            report = generator.generate_daily_report()
        else:
            # Handle custom report generation
            pass
        
        return JsonResponse({
            'success': True,
            'report_id': report.id,
            'message': 'Report generated successfully'
        })
        
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})

# Data Retention Management Views
class DataRetentionPolicyListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = DataRetentionPolicy
    template_name = 'core/analytics/retention_policies.html'
    context_object_name = 'policies'
    
    def test_func(self):
        return is_admin(self.request.user)

@login_required
@require_POST
def apply_retention_policies(request):
    """Apply all data retention policies"""
    if not is_admin(request.user):
        return JsonResponse({'error': 'Permission denied'}, status=403)
    
    try:
        manager = DataRetentionManager()
        manager.apply_retention_policies()
        
        return JsonResponse({
            'success': True,
            'message': 'Retention policies applied successfully'
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': str(e)})
