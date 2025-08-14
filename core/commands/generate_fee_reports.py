# management/commands/generate_fee_reports.py
from django.core.management.base import BaseCommand
from django.template.loader import render_to_string
from django.core.mail import EmailMessage
from finance.models import Fee
from datetime import date, timedelta

class Command(BaseCommand):
    help = 'Generates and sends fee status reports'
    
    def handle(self, *args, **options):
        # Daily report for overdue fees
        overdue_fees = Fee.objects.filter(
            payment_status='OVERDUE',
            due_date__lte=date.today()
        )
        
        # Weekly report for all statuses
        if date.today().weekday() == 0:  # Monday
            self.generate_weekly_report()
            
        # Monthly summary
        if date.today().day == 1:  # First day of month
            self.generate_monthly_report()
    
    def generate_weekly_report(self):
        start_date = date.today() - timedelta(days=7)
        end_date = date.today()
        
        fees = Fee.objects.filter(
            date_recorded__range=(start_date, end_date)
        ).select_related('student', 'category')
        
        context = {
            'start_date': start_date,
            'end_date': end_date,
            'fees': fees,
            'summary': self.get_summary(fees)
        }
        
        html_content = render_to_string('finance/email/weekly_report.html', context)
        
        msg = EmailMessage(
            f"Weekly Fee Report - {date.today()}",
            html_content,
            'finance@school.edu',
            ['bursar@school.edu', 'principal@school.edu']
        )
        msg.content_subtype = "html"
        msg.send()
    
    def generate_monthly_report(self):
        pass  # Similar to weekly but for entire month
    
    def get_summary(self, fees):
        return {
            'total_payable': fees.aggregate(Sum('amount_payable'))['amount_payable__sum'] or 0,
            'total_paid': fees.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0,
            'counts': {
                'paid': fees.filter(payment_status='PAID').count(),
                'partial': fees.filter(payment_status='PARTIAL').count(),
                'unpaid': fees.filter(payment_status='UNPAID').count(),
                'overdue': fees.filter(payment_status='OVERDUE').count(),
            }
        }