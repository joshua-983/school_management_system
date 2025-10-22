# core/management/commands/apply_data_retention.py
from django.core.management.base import BaseCommand
from core.utils.audit_enhancements import DataRetentionManager

class Command(BaseCommand):
    help = 'Apply data retention policies'
    
    def handle(self, *args, **options):
        manager = DataRetentionManager()
        manager.apply_retention_policies()
        
        self.stdout.write(
            self.style.SUCCESS('Successfully applied data retention policies')
        )