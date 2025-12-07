# core/views_group_management.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth.models import User, Group
from django.contrib import messages
from django.db.models import Q
from django.core.paginator import Paginator
from django.http import JsonResponse

@login_required
@user_passes_test(lambda u: u.is_superuser)
def manage_timetable_groups(request):
    """Admin interface for managing timetable groups"""
    groups = Group.objects.filter(
        Q(name='Timetable Admin') | 
        Q(name='Timetable Teacher') | 
        Q(name='Timetable Student') | 
        Q(name='Timetable Parent')
    )
    
    group_data = []
    for group in groups:
        users = group.user_set.all()
        group_data.append({
            'group': group,
            'user_count': users.count(),
            'users': users[:5],  # First 5 users for preview
            'permissions': group.permissions.all()
        })
    
    return render(request, 'core/admin/timetable_groups.html', {
        'groups': group_data,
        'total_users': User.objects.count(),
    })

@login_required
@user_passes_test(lambda u: u.is_superuser)
def assign_user_to_group(request, user_id, group_id):
    """Assign a user to a timetable group"""
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        group = get_object_or_404(Group, id=group_id)
        
        # Check if group is a timetable group
        if not group.name.startswith('Timetable'):
            messages.error(request, 'Can only assign to timetable groups')
            return redirect('manage_timetable_groups')
        
        # Remove user from other timetable groups first
        timetable_groups = Group.objects.filter(name__startswith='Timetable')
        for timetable_group in timetable_groups:
            if timetable_group != group:
                timetable_group.user_set.remove(user)
        
        # Add to selected group
        group.user_set.add(user)
        
        # If adding to admin group, make user staff
        if group.name == 'Timetable Admin':
            user.is_staff = True
            user.save()
            messages.success(request, f'{user.get_full_name()} added to {group.name} and granted staff access')
        else:
            messages.success(request, f'{user.get_full_name()} added to {group.name}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
        
    return redirect('manage_timetable_groups')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def remove_user_from_group(request, user_id, group_id):
    """Remove a user from a timetable group"""
    if request.method == 'POST':
        user = get_object_or_404(User, id=user_id)
        group = get_object_or_404(Group, id=group_id)
        
        group.user_set.remove(user)
        
        # If removing from admin group, consider removing staff status
        if group.name == 'Timetable Admin':
            # Check if user is in any other staff groups
            other_admin_groups = user.groups.filter(name__in=['Timetable Admin', 'Administrators'])
            if not other_admin_groups.exists():
                user.is_staff = False
                user.save()
                messages.info(request, f'{user.get_full_name()} staff access removed')
        
        messages.success(request, f'{user.get_full_name()} removed from {group.name}')
        
        if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
            return JsonResponse({'success': True})
    
    return redirect('manage_timetable_groups')

@login_required
@user_passes_test(lambda u: u.is_superuser)
def user_group_management(request):
    """Search and manage user group assignments"""
    search_query = request.GET.get('search', '')
    page_number = request.GET.get('page', 1)
    
    users = User.objects.all()
    
    if search_query:
        users = users.filter(
            Q(username__icontains=search_query) |
            Q(first_name__icontains=search_query) |
            Q(last_name__icontains=search_query) |
            Q(email__icontains=search_query)
        )
    
    paginator = Paginator(users, 20)
    page_obj = paginator.get_page(page_number)
    
    timetable_groups = Group.objects.filter(name__startswith='Timetable')
    
    return render(request, 'core/admin/user_group_management.html', {
        'users': page_obj,
        'timetable_groups': timetable_groups,
        'search_query': search_query,
    })