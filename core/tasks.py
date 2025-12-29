# Add these imports at the top if not already present
import os
from celery import shared_task
from django.core.management import call_command
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


@shared_task
def backup_database():
    """Celery task to backup database daily"""
    try:
        logger.info("Starting automated database backup")
        
        # Create backup directory if it doesn't exist
        backup_dir = settings.BASE_DIR / 'backups'
        backup_dir.mkdir(exist_ok=True)
        
        # Run backup command
        call_command('backup_system', '--type', 'database', '--compress', '--retention-days', '30')
        
        logger.info("Database backup completed successfully")
        return "Backup completed"
        
    except Exception as e:
        logger.error(f"Database backup failed: {str(e)}")
        return f"Backup failed: {str(e)}"


@shared_task
def backup_full_system():
    """Celery task to backup entire system weekly"""
    try:
        logger.info("Starting full system backup")
        
        call_command('backup_system', '--type', 'full', '--compress', '--retention-days', '90')
        
        logger.info("Full system backup completed")
        return "Full backup completed"
        
    except Exception as e:
        logger.error(f"Full system backup failed: {str(e)}")
        return f"Full backup failed: {str(e)}"


@shared_task
def cleanup_old_backups():
    """Clean up old backup files"""
    try:
        backup_dir = settings.BASE_DIR / 'backups'
        if not backup_dir.exists():
            return "No backup directory found"
        
        # Delete backups older than 90 days
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=90)
        
        deleted_count = 0
        for item in backup_dir.iterdir():
            try:
                # Parse date from filename
                if item.name.startswith('backup_') and item.suffix == '.zip':
                    date_str = item.name[7:22]  # backup_YYYYMMDD_HHMMSS.zip
                    item_date = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
                    
                    if item_date < cutoff_date:
                        item.unlink()
                        deleted_count += 1
            except (ValueError, IndexError):
                continue
        
        logger.info(f"Cleaned up {deleted_count} old backups")
        return f"Cleaned {deleted_count} old backups"
        
    except Exception as e:
        logger.error(f"Backup cleanup failed: {str(e)}")
        return f"Cleanup failed: {str(e)}"