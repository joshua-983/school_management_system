# core/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    
    def ready(self):
        """
        Import and register signals when the app is ready.
        This method is called when Django starts.
        """
        try:
            # Import signals module
            import core.signals
            logger.info("✅ Successfully imported core signals")
            
        except ImportError as e:
            logger.error(f"❌ Failed to import signals module: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error in app ready method: {str(e)}")
            # Don't raise the exception to prevent app startup failure