# school_mgt_system/__init__.py - FIXED VERSION
from __future__ import absolute_import, unicode_literals

# Initialize celery_app to None by default
celery_app = None
__all__ = ('celery_app',)

# Try to import Celery app, but don't fail if it doesn't work
try:
    # Import at the end to avoid circular imports
    from .celery import app as celery_app
    print("✅ Celery app imported successfully")
except ImportError as e:
    print(f"⚠️  Celery import error: {e}")
    print("⚠️  Running without Celery (tasks will be synchronous)")
except Exception as e:
    print(f"⚠️  Unexpected error importing Celery: {e}")
    print("⚠️  Running without Celery")