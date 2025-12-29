# core/utils/query_optimizer.py
"""
Query optimization utilities for parent portal
"""
from django.db.models import Prefetch, Count, Sum, Avg, Q, Subquery, OuterRef
from django.db.models.functions import Coalesce
from django.utils import timezone
from datetime import timedelta

class ParentQueryOptimizer:
    """Optimized query builder for parent portal"""
    
    @staticmethod
    def optimize_child_queries(children_queryset):
        """
        Apply optimal prefetching and selecting for children queryset
        """
        from core.models import Grade, StudentAttendance, Fee, StudentAssignment
        
        current_date = timezone.now().date()
        current_month = current_date.month
        current_year = current_date.year
        
        return children_queryset.select_related('user').prefetch_related(
            # Prefetch recent grades (max 3 per child)
            Prefetch(
                'grade_set',
                queryset=Grade.objects.select_related('subject')
                                     .order_by('-last_updated')[:3],
                to_attr='prefetched_recent_grades'
            ),
            # Prefetch current month attendance
            Prefetch(
                'studentattendance_set',
                queryset=StudentAttendance.objects.filter(
                    date__month=current_month,
                    date__year=current_year
                ),
                to_attr='prefetched_monthly_attendance'
            ),
            # Prefetch unpaid fees
            Prefetch(
                'fee_set',
                queryset=Fee.objects.filter(
                    payment_status__in=['unpaid', 'partial']
                ).select_related('category'),
                to_attr='prefetched_unpaid_fees'
            ),
            # Prefetch recent assignments
            Prefetch(
                'studentassignment_set',
                queryset=StudentAssignment.objects.select_related('assignment')
                                                 .order_by('-assignment__due_date')[:3],
                to_attr='prefetched_recent_assignments'
            )
        )
    
    @staticmethod
    def get_child_summary_stats(child):
        """
        Calculate summary statistics for a child using prefetched data
        Returns data without additional database queries
        """
        # Use prefetched data
        recent_grades = getattr(child, 'prefetched_recent_grades', [])
        monthly_attendance = getattr(child, 'prefetched_monthly_attendance', [])
        unpaid_fees = getattr(child, 'prefetched_unpaid_fees', [])
        
        # Calculate attendance from prefetched data
        present_count = sum(1 for a in monthly_attendance if a.status == 'present')
        total_attendance = len(monthly_attendance)
        attendance_percentage = round((present_count / total_attendance * 100), 1) if total_attendance > 0 else 0
        
        # Calculate fee totals from prefetched data
        total_due = sum(fee.balance for fee in unpaid_fees)
        
        # Calculate average grade from prefetched data
        if recent_grades:
            avg_grade = sum(grade.total_score for grade in recent_grades) / len(recent_grades)
        else:
            avg_grade = 0
        
        # Determine performance level
        performance_level = "No Data"
        if avg_grade > 0:
            if avg_grade >= 80:
                performance_level = "Excellent"
            elif avg_grade >= 70:
                performance_level = "Very Good"
            elif avg_grade >= 60:
                performance_level = "Good"
            elif avg_grade >= 50:
                performance_level = "Satisfactory"
            elif avg_grade >= 40:
                performance_level = "Fair"
            else:
                performance_level = "Needs Improvement"
        
        return {
            'recent_grades': recent_grades[:3],  # Ensure max 3
            'average_grade': round(avg_grade, 1),
            'performance_level': performance_level,
            'attendance': {
                'present': present_count,
                'absent': sum(1 for a in monthly_attendance if a.status == 'absent'),
                'late': sum(1 for a in monthly_attendance if a.status == 'late'),
                'excused': sum(1 for a in monthly_attendance if a.status == 'excused'),
                'total': total_attendance,
                'percentage': attendance_percentage
            },
            'fee_summary': {
                'total_due': total_due,
                'unpaid_count': len(unpaid_fees),
                'total_payable': sum(fee.amount_payable for fee in unpaid_fees),
                'total_paid': sum(fee.amount_paid for fee in unpaid_fees),
                'balance': total_due
            }
        }
    
    @staticmethod
    def get_aggregated_stats(parent):
        """
        Get aggregated statistics for all children with minimal queries
        """
        from core.models import StudentAttendance, Fee, Grade
        
        children = parent.students.all()
        child_ids = list(children.values_list('id', flat=True))
        
        if not child_ids:
            return {}
        
        current_date = timezone.now().date()
        current_month = current_date.month
        current_year = current_date.year
        
        # Single query for attendance stats
        attendance_stats = StudentAttendance.objects.filter(
            student_id__in=child_ids,
            date__month=current_month,
            date__year=current_year
        ).aggregate(
            total=Count('id'),
            present=Count('id', filter=Q(status='present')),
            absent=Count('id', filter=Q(status='absent')),
            late=Count('id', filter=Q(status='late')),
            excused=Count('id', filter=Q(status='excused'))
        )
        
        # Single query for fee stats
        fee_stats = Fee.objects.filter(
            student_id__in=child_ids
        ).aggregate(
            total_payable=Coalesce(Sum('amount_payable'), 0),
            total_paid=Coalesce(Sum('amount_paid'), 0),
            unpaid_count=Count('id', filter=Q(payment_status__in=['unpaid', 'partial'])),
            overdue_count=Count('id', filter=Q(
                due_date__lt=current_date,
                payment_status__in=['unpaid', 'partial']
            ))
        )
        
        # Calculate attendance rate
        if attendance_stats['total'] > 0:
            attendance_rate = (attendance_stats['present'] / attendance_stats['total']) * 100
        else:
            attendance_rate = 0
        
        return {
            'total_children': len(child_ids),
            'total_attendance_records': attendance_stats['total'],
            'present_count': attendance_stats['present'],
            'absent_count': attendance_stats['absent'],
            'late_count': attendance_stats['late'],
            'excused_count': attendance_stats['excused'],
            'attendance_rate': round(attendance_rate, 1),
            'total_payable': fee_stats['total_payable'],
            'total_paid': fee_stats['total_paid'],
            'total_balance': fee_stats['total_payable'] - fee_stats['total_paid'],
            'unpaid_fee_count': fee_stats['unpaid_count'],
            'overdue_fee_count': fee_stats['overdue_count'],
        }