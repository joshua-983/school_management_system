# core/views/announcement_views.py
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.db import models
from django.db.models import Q
from datetime import timedelta, datetime

import logging

from core.models import Announcement, UserAnnouncementView, Notification
from core.forms import AnnouncementForm

logger = logging.getLogger(__name__)

# Class level constants
CLASS_LEVEL_CHOICES = [
    ('P1', 'Primary 1'),
    ('P2', 'Primary 2'),
    ('P3', 'Primary 3'),
    ('P4', 'Primary 4'),
    ('P5', 'Primary 5'),
    ('P6', 'Primary 6'),
    ('J1', 'JHS 1'),
    ('J2', 'JHS 2'),
    ('J3', 'JHS 3'),
]

class AnnouncementListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Announcement
    template_name = 'core/announcements/announcement_list.html'
    context_object_name = 'announcements'
    paginate_by = 20
    
    def test_func(self):
        return self.request.user.is_staff or hasattr(self.request.user, 'teacher')
    
    def get_queryset(self):
        queryset = Announcement.objects.all().select_related('created_by').order_by('-created_at')
        
        # Apply filters
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                Q(title__icontains=search) | 
                Q(message__icontains=search)
            )
        
        priority = self.request.GET.get('priority')
        if priority:
            priorities = priority.split(',')
            queryset = queryset.filter(priority__in=priorities)
        
        status = self.request.GET.get('status')
        if status:
            statuses = status.split(',')
            queryset = self.apply_status_filter(queryset, statuses)
        
        class_level = self.request.GET.get('class_level')
        if class_level:
            queryset = queryset.filter(target_class_levels__icontains=class_level)
        
        return queryset
    
    def apply_status_filter(self, queryset, statuses):
        today = timezone.now().date()
        
        status_filters = Q()
        
        if 'active' in statuses:
            status_filters |= Q(is_active=True)
        
        if 'inactive' in statuses:
            status_filters |= Q(is_active=False)
        
        if 'expired' in statuses:
            status_filters |= Q(
                end_date__lt=timezone.now(),
                is_active=True
            )
        
        if 'upcoming' in statuses:
            status_filters |= Q(
                start_date__gt=timezone.now(),
                is_active=True
            )
        
        return queryset.filter(status_filters)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Add class level choices for filters
        context['class_levels'] = CLASS_LEVEL_CHOICES
        
        # Add priority choices
        context['priority_choices'] = [
            {'value': choice[0], 'label': choice[1]} 
            for choice in Announcement.PRIORITY_CHOICES
        ]
        
        # Add stats
        today = timezone.now().date()
        queryset = self.get_queryset()
        
        # Calculate priority stats
        priority_stats = []
        for priority_value, priority_label in Announcement.PRIORITY_CHOICES:
            count = queryset.filter(priority=priority_value).count()
            total = queryset.count()
            percentage = round((count / total * 100), 1) if total > 0 else 0
            priority_stats.append({
                'name': priority_value,
                'label': priority_label,
                'count': count,
                'percentage': percentage
            })
        
        # Get selected filters for template
        selected_priorities = self.request.GET.get('priority', '').split(',')
        selected_status = self.request.GET.get('status', '').split(',')
        
        context.update({
            'today': today,
            'total_count': queryset.count(),
            'active_count': queryset.filter(is_active=True).count(),
            'urgent_count': queryset.filter(priority='URGENT', is_active=True).count(),
            'today_count': queryset.filter(created_at__date=today).count(),
            'expired_count': queryset.filter(
                end_date__lt=timezone.now(),
                is_active=True
            ).count(),
            'priority_stats': priority_stats,
            'high_count': queryset.filter(priority='HIGH', is_active=True).count(),
            'recent_activity': self.get_recent_activity(),
            'selected_priorities': [p for p in selected_priorities if p],
            'selected_status': [s for s in selected_status if s],
            'has_active_filters': any([
                self.request.GET.get('search'),
                self.request.GET.get('priority'),
                self.request.GET.get('status'),
                self.request.GET.get('class_level')
            ])
        })
        
        return context
    
    def get_recent_activity(self):
        """Get recent announcement activity for stats"""
        recent_announcements = Announcement.objects.all().order_by('-created_at')[:5]
        activity = []
        
        for announcement in recent_announcements:
            activity.append({
                'icon': 'megaphone',
                'color': 'primary',
                'title': f'New: {announcement.title}',
                'description': f'By {announcement.created_by.get_full_name()}',
                'time': announcement.created_at
            })
        
        return activity


