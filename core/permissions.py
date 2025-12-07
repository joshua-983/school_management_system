# core/permissions.py
from django.contrib.auth.decorators import user_passes_test
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.shortcuts import redirect
from django.urls import reverse

# ===== ROLE CHECK FUNCTIONS =====

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

# ===== PERMISSION CHECK FUNCTIONS =====

def has_timetable_view_permission(user):
    """Check if user can view timetables"""
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    if is_teacher(user):
        return True
    if is_student(user):
        return True
    if is_parent(user):
        return True
    return False

def has_timetable_manage_permission(user):
    """Check if user can manage timetables (create/edit/delete)"""
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    return False

def has_timeslot_manage_permission(user):
    """Check if user can manage time slots"""
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    return False

def has_timetable_entry_manage_permission(user, timetable=None):
    """
    Check if user can manage timetable entries
    For teachers, only allow if they teach the class
    """
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    if is_teacher(user):
        if timetable:
            # Check if teacher teaches this class
            from core.models import ClassAssignment
            return ClassAssignment.objects.filter(
                class_level=timetable.class_level,
                teacher=user.teacher
            ).exists()
        return True  # Teachers can manage entries for their classes
    return False

def can_view_timetable(user, timetable):
    """Check if user can view a specific timetable"""
    if not user.is_authenticated:
        return False
    if is_admin(user):
        return True
    if is_teacher(user):
        # Teachers can view timetables for classes they teach
        from core.models import ClassAssignment
        return ClassAssignment.objects.filter(
            class_level=timetable.class_level,
            teacher=user.teacher
        ).exists()
    if is_student(user):
        # Students can view their own class timetable
        return user.student.class_level == timetable.class_level
    if is_parent(user):
        # Parents can view timetables for their children's classes
        children_classes = user.parentguardian.students.values_list('class_level', flat=True)
        return timetable.class_level in children_classes
    return False

# ===== PERMISSION SETUP FOR DJANGO GROUPS =====

def setup_timetable_groups_and_permissions():
    """
    Create Django groups and assign permissions for timetable management
    This should be run once during setup
    """
    try:
        with transaction.atomic():
            # Import models here to avoid circular imports
            from core.models import TimeSlot, Timetable, TimetableEntry, Subject, Teacher
            
            # Get content types
            timeslot_ct = ContentType.objects.get_for_model(TimeSlot)
            timetable_ct = ContentType.objects.get_for_model(Timetable)
            timetable_entry_ct = ContentType.objects.get_for_model(TimetableEntry)
            subject_ct = ContentType.objects.get_for_model(Subject)
            teacher_ct = ContentType.objects.get_for_model(Teacher)
            
            # Create or get permissions
            permissions = {}
            
            # TimeSlot permissions
            permissions['view_timeslot'], _ = Permission.objects.get_or_create(
                codename='view_timeslot',
                content_type=timeslot_ct,
                defaults={'name': 'Can view time slot'}
            )
            
            # Timetable permissions
            permissions['view_timetable'], _ = Permission.objects.get_or_create(
                codename='view_timetable',
                content_type=timetable_ct,
                defaults={'name': 'Can view timetable'}
            )
            permissions['add_timetable'], _ = Permission.objects.get_or_create(
                codename='add_timetable',
                content_type=timetable_ct,
                defaults={'name': 'Can add timetable'}
            )
            permissions['change_timetable'], _ = Permission.objects.get_or_create(
                codename='change_timetable',
                content_type=timetable_ct,
                defaults={'name': 'Can change timetable'}
            )
            permissions['delete_timetable'], _ = Permission.objects.get_or_create(
                codename='delete_timetable',
                content_type=timetable_ct,
                defaults={'name': 'Can delete timetable'}
            )
            
            # TimetableEntry permissions
            permissions['view_timetable_entry'], _ = Permission.objects.get_or_create(
                codename='view_timetable_entry',
                content_type=timetable_entry_ct,
                defaults={'name': 'Can view timetable entry'}
            )
            permissions['add_timetable_entry'], _ = Permission.objects.get_or_create(
                codename='add_timetable_entry',
                content_type=timetable_entry_ct,
                defaults={'name': 'Can add timetable entry'}
            )
            permissions['change_timetable_entry'], _ = Permission.objects.get_or_create(
                codename='change_timetable_entry',
                content_type=timetable_entry_ct,
                defaults={'name': 'Can change timetable entry'}
            )
            permissions['delete_timetable_entry'], _ = Permission.objects.get_or_create(
                codename='delete_timetable_entry',
                content_type=timetable_entry_ct,
                defaults={'name': 'Can delete timetable entry'}
            )
            
            # Subject view permission
            permissions['view_subject'], _ = Permission.objects.get_or_create(
                codename='view_subject',
                content_type=subject_ct,
                defaults={'name': 'Can view subject'}
            )
            
            # Teacher view permission
            permissions['view_teacher'], _ = Permission.objects.get_or_create(
                codename='view_teacher',
                content_type=teacher_ct,
                defaults={'name': 'Can view teacher'}
            )
            
            # Create Groups (if they don't exist) and assign permissions
            
            # Teachers Group
            teachers_group, _ = Group.objects.get_or_create(name='Teachers')
            teachers_group.permissions.clear()
            teachers_group.permissions.add(
                permissions['view_timetable'],
                permissions['view_timetable_entry'],
                permissions['view_subject'],
                permissions['view_teacher'],
                permissions['view_timeslot'],
            )
            
            # Students Group
            students_group, _ = Group.objects.get_or_create(name='Students')
            students_group.permissions.clear()
            students_group.permissions.add(
                permissions['view_timetable'],
                permissions['view_subject'],
                permissions['view_teacher'],
            )
            
            # Parents Group
            parents_group, _ = Group.objects.get_or_create(name='Parents')
            parents_group.permissions.clear()
            parents_group.permissions.add(
                permissions['view_timetable'],
                permissions['view_subject'],
                permissions['view_teacher'],
            )
            
            print("Successfully setup timetable groups and permissions")
            return True
            
    except Exception as e:
        print(f"Error setting up timetable groups and permissions: {e}")
        return False

