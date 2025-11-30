# core/parent_management_views.py
from django.shortcuts import render, get_object_or_404, redirect
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Q
from django.http import HttpResponse, JsonResponse
from django.utils import timezone
import csv
from datetime import datetime, timedelta
import logging

from .models import ParentGuardian, Student, User
from .parent_forms import ParentCreationForm, BulkParentForm, ParentMessageForm, AdminParentRegistrationForm

logger = logging.getLogger(__name__)

def is_admin(user):
    return user.is_superuser or user.is_staff

@login_required
@user_passes_test(is_admin)
def parent_registration_management(request):
    """
    Admin view for managing parent registration requests and approvals
    """
    try:
        # Get registration statistics
        total_parents = ParentGuardian.objects.count()
        active_parents = ParentGuardian.objects.filter(user__is_active=True).count()
        pending_approvals = ParentGuardian.objects.filter(
            user__is_active=False,
            registration_completed=True
        ).count()
        
        # Get recent registration requests (last 30 days)
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_registrations = ParentGuardian.objects.filter(
            created_at__gte=thirty_days_ago
        ).select_related('user').order_by('-created_at')[:10]
        
        # Get pending approval requests
        pending_requests = ParentGuardian.objects.filter(
            user__is_active=False,
            registration_completed=True
        ).select_related('user').order_by('created_at')
        
        # Registration statistics by month
        from django.db.models.functions import TruncMonth
        monthly_stats = ParentGuardian.objects.annotate(
            month=TruncMonth('created_at')
        ).values('month').annotate(
            count=Count('id')
        ).order_by('-month')[:6]
        
        context = {
            'total_parents': total_parents,
            'active_parents': active_parents,
            'pending_approvals': pending_approvals,
            'recent_registrations': recent_registrations,
            'pending_requests': pending_requests,
            'monthly_stats': monthly_stats,
            'current_date': timezone.now(),
        }
        
        return render(request, 'core/admin/parent_registration_management.html', context)
        
    except Exception as e:
        logger.error(f"Error loading parent registration management: {str(e)}", exc_info=True)
        messages.error(request, "Error loading registration management data.")
        return render(request, 'core/admin/parent_registration_management.html', {})

@login_required
@user_passes_test(is_admin)
def parent_management_dashboard(request):
    """Main parent management dashboard"""
    total_parents = ParentGuardian.objects.count()
    active_parents = ParentGuardian.objects.filter(account_status='active').count()
    pending_parents = ParentGuardian.objects.filter(account_status='pending').count()
    parents_with_accounts = ParentGuardian.objects.filter(user__isnull=False).count()
    
    # Recent parent registrations
    recent_parents = ParentGuardian.objects.select_related('user').prefetch_related('students').order_by('-created_at')[:10]
    
    # Parents needing attention
    parents_needing_attention = ParentGuardian.objects.filter(
        Q(account_status='pending') | Q(students__isnull=True)
    ).distinct()[:5]
    
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
def parent_account_management(request):
    """Detailed parent account management"""
    parents = ParentGuardian.objects.select_related('user').prefetch_related('students')
    
    # Filter by status
    status_filter = request.GET.get('status')
    if status_filter:
        parents = parents.filter(account_status=status_filter)
    
    # Statistics
    total_parents = parents.count()
    active_parents = parents.filter(account_status='active').count()
    pending_parents = parents.filter(account_status='pending').count()
    
    context = {
        'parents': parents,
        'total_parents': total_parents,
        'active_parents': active_parents,
        'pending_parents': pending_parents,
        'status_filter': status_filter,
    }
    
    return render(request, 'core/admin/parent_account_management.html', context)

@login_required
@user_passes_test(is_admin)
def parent_directory(request):
    """Parent directory view"""
    parents = ParentGuardian.objects.select_related('user').prefetch_related('students')
    
    # Search functionality
    search_query = request.GET.get('search')
    if search_query:
        parents = parents.filter(
            Q(user__first_name__icontains=search_query) |
            Q(user__last_name__icontains=search_query) |
            Q(user__email__icontains=search_query) |
            Q(email__icontains=search_query) |
            Q(phone_number__icontains=search_query)
        )
    
    context = {
        'parents': parents,
        'search_query': search_query,
    }
    
    return render(request, 'core/parents/admin_parent_directory.html', context)

@login_required
@user_passes_test(is_admin)
def admin_parent_create(request):
    """Create a single parent account using the fixed form"""
    if request.method == 'POST':
        form = AdminParentRegistrationForm(request.POST)
        if form.is_valid():
            parent = form.save()
            messages.success(request, f'Parent account for {parent.get_user_full_name()} created successfully!')
            return redirect('parent_account_management')
    else:
        form = AdminParentRegistrationForm()
    
    context = {
        'form': form,
        'title': 'Create Parent Account'
    }
    
    return render(request, 'core/admin/admin_parent_create.html', context)

@login_required
@user_passes_test(is_admin)
def bulk_parent_creation(request):
    """Bulk create parent accounts"""
    if request.method == 'POST':
        form = BulkParentForm(request.POST, request.FILES)
        if form.is_valid():
            # Process bulk creation
            # This would be implemented based on your CSV processing logic
            csv_file = form.cleaned_data['csv_file']
            send_invites = form.cleaned_data['send_invites']
            
            # Placeholder for bulk creation logic
            messages.success(request, 'Bulk parent creation feature will be implemented soon!')
            return redirect('parent_management_dashboard')
    else:
        form = BulkParentForm()
    
    context = {
        'form': form,
        'title': 'Bulk Parent Creation'
    }
    
    return render(request, 'core/parents/bulk_parent_creation.html', context)

