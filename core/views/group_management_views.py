# group_management_views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.contrib import messages
from core.permissions import is_admin

@login_required
@user_passes_test(is_admin)
def manage_timetable_groups(request):
    """View for managing timetable groups"""
    groups = Group.objects.all()
    return render(request, 'core/timetable/admin/group_management.html', {'groups': groups})

@login_required
@user_passes_test(is_admin)
def user_group_management(request):
    """View for managing user group assignments"""
    users = User.objects.all().select_related('teacher', 'student', 'parentguardian')
    groups = Group.objects.all()
    return render(request, 'core/timetable/admin/user_group_management.html', {
        'users': users,
        'groups': groups
    })

@login_required
@user_passes_test(is_admin)
def assign_user_to_group(request, user_id, group_id):
    """Assign user to a group"""
    user = get_object_or_404(User, id=user_id)
    group = get_object_or_404(Group, id=group_id)
    user.groups.add(group)
    messages.success(request, f'User {user.username} added to group {group.name}')
    return redirect('user_group_management')

@login_required
@user_passes_test(is_admin)
def remove_user_from_group(request, user_id, group_id):
    """Remove user from a group"""
    user = get_object_or_404(User, id=user_id)
    group = get_object_or_404(Group, id=group_id)
    user.groups.remove(group)
    messages.success(request, f'User {user.username} removed from group {group.name}')
    return redirect('user_group_management')