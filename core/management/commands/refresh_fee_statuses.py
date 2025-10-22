from django.core.management.base import BaseCommand
from django.utils import timezone
from django.db.models import Sum
from core.models import Student, Fee

class Command(BaseCommand):
    help = 'Refresh all fee payment statuses based on actual payments'

    def handle(self, *args, **options):
        self.stdout.write('Starting fee status refresh...')
        
        for student in Student.objects.all():
            fees = Fee.objects.filter(student=student)
            for fee in fees:
                total_paid = fee.payments.aggregate(Sum('amount'))['amount__sum'] or 0
                fee.amount_paid = total_paid
                fee.balance = fee.amount_payable - fee.amount_paid
                
                if fee.balance <= 0:
                    fee.payment_status = 'paid'
                elif fee.amount_paid > 0:
                    fee.payment_status = 'partial'
                else:
                    fee.payment_status = 'unpaid'
                    
                if fee.due_date and fee.due_date < timezone.now().date() and fee.payment_status != 'paid':
                    fee.payment_status = 'overdue'
                    
                fee.save()
            
            if fees.count() > 0:
                self.stdout.write(
                    self.style.SUCCESS(f'Updated {fees.count()} fees for {student.get_full_name()}')
                )
        
        self.stdout.write(
            self.style.SUCCESS('Successfully refreshed all fee statuses!')
        )