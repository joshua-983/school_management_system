# core/services/financial_reports.py
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Avg, Q, F
from django.db import connection
from collections import defaultdict
import calendar

from core.models import Fee, FeePayment, Bill, BillPayment, Student, FeeCategory
from core.utils.financial import FinancialCalculator

logger = logging.getLogger(__name__)


class FinancialReportGenerator:
    """Generate professional financial reports"""
    
    def __init__(self, academic_year=None, term=None):
        self.academic_year = academic_year
        self.term = term
        self.calculator = FinancialCalculator()
        
        if not academic_year:
            current_year = timezone.now().year
            self.academic_year = f"{current_year}/{current_year + 1}"
    
    def generate_income_statement(self, start_date=None, end_date=None):
        """Generate income statement (Profit & Loss)"""
        if not start_date:
            start_date = timezone.now().replace(day=1, month=1).date()
        if not end_date:
            end_date = timezone.now().date()
        
        # Calculate revenue
        revenue_data = self._calculate_revenue(start_date, end_date)
        
        # Calculate expenses (you'll need an Expense model)
        expense_data = self._calculate_expenses(start_date, end_date)
        
        # Calculate net income
        total_revenue = revenue_data['total']
        total_expenses = expense_data['total']
        net_income = total_revenue - total_expenses
        
        # Calculate margins
        gross_margin = revenue_data.get('gross_margin', 0)
        net_margin = (net_income / total_revenue * 100) if total_revenue > 0 else 0
        
        return {
            'period': {
                'start_date': start_date,
                'end_date': end_date,
                'days': (end_date - start_date).days
            },
            'revenue': revenue_data,
            'expenses': expense_data,
            'profitability': {
                'net_income': net_income,
                'gross_margin': gross_margin,
                'net_margin': net_margin,
                'operating_margin': self._calculate_operating_margin(total_revenue, expense_data),
                'ebitda': self._calculate_ebitda(net_income, expense_data)
            },
            'key_metrics': self._calculate_key_metrics(start_date, end_date)
        }
    
    def generate_balance_sheet(self, as_of_date=None):
        """Generate balance sheet"""
        if not as_of_date:
            as_of_date = timezone.now().date()
        
        # Assets
        assets = self._calculate_assets(as_of_date)
        
        # Liabilities
        liabilities = self._calculate_liabilities(as_of_date)
        
        # Equity
        equity = self._calculate_equity(assets['total'], liabilities['total'])
        
        return {
            'as_of_date': as_of_date,
            'assets': assets,
            'liabilities': liabilities,
            'equity': equity,
            'balance_check': assets['total'] == (liabilities['total'] + equity['total']),
            'ratios': self._calculate_financial_ratios(assets, liabilities, equity)
        }
    
    def generate_cash_flow_statement(self, start_date=None, end_date=None):
        """Generate cash flow statement"""
        if not start_date:
            start_date = timezone.now().replace(day=1).date() - timedelta(days=30)
        if not end_date:
            end_date = timezone.now().date()
        
        # Operating activities
        operating = self._calculate_operating_cash_flow(start_date, end_date)
        
        # Investing activities (placeholder)
        investing = {
            'equipment_purchases': Decimal('0.00'),
            'property_investments': Decimal('0.00'),
            'other_investing': Decimal('0.00'),
            'total': Decimal('0.00')
        }
        
        # Financing activities (placeholder)
        financing = {
            'loans_received': Decimal('0.00'),
            'loan_repayments': Decimal('0.00'),
            'equity_investments': Decimal('0.00'),
            'dividends_paid': Decimal('0.00'),
            'total': Decimal('0.00')
        }
        
        net_cash_flow = operating['total'] + investing['total'] + financing['total']
        
        # Beginning and ending cash (simplified)
        beginning_cash = self._get_cash_balance(start_date - timedelta(days=1))
        ending_cash = beginning_cash + net_cash_flow
        
        return {
            'period': {'start_date': start_date, 'end_date': end_date},
            'operating_activities': operating,
            'investing_activities': investing,
            'financing_activities': financing,
            'cash_flow_summary': {
                'net_cash_flow': net_cash_flow,
                'beginning_cash': beginning_cash,
                'ending_cash': ending_cash,
                'cash_change_percentage': ((ending_cash - beginning_cash) / beginning_cash * 100) if beginning_cash > 0 else 0
            }
        }
    
    def generate_student_arrears_report(self):
        """Generate detailed student arrears report"""
        # Get students with outstanding balances
        students_with_arrears = Student.objects.filter(
            Q(fees__payment_status__in=['unpaid', 'partial', 'overdue']) |
            Q(bills__status__in=['issued', 'partial', 'overdue'])
        ).distinct().annotate(
            total_fee_balance=Sum('fees__balance', filter=Q(fees__payment_status__in=['unpaid', 'partial', 'overdue'])),
            total_bill_balance=Sum('bills__balance', filter=Q(bills__status__in=['issued', 'partial', 'overdue']))
        )
        
        report_data = []
        total_arrears = Decimal('0.00')
        
        for student in students_with_arrears:
            fee_balance = student.total_fee_balance or Decimal('0.00')
            bill_balance = student.total_bill_balance or Decimal('0.00')
            total_balance = fee_balance + bill_balance
            
            if total_balance > 0:
                # Get overdue details
                overdue_fees = student.fees.filter(
                    payment_status='overdue'
                ).count()
                
                overdue_bills = student.bills.filter(
                    status='overdue'
                ).count()
                
                # Calculate days overdue for oldest item
                oldest_due_date = self._get_oldest_due_date(student)
                days_overdue = (timezone.now().date() - oldest_due_date).days if oldest_due_date else 0
                
                student_data = {
                    'student_id': student.student_id,
                    'name': student.get_full_name(),
                    'class': student.get_class_level_display(),
                    'contact_phone': student.parent_phone or '',
                    'fee_balance': fee_balance,
                    'bill_balance': bill_balance,
                    'total_balance': total_balance,
                    'overdue_fees': overdue_fees,
                    'overdue_bills': overdue_bills,
                    'days_overdue': days_overdue,
                    'risk_level': self._calculate_risk_level(total_balance, days_overdue),
                    'last_payment_date': self._get_last_payment_date(student),
                    'payment_plan_eligible': total_balance > Decimal('1000.00')  # Example criteria
                }
                
                report_data.append(student_data)
                total_arrears += total_balance
        
        # Sort by highest balance
        report_data.sort(key=lambda x: x['total_balance'], reverse=True)
        
        return {
            'generated_date': timezone.now().date(),
            'total_students': len(report_data),
            'total_arrears': total_arrears,
            'average_arrears': total_arrears / len(report_data) if report_data else Decimal('0.00'),
            'students': report_data[:100],  # Limit for performance
            'summary_by_class': self._summarize_arrears_by_class(report_data),
            'collection_strategies': self._generate_collection_strategies(report_data)
        }
    
    def generate_fee_collection_analysis(self):
        """Analyze fee collection patterns and performance"""
        # Collection by month
        monthly_collection = self._get_monthly_collection()
        
        # Collection by payment method
        payment_method_analysis = self._analyze_payment_methods()
        
        # Collection efficiency
        efficiency_metrics = self._calculate_collection_efficiency()
        
        # Predictive analysis
        predictions = self._predict_future_collections()
        
        return {
            'time_period': {
                'start': self._get_academic_year_start(),
                'end': timezone.now().date()
            },
            'monthly_collection': monthly_collection,
            'payment_method_analysis': payment_method_analysis,
            'efficiency_metrics': efficiency_metrics,
            'predictions': predictions,
            'recommendations': self._generate_collection_recommendations(efficiency_metrics)
        }
    
    # Helper methods
    def _calculate_revenue(self, start_date, end_date):
        """Calculate revenue from fees and bills"""
        # Fee payments
        fee_revenue = FeePayment.objects.filter(
            payment_date__range=[start_date, end_date],
            is_confirmed=True
        ).aggregate(
            total=Sum('amount'),
            count=Count('id'),
            average=Avg('amount')
        )
        
        # Bill payments
        bill_revenue = BillPayment.objects.filter(
            payment_date__range=[start_date, end_date]
        ).aggregate(
            total=Sum('amount'),
            count=Count('id'),
            average=Avg('amount')
        )
        
        total_revenue = (fee_revenue['total'] or Decimal('0.00')) + (bill_revenue['total'] or Decimal('0.00'))
        
        # Revenue by category
        category_revenue = FeePayment.objects.filter(
            payment_date__range=[start_date, end_date],
            is_confirmed=True
        ).values(
            'fee__category__name'
        ).annotate(
            total=Sum('amount'),
            count=Count('id')
        ).order_by('-total')
        
        return {
            'total': total_revenue,
            'fee_revenue': fee_revenue,
            'bill_revenue': bill_revenue,
            'by_category': list(category_revenue),
            'gross_margin': Decimal('85.00'),  # Placeholder - should calculate based on costs
            'growth_rate': self._calculate_revenue_growth(start_date, end_date)
        }
    
    def _calculate_collection_efficiency(self):
        """Calculate collection efficiency metrics"""
        current_date = timezone.now().date()
        
        # Total fees billed
        total_billed = Fee.objects.filter(
            academic_year=self.academic_year
        ).aggregate(
            total=Sum('amount_payable')
        )['total'] or Decimal('0.00')
        
        # Total collected
        total_collected = FeePayment.objects.filter(
            fee__academic_year=self.academic_year,
            is_confirmed=True
        ).aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        # Overdue amounts
        overdue_amount = Fee.objects.filter(
            academic_year=self.academic_year,
            payment_status='overdue'
        ).aggregate(
            total=Sum('balance')
        )['total'] or Decimal('0.00')
        
        # Collection rate
        collection_rate = (total_collected / total_billed * 100) if total_billed > 0 else 0
        
        # Average collection period (days)
        avg_collection_period = self._calculate_average_collection_period()
        
        # Bad debt ratio
        bad_debt_ratio = (overdue_amount / total_billed * 100) if total_billed > 0 else 0
        
        return {
            'collection_rate': collection_rate,
            'total_billed': total_billed,
            'total_collected': total_collected,
            'overdue_amount': overdue_amount,
            'avg_collection_period': avg_collection_period,
            'bad_debt_ratio': bad_debt_ratio,
            'efficiency_score': self._calculate_efficiency_score(collection_rate, bad_debt_ratio)
        }
    
    def _calculate_average_collection_period(self):
        """Calculate average collection period in days"""
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT AVG(DATEDIFF(p.payment_date, f.due_date))
                FROM core_feepayment p
                JOIN core_fee f ON p.fee_id = f.id
                WHERE p.is_confirmed = 1 
                AND p.payment_date > f.due_date
                AND f.academic_year = %s
            """, [self.academic_year])
            
            result = cursor.fetchone()
            return result[0] if result[0] else 0
    
    def _calculate_efficiency_score(self, collection_rate, bad_debt_ratio):
        """Calculate collection efficiency score (0-100)"""
        # Weighted scoring
        collection_score = min(collection_rate, 100)  # Max 100
        bad_debt_score = max(0, 100 - (bad_debt_ratio * 2))  # Penalize bad debt
        
        # Weighted average
        efficiency_score = (collection_score * 0.7) + (bad_debt_score * 0.3)
        return round(efficiency_score, 1)
    
    def _generate_collection_recommendations(self, efficiency_metrics):
        """Generate recommendations based on collection efficiency"""
        recommendations = []
        
        if efficiency_metrics['collection_rate'] < 80:
            recommendations.append({
                'priority': 'high',
                'action': 'Implement automated payment reminders',
                'impact': 'Increase collection rate by 10-15%',
                'cost': 'Low',
                'timeline': 'Immediate'
            })
        
        if efficiency_metrics['bad_debt_ratio'] > 5:
            recommendations.append({
                'priority': 'high',
                'action': 'Review payment plans for students with high arrears',
                'impact': 'Reduce bad debt by 20-30%',
                'cost': 'Medium',
                'timeline': '1 month'
            })
        
        if efficiency_metrics['avg_collection_period'] > 30:
            recommendations.append({
                'priority': 'medium',
                'action': 'Offer early payment discounts',
                'impact': 'Reduce collection period by 10-15 days',
                'cost': 'Low',
                'timeline': 'Next term'
            })
        
        # Always include standard recommendations
        recommendations.extend([
            {
                'priority': 'low',
                'action': 'Diversify payment methods (add mobile money, bank transfer)',
                'impact': 'Increase convenience, potentially increase collections by 5%',
                'cost': 'Medium',
                'timeline': '3 months'
            },
            {
                'priority': 'medium',
                'action': 'Implement online payment portal',
                'impact': 'Reduce administrative costs, improve cash flow',
                'cost': 'High',
                'timeline': '6 months'
            }
        ])
        
        return recommendations