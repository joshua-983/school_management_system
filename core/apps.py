# core/apps.py
from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    
    def ready(self):
        """
        Initialize the core application and register all signals.
        This method is called when Django starts.
        """
        try:
            # Import signals module
            import core.signals
            
            # Initialize signals (this will create timetable groups if needed)
            core.signals.initialize_signals()
            
            logger.info("✅ Core application initialized successfully")
            logger.info("✅ All signals registered and timetable groups verified")
            
        except ImportError as e:
            logger.error(f"❌ Error importing signals module: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error initializing core application: {str(e)}", exc_info=True)
            
        # Optional: You can also import other initialization functions here
        # import core.initialization
        # core.initialization.setup_default_settings()