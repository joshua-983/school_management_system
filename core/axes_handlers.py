# core/axes_handlers.py
from axes.handlers.database import AxesDatabaseHandler
from axes.models import AccessAttempt
from django.utils import timezone
from django.db.models import Q

class CustomAxesHandler(AxesDatabaseHandler):
    """Custom Axes handler with enhanced functionality"""
    
    def get_locked_users(self):
        """Get currently locked users"""
        now = timezone.now()
        locked_users = []
        
        # Get access attempts with failures
        attempts = AccessAttempt.objects.filter(
            failures_since_start__gte=5
        ).select_related('user')
        
        for attempt in attempts:
            # Check if user is still locked based on cooloff time
            if attempt.attempt_time:
                lockout_duration = timezone.now() - attempt.attempt_time
                if lockout_duration.total_seconds() < 15 * 60:  # 15 minutes
                    locked_users.append({
                        'username': attempt.username,
                        'ip_address': attempt.ip_address,
                        'user_agent': attempt.user_agent,
                        'failures': attempt.failures_since_start,
                        'locked_at': attempt.attempt_time,
                        'user': attempt.user
                    })
        
        return locked_users
    
    def unlock_user(self, username):
        """Unlock a specific user"""
        try:
            deleted_count, _ = AccessAttempt.objects.filter(
                username=username
            ).delete()
            return deleted_count
        except Exception as e:
            print(f"Error unlocking user {username}: {e}")
            return 0
    
    def unlock_all_users(self):
        """Unlock all users"""
        try:
            locked_count = AccessAttempt.objects.filter(
                failures_since_start__gte=5
            ).count()
            deleted_count, _ = AccessAttempt.objects.all().delete()
            return deleted_count, locked_count
        except Exception as e:
            print(f"Error unlocking all users: {e}")
            return 0, 0