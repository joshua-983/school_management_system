from django.apps import AppConfig
import logging

logger = logging.getLogger(__name__)

class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'
    
    def ready(self):
        try:
            import core.signals
            logger.info("✅ Core signals imported successfully")
        except Exception as e:
            logger.error(f"❌ Error importing signals: {str(e)}")