import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgt_system.settings')
os.environ['AXES_ENABLED'] = 'False'

django.setup()

from django.test import RequestFactory
from django.contrib.auth import get_user_model
from core.views.base_views import admin_dashboard

User = get_user_model()

print("=== SIMPLE DIRECT TEST ===")

# Get admin user
admin = User.objects.get(username='Administrator')
print(f"Using admin: {admin.username}")

# Create simple request
factory = RequestFactory()
request = factory.get('/admin-dashboard/')
request.user = admin

# Call view directly
try:
    response = admin_dashboard(request)
    print(f"✅ View executed: Status {response.status_code}")
    
    # Check content
    content = response.content.decode('utf-8', errors='ignore')
    
    if 'VariableDoesNotExist' in content:
        print("❌ VariableDoesNotExist error still present!")
        import re
        error = re.search(r'VariableDoesNotExist[^<]*', content)
        if error:
            print(f"   Error: {error.group()[:80]}")
    else:
        print("✅ No VariableDoesNotExist error")
        
    if 'Failed lookup' in content:
        print("❌ Failed lookup error still present!")
        error = re.search(r'Failed lookup[^<]*', content)
        if error:
            print(f"   Error: {error.group()[:80]}")
    else:
        print("✅ No Failed lookup error")
        
    # Check for content
    if 'Welcome' in content or 'Dashboard' in content:
        print("✅ Page content found")
    else:
        print("⚠️  No welcome/dashboard text (might be redirecting)")
        
    # Check context
    if hasattr(response, 'context_data'):
        print(f"✅ Context data available with {len(response.context_data)} keys")
        if 'user' in response.context_data:
            print(f"   - User in context: {response.context_data['user']}")
        if 'recent_logs' in response.context_data:
            logs = response.context_data['recent_logs']
            print(f"   - Recent logs: {len(logs) if logs else 0} items")
            # Check if any log has None user
            if logs:
                for i, log in enumerate(logs[:3]):
                    print(f"     Log {i}: user={'Present' if log.user else 'None'}")
                    
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()

print("\n=== TEST COMPLETE ===")
