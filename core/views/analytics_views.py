from django.views.generic import ListView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import Count, Sum, Avg, Max, Min, Q
from django.http import JsonResponse
from django.utils import timezone
import json
from decimal import Decimal
from datetime import date, timedelta

from .base_views import *
from ..models import AuditLog, AnalyticsCache, GradeAnalytics, AttendanceAnalytics
from ..filters import AuditLogFilter
from core.models import StudentAttendance, Fee, Grade, ClassAssignment
from core.utils import send_email

# analytics views

class DecimalJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, Decimal):
            return float(obj)
        elif isinstance(obj, date):
            return obj.isoformat()  # Convert date to ISO format string
        return super().default(obj)

class AnalyticsDashboardView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/analytics/dashboard.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_admin'] = is_admin(self.request.user)
        context['is_teacher'] = is_teacher(self.request.user)
        # Get date range for analytics (last 30 days)
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=30)
        
        context.update({
            'attendance_stats': self._get_attendance_stats(start_date, end_date),
            'grade_stats': self._get_grade_stats(),
            'fee_stats': self._get_fee_stats(start_date, end_date),
            'start_date': start_date,
            'end_date': end_date,
        })
        return context

    def _get_attendance_stats(self, start_date, end_date):
        """Get attendance statistics with caching"""
        cache_key = f"attendance_stats_{start_date}_{end_date}"
        cached_data = AnalyticsCache.get_cached_data(cache_key)

        if cached_data:
            return cached_data
        
        # Calculate fresh data if not cached
        if is_admin(self.request.user):
            attendance_data = StudentAttendance.objects.filter(
                date__range=(start_date, end_date)
            )
        else:
            # For teachers, only show their classes
            teacher_classes = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            ).values_list('class_level', flat=True)
            
            attendance_data = StudentAttendance.objects.filter(
                date__range=(start_date, end_date),
                student__class_level__in=teacher_classes
            )
        
        stats = attendance_data.aggregate(
            present=Count('id', filter=Q(status='present')),
            absent=Count('id', filter=Q(status='absent')),
            late=Count('id', filter=Q(status='late')),
            excused=Count('id', filter=Q(status='excused')),
        )
        
        total = sum(stats.values())
        attendance_rate = round((stats['present'] / total) * 100, 2) if total > 0 else 0
        
        result = {
            'stats': stats,
            'attendance_rate': attendance_rate,
            'trend_data': self._get_attendance_trend(start_date, end_date),
            'class_breakdown': self._get_class_attendance(start_date, end_date),
        }
        
        # Cache the result with proper Decimal handling
        AnalyticsCache.objects.update_or_create(
            name=cache_key,
            defaults={'data': json.loads(json.dumps(result, cls=DecimalJSONEncoder))}
        )
        
        return result
    
    def _get_attendance_trend(self, start_date, end_date):
        """Get attendance trend data by day"""
        if is_admin(self.request.user):
            trend_data = StudentAttendance.objects.filter(
                date__range=(start_date, end_date)
            ).values('date').annotate(
                present=Count('id', filter=Q(status='present')),
                absent=Count('id', filter=Q(status='absent')),
                late=Count('id', filter=Q(status='late')),
            ).order_by('date')
        else:
            teacher_classes = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            ).values_list('class_level', flat=True)
            
            trend_data = StudentAttendance.objects.filter(
                date__range=(start_date, end_date),
                student__class_level__in=teacher_classes
            ).values('date').annotate(
                present=Count('id', filter=Q(status='present')),
                absent=Count('id', filter=Q(status='absent')),
                late=Count('id', filter=Q(status='late')),
            ).order_by('date')
        
        return list(trend_data)
    
    def _get_class_attendance(self, start_date, end_date):
        """Get attendance breakdown by class"""
        if is_admin(self.request.user):
            class_data = StudentAttendance.objects.filter(
                date__range=(start_date, end_date)
            ).values('student__class_level').annotate(
                present=Count('id', filter=Q(status='present')),
                absent=Count('id', filter=Q(status='absent')),
                late=Count('id', filter=Q(status='late')),
                total=Count('id'),
            ).order_by('student__class_level')
        else:
            teacher_classes = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            ).values_list('class_level', flat=True)
            
            class_data = StudentAttendance.objects.filter(
                date__range=(start_date, end_date),
                student__class_level__in=teacher_classes
            ).values('student__class_level').annotate(
                present=Count('id', filter=Q(status='present')),
                absent=Count('id', filter=Q(status='absent')),
                late=Count('id', filter=Q(status='late')),
                total=Count('id'),
            ).order_by('student__class_level')
        
        # Calculate percentages
        for item in class_data:
            item['present_pct'] = round((item['present'] / item['total']) * 100, 1) if item['total'] > 0 else 0
            item['absent_pct'] = round((item['absent'] / item['total']) * 100, 1) if item['total'] > 0 else 0
            item['late_pct'] = round((item['late'] / item['total']) * 100, 1) if item['total'] > 0 else 0
        
        return list(class_data)
    
    def _get_grade_stats(self):
        """Get grade statistics with caching"""
        cache_key = "grade_stats"
        cached_data = AnalyticsCache.get_cached_data(cache_key)
        
        if cached_data:
            return cached_data
        
        # Calculate fresh data if not cached
        if is_admin(self.request.user):
            grade_data = Grade.objects.all()
        else:
            # For teachers, only show their classes
            teacher_classes = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            ).values_list('class_level', flat=True)
            
            grade_data = Grade.objects.filter(
                class_assignment__class_level__in=teacher_classes
            )
        
        stats = grade_data.aggregate(
            avg_score=Avg('total_score'),
            max_score=Max('total_score'),
            min_score=Min('total_score'),
            count=Count('id'),
        )
        
        # Get grade distribution
        grade_distribution = grade_data.values(
            'student__class_level'
        ).annotate(
            avg_score=Avg('total_score'),
            count=Count('id'),
        ).order_by('student__class_level')
        
        # Get subject performance
        subject_performance = grade_data.values(
            'subject__name'
        ).annotate(
            avg_score=Avg('total_score'),
            count=Count('id'),
        ).order_by('-avg_score')
        
        # Convert Decimal to float for JSON serialization
        result = {
            'overall': {
                'avg_score': float(stats['avg_score']) if stats['avg_score'] else 0,
                'max_score': float(stats['max_score']) if stats['max_score'] else 0,
                'min_score': float(stats['min_score']) if stats['min_score'] else 0,
                'count': stats['count']
            },
            'grade_distribution': [
                {
                    **item,
                    'avg_score': float(item['avg_score']) if item['avg_score'] else 0
                }
                for item in grade_distribution
            ],
            'subject_performance': [
                {
                    **item,
                    'avg_score': float(item['avg_score']) if item['avg_score'] else 0
                }
                for item in subject_performance
            ],
        }
        
        AnalyticsCache.objects.update_or_create(
            name=cache_key,
            defaults={'data': json.loads(json.dumps(result, cls=DecimalJSONEncoder))}
        )
        return result

    def _get_fee_stats(self, start_date, end_date):
        """Get fee statistics with caching"""
        cache_key = f"fee_stats_{start_date}_{end_date}"
        cached_data = AnalyticsCache.get_cached_data(cache_key)
        
        if cached_data:
            return cached_data
        
        # Calculate fresh data if not cached
        if is_admin(self.request.user):
            fee_data = Fee.objects.filter(
                date_recorded__range=(start_date, end_date)
            )
        else:
            # Teachers can only see their classes' fees
            teacher_classes = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            ).values_list('class_level', flat=True)
            
            fee_data = Fee.objects.filter(
                date_recorded__range=(start_date, end_date),
                student__class_level__in=teacher_classes
            )
        
        stats = fee_data.aggregate(
            total_payable=Sum('amount_payable'),
            total_paid=Sum('amount_paid'),
            count=Count('id'),
        )
        
        # Calculate collection rate
        total_payable = stats['total_payable'] or Decimal('0')
        total_paid = stats['total_paid'] or Decimal('0')
        collection_rate = round((total_paid / total_payable) * 100, 2) if total_payable > 0 else 0
        
        # Get payment status distribution
        status_distribution = fee_data.values(
            'payment_status'
        ).annotate(
            count=Count('id'),
            amount=Sum('amount_payable'),
        ).order_by('payment_status')
        
        # Get fee category breakdown
        category_breakdown = fee_data.values(
            'category__name'
        ).annotate(
            total_payable=Sum('amount_payable'),
            total_paid=Sum('amount_paid'),
            count=Count('id'),
        ).order_by('-total_payable')
        
        # Convert Decimal to float for JSON serialization
        result = {
            'stats': {
                'total_payable': float(stats['total_payable']) if stats['total_payable'] else 0,
                'total_paid': float(stats['total_paid']) if stats['total_paid'] else 0,
                'count': stats['count']
            },
            'collection_rate': collection_rate,
            'status_distribution': [
                {
                    **item,
                    'amount': float(item['amount']) if item['amount'] else 0
                }
                for item in status_distribution
            ],
            'category_breakdown': [
                {
                    **item,
                    'total_payable': float(item['total_payable']) if item['total_payable'] else 0,
                    'total_paid': float(item['total_paid']) if item['total_paid'] else 0
                }
                for item in category_breakdown
            ],
        }
        
        AnalyticsCache.objects.update_or_create(
            name=cache_key,
            defaults={'data': json.loads(json.dumps(result, cls=DecimalJSONEncoder))}
        )
        return result

def generate_receipt_pdf(payment):
    from reportlab.pdfgen import canvas
    from io import BytesIO
    
    buffer = BytesIO()
    p = canvas.Canvas(buffer)
    
    # Draw receipt content
    p.drawString(100, 800, f"Receipt #: {payment.receipt_number}")
    p.drawString(100, 780, f"Date: {payment.payment_date.strftime('%Y-%m-%d')}")
    p.drawString(100, 760, f"Student: {payment.fee.student.get_full_name()}")
    p.drawString(100, 740, f"Amount: ${payment.amount:.2f}")
    
    p.showPage()
    p.save()
    
    pdf = buffer.getvalue()
    buffer.close()
    return pdf


def send_payment_reminders():
    upcoming_due = date.today() + timedelta(days=3)  # 3 days before due
    overdue_fees = Fee.objects.filter(
        due_date=upcoming_due,
        payment_status__in=['unpaid', 'partial']
    )
    
    for fee in overdue_fees:
        for parent in fee.student.parents.all():
            send_email(
                subject=f"Upcoming Fee Payment Due for {fee.student}",
                message=f"Payment of {fee.balance} is due on {fee.due_date}",
                recipient=parent.email
            )