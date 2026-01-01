import os
import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgt_system.settings')
os.environ['AXES_ENABLED'] = 'False'

# Enable template debugging
os.environ['TEMPLATE_DEBUG'] = 'True'

django.setup()

from django.template import TemplateSyntaxError
from django.test import RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.sessions.middleware import SessionMiddleware
from django.contrib.auth.middleware import AuthenticationMiddleware
import traceback

User = get_user_model()

print("=== TRACING TEMPLATE ERROR ===")

# Get admin
admin = User.objects.get(username='Administrator')

# Create request
factory = RequestFactory()
request = factory.get('/admin-dashboard/')
request.user = admin

session_middleware = SessionMiddleware(lambda req: None)
session_middleware.process_request(request)
request.session.save()

auth_middleware = AuthenticationMiddleware(lambda req: None)
auth_middleware.process_request(request)

# Try to import and trace the view
import sys
import io

# Capture stdout to analyze
old_stdout = sys.stdout
sys.stdout = io.StringIO()

try:
    from core.views.base_views import admin_dashboard
    response = admin_dashboard(request)
except Exception as e:
    # Get the captured output
    output = sys.stdout.getvalue()
    sys.stdout = old_stdout
    
    print(f"Error: {e}")
    
    # Print the traceback
    exc_type, exc_value, exc_traceback = sys.exc_info()
    
    # Look for template-related frames
    tb_lines = traceback.format_exception(exc_type, exc_value, exc_traceback)
    for i, line in enumerate(tb_lines):
        if 'template' in line.lower():
            print(f"\nTemplate-related traceback frame {i}:")
            print(line)
            # Show a few lines before and after
            for j in range(max(0, i-2), min(len(tb_lines), i+3)):
                if j != i:
                    print(f"{j}: {tb_lines[j][:100]}...")
else:
    sys.stdout = old_stdout
    print("No error occurred!")

# Also, let's manually check the context
print("\n=== MANUAL CONTEXT CHECK ===")
from core.views.base_views import admin_dashboard

# Monkey-patch to intercept context
original_render = None
import django.shortcuts

def debug_render(request, template_name, context=None, content_type=None, status=None, using=None):
    print(f"\nDEBUG RENDER CALLED:")
    print(f"  Template: {template_name}")
    print(f"  Context keys: {list(context.keys()) if context else 'None'}")
    
    # Check for None values
    if context:
        for key, value in context.items():
            if value is None:
                print(f"  WARNING: context['{key}'] = None")
            elif hasattr(value, 'username'):
                print(f"  context['{key}'].username = {value.username}")
    
    # Call original
    return original_render(request, template_name, context, content_type, status, using)

# Patch it
original_render = django.shortcuts.render
django.shortcuts.render = debug_render

# Now call the view
try:
    response = admin_dashboard(request)
except Exception as e:
    print(f"Error during debug: {e}")
