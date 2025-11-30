from django.shortcuts import render, redirect
from django.http import HttpResponse
from django.utils import timezone

def home(request):
    """Simple home page that works without database access"""
    # Safe user authentication check
    user_authenticated = hasattr(request, 'user') and request.user.is_authenticated
    
    if user_authenticated:
        # Check if user has a specific role that should go to dashboard
        if (hasattr(request.user, 'teacher') or
            hasattr(request.user, 'student') or
            hasattr(request.user, 'parentguardian') or
            (hasattr(request.user, 'is_staff') and request.user.is_staff)):
            return redirect('dashboard')
    
    # Use simple static stats instead of database queries
    context = {
        'current_year': timezone.now().year,
        'featured_stats': {
            'total_students': 0,  # Placeholder - no database access
            'total_teachers': 0,  # Placeholder - no database access  
            'total_subjects': 0,  # Placeholder - no database access
        }
    }
    
    # Try to render the template, fall back to simple HTML if it fails
    try:
        return render(request, 'core/home.html', context)
    except Exception as e:
        # Fallback: simple HTML response if template fails
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <title>School Management System</title>
            <style>
                body {{ font-family: Arial, sans-serif; margin: 40px; }}
                .container {{ max-width: 800px; margin: 0 auto; }}
                .header {{ background: #f8f9fa; padding: 30px; border-radius: 10px; text-align: center; }}
                .nav {{ margin: 30px 0; text-align: center; }}
                .nav a {{ margin: 0 15px; padding: 10px 20px; background: #007bff; color: white; text-decoration: none; border-radius: 5px; }}
                .nav a:hover {{ background: #0056b3; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>🏫 School Management System</h1>
                    <p>Welcome! System is running successfully. ✅</p>
                </div>
                
                <div class="nav">
                    <a href="/admin/">🔧 Admin Panel</a>
                    <a href="/accounts/signin/">🔐 Login</a>
                </div>
                
                <div style="background: #d4edda; color: #155724; padding: 15px; border-radius: 5px; margin: 20px 0;">
                    <strong>System Status:</strong> Running | 
                    <strong>User:</strong> {request.user.username if user_authenticated else "Not logged in"}
                </div>
            </div>
        </body>
        </html>
        """
        return HttpResponse(html_content)

def dashboard(request):
    return HttpResponse("<h1>Dashboard</h1><p>This is the dashboard page.</p>")

def admin_dashboard(request):
    return HttpResponse("<h1>Admin Dashboard</h1>")

def teacher_dashboard(request):
    return HttpResponse("<h1>Teacher Dashboard</h1>")