class CreateAnnouncementView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Announcement
    template_name = 'core/announcements/create_announcement.html'
    form_class = AnnouncementForm
    success_url = reverse_lazy('announcement_list')
    
    def test_func(self):
        return self.request.user.is_staff or hasattr(self.request.user, 'teacher')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['class_levels'] = CLASS_LEVEL_CHOICES
        return context
    
    def form_valid(self, form):
        try:
            form.instance.created_by = self.request.user
            
            # Check for duplicate titles
            title = form.cleaned_data['title']
            if self.is_duplicate_title(title):
                messages.warning(
                    self.request, 
                    f"An announcement with a similar title already exists. "
                    f"Please consider using a different title to avoid confusion."
                )
            
            # Log the creation details
            logger.info(f"Creating announcement: {title}")
            logger.info(f"Target roles: {form.cleaned_data['target_roles']}")
            logger.info(f"Target class levels: {form.cleaned_data.get('target_class_levels', [])}")
            
            # Save the announcement first - this will handle target_class_levels in the form's save method
            response = super().form_valid(form)
            
            # Send notifications to targeted users
            notification_count = self.send_announcement_notifications(self.object)
            
            messages.success(
                self.request, 
                f"Announcement '{self.object.title}' created successfully! "
                f"Notifications sent to {notification_count} users."
            )
            return response
        except Exception as e:
            logger.error(f"Error creating announcement: {str(e)}")
            messages.error(self.request, f"Error creating announcement: {str(e)}")
            return self.form_invalid(form)
    
    def is_duplicate_title(self, title, exclude_id=None):
        """Check if an announcement with similar title already exists"""
        similar_titles = Announcement.objects.filter(
            title__icontains=title
        )
        
        if exclude_id:
            similar_titles = similar_titles.exclude(id=exclude_id)
        
        return similar_titles.exists()
    
    def form_invalid(self, form):
        logger.error(f"Announcement form invalid: {form.errors}")
        # Log each field error for debugging
        for field, errors in form.errors.items():
            for error in errors:
                logger.error(f"Field {field} error: {error}")
                
                # Add specific error messages for target_roles
                if field == 'target_roles':
                    messages.error(self.request, f"Target audience is required: {error}")
        
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)

    def send_announcement_notifications(self, announcement):
        """Send notifications to targeted users based on class levels and roles"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            target_users = self.get_target_users(announcement)
            notification_count = 0
            
            for user in target_users:
                # Create notification using the Notification model method
                notification = Notification.create_notification(
                    recipient=user,
                    title=f"New Announcement: {announcement.title}",
                    message=announcement.message[:200] + "..." if len(announcement.message) > 200 else announcement.message,
                    notification_type="ANNOUNCEMENT",
                    link=reverse('announcement_detail', kwargs={'pk': announcement.pk}),
                    related_object=announcement
                )
                if notification:
                    notification_count += 1
            
            logger.info(f"Sent {notification_count} notifications for announcement {announcement.id}")
            return notification_count
            
        except Exception as e:
            logger.error(f"Failed to send announcement notifications: {str(e)}")
            return 0
    
    def get_target_users(self, announcement):
        """Get users who should receive this announcement based on roles and class levels"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        target_class_levels = announcement.get_target_class_levels()
        target_roles = announcement.target_roles
        
        # Build query based on target roles and class levels
        user_query = Q(is_active=True)
        
        # Filter by roles
        role_queries = Q()
        if 'STUDENT' in target_roles:
            role_queries |= Q(student__isnull=False)
        if 'TEACHER' in target_roles:
            role_queries |= Q(teacher__isnull=False)
        if 'PARENT' in target_roles:
            role_queries |= Q(parentguardian__isnull=False)
        if 'STAFF' in target_roles:
            role_queries |= Q(is_staff=True)
        
        user_query &= role_queries
        
        # Filter by class levels if specified
        if target_class_levels:
            class_level_query = Q()
            
            # Students in target classes
            if 'STUDENT' in target_roles:
                class_level_query |= Q(student__class_level__in=target_class_levels)
            
            # Parents of students in target classes
            if 'PARENT' in target_roles:
                class_level_query |= Q(parentguardian__students__class_level__in=target_class_levels)
            
            # Teachers and staff always receive class-specific announcements
            if 'TEACHER' in target_roles or 'STAFF' in target_roles:
                class_level_query |= Q(teacher__isnull=False) | Q(is_staff=True)
            
            user_query &= class_level_query
        
        target_users = User.objects.filter(user_query).distinct()
        
        # Log targeting information
        logger.info(f"Targeting {target_users.count()} users for announcement")
        logger.info(f"Target roles: {target_roles}")
        if target_class_levels:
            logger.info(f"Target class levels: {target_class_levels}")
        
        return target_users


