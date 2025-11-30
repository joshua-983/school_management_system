# core/permissions.py
from django.contrib.auth.decorators import user_passes_test

def is_admin(user):
    """Check if user is an admin/superuser"""
    return user.is_authenticated and (user.is_superuser or user.is_staff)

def is_teacher(user):
    """Check if user is a teacher"""
    return user.is_authenticated and hasattr(user, 'teacher') and user.teacher is not None

def is_student(user):
    """Check if user is a student"""
    return user.is_authenticated and hasattr(user, 'student') and user.student is not None

def is_parent(user):
    """Check if user is a parent"""
    return user.is_authenticated and hasattr(user, 'parentguardian') and user.parentguardian is not None

# Decorators for view protection
def admin_required(view_func=None, login_url=None):
    """
    Decorator for views that checks if the user is an admin,
    redirecting to the login page if necessary.
    """
    actual_decorator = user_passes_test(
        lambda u: is_admin(u),
        login_url=login_url,
    )
    if view_func:
        return actual_decorator(view_func)
    return actual_decorator

def teacher_required(view_func=None, login_url=None):
    """
    Decorator for views that checks if the user is a teacher,
    redirecting to the login page if necessary.
    """
    actual_decorator = user_passes_test(
        lambda u: is_teacher(u),
        login_url=login_url,
    )
    if view_func:
        return actual_decorator(view_func)
    return actual_decorator

def student_required(view_func=None, login_url=None):
    """
    Decorator for views that checks if the user is a student,
    redirecting to the login page if necessary.
    """
    actual_decorator = user_passes_test(
        lambda u: is_student(u),
        login_url=login_url,
    )
    if view_func:
        return actual_decorator(view_func)
    return actual_decorator

def parent_required(view_func=None, login_url=None):
    """
    Decorator for views that checks if the user is a parent,
    redirecting to the login page if necessary.
    """
    actual_decorator = user_passes_test(
        lambda u: is_parent(u),
        login_url=login_url,
    )
    if view_func:
        return actual_decorator(view_func)
    return actual_decorator

def staff_required(view_func=None, login_url=None):
    """
    Decorator for views that checks if the user is staff (admin or teacher),
    redirecting to the login page if necessary.
    """
    actual_decorator = user_passes_test(
        lambda u: is_admin(u) or is_teacher(u),
        login_url=login_url,
    )
    if view_func:
        return actual_decorator(view_func)
    return actual_decorator

# Mixin classes for class-based views
class AdminRequiredMixin:
    """Mixin to ensure user is an admin"""
    def dispatch(self, request, *args, **kwargs):
        if not is_admin(request.user):
            from django.contrib.auth.views import redirect_to_login
            from django.urls import reverse
            return redirect_to_login(request.get_full_path(), reverse('login'))
        return super().dispatch(request, *args, **kwargs)

class TeacherRequiredMixin:
    """Mixin to ensure user is a teacher"""
    def dispatch(self, request, *args, **kwargs):
        if not is_teacher(request.user):
            from django.contrib.auth.views import redirect_to_login
            from django.urls import reverse
            return redirect_to_login(request.get_full_path(), reverse('login'))
        return super().dispatch(request, *args, **kwargs)

class StudentRequiredMixin:
    """Mixin to ensure user is a student"""
    def dispatch(self, request, *args, **kwargs):
        if not is_student(request.user):
            from django.contrib.auth.views import redirect_to_login
            from django.urls import reverse
            return redirect_to_login(request.get_full_path(), reverse('login'))
        return super().dispatch(request, *args, **kwargs)

class ParentRequiredMixin:
    """Mixin to ensure user is a parent"""
    def dispatch(self, request, *args, **kwargs):
        if not is_parent(request.user):
            from django.contrib.auth.views import redirect_to_login
            from django.urls import reverse
            return redirect_to_login(request.get_full_path(), reverse('parent_login'))
        return super().dispatch(request, *args, **kwargs)

class StaffRequiredMixin:
    """Mixin to ensure user is staff (admin or teacher)"""
    def dispatch(self, request, *args, **kwargs):
        if not (is_admin(request.user) or is_teacher(request.user)):
            from django.contrib.auth.views import redirect_to_login
            from django.urls import reverse
            return redirect_to_login(request.get_full_path(), reverse('login'))
        return super().dispatch(request, *args, **kwargs)