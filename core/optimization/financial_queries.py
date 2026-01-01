# core/optimization/financial_queries.py
from django.db.models import Prefetch, Subquery, OuterRef
from django.db import connection
from django.core.cache import cache
import hashlib
import json

class OptimizedFinancialQueries:
    """Optimized database queries for financial operations"""
    
    @staticmethod
    def get_student_financial_summary(student_id, use_cache=True):
        """Get optimized financial summary for student"""
        cache_key = f"student_financial_{student_id}"
        
        if use_cache:
            cached = cache.get(cache_key)
            if cached:
                return cached
        
        # Optimized query using subqueries
        from core.models import Fee, Bill, FeePayment
        
        # Use subquery for recent payments
        recent_payments_subquery = FeePayment.objects.filter(
            fee=OuterRef('pk')
        ).order_by('-payment_date').values('amount')[:5]
        
        # Prefetch related data efficiently
        fees = Fee.objects.filter(
            student_id=student_id
        ).select_related('category').prefetch_related(
            Prefetch('payments', queryset=FeePayment.objects.order_by('-payment_date')[:10])
        ).annotate(
            recent_payments=Subquery(recent_payments_subquery)
        )
        
        bills = Bill.objects.filter(
            student_id=student_id
        ).select_related('student').prefetch_related('items')
        
        # Calculate summary
        summary = {
            'total_fees': sum(f.amount_payable for f in fees),
            'total_paid': sum(f.amount_paid for f in fees),
            'total_balance': sum(f.balance for f in fees),
            'bill_total': sum(b.total_amount for b in bills),
            'bill_paid': sum(b.amount_paid for b in bills),
            'bill_balance': sum(b.balance for b in bills),
            'fees': list(fees.values('id', 'category__name', 'amount_payable', 'amount_paid', 'balance', 'payment_status')),
            'bills': list(bills.values('id', 'bill_number', 'total_amount', 'amount_paid', 'balance', 'status'))
        }
        
        # Cache for 5 minutes
        if use_cache:
            cache.set(cache_key, summary, timeout=300)
        
        return summary
    
    @staticmethod
    def bulk_financial_report(academic_year, term, class_levels=None):
        """Optimized bulk financial report"""
        # Use raw SQL for complex aggregations
        query = """
        SELECT 
            s.id as student_id,
            s.student_id as student_number,
            CONCAT(s.first_name, ' ', s.last_name) as student_name,
            s.class_level,
            COALESCE(SUM(f.amount_payable), 0) as total_fees,
            COALESCE(SUM(f.amount_paid), 0) as total_paid,
            COALESCE(SUM(f.balance), 0) as total_balance,
            COUNT(CASE WHEN f.payment_status = 'overdue' THEN 1 END) as overdue_count,
            MAX(f.due_date) as latest_due_date
        FROM core_student s
        LEFT JOIN core_fee f ON s.id = f.student_id 
            AND f.academic_year = %s 
            AND f.term = %s
        WHERE s.is_active = TRUE
        """
        
        params = [academic_year, term]
        
        if class_levels:
            placeholders = ', '.join(['%s'] * len(class_levels))
            query += f" AND s.class_level IN ({placeholders})"
            params.extend(class_levels)
        
        query += " GROUP BY s.id, s.student_id, s.first_name, s.last_name, s.class_level"
        query += " ORDER BY s.class_level, s.last_name, s.first_name"
        
        with connection.cursor() as cursor:
            cursor.execute(query, params)
            columns = [col[0] for col in cursor.description]
            results = [dict(zip(columns, row)) for row in cursor.fetchall()]
        
        return results