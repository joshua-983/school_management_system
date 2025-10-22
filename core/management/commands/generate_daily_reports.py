# core/management/commands/generate_daily_reports.py
from django.core.management.base import BaseCommand
from core.utils.audit_enhancements import AuditReportGenerator

class Command(BaseCommand):
    help = 'Generate daily security reports'
    
    def handle(self, *args, **options):
        generator = AuditReportGenerator()
        report = generator.generate_daily_report()
        
        self.stdout.write(
            self.style.SUCCESS(f'Successfully generated daily report: {report.name}')
        )