# core/views/announcement_views.py
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.db import models
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

from core.models import Announcement, UserAnnouncementView
from core.forms import AnnouncementForm  # Import the updated form

logger = logging.getLogger(__name__)

class AnnouncementListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Announcement
    template_name = 'core/announcements/announcement_list.html'
    context_object_name = 'announcements'
    paginate_by = 20
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_teacher
    
    def get_queryset(self):
        # Add filtering based on request parameters
        queryset = Announcement.objects.all().order_by('-created_at')
        
        # Apply filters from request
        search = self.request.GET.get('search')
        if search:
            queryset = queryset.filter(
                models.Q(title__icontains=search) | 
                models.Q(message__icontains=search)
            )
        
        priority = self.request.GET.get('priority')
        if priority:
            priorities = priority.split(',')
            queryset = queryset.filter(priority__in=priorities)
        
        status = self.request.GET.get('status')
        if status:
            statuses = status.split(',')
            if 'active' in statuses:
                queryset = queryset.filter(is_active=True)
            if 'inactive' in statuses:
                queryset = queryset.filter(is_active=False)
            if 'expired' in statuses:
                queryset = queryset.filter(
                    end_date__lt=timezone.now(),
                    is_active=True
                )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        announcements = context['announcements']
        
        # Calculate stats
        today = timezone.now().date()
        context['active_count'] = announcements.filter(is_active=True).count()
        context['urgent_count'] = announcements.filter(priority='URGENT', is_active=True).count()
        context['today_count'] = announcements.filter(created_at__date=today).count()
        context['today'] = today
        context['total_count'] = announcements.count()
        
        # Priority statistics for the chart
        priority_stats = []
        for priority_value, priority_label in Announcement.PRIORITY_CHOICES:
            count = announcements.filter(priority=priority_value).count()
            percentage = (count / context['total_count'] * 100) if context['total_count'] > 0 else 0
            priority_stats.append({
                'name': priority_value,
                'label': priority_label,
                'count': count,
                'percentage': round(percentage, 1)
            })
        context['priority_stats'] = priority_stats
        
        # Recent activity (you might want to create an Activity model for this)
        context['recent_activity'] = self.get_recent_activity()
        
        # Filter options
        context['priority_choices'] = Announcement.PRIORITY_CHOICES
        context['selected_priorities'] = self.request.GET.get('priority', '').split(',')
        context['selected_status'] = self.request.GET.get('status', '').split(',')
        context['has_active_filters'] = any([
            self.request.GET.get('search'),
            self.request.GET.get('priority'),
            self.request.GET.get('status'),
            self.request.GET.get('date_range')
        ])
        
        # Class levels for display (using the choices, not a model)
        context['class_level_choices'] = [
            ('P1', 'Primary 1'), ('P2', 'Primary 2'), ('P3', 'Primary 3'),
            ('P4', 'Primary 4'), ('P5', 'Primary 5'), ('P6', 'Primary 6'),
            ('J1', 'JHS 1'), ('J2', 'JHS 2'), ('J3', 'JHS 3')
        ]
        
        return context
    
    def get_recent_activity(self):
        """Get recent announcement activity for the stats panel"""
        # This is a simplified version - you might want to create an Activity model
        recent_announcements = Announcement.objects.all().order_by('-created_at')[:5]
        activity = []
        
        for announcement in recent_announcements:
            activity.append({
                'icon': 'megaphone',
                'color': 'primary',
                'title': f'New: {announcement.title}',
                'description': f'Created by {announcement.created_by.get_full_name()}',
                'time': announcement.created_at
            })
        
        return activity

class CreateAnnouncementView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Announcement
    template_name = 'core/announcements/create_announcement.html'
    form_class = AnnouncementForm  # Use the form instead of fields
    success_url = reverse_lazy('announcement_list')
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_teacher
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        
        # Broadcast the announcement to all relevant users via WebSocket
        self.broadcast_announcement(self.object)
        messages.success(self.request, "Announcement published successfully!")
        return response
    
    def broadcast_announcement(self, announcement):
        """Send announcement to all relevant users via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            target_user_ids = self.get_target_user_ids(announcement)
            
            # Send to each user
            for user_id in target_user_ids:
                async_to_sync(channel_layer.group_send)(
                    f'announcements_{user_id}',
                    {
                        'type': 'new_announcement',
                        'announcement': {
                            'id': announcement.id,
                            'title': announcement.title,
                            'message': announcement.message,
                            'priority': announcement.priority,
                            'created_by': announcement.created_by.get_full_name() or announcement.created_by.username,
                            'created_at': announcement.created_at.isoformat(),
                        }
                    }
                )
            
            logger.info(f"Announcement broadcast to {len(target_user_ids)} users: {announcement.title}")
                
        except Exception as e:
            logger.error(f"Announcement broadcast failed: {str(e)}")
    
    def get_target_user_ids(self, announcement):
        """Get list of user IDs who should receive this announcement"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        target_class_levels = announcement.get_target_class_levels()
        
        if target_class_levels:
            # Specific classes - get students in those classes
            from core.models import Student
            student_users = Student.objects.filter(
                class_level__in=target_class_levels
            ).values_list('user_id', flat=True)
            
            # Also include teachers/staff
            teacher_staff_users = User.objects.filter(
                models.Q(is_teacher=True) | models.Q(is_staff=True),
                is_active=True
            ).values_list('id', flat=True)
            
            # Combine and remove duplicates
            target_user_ids = set(list(student_users) + list(teacher_staff_users))
        else:
            # School-wide announcement - send to all active users
            target_user_ids = set(User.objects.filter(
                is_active=True
            ).values_list('id', flat=True))
        
        return list(target_user_ids)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add class level choices for the template
        context['class_level_choices'] = [
            ('P1', 'Primary 1'), ('P2', 'Primary 2'), ('P3', 'Primary 3'),
            ('P4', 'Primary 4'), ('P5', 'Primary 5'), ('P6', 'Primary 6'),
            ('J1', 'JHS 1'), ('J2', 'JHS 2'), ('J3', 'JHS 3')
        ]
        return context

