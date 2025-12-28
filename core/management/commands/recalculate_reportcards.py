from django.core.management.base import BaseCommand
from core.models import ReportCard
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Recalculate all report card statistics'

    def handle(self, *args, **kwargs):
        report_cards = ReportCard.objects.all()
        count = report_cards.count()
        
        self.stdout.write(f"Recalculating {count} report cards...")
        
        for i, report_card in enumerate(report_cards, 1):
            try:
                report_card.calculate_grades()
                report_card.save()
                if i % 50 == 0:
                    self.stdout.write(f"Processed {i}/{count} report cards...")
            except Exception as e:
                self.stderr.write(f"Error processing report card {report_card.id}: {e}")
        
        self.stdout.write(self.style.SUCCESS(f"Successfully recalculated {count} report cards"))