# ===== DECORATORS FOR VIEW PROTECTION =====

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

def timetable_view_required(view_func=None, login_url=None):
    """
    Decorator for views that checks if the user can view timetables
    """
    actual_decorator = user_passes_test(
        lambda u: has_timetable_view_permission(u),
        login_url=login_url,
    )
    if view_func:
        return actual_decorator(view_func)
    return actual_decorator

def timetable_manage_required(view_func=None, login_url=None):
    """
    Decorator for views that checks if the user can manage timetables
    """
    actual_decorator = user_passes_test(
        lambda u: has_timetable_manage_permission(u),
        login_url=login_url,
    )
    if view_func:
        return actual_decorator(view_func)
    return actual_decorator

# ===== MIXIN CLASSES FOR CLASS-BASED VIEWS =====

class AdminRequiredMixin:
    """Mixin to ensure user is an admin"""
    def dispatch(self, request, *args, **kwargs):
        if not is_admin(request.user):
            return redirect_to_login(request.get_full_path(), reverse('login'))
        return super().dispatch(request, *args, **kwargs)

class TeacherRequiredMixin:
    """Mixin to ensure user is a teacher"""
    def dispatch(self, request, *args, **kwargs):
        if not is_teacher(request.user):
            return redirect_to_login(request.get_full_path(), reverse('login'))
        return super().dispatch(request, *args, **kwargs)

class StudentRequiredMixin:
    """Mixin to ensure user is a student"""
    def dispatch(self, request, *args, **kwargs):
        if not is_student(request.user):
            return redirect_to_login(request.get_full_path(), reverse('login'))
        return super().dispatch(request, *args, **kwargs)

class ParentRequiredMixin:
    """Mixin to ensure user is a parent"""
    def dispatch(self, request, *args, **kwargs):
        if not is_parent(request.user):
            return redirect_to_login(request.get_full_path(), reverse('parent_login'))
        return super().dispatch(request, *args, **kwargs)

class StaffRequiredMixin:
    """Mixin to ensure user is staff (admin or teacher)"""
    def dispatch(self, request, *args, **kwargs):
        if not (is_admin(request.user) or is_teacher(request.user)):
            return redirect_to_login(request.get_full_path(), reverse('login'))
        return super().dispatch(request, *args, **kwargs)

class TimetableViewRequiredMixin:
    """Mixin to ensure user can view timetables"""
    def dispatch(self, request, *args, **kwargs):
        if not has_timetable_view_permission(request.user):
            return redirect_to_login(request.get_full_path(), reverse('login'))
        return super().dispatch(request, *args, **kwargs)

class TimetableManageRequiredMixin:
    """Mixin to ensure user can manage timetables"""
    def dispatch(self, request, *args, **kwargs):
        if not has_timetable_manage_permission(request.user):
            return redirect_to_login(request.get_full_path(), reverse('login'))
        return super().dispatch(request, *args, **kwargs)

# ===== UTILITY FUNCTIONS =====

def redirect_to_login(next_url, login_url):
    """Helper function to redirect to login page"""
    from django.contrib.auth.views import redirect_to_login as auth_redirect_to_login
    return auth_redirect_to_login(next_url, login_url)

def get_user_timetable_permissions(user):
    """
    Return a dictionary of timetable permissions for the user
    Useful for template context
    """
    return {
        'can_view_timetables': has_timetable_view_permission(user),
        'can_manage_timetables': has_timetable_manage_permission(user),
        'can_manage_timeslots': has_timeslot_manage_permission(user),
        'is_admin': is_admin(user),
        'is_teacher': is_teacher(user),
        'is_student': is_student(user),
        'is_parent': is_parent(user),
    }

def assign_user_to_group(user, group_name):
    """
    Assign a user to a specific group
    """
    try:
        group = Group.objects.get(name=group_name)
        user.groups.add(group)
        return True
    except Group.DoesNotExist:
        print(f"Group '{group_name}' does not exist")
        return False
    except Exception as e:
        print(f"Error assigning user to group: {e}")
        return False

# ===== SIGNAL HANDLERS (to be connected in apps.py) =====

def assign_user_to_group_on_save(sender, instance, created, **kwargs):
    """
    Signal handler to automatically assign users to groups based on their role
    """
    if created:
        if hasattr(instance, 'teacher'):
            assign_user_to_group(instance, 'Teachers')
        elif hasattr(instance, 'student'):
            assign_user_to_group(instance, 'Students')
        elif hasattr(instance, 'parentguardian'):
            assign_user_to_group(instance, 'Parents')