class UpdateAnnouncementView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Announcement
    template_name = 'core/announcements/update_announcement.html'
    form_class = AnnouncementForm  # Use the form instead of fields
    success_url = reverse_lazy('announcement_list')
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_teacher
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Announcement updated successfully!")
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add class level choices for the template
        context['class_level_choices'] = [
            ('P1', 'Primary 1'), ('P2', 'Primary 2'), ('P3', 'Primary 3'),
            ('P4', 'Primary 4'), ('P5', 'Primary 5'), ('P6', 'Primary 6'),
            ('J1', 'JHS 1'), ('J2', 'JHS 2'), ('J3', 'JHS 3')
        ]
        
        # Add stats for the update view
        context['views_count'] = UserAnnouncementView.objects.filter(
            announcement=self.object
        ).count()
        
        return context

class DeleteAnnouncementView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Announcement
    template_name = 'core/announcements/delete_announcement.html'
    success_url = reverse_lazy('announcement_list')
    
    def test_func(self):
        return self.request.user.is_staff or self.request.user.is_teacher
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, "Announcement deleted successfully!")
        return super().delete(request, *args, **kwargs)

@login_required
def get_active_announcements(request):
    """API endpoint to get active announcements for the current user"""
    try:
        announcements = Announcement.objects.filter(
            is_active=True,
            start_date__lte=timezone.now(),
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=timezone.now())
        )
        
        # Filter by user's class if they're a student
        if hasattr(request.user, 'student'):
            student = request.user.student
            # Check if announcement is for this student's class or all classes
            filtered_announcements = []
            for announcement in announcements:
                target_class_levels = announcement.get_target_class_levels()
                if not target_class_levels or student.class_level in target_class_levels:
                    filtered_announcements.append(announcement)
            announcements = filtered_announcements
        
        # If user is teacher/staff, show all announcements
        elif request.user.is_teacher or request.user.is_staff:
            # Show all announcements for staff/teachers
            pass
        
        announcements = list(announcements)  # Convert to list since we filtered manually
        announcements.sort(key=lambda x: (x.priority != 'URGENT', -x.created_at.timestamp()))
        
        # Check which announcements user has dismissed
        dismissed_announcements = UserAnnouncementView.objects.filter(
            user=request.user,
            dismissed=True
        ).values_list('announcement_id', flat=True)
        
        active_announcements = []
        for announcement in announcements:
            if announcement.id not in dismissed_announcements:
                active_announcements.append({
                    'id': announcement.id,
                    'title': announcement.title,
                    'message': announcement.message,
                    'priority': announcement.priority,
                    'created_by': announcement.created_by.get_full_name() or announcement.created_by.username,
                    'created_at': announcement.created_at.strftime('%b %d, %Y %I:%M %p'),
                    'is_urgent': announcement.priority == 'URGENT'
                })
        
        return JsonResponse({'announcements': active_announcements})
        
    except Exception as e:
        logger.error(f"Failed to get active announcements: {str(e)}")
        return JsonResponse({'announcements': []})

@login_required
@require_POST
def dismiss_announcement(request, pk):
    """API endpoint to dismiss an announcement"""
    try:
        announcement = get_object_or_404(Announcement, pk=pk)
        UserAnnouncementView.objects.update_or_create(
            user=request.user,
            announcement=announcement,
            defaults={'dismissed': True}
        )
        return JsonResponse({'status': 'success'})
    except Exception as e:
        logger.error(f"Failed to dismiss announcement: {str(e)}")
        return JsonResponse({'status': 'error'}, status=400)

@login_required
@require_POST
def dismiss_all_announcements(request):
    """API endpoint to dismiss all active announcements"""
    try:
        # Get all active announcements
        announcements = Announcement.objects.filter(
            is_active=True,
            start_date__lte=timezone.now(),
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=timezone.now())
        )
        
        # Create dismissal records for all active announcements
        for announcement in announcements:
            UserAnnouncementView.objects.update_or_create(
                user=request.user,
                announcement=announcement,
                defaults={'dismissed': True}
            )
        
        return JsonResponse({'status': 'success', 'dismissed_count': announcements.count()})
    except Exception as e:
        logger.error(f"Failed to dismiss all announcements: {str(e)}")
        return JsonResponse({'status': 'error'}, status=400)

def check_expired_announcements():
    """Check and handle expired announcements (call this via cron or celery)"""
    try:
        expired_announcements = Announcement.objects.filter(
            is_active=True,
            end_date__lt=timezone.now()
        )
        
        count = expired_announcements.count()
        if count > 0:
            expired_announcements.update(is_active=False)
            logger.info(f"Deactivated {count} expired announcements")
        
        return count
    except Exception as e:
        logger.error(f"Failed to check expired announcements: {str(e)}")
        return 0