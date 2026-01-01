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
            
            # Apply async middleware patches
            self._apply_async_patches()
            
            logger.info("✅ Core application initialized successfully")
            logger.info("✅ All signals registered and timetable groups verified")
            
        except ImportError as e:
            logger.error(f"❌ Error importing signals module: {str(e)}")
        except Exception as e:
            logger.error(f"❌ Error initializing core application: {str(e)}", exc_info=True)
    
    def _apply_async_patches(self):
        """Apply all async compatibility patches."""
        try:
            # Patch Axes middleware check
            from core.middleware.axes_async_patch import patch_axes_middleware_check
            if patch_axes_middleware_check():
                logger.info("✅ Axes async middleware patch applied")
            else:
                logger.warning("⚠️ Could not apply Axes async middleware patch")
                
        except ImportError as e:
            logger.warning(f"⚠️ Could not import async patches: {e}")
        except Exception as e:
            logger.warning(f"⚠️ Error applying async patches: {e}")