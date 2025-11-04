# core/views/announcement_views.py
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
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
        
        # Add stats
        today = timezone.now().date()
        queryset = self.get_queryset()
        
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
        })
        
        return context

class CreateAnnouncementView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Announcement
    template_name = 'core/announcements/create_announcement.html'
    form_class = AnnouncementForm
    success_url = reverse_lazy('announcement_list')
    
    def test_func(self):
        return self.request.user.is_staff or hasattr(self.request.user, 'teacher')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['initial'] = {
            'target_roles': 'ALL'  # Default to all users
        }
        return kwargs
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        
        # Log the creation details
        logger.info(f"Creating announcement: {form.cleaned_data['title']}")
        logger.info(f"Target class levels: {form.cleaned_data.get('target_class_levels', 'None')}")
        
        response = super().form_valid(form)
        
        # Send notifications to targeted users
        notification_count = self.send_announcement_notifications(self.object)
        
        messages.success(
            self.request, 
            f"Announcement '{self.object.title}' created successfully! "
            f"Notifications sent to {notification_count} users."
        )
        return response
    
    def form_invalid(self, form):
        logger.error(f"Announcement form invalid: {form.errors}")
        return super().form_invalid(form)
    
    def send_announcement_notifications(self, announcement):
        """Send notifications to targeted users based on class levels"""
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
                    link=reverse('announcement_list'),
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
        """Get users who should receive this announcement based on class levels"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        target_class_levels = announcement.get_target_class_levels()
        
        # Build query based on target class levels
        user_query = Q(is_active=True)
        
        if target_class_levels:
            # Target specific class levels
            user_query &= (
                # Students in target classes
                Q(student__class_level__in=target_class_levels) |
                # Parents of students in target classes
                Q(parentguardian__students__class_level__in=target_class_levels) |
                # Teachers and staff (always receive announcements)
                Q(teacher__isnull=False) |
                Q(is_staff=True)
            )
        else:
            # School-wide announcement - all active users
            user_query &= Q(is_active=True)
        
        target_users = User.objects.filter(user_query).distinct()
        
        # Log targeting information
        logger.info(f"Targeting {target_users.count()} users for announcement")
        if target_class_levels:
            logger.info(f"Target class levels: {target_class_levels}")
        
        return target_users
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['class_levels'] = CLASS_LEVEL_CHOICES
        return context

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
        response = super().form_valid(form)
        messages.success(self.request, "Announcement updated successfully!")
        return response
    
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
        
        # Prepare response data
        announcement_data = []
        for announcement in filtered_announcements[:10]:  # Limit to 10 most recent
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
            })
        
        return JsonResponse({'announcements': announcement_data})
        
    except Exception as e:
        logger.error(f"Failed to get active announcements: {str(e)}")
        return JsonResponse({'announcements': []})

def should_user_see_announcement(user, announcement):
    """Check if a user should see a specific announcement"""
    target_class_levels = announcement.get_target_class_levels()
    
    # Staff and teachers see all announcements
    if user.is_staff or hasattr(user, 'teacher'):
        return True
    
    # Students see announcements for their class or school-wide
    if hasattr(user, 'student'):
        student = user.student
        if not target_class_levels or student.class_level in target_class_levels:
            return True
    
    # Parents see announcements for their children's classes
    if hasattr(user, 'parentguardian'):
        parent = user.parentguardian
        children_classes = parent.students.values_list('class_level', flat=True).distinct()
        if not target_class_levels or any(cls in target_class_levels for cls in children_classes):
            return True
    
    return False

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
        return JsonResponse({'status': 'error'}, status=400)

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
        return JsonResponse({'status': 'error'}, status=400)

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
    
    return render(request, 'core/announcements/announcement_detail.html', {
        'announcement': announcement
    })

# Utility function to check expired announcements (call via cron/celery)
def check_expired_announcements():
    """Deactivate expired announcements"""
    try:
        expired_announcements = Announcement.objects.filter(
            is_active=True,
            end_date__lt=timezone.now()
        )
        
        count = expired_announcements.count()
        if count > 0:
            expired_announcements.update(is_active=False)
            logger.info(f"Automatically deactivated {count} expired announcements")
        
        return count
    except Exception as e:
        logger.error(f"Failed to check expired announcements: {str(e)}")
        return 0

@login_required
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
        messages.success(request, f"Announcement {action} successfully!")
        
        return JsonResponse({
            'status': 'success', 
            'is_active': announcement.is_active,
            'message': f'Announcement {action} successfully!'
        })
        
    except Exception as e:
        logger.error(f"Failed to toggle announcement status: {str(e)}")
        return JsonResponse({'status': 'error', 'message': 'Failed to update status'}, status=400)