class UpdateAnnouncementView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Announcement
    template_name = 'core/announcements/update_announcement.html'
    form_class = AnnouncementForm
    success_url = reverse_lazy('announcement_list')
    
    def test_func(self):
        announcement = self.get_object()
        return (self.request.user.is_staff or 
                hasattr(self.request.user, 'teacher') or
                self.request.user == announcement.created_by)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        # Set initial class levels from the instance
        if self.object and self.object.target_class_levels:
            kwargs['initial'] = {
                'target_class_levels': self.object.get_target_class_levels()
            }
        return kwargs
    
    def form_valid(self, form):
        # Check for duplicate titles (excluding current announcement)
        title = form.cleaned_data['title']
        if self.is_duplicate_title(title, self.object.id):
            messages.warning(
                self.request, 
                f"An announcement with a similar title already exists. "
                f"Please consider using a different title to avoid confusion."
            )
        
        response = super().form_valid(form)
        messages.success(self.request, "Announcement updated successfully!")
        return response
    
    def is_duplicate_title(self, title, exclude_id=None):
        """Check if an announcement with similar title already exists"""
        similar_titles = Announcement.objects.filter(
            title__icontains=title
        ).exclude(id=exclude_id)
        
        return similar_titles.exists()
    
    def form_invalid(self, form):
        messages.error(self.request, "Please correct the errors below.")
        return super().form_invalid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['class_levels'] = CLASS_LEVEL_CHOICES
        
        # Get view count
        context['views_count'] = UserAnnouncementView.objects.filter(
            announcement=self.object
        ).count()
        
        return context


class DeleteAnnouncementView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Announcement
    template_name = 'core/announcements/delete_announcement.html'
    success_url = reverse_lazy('announcement_list')
    
    def test_func(self):
        announcement = self.get_object()
        return (self.request.user.is_staff or 
                hasattr(self.request.user, 'teacher') or
                self.request.user == announcement.created_by)
    
    def delete(self, request, *args, **kwargs):
        announcement = self.get_object()
        messages.success(request, f"Announcement '{announcement.title}' deleted successfully!")
        return super().delete(request, *args, **kwargs)

# API Views for announcements
@login_required
def get_active_announcements(request):
    """Get active announcements for the current user"""
    try:
        announcements = Announcement.objects.filter(
            is_active=True,
            start_date__lte=timezone.now(),
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=timezone.now())
        ).order_by('-priority', '-created_at')
        
        # Filter announcements based on user type and class levels
        filtered_announcements = []
        
        for announcement in announcements:
            if should_user_see_announcement(request.user, announcement):
                filtered_announcements.append(announcement)
        
        # Remove duplicates by title (case-insensitive)
        seen_titles = set()
        unique_announcements = []
        
        for announcement in filtered_announcements:
            title_lower = announcement.title.lower()
            if title_lower not in seen_titles:
                seen_titles.add(title_lower)
                unique_announcements.append(announcement)
        
        # Prepare response data
        announcement_data = []
        for announcement in unique_announcements[:10]:  # Limit to 10 most recent
            # Mark as viewed
            UserAnnouncementView.objects.get_or_create(
                user=request.user,
                announcement=announcement,
                defaults={'viewed_at': timezone.now()}
            )
            
            announcement_data.append({
                'id': announcement.id,
                'title': announcement.title,
                'message': announcement.message,
                'priority': announcement.priority,
                'created_by': announcement.created_by.get_full_name() or announcement.created_by.username,
                'created_at': announcement.created_at.strftime('%b %d, %Y %I:%M %p'),
                'is_urgent': announcement.priority == 'URGENT',
                'target_classes': announcement.get_target_class_levels(),
                'target_roles': announcement.target_roles,
            })
        
        return JsonResponse({'announcements': announcement_data})
        
    except Exception as e:
        logger.error(f"Failed to get active announcements: {str(e)}")
        return JsonResponse({'announcements': []})

