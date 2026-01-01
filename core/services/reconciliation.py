# core/services/reconciliation.py
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from django.utils import timezone
from django.db.models import Sum, Count, Q
from collections import defaultdict

from core.models import FeePayment, BillPayment, Expense
from core.models.audit import FinancialAuditTrail
from core.utils.financial import FinancialCalculator

logger = logging.getLogger(__name__)


class ReconciliationService:
    """Financial reconciliation service"""
    
    def __init__(self):
        self.calculator = FinancialCalculator()
    
    def daily_reconciliation(self, date=None):
        """Perform daily financial reconciliation"""
        if not date:
            date = timezone.now().date()
        
        try:
            # Get all payments for the day
            fee_payments = FeePayment.objects.filter(
                payment_date__date=date,
                is_confirmed=True
            )
            
            bill_payments = BillPayment.objects.filter(
                payment_date=date
            )
            
            # Calculate totals
            fee_total = fee_payments.aggregate(
                total=Sum('amount'),
                count=Count('id')
            )
            
            bill_total = bill_payments.aggregate(
                total=Sum('amount'),
                count=Count('id')
            )
            
            total_collected = (fee_total['total'] or Decimal('0.00')) + (bill_total['total'] or Decimal('0.00'))
            
            # Get expected cash (from cash payments)
            cash_payments = fee_payments.filter(payment_mode='cash').aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
            
            cash_bill_payments = bill_payments.filter(payment_mode='cash').aggregate(
                total=Sum('amount')
            )['total'] or Decimal('0.00')
            
            total_cash_expected = cash_payments + cash_bill_payments
            
            # Get bank deposits (from electronic payments)
            electronic_total = total_collected - total_cash_expected
            
            # Check for discrepancies
            discrepancies = self._check_for_discrepancies(
                date, total_collected, total_cash_expected, electronic_total
            )
            
            reconciliation_data = {
                'date': date,
                'summary': {
                    'total_collected': total_collected,
                    'fee_payments': {
                        'total': fee_total['total'] or Decimal('0.00'),
                        'count': fee_total['count'] or 0
                    },
                    'bill_payments': {
                        'total': bill_total['total'] or Decimal('0.00'),
                        'count': bill_total['count'] or 0
                    },
                    'cash_expected': total_cash_expected,
                    'electronic_total': electronic_total
                },
                'payment_method_breakdown': self._get_payment_method_breakdown(date),
                'discrepancies': discrepancies,
                'reconciliation_status': 'balanced' if not discrepancies else 'unbalanced'
            }
            
            # Log reconciliation
            FinancialAuditTrail.log_action(
                action='RECONCILIATION',
                model_name='DailyReconciliation',
                object_id=f"recon_{date.strftime('%Y%m%d')}",
                user=None,
                notes=f'Daily reconciliation for {date.strftime("%d/%m/%Y")} - Status: {reconciliation_data["reconciliation_status"]}'
            )
            
            # Send alert if unbalanced
            if discrepancies:
                self._send_reconciliation_alert(date, discrepancies)
            
            return reconciliation_data
            
        except Exception as e:
            logger.error(f"Error in daily reconciliation: {str(e)}")
            raise
    
    def monthly_reconciliation(self, year=None, month=None):
        """Perform monthly bank reconciliation"""
        if not year or not month:
            today = timezone.now().date()
            year = today.year
            month = today.month
        
        try:
            # Get all payments for the month
            fee_payments = FeePayment.objects.filter(
                payment_date__year=year,
                payment_date__month=month,
                is_confirmed=True
            )
            
            bill_payments = BillPayment.objects.filter(
                payment_date__year=year,
                payment_date__month=month
            )
            
            # Get expenses for the month
            expenses = Expense.objects.filter(
                date__year=year,
                date__month=month
            )
            
            # Calculate book balances
            book_balance = self._calculate_book_balance(fee_payments, bill_payments, expenses)
            
            # Get bank statement data (this would come from bank API or uploaded file)
            bank_statement = self._get_bank_statement(year, month)
            
            # Perform reconciliation
            reconciliation = self._reconcile_book_to_bank(book_balance, bank_statement)
            
            # Generate report
            reconciliation_data = {
                'period': f"{year}-{month:02d}",
                'book_balance': book_balance,
                'bank_statement': bank_statement,
                'reconciliation': reconciliation,
                'outstanding_items': self._identify_outstanding_items(reconciliation),
                'adjustments_needed': self._calculate_adjustments_needed(reconciliation)
            }
            
            # Log monthly reconciliation
            FinancialAuditTrail.log_action(
                action='RECONCILIATION',
                model_name='MonthlyReconciliation',
                object_id=f"monthly_{year}{month:02d}",
                user=None,
                notes=f'Monthly bank reconciliation for {year}-{month:02d}'
            )
            
            return reconciliation_data
            
        except Exception as e:
            logger.error(f"Error in monthly reconciliation: {str(e)}")
            raise
    
    def _check_for_discrepancies(self, date, total_collected, cash_expected, electronic_total):
        """Check for discrepancies in daily reconciliation"""
        discrepancies = []
        
        # Check for unconfirmed payments
        unconfirmed_payments = FeePayment.objects.filter(
            payment_date__date=date,
            is_confirmed=False
        ).count()
        
        if unconfirmed_payments > 0:
            discrepancies.append({
                'type': 'unconfirmed_payments',
                'count': unconfirmed_payments,
                'severity': 'medium',
                'action': 'Review and confirm pending payments'
            })
        
        # Check for large cash payments that need verification
        large_cash_payments = FeePayment.objects.filter(
            payment_date__date=date,
            payment_mode='cash',
            amount__gte=Decimal('1000.00')
        ).count()
        
        if large_cash_payments > 0:
            discrepancies.append({
                'type': 'large_cash_payments',
                'count': large_cash_payments,
                'severity': 'low',
                'action': 'Verify large cash payments with receipts'
            })
        
        # Check for duplicate payments
        duplicate_check = self._check_for_duplicate_payments(date)
        if duplicate_check['found']:
            discrepancies.append({
                'type': 'possible_duplicates',
                'details': duplicate_check['details'],
                'severity': 'high',
                'action': 'Investigate possible duplicate payments'
            })
        
        return discrepancies
    
    def _check_for_duplicate_payments(self, date):
        """Check for possible duplicate payments"""
        # Get all payments for the day
        payments = list(FeePayment.objects.filter(
            payment_date__date=date,
            is_confirmed=True
        ).values('fee_id', 'amount', 'payment_mode', 'id'))
        
        # Group by fee and amount
        fee_amount_groups = defaultdict(list)
        for payment in payments:
            key = f"{payment['fee_id']}_{payment['amount']}"
            fee_amount_groups[key].append(payment)
        
        duplicates = []
        for key, payment_list in fee_amount_groups.items():
            if len(payment_list) > 1:
                duplicates.append({
                    'fee_id': payment_list[0]['fee_id'],
                    'amount': payment_list[0]['amount'],
                    'payments': payment_list,
                    'count': len(payment_list)
                })
        
        return {
            'found': len(duplicates) > 0,
            'details': duplicates
        }
    
    def _get_payment_method_breakdown(self, date):
        """Get payment method breakdown for the day"""
        fee_methods = FeePayment.objects.filter(
            payment_date__date=date,
            is_confirmed=True
        ).values('payment_mode').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        bill_methods = BillPayment.objects.filter(
            payment_date=date
        ).values('payment_mode').annotate(
            total=Sum('amount'),
            count=Count('id')
        )
        
        # Combine results
        all_methods = defaultdict(lambda: {'total': Decimal('0.00'), 'count': 0})
        
        for method in fee_methods:
            all_methods[method['payment_mode']]['total'] += method['total'] or Decimal('0.00')
            all_methods[method['payment_mode']]['count'] += method['count'] or 0
        
        for method in bill_methods:
            all_methods[method['payment_mode']]['total'] += method['total'] or Decimal('0.00')
            all_methods[method['payment_mode']]['count'] += method['count'] or 0
        
        # Convert to list
        breakdown = []
        for method, data in all_methods.items():
            breakdown.append({
                'method': method,
                'display_name': self._get_payment_method_display(method),
                'total': data['total'],
                'count': data['count'],
                'percentage': (data['total'] / sum(item['total'] for item in all_methods.values()) * 100) 
                              if sum(item['total'] for item in all_methods.values()) > 0 else 0
            })
        
        # Sort by total descending
        breakdown.sort(key=lambda x: x['total'], reverse=True)
        
        return breakdown
    
    def _get_payment_method_display(self, method):
        """Get display name for payment method"""
        display_names = {
            'cash': 'Cash',
            'mobile_money': 'Mobile Money',
            'bank_transfer': 'Bank Transfer',
            'check': 'Cheque',
            'online': 'Online Payment',
            'other': 'Other'
        }
        return display_names.get(method, method.title())
    
    def _send_reconciliation_alert(self, date, discrepancies):
        """Send alert for reconciliation discrepancies"""
        # Get admin emails from settings
        admin_emails = getattr(settings, 'ADMIN_EMAILS', [])
        
        if not admin_emails:
            return
        
        # Prepare alert message
        subject = f"Reconciliation Alert - {date.strftime('%d/%m/%Y')}"
        
        message_lines = [
            f"Daily reconciliation for {date.strftime('%d/%m/%Y')} found discrepancies:",
            ""
        ]
        
        for disc in discrepancies:
            message_lines.append(f"• {disc['type'].replace('_', ' ').title()}: {disc.get('count', 'N/A')}")
            message_lines.append(f"  Severity: {disc['severity']}")
            message_lines.append(f"  Action: {disc['action']}")
            message_lines.append("")
        
        message = "\n".join(message_lines)
        
        try:
            from django.core.mail import send_mail
            send_mail(
                subject=subject,
                message=message,
                from_email=getattr(settings, 'DEFAULT_FROM_EMAIL'),
                recipient_list=admin_emails,
                fail_silently=True
            )
        except Exception as e:
            logger.error(f"Error sending reconciliation alert: {str(e)}")