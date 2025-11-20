from django.core.management.base import BaseCommand
from django.utils import timezone
from core.models import UserProfile
import logging

logger = logging.getLogger(__name__)

class Command(BaseCommand):
    help = 'Automatically unblock users whose temporary block has expired'
    
    def handle(self, *args, **options):
        now = timezone.now()
        expired_blocks = UserProfile.objects.filter(
            is_blocked=True,
            auto_unblock_at__isnull=False,
            auto_unblock_at__lte=now
        )
        
        count = expired_blocks.count()
        
        for profile in expired_blocks:
            profile.unblock_user(None, "Automatic unblock after temporary block period")
            self.stdout.write(
                self.style.SUCCESS(f'Automatically unblocked user: {profile.user.username}')
            )
        
        if count > 0:
            logger.info(f"Auto-unblocked {count} users")
            self.stdout.write(
                self.style.SUCCESS(f'Successfully unblocked {count} users')
            )
        else:
            self.stdout.write('No users to unblock')