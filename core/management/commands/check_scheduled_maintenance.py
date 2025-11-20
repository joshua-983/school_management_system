from django.core.management.base import BaseCommand
from django.utils import timezone
from django.conf import settings
from core.models import ScheduledMaintenance, AuditLog
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Check and execute scheduled maintenance windows'
    
    def handle(self, *args, **options):
        now = timezone.now()
        
        # Check for maintenance that should start
        starting_maintenance = ScheduledMaintenance.objects.filter(
            is_active=True,
            was_executed=False,
            start_time__lte=now,
            end_time__gte=now
        )
        
        for maintenance in starting_maintenance:
            # Enable maintenance mode
            settings.MAINTENANCE_MODE = True
            settings.MAINTENANCE_MESSAGE = maintenance.message
            maintenance.was_executed = True
            maintenance.save()
            
            logger.info(f"Started scheduled maintenance: {maintenance.title}")
            self.stdout.write(
                self.style.SUCCESS(f'Started maintenance: {maintenance.title}')
            )
            
            # Log the action
            AuditLog.log_action(
                user=maintenance.created_by,
                action='MAINTENANCE_START',
                model_name='ScheduledMaintenance',
                object_id=maintenance.id,
                details={
                    'title': maintenance.title,
                    'type': maintenance.maintenance_type,
                    'started_at': now.isoformat()
                }
            )
        
        # Check for maintenance that should end
        active_maintenance = getattr(settings, 'MAINTENANCE_MODE', False)
        if active_maintenance:
            # Check if any maintenance window has ended
            ended_maintenance = ScheduledMaintenance.objects.filter(
                is_active=True,
                was_executed=True,
                end_time__lt=now
            )
            
            if ended_maintenance.exists():
                # Disable maintenance mode
                settings.MAINTENANCE_MODE = False
                
                for maintenance in ended_maintenance:
                    maintenance.is_active = False
                    maintenance.save()
                    
                    logger.info(f"Ended scheduled maintenance: {maintenance.title}")
                    self.stdout.write(
                        self.style.SUCCESS(f'Ended maintenance: {maintenance.title}')
                    )
                    
                    # Log the action
                    AuditLog.log_action(
                        user=maintenance.created_by,
                        action='MAINTENANCE_END',
                        model_name='ScheduledMaintenance',
                        object_id=maintenance.id,
                        details={
                            'title': maintenance.title,
                            'ended_at': now.isoformat()
                        }
                    )