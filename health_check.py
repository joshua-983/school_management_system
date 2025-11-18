# health_check.py
import os
import sys
import django
import time
from pathlib import Path

# Setup Django
sys.path.append(str(Path(__file__).parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgt_system.settings')
django.setup()

def system_health_check():
    print("🔍 SCHOOL MANAGEMENT SYSTEM HEALTH CHECK")
    print("=" * 50)
    
    # Database Health
    print("\n📊 DATABASE HEALTH")
    try:
        from django.db import connection
        from django.db.utils import OperationalError
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            db_result = cursor.fetchone()
        
        print("✅ Database: Connected and responsive")
        
        # Check if we can query models
        from django.contrib.auth import get_user_model
        User = get_user_model()
        user_count = User.objects.count()
        print(f"✅ User models: {user_count} users in database")
        
    except OperationalError as e:
        print(f"❌ Database: Connection failed - {e}")
    except Exception as e:
        print(f"❌ Database: Error - {e}")

    # Cache Health
    print("\n💾 CACHE HEALTH")
    try:
        from django.core.cache import cache
        test_key = "health_check_" + str(time.time())
        cache.set(test_key, "test_value", 10)
        cached_value = cache.get(test_key)
        
        if cached_value == "test_value":
            print("✅ Cache: Working correctly")
        else:
            print("⚠️  Cache: May not be working correctly")
            
    except Exception as e:
        print(f"❌ Cache: Error - {e}")

    # Application Health
    print("\n🚀 APPLICATION HEALTH")
    try:
        from django.apps import apps
        app_configs = apps.get_app_configs()
        
        print("✅ Core applications loaded:")
        for app in app_configs:
            if app.name in ['core', 'accounts', 'admin', 'auth']:
                models = list(app.get_models())  # Convert to list to get count
                print(f"   - {app.name}: {len(models)} models")
            
    except Exception as e:
        print(f"❌ Applications: Error - {e}")

    # Security Health
    print("\n🛡️  SECURITY HEALTH")
    try:
        from django.conf import settings
        
        security_checks = [
            ("DEBUG mode", not settings.DEBUG, "Production should have DEBUG=False"),
            ("Secret key", settings.SECRET_KEY != "dummy-key", "Secret key should be set"),
            ("Allowed hosts", len(settings.ALLOWED_HOSTS) > 0, "ALLOWED_HOSTS should be configured"),
            ("CSRF protection", settings.CSRF_COOKIE_HTTPONLY, "CSRF cookies should be HTTPOnly"),
            ("Session security", settings.SESSION_COOKIE_HTTPONLY, "Session cookies should be HTTPOnly"),
        ]
        
        for check_name, condition, recommendation in security_checks:
            if condition:
                print(f"✅ {check_name}: OK")
            else:
                print(f"⚠️  {check_name}: {recommendation}")
                
    except Exception as e:
        print(f"❌ Security: Error - {e}")

    print("\n" + "=" * 50)
    print("🎉 HEALTH CHECK COMPLETE")

if __name__ == "__main__":
    system_health_check()
