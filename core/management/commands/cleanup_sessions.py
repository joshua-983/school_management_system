from django.core.management.base import BaseCommand
from django.contrib.sessions.models import Session
from django.utils import timezone
from django.db import transaction
import datetime
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Clean up expired sessions and prevent session corruption'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=7,
            help='Delete sessions older than this many days (default: 7)',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Show what would be deleted without actually deleting',
        )

    def handle(self, *args, **options):
        days = options['days']
        dry_run = options['dry_run']
        
        cutoff_date = timezone.now() - datetime.timedelta(days=days)
        
        self.stdout.write(f"🔍 Looking for sessions older than {days} days (before {cutoff_date})")
        
        try:
            # Find expired sessions and potential corrupted sessions
            expired_sessions = Session.objects.filter(expire_date__lt=cutoff_date)
            
            # Also look for sessions with malformed data
            corrupted_sessions = Session.objects.filter(
                expire_date__isnull=True
            ) | Session.objects.filter(
                session_data__isnull=True
            ) | Session.objects.filter(
                session_data=''
            )
            
            all_sessions_to_delete = expired_sessions | corrupted_sessions
            count = all_sessions_to_delete.count()
            
            if dry_run:
                self.stdout.write(
                    self.style.WARNING(f"🧹 DRY RUN: Would delete {count} sessions")
                )
                if count > 0:
                    self.stdout.write("Sessions that would be deleted:")
                    for session in all_sessions_to_delete[:10]:  # Show first 10
                        self.stdout.write(f"  - {session.session_key} (expires: {session.expire_date})")
                    if count > 10:
                        self.stdout.write(f"  ... and {count - 10} more")
                return
            
            if count == 0:
                self.stdout.write(self.style.SUCCESS("✅ No sessions to clean up"))
                return
            
            with transaction.atomic():
                deleted_count, _ = all_sessions_to_delete.delete()
            
            # Log the cleanup
            logger.info(f"Session cleanup: deleted {deleted_count} sessions older than {days} days")
            
            self.stdout.write(
                self.style.SUCCESS(f"✅ Successfully deleted {deleted_count} expired/corrupted sessions")
            )
            
            # Additional stats
            total_sessions = Session.objects.count()
            self.stdout.write(f"📊 Total sessions remaining: {total_sessions}")
            
        except Exception as e:
            logger.error(f"Session cleanup failed: {str(e)}")
            self.stdout.write(
                self.style.ERROR(f"❌ Error during session cleanup: {str(e)}")
            )