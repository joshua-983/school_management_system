# core/views/dashboard_views.py
import json
from datetime import datetime, timedelta
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.utils import timezone
from django.db.models import Sum, Count, Q
from django.http import JsonResponse

from core.models import Fee, Bill, FeePayment, Student
from core.services.financial_reports import FinancialReportGenerator
from core.services.automation import FinancialAutomationService


class ProfessionalFinanceDashboard(LoginRequiredMixin, TemplateView):
    """Professional finance dashboard with real-time data"""
    template_name = 'core/finance/dashboard/professional_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get date range
        today = timezone.now().date()
        start_of_month = today.replace(day=1)
        start_of_year = today.replace(month=1, day=1)
        
        # Real-time statistics
        context.update(self._get_real_time_stats(today))
        
        # Monthly trends
        context.update(self._get_monthly_trends(start_of_month))
        
        # Performance metrics
        context.update(self._get_performance_metrics())
        
        # Alerts and notifications
        context.update(self._get_alerts_and_notifications())
        
        # Recent activity
        context.update(self._get_recent_activity())
        
        return context
    
    def _get_real_time_stats(self, today):
        """Get real-time financial statistics"""
        # Today's collections
        today_collections = FeePayment.objects.filter(
            payment_date__date=today,
            is_confirmed=True
        ).aggregate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Outstanding amounts
        outstanding_fees = Fee.objects.filter(
            payment_status__in=['unpaid', 'partial', 'overdue']
        ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
        
        outstanding_bills = Bill.objects.filter(
            status__in=['issued', 'partial', 'overdue']
        ).aggregate(total=Sum('balance'))['total'] or Decimal('0.00')
        
        # Student statistics
        total_students = Student.objects.filter(is_active=True).count()
        students_with_arrears = Student.objects.filter(
            Q(fees__payment_status__in=['unpaid', 'partial', 'overdue']) |
            Q(bills__status__in=['issued', 'partial', 'overdue'])
        ).distinct().count()
        
        return {
            'today_collections': {
                'total': today_collections['total'] or Decimal('0.00'),
                'count': today_collections['count'] or 0,
                'average': (today_collections['total'] / today_collections['count']) 
                          if today_collections['count'] > 0 else Decimal('0.00')
            },
            'outstanding': {
                'fees': outstanding_fees,
                'bills': outstanding_bills,
                'total': outstanding_fees + outstanding_bills
            },
            'student_stats': {
                'total': total_students,
                'with_arrears': students_with_arrears,
                'percentage': (students_with_arrears / total_students * 100) if total_students > 0 else 0
            }
        }
    
    def _get_monthly_trends(self, start_of_month):
        """Get monthly trends for charts"""
        # Monthly collection trend
        monthly_data = []
        for i in range(6):  # Last 6 months
            month_date = start_of_month - timedelta(days=30*i)
            month_start = month_date.replace(day=1)
            month_end = (month_start + timedelta(days=32)).replace(day=1) - timedelta(days=1)
            
            month_total = FeePayment.objects.filter(
                payment_date__range=[month_start, month_end],
                is_confirmed=True
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            monthly_data.append({
                'month': month_start.strftime('%b %Y'),
                'total': float(month_total),
                'date': month_start.strftime('%Y-%m')
            })
        
        monthly_data.reverse()  # Oldest to newest
        
        # Payment method distribution
        payment_methods = FeePayment.objects.filter(
            payment_date__gte=start_of_month,
            is_confirmed=True
        ).values('payment_mode').annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')
        
        return {
            'monthly_trend_data': json.dumps(monthly_data),
            'payment_methods': payment_methods,
            'current_month': start_of_month.strftime('%B %Y')
        }
    
    def _get_alerts_and_notifications(self):
        """Get alerts and notifications for dashboard"""
        alerts = []
        
        # Overdue payments alert
        overdue_count = Fee.objects.filter(
            payment_status='overdue'
        ).count()
        
        if overdue_count > 0:
            alerts.append({
                'type': 'warning',
                'title': f'{overdue_count} Overdue Payments',
                'message': f'There are {overdue_count} overdue fee payments requiring attention.',
                'icon': 'exclamation-triangle',
                'link': '/financial/fees/?status=overdue'
            })
        
        # Large cash transactions alert
        today = timezone.now().date()
        large_cash_count = FeePayment.objects.filter(
            payment_date__date=today,
            payment_mode='cash',
            amount__gte=Decimal('5000.00')
        ).count()
        
        if large_cash_count > 0:
            alerts.append({
                'type': 'info',
                'title': f'{large_cash_count} Large Cash Transactions',
                'message': f'{large_cash_count} cash transactions above GH₵5,000 today.',
                'icon': 'cash',
                'link': '/financial/reports/large-transactions/'
            })
        
        # Reconciliation alert
        yesterday = today - timedelta(days=1)
        reconciled = FinancialAuditTrail.objects.filter(
            action='RECONCILIATION',
            timestamp__date=yesterday
        ).exists()
        
        if not reconciled:
            alerts.append({
                'type': 'danger',
                'title': 'Pending Reconciliation',
                'message': 'Yesterday\'s transactions have not been reconciled.',
                'icon': 'calculator',
                'link': '/financial/reconcile/daily/'
            })
        
        return {
            'alerts': alerts,
            'alert_count': len(alerts)
        }