def should_user_see_announcement(user, announcement):
    """Check if a user should see a specific announcement based on roles and class levels"""
    target_class_levels = announcement.get_target_class_levels()
    target_roles = announcement.target_roles
    
    # Check if user's role is in target roles
    user_role_matches = False
    
    if user.is_staff and 'STAFF' in target_roles:
        user_role_matches = True
    elif hasattr(user, 'teacher') and 'TEACHER' in target_roles:
        user_role_matches = True
    elif hasattr(user, 'student') and 'STUDENT' in target_roles:
        user_role_matches = True
    elif hasattr(user, 'parentguardian') and 'PARENT' in target_roles:
        user_role_matches = True
    
    if not user_role_matches:
        return False
    
    # Check class level restrictions
    if target_class_levels:
        # Staff and teachers see all class-specific announcements
        if user.is_staff or hasattr(user, 'teacher'):
            return True
        
        # Students see announcements for their class
        if hasattr(user, 'student'):
            student = user.student
            return student.class_level in target_class_levels
        
        # Parents see announcements for their children's classes
        if hasattr(user, 'parentguardian'):
            parent = user.parentguardian
            children_classes = parent.students.values_list('class_level', flat=True).distinct()
            return any(cls in target_class_levels for cls in children_classes)
    
    return True

@login_required
@require_POST
def dismiss_announcement(request, pk):
    """Dismiss an announcement for the current user"""
    try:
        announcement = get_object_or_404(Announcement, pk=pk)
        UserAnnouncementView.objects.update_or_create(
            user=request.user,
            announcement=announcement,
            defaults={'dismissed': True, 'viewed_at': timezone.now()}
        )
        return JsonResponse({'status': 'success'})
    except Exception as e:
        logger.error(f"Failed to dismiss announcement: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def dismiss_all_announcements(request):
    """Dismiss all active announcements for the current user"""
    try:
        active_announcements = Announcement.objects.filter(
            is_active=True,
            start_date__lte=timezone.now(),
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=timezone.now())
        )
        
        dismissed_count = 0
        for announcement in active_announcements:
            if should_user_see_announcement(request.user, announcement):
                UserAnnouncementView.objects.update_or_create(
                    user=request.user,
                    announcement=announcement,
                    defaults={'dismissed': True, 'viewed_at': timezone.now()}
                )
                dismissed_count += 1
        
        return JsonResponse({'status': 'success', 'dismissed_count': dismissed_count})
    except Exception as e:
        logger.error(f"Failed to dismiss all announcements: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
def announcement_detail(request, pk):
    """View announcement details and mark as viewed"""
    announcement = get_object_or_404(Announcement, pk=pk)
    
    # Check if user should see this announcement
    if not should_user_see_announcement(request.user, announcement):
        messages.error(request, "You don't have permission to view this announcement.")
        return redirect('announcement_list')
    
    # Mark as viewed
    UserAnnouncementView.objects.update_or_create(
        user=request.user,
        announcement=announcement,
        defaults={'viewed_at': timezone.now()}
    )
    
    # Get views count
    views_count = UserAnnouncementView.objects.filter(announcement=announcement).count()
    
    return render(request, 'core/announcements/announcement_detail.html', {
        'announcement': announcement,
        'now': timezone.now(),
        'views_count': views_count
    })

@login_required
@require_POST
def toggle_announcement_status(request, pk):
    """Toggle announcement active status"""
    try:
        announcement = get_object_or_404(Announcement, pk=pk)
        
        # Check permission
        if not (request.user.is_staff or hasattr(request.user, 'teacher') or request.user == announcement.created_by):
            return JsonResponse({'status': 'error', 'message': 'Permission denied'}, status=403)
        
        announcement.is_active = not announcement.is_active
        announcement.save()
        
        action = "activated" if announcement.is_active else "deactivated"
        
        return JsonResponse({
            'status': 'success', 
            'is_active': announcement.is_active,
            'message': f'Announcement {action} successfully!'
        })
        
    except Exception as e:
        logger.error(f"Failed to toggle announcement status: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)}, status=400)

@login_required
@require_POST
def bulk_action_announcements(request):
    """Handle bulk actions for announcements"""
    try:
        announcement_ids = request.POST.getlist('announcement_ids')
        action = request.POST.get('action')
        
        if not announcement_ids:
            return JsonResponse({'status': 'error', 'message': 'No announcements selected'})
        
        # Convert string IDs to integers
        announcement_ids = [int(id) for id in announcement_ids if id.isdigit()]
        
        # Get announcements that user has permission to modify
        announcements = Announcement.objects.filter(id__in=announcement_ids)
        
        # Filter based on user permissions
        if not request.user.is_staff:
            announcements = announcements.filter(created_by=request.user)
        
        count = announcements.count()
        
        if action == 'activate':
            announcements.update(is_active=True)
            message = f'Activated {count} announcement(s)'
        elif action == 'deactivate':
            announcements.update(is_active=False)
            message = f'Deactivated {count} announcement(s)'
        elif action == 'delete':
            # Store titles for message
            titles = list(announcements.values_list('title', flat=True))
            announcements.delete()
            message = f'Deleted {count} announcement(s)'
        else:
            return JsonResponse({'status': 'error', 'message': 'Invalid action'})
        
        return JsonResponse({'status': 'success', 'message': message})
        
    except Exception as e:
        logger.error(f"Bulk action failed: {str(e)}")
        return JsonResponse({'status': 'error', 'message': str(e)})

# Add duplicate title check API
@login_required
def check_duplicate_title(request):
    """API endpoint to check for duplicate announcement titles"""
    title = request.GET.get('title', '')
    exclude_id = request.GET.get('exclude_id')
    
    if not title:
        return JsonResponse({'exists': False})
    
    similar_titles = Announcement.objects.filter(
        title__icontains=title
    )
    
    if exclude_id:
        similar_titles = similar_titles.exclude(id=exclude_id)
    
    exists = similar_titles.exists()
    
    return JsonResponse({
        'exists': exists,
        'similar_count': similar_titles.count()
    })



# Add to core/views/announcement_views.py
class AnnouncementStatsView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/announcements/announcement_stats.html'
    
    def test_func(self):
        return self.request.user.is_staff or hasattr(self.request.user, 'teacher')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get date range from request
        start_date = self.request.GET.get('start_date')
        end_date = self.request.GET.get('end_date')
        
        # Set default date range (last 30 days)
        if not start_date or not end_date:
            end_date = timezone.now().date()
            start_date = end_date - timedelta(days=30)
        else:
            start_date = datetime.strptime(start_date, '%Y-%m-%d').date()
            end_date = datetime.strptime(end_date, '%Y-%m-%d').date()
        
        # Filter announcements by date range
        announcements = Announcement.objects.filter(
            created_at__date__range=[start_date, end_date]
        )
        
        # Calculate statistics
        total_count = announcements.count()
        active_count = announcements.filter(is_active=True).count()
        urgent_count = announcements.filter(priority='URGENT', is_active=True).count()
        high_count = announcements.filter(priority='HIGH', is_active=True).count()
        today_count = announcements.filter(created_at__date=timezone.now().date()).count()
        
        # Calculate expired count
        expired_count = announcements.filter(
            end_date__lt=timezone.now(),
            is_active=True
        ).count()
        
        # Priority distribution
        priority_stats = []
        for priority_value, priority_label in Announcement.PRIORITY_CHOICES:
            count = announcements.filter(priority=priority_value).count()
            total = total_count if total_count > 0 else 1
            percentage = round((count / total) * 100, 1)
            priority_stats.append({
                'name': priority_value,
                'label': priority_label,
                'count': count,
                'percentage': percentage
            })
        
        # Class level distribution
        class_level_stats = []
        for class_value, class_label in CLASS_LEVEL_CHOICES:
            count = announcements.filter(target_class_levels__icontains=class_value).count()
            class_level_stats.append({
                'class_level': class_label,
                'count': count,
                'percentage': round((count / total_count) * 100, 1) if total_count > 0 else 0
            })
        
        # Recent activity
        recent_activity = []
        recent_announcements = announcements.order_by('-created_at')[:10]
        for announcement in recent_announcements:
            recent_activity.append({
                'icon': 'megaphone',
                'color': 'primary',
                'title': f'Created: {announcement.title}',
                'description': f'By {announcement.created_by.get_full_name()}',
                'time': announcement.created_at,
                'priority': announcement.priority
            })
        
        # Top performers (by views)
        top_performers = []
        for announcement in announcements:
            views_count = UserAnnouncementView.objects.filter(announcement=announcement).count()
            if views_count > 0:
                top_performers.append({
                    'title': announcement.title,
                    'views': views_count,
                    'priority': announcement.priority
                })
        
        top_performers = sorted(top_performers, key=lambda x: x['views'], reverse=True)[:5]
        
        context.update({
            'total_count': total_count,
            'active_count': active_count,
            'urgent_count': urgent_count,
            'high_count': high_count,
            'today_count': today_count,
            'expired_count': expired_count,
            'priority_stats': priority_stats,
            'class_level_stats': class_level_stats,
            'recent_activity': recent_activity,
            'top_performers': top_performers,
            'default_start_date': start_date,
            'default_end_date': end_date,
        })
        
        return context