@login_required
@user_passes_test(is_admin)
def bulk_parent_invite(request):
    """Bulk invite parents to create accounts"""
    if request.method == 'POST':
        # Process bulk invites
        parent_ids = request.POST.getlist('parent_ids')
        parents = ParentGuardian.objects.filter(id__in=parent_ids)
        
        # Send invitation emails (placeholder)
        for parent in parents:
            if not parent.user and parent.email:
                # Create user account and send invitation
                parent.create_user_account()
                # send_parent_invitation_email(parent)  # Implement this function
        
        messages.success(request, f'Invitations sent to {len(parents)} parents!')
        return redirect('parent_account_management')
    
    parents = ParentGuardian.objects.filter(user__isnull=True)
    context = {
        'parents': parents
    }
    
    return render(request, 'core/parents/bulk_parent_invite.html', context)

@login_required
@user_passes_test(is_admin)
def activate_parent_account(request, parent_id):
    """Activate a parent account"""
    parent = get_object_or_404(ParentGuardian, id=parent_id)
    parent.account_status = 'active'
    parent.save()
    
    # If there's a user account, activate it too
    if parent.user:
        parent.user.is_active = True
        parent.user.save()
    
    messages.success(request, f'Parent account for {parent.get_user_full_name()} has been activated!')
    
    # Return JSON for AJAX requests
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return JsonResponse({
            'success': True,
            'message': f'Parent account for {parent.get_user_full_name()} has been activated!'
        })
    
    return redirect('parent_account_management')

@login_required
@user_passes_test(is_admin)
def suspend_parent_account(request, parent_id):
    """Suspend a parent account"""
    parent = get_object_or_404(ParentGuardian, id=parent_id)
    parent.account_status = 'suspended'
    parent.save()
    
    # If there's a user account, deactivate it too
    if parent.user:
        parent.user.is_active = False
        parent.user.save()
    
    messages.warning(request, f'Parent account for {parent.get_user_full_name()} has been suspended!')
    return redirect('parent_account_management')

@login_required
@user_passes_test(is_admin)
def send_parent_message(request, parent_id):
    """Send message to individual parent"""
    parent = get_object_or_404(ParentGuardian, id=parent_id)
    
    if request.method == 'POST':
        form = ParentMessageForm(request.POST)
        if form.is_valid():
            # Send message (email, SMS, or internal message)
            message = form.cleaned_data['message']
            subject = form.cleaned_data['subject']
            message_type = form.cleaned_data['message_type']
            
            # Implementation depends on your messaging system
            # send_parent_notification(parent, subject, message, message_type)
            
            messages.success(request, f'Message sent to {parent.get_user_full_name()}!')
            return redirect('parent_account_management')
    else:
        form = ParentMessageForm()
    
    context = {
        'form': form,
        'parent': parent
    }
    
    return render(request, 'core/parents/send_parent_message.html', context)

@login_required
@user_passes_test(is_admin)
def bulk_parent_message(request):
    """Send message to multiple parents"""
    if request.method == 'POST':
        form = ParentMessageForm(request.POST)
        if form.is_valid():
            parent_ids = request.POST.getlist('parent_ids')
            parents = ParentGuardian.objects.filter(id__in=parent_ids)
            
            # Send bulk messages
            for parent in parents:
                # Implementation depends on your messaging system
                pass
            
            messages.success(request, f'Message sent to {len(parents)} parents!')
            return redirect('parent_account_management')
    else:
        form = ParentMessageForm()
    
    parents = ParentGuardian.objects.filter(account_status='active')
    context = {
        'form': form,
        'parents': parents
    }
    
    return render(request, 'core/parents/bulk_parent_message.html', context)

@login_required
@user_passes_test(is_admin)
def parent_communication_log(request):
    """View communication history with parents"""
    # This would typically query a CommunicationLog model
    communications = []  # Placeholder
    
    context = {
        'communications': communications
    }
    
    return render(request, 'core/parents/parent_communication_log.html', context)

@login_required
@user_passes_test(is_admin)
def parent_engagement_dashboard(request):
    """Parent engagement analytics"""
    # Calculate engagement metrics
    total_parents = ParentGuardian.objects.count()
    active_this_week = ParentGuardian.objects.filter(
        last_login_date__gte=datetime.now() - timedelta(days=7)
    ).count()
    
    engagement_rate = (active_this_week / total_parents * 100) if total_parents > 0 else 0
    
    context = {
        'total_parents': total_parents,
        'active_this_week': active_this_week,
        'engagement_rate': engagement_rate,
    }
    
    return render(request, 'core/parents/parent_engagement_dashboard.html', context)

@login_required
@user_passes_test(is_admin)
def export_parent_data(request):
    """Export parent data to CSV/Excel"""
    if request.method == 'POST':
        format_type = request.POST.get('format', 'csv')
        include_personal = request.POST.get('include_personal')
        include_students = request.POST.get('include_students')
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="parent_data.csv"'
        
        writer = csv.writer(response)
        writer.writerow(['Name', 'Email', 'Phone', 'Status', 'Students'])
        
        parents = ParentGuardian.objects.select_related('user').prefetch_related('students')
        for parent in parents:
            student_names = ", ".join([s.get_full_name() for s in parent.students.all()])
            writer.writerow([
                parent.get_user_full_name(),
                parent.email,
                parent.phone_number,
                parent.get_account_status_display(),
                student_names
            ])
        
        return response
    
    return redirect('parent_account_management')