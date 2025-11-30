# core/admin_views.py
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib import messages
from django.utils import timezone

from .models import ParentGuardian
from .utils import is_admin

@login_required
@user_passes_test(is_admin)
def parent_account_management(request):
    """Admin view to manage parent accounts"""
    parents = ParentGuardian.objects.select_related('user').prefetch_related('students')
    
    # Filter by account status
    status_filter = request.GET.get('status')
    if status_filter:
        parents = parents.filter(account_status=status_filter)
    
    context = {
        'parents': parents,
        'total_parents': parents.count(),
        'active_parents': parents.filter(account_status='active').count(),
        'pending_parents': parents.filter(account_status='pending').count(),
        'status_filter': status_filter,
    }
    
    return render(request, 'core/admin/parent_account_management.html', context)

@login_required
@user_passes_test(is_admin)
def activate_parent_account(request, parent_id):
    """Activate a parent account"""
    parent = get_object_or_404(ParentGuardian, pk=parent_id)
    
    if parent.account_status != 'active':
        parent.account_status = 'active'
        parent.save()
        
        messages.success(request, f'Parent account for {parent.get_user_full_name()} has been activated.')
        
        # Here you could send an activation email
        # send_parent_account_activated_email(parent)
    
    return redirect('parent_account_management')

@login_required
@user_passes_test(is_admin)
def suspend_parent_account(request, parent_id):
    """Suspend a parent account"""
    parent = get_object_or_404(ParentGuardian, pk=parent_id)
    
    if parent.account_status == 'active':
        parent.account_status = 'suspended'
        parent.save()
        
        messages.warning(request, f'Parent account for {parent.get_user_full_name()} has been suspended.')
    
    return redirect('parent_account_management')



# core/admin_views.py
@login_required
@user_passes_test(is_admin)
def parent_management_dashboard(request):
    """Admin dashboard for parent management"""
    parents = ParentGuardian.objects.select_related('user').prefetch_related('students')
    
    # Statistics
    total_parents = parents.count()
    active_parents = parents.filter(account_status='active').count()
    pending_parents = parents.filter(account_status='pending').count()
    parents_with_accounts = parents.filter(user__isnull=False).count()
    
    # Recent parent registrations
    recent_parents = parents.order_by('-created_at')[:10]
    
    # Parents needing attention
    parents_needing_attention = parents.filter(
        Q(account_status='pending') | 
        Q(user__isnull=True)
    )[:5]
    
    context = {
        'total_parents': total_parents,
        'active_parents': active_parents,
        'pending_parents': pending_parents,
        'parents_with_accounts': parents_with_accounts,
        'recent_parents': recent_parents,
        'parents_needing_attention': parents_needing_attention,
    }
    
    return render(request, 'core/admin/parent_management_dashboard.html', context)



@login_required
@user_passes_test(is_admin)
def admin_parent_create(request):
    """Admin view to create parent accounts"""
    if request.method == 'POST':
        form = AdminParentRegistrationForm(request.POST)
        if form.is_valid():
            try:
                with transaction.atomic():
                    parent = form.save()
                    
                    # Send activation email if requested
                    if form.cleaned_data.get('send_activation_email') and parent.user:
                        # Implement email sending logic here
                        pass
                    
                    messages.success(request, f'Parent account created successfully for {parent.get_user_full_name()}')
                    return redirect('parent_management_dashboard')
                    
            except Exception as e:
                messages.error(request, f'Error creating parent account: {str(e)}')
    else:
        form = AdminParentRegistrationForm()
    
    context = {
        'form': form,
        'title': 'Create Parent Account'
    }
    return render(request, 'core/admin/parent_create.html', context)

@login_required
@user_passes_test(is_admin)
def bulk_parent_creation(request):
    """Bulk create parent accounts from student list"""
    if request.method == 'POST':
        student_ids = request.POST.getlist('student_ids')
        relationship = request.POST.get('relationship', 'G')
        
        created_count = 0
        for student_id in student_ids:
            try:
                student = Student.objects.get(pk=student_id)
                
                # Generate parent email if not provided
                base_email = f"parent.{student.student_id}@school.edu.gh"
                email = base_email
                counter = 1
                while ParentGuardian.objects.filter(email=email).exists():
                    email = f"parent.{student.student_id}{counter}@school.edu.gh"
                    counter += 1
                
                # Create parent record
                parent = ParentGuardian.objects.create(
                    relationship=relationship,
                    email=email,
                    account_status='pending'
                )
                parent.students.add(student)
                created_count += 1
                
            except Exception as e:
                messages.warning(request, f'Error creating parent for student {student_id}: {str(e)}')
                continue
        
        messages.success(request, f'Successfully created {created_count} parent records')
        return redirect('parent_management_dashboard')
    
    # GET request - show student selection form
    students = Student.objects.filter(is_active=True).select_related('user')
    context = {
        'students': students,
        'relationship_choices': ParentGuardian.RELATIONSHIP_CHOICES
    }
    return render(request, 'core/admin/bulk_parent_create.html', context)






