# core/views/announcement_views.py
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth.decorators import login_required
from django.views.decorators.http import require_POST
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.urls import reverse_lazy, reverse
from django.utils import timezone
from django.db import models
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import logging

from core.models import Announcement, UserAnnouncementView, Notification
from core.forms import AnnouncementForm

logger = logging.getLogger(__name__)

class AnnouncementListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Announcement
    template_name = 'core/announcements/announcement_list.html'
    context_object_name = 'announcements'
    paginate_by = 20
    
    def test_func(self):
        return self.request.user.is_staff or hasattr(self.request.user, 'teacher')
    
    def get_queryset(self):
        queryset = Announcement.objects.all().select_related('created_by').order_by('-created_at')
        
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
            queryset = self.apply_status_filter(queryset, statuses)
        
        date_range = self.request.GET.get('date_range')
        if date_range:
            queryset = self.apply_date_range_filter(queryset, date_range)
        
        return queryset
    
    def apply_status_filter(self, queryset, statuses):
        today = timezone.now().date()
        
        status_filters = models.Q()
        
        if 'active' in statuses:
            status_filters |= models.Q(is_active=True)
        
        if 'inactive' in statuses:
            status_filters |= models.Q(is_active=False)
        
        if 'expired' in statuses:
            status_filters |= models.Q(
                end_date__lt=timezone.now(),
                is_active=True
            )
        
        if 'upcoming' in statuses:
            status_filters |= models.Q(
                start_date__gt=timezone.now(),
                is_active=True
            )
        
        if 'today' in statuses:
            status_filters |= models.Q(created_at__date=today)
        
        return queryset.filter(status_filters)
    
    def apply_date_range_filter(self, queryset, date_range):
        today = timezone.now().date()
        
        if date_range == 'today':
            return queryset.filter(created_at__date=today)
        elif date_range == 'yesterday':
            yesterday = today - timezone.timedelta(days=1)
            return queryset.filter(created_at__date=yesterday)
        elif date_range == 'week':
            week_ago = today - timezone.timedelta(days=7)
            return queryset.filter(created_at__date__gte=week_ago)
        elif date_range == 'month':
            month_ago = today - timezone.timedelta(days=30)
            return queryset.filter(created_at__date__gte=month_ago)
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        original_queryset = self.get_queryset()
        
        today = timezone.now().date()
        context.update({
            'active_count': original_queryset.filter(is_active=True).count(),
            'urgent_count': original_queryset.filter(priority='URGENT', is_active=True).count(),
            'today_count': original_queryset.filter(created_at__date=today).count(),
            'total_count': original_queryset.count(),
            'today': today,
            'expired_count': original_queryset.filter(
                end_date__lt=timezone.now(),
                is_active=True
            ).count(),
            'upcoming_count': original_queryset.filter(
                start_date__gt=timezone.now(),
                is_active=True
            ).count(),
        })
        
        priority_stats = self.get_priority_stats(original_queryset, context['total_count'])
        context['priority_stats'] = priority_stats
        
        context['status_stats'] = self.get_status_stats(original_queryset)
        context['recent_activity'] = self.get_recent_activity()
        context.update(self.get_filter_context())
        context.update(self.get_performance_metrics())
        
        return context
    
    def get_priority_stats(self, queryset, total_count):
        priority_stats = []
        for priority_value, priority_label in Announcement.PRIORITY_CHOICES:
            count = queryset.filter(priority=priority_value).count()
            percentage = (count / total_count * 100) if total_count > 0 else 0
            priority_stats.append({
                'name': priority_value,
                'label': priority_label,
                'count': count,
                'percentage': round(percentage, 1),
                'color': self.get_priority_color(priority_value)
            })
        return priority_stats
    
    def get_priority_color(self, priority):
        colors = {
            'URGENT': 'danger',
            'HIGH': 'warning',
            'MEDIUM': 'info',
            'LOW': 'success'
        }
        return colors.get(priority, 'secondary')
    
    def get_status_stats(self, queryset):
        today = timezone.now()
        total = queryset.count()
        
        if total == 0:
            return []
        
        status_stats = [
            {
                'name': 'Active',
                'count': queryset.filter(is_active=True).count(),
                'percentage': round(queryset.filter(is_active=True).count() / total * 100, 1),
                'color': 'success'
            },
            {
                'name': 'Inactive',
                'count': queryset.filter(is_active=False).count(),
                'percentage': round(queryset.filter(is_active=False).count() / total * 100, 1),
                'color': 'secondary'
            },
            {
                'name': 'Expired',
                'count': queryset.filter(end_date__lt=today, is_active=True).count(),
                'percentage': round(queryset.filter(end_date__lt=today, is_active=True).count() / total * 100, 1),
                'color': 'warning'
            },
            {
                'name': 'Upcoming',
                'count': queryset.filter(start_date__gt=today, is_active=True).count(),
                'percentage': round(queryset.filter(start_date__gt=today, is_active=True).count() / total * 100, 1),
                'color': 'info'
            }
        ]
        
        return status_stats
    
    def get_filter_context(self):
        return {
            'priority_choices': Announcement.PRIORITY_CHOICES,
            'selected_priorities': self.request.GET.get('priority', '').split(','),
            'selected_status': self.request.GET.get('status', '').split(','),
            'selected_date_range': self.request.GET.get('date_range', ''),
            'search_query': self.request.GET.get('search', ''),
            'has_active_filters': self.has_active_filters(),
            'class_level_choices': [
                ('P1', 'Primary 1'), ('P2', 'Primary 2'), ('P3', 'Primary 3'),
                ('P4', 'Primary 4'), ('P5', 'Primary 5'), ('P6', 'Primary 6'),
                ('J1', 'JHS 1'), ('J2', 'JHS 2'), ('J3', 'JHS 3')
            ],
            'date_range_choices': [
                ('today', 'Today'),
                ('yesterday', 'Yesterday'),
                ('week', 'Last 7 Days'),
                ('month', 'Last 30 Days')
            ]
        }
    
    def has_active_filters(self):
        return any([
            self.request.GET.get('search'),
            self.request.GET.get('priority'),
            self.request.GET.get('status'),
            self.request.GET.get('date_range')
        ])
    
    def get_performance_metrics(self):
        total_announcements = Announcement.objects.count()
        active_announcements = Announcement.objects.filter(is_active=True).count()
        
        try:
            total_views = UserAnnouncementView.objects.count()
            avg_views = total_views / total_announcements if total_announcements > 0 else 0
        except Exception as e:
            logger.error(f"Error calculating average views: {str(e)}")
            avg_views = 0
        
        try:
            active_views = UserAnnouncementView.objects.filter(
                announcement__is_active=True
            ).count()
            avg_active_views = active_views / active_announcements if active_announcements > 0 else 0
        except Exception as e:
            logger.error(f"Error calculating active views: {str(e)}")
            avg_active_views = 0
        
        return {
            'total_announcements': total_announcements,
            'active_announcements': active_announcements,
            'avg_views': round(avg_views, 1),
            'avg_active_views': round(avg_active_views, 1),
            'completion_rate': round((active_announcements / total_announcements * 100), 1) if total_announcements > 0 else 0
        }
    
    def get_recent_activity(self):
        recent_announcements = Announcement.objects.select_related('created_by').order_by('-created_at')[:5]
        activity = []
        
        for announcement in recent_announcements:
            if announcement.priority == 'URGENT':
                icon = 'alert-triangle'
                color = 'danger'
                activity_type = 'Urgent'
            elif announcement.start_date > timezone.now():
                icon = 'clock'
                color = 'info'
                activity_type = 'Scheduled'
            else:
                icon = 'megaphone'
                color = 'primary'
                activity_type = 'Published'
            
            activity.append({
                'icon': icon,
                'color': color,
                'type': activity_type,
                'title': announcement.title,
                'description': f'By {announcement.created_by.get_full_name() or announcement.created_by.username}',
                'time': announcement.created_at,
                'priority': announcement.priority,
                'is_active': announcement.is_active
            })
        
        return activity


class CreateAnnouncementView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Announcement
    template_name = 'core/announcements/create_announcement.html'
    form_class = AnnouncementForm
    success_url = reverse_lazy('announcement_list')
    
    def test_func(self):
        return self.request.user.is_staff or hasattr(self.request.user, 'teacher')
    
    def form_valid(self, form):
        form.instance.created_by = self.request.user
        response = super().form_valid(form)
        
        # DEBUG: Log announcement creation
        logger.info(f"🎯 CREATING ANNOUNCEMENT: {self.object.title}")
        logger.info(f"🎯 Target classes: {self.object.target_class_levels}")
        logger.info(f"🎯 Priority: {self.object.priority}")
        logger.info(f"🎯 Is active: {self.object.is_active}")
        
        # Send notifications to all relevant users
        notification_count = self.send_announcement_notifications(self.object)
        
        # Broadcast the announcement to all relevant users via WebSocket
        self.broadcast_announcement(self.object)
        
        messages.success(self.request, f"Announcement published successfully! Notifications sent to {notification_count} users.")
        return response
    
    def send_announcement_notifications(self, announcement):
        """Send notifications to all users who should see this announcement"""
        try:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            # Get target users based on announcement settings
            target_users = self.get_target_users(announcement)
            
            # DEBUG: Check if we found any users
            if target_users.count() == 0:
                logger.warning("⚠️  No target users found for announcement!")
                return 0
            
            notification_count = 0
            for user in target_users:
                # DEBUG: Log each user being notified
                user_type = "Student" if hasattr(user, 'student') else \
                           "Parent" if hasattr(user, 'parentguardian') else \
                           "Teacher" if hasattr(user, 'teacher') else \
                           "Staff" if user.is_staff else "Unknown"
                
                logger.info(f"🎯 Notifying {user_type}: {user.username} ({user.get_full_name()})")
                
                # Use the Notification class method to create notification
                notification = Notification.create_notification(
                    recipient=user,
                    title=f"New Announcement: {announcement.title}",
                    message=announcement.message[:100] + "..." if len(announcement.message) > 100 else announcement.message,
                    notification_type="GENERAL",
                    link=reverse('announcement_list'),
                    related_object=announcement
                )
                if notification:
                    notification_count += 1
                    logger.info(f"✅ Notification created for {user.username}")
                else:
                    logger.error(f"❌ Failed to create notification for {user.username}")
            
            logger.info(f"🎯 FINAL: Notifications sent to {notification_count}/{target_users.count()} users")
            return notification_count
            
        except Exception as e:
            logger.error(f"❌ Failed to send announcement notifications: {str(e)}", exc_info=True)
            return 0
    
    def get_target_users(self, announcement):
        """Get all users who should receive this announcement"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        target_class_levels = announcement.get_target_class_levels()
        
        # Use Q objects to combine queries properly
        from django.db.models import Q
        
        if target_class_levels:
            # Build a complex query using Q objects
            user_query = Q(is_active=True) & (
                # Students in target classes
                Q(student__class_level__in=target_class_levels) |
                # Parents of students in target classes  
                Q(parentguardian__students__class_level__in=target_class_levels) |
                # Teachers (always get announcements)
                Q(teacher__isnull=False) |
                # Staff (always get announcements)
                Q(is_staff=True)
            )
            
            target_users = User.objects.filter(user_query).distinct()
            
            # DEBUG: Log the counts
            student_count = User.objects.filter(
                student__class_level__in=target_class_levels, 
                is_active=True
            ).count()
            parent_count = User.objects.filter(
                parentguardian__students__class_level__in=target_class_levels,
                is_active=True
            ).distinct().count()
            teacher_count = User.objects.filter(
                teacher__isnull=False,
                is_active=True
            ).count()
            staff_count = User.objects.filter(
                is_staff=True,
                is_active=True
            ).count()
            
            logger.info(f"🎯 Target users breakdown:")
            logger.info(f"🎯 Students in classes {target_class_levels}: {student_count}")
            logger.info(f"🎯 Parents of students in classes {target_class_levels}: {parent_count}")
            logger.info(f"🎯 Teachers: {teacher_count}")
            logger.info(f"🎯 Staff: {staff_count}")
            logger.info(f"🎯 Total target users: {target_users.count()}")
            
        else:
            # School-wide announcement - send to all active users
            target_users = User.objects.filter(is_active=True)
            logger.info(f"🎯 School-wide announcement - All active users: {target_users.count()}")
        
        return target_users
    
    def broadcast_announcement(self, announcement):
        """Send announcement to all relevant users via WebSocket"""
        try:
            channel_layer = get_channel_layer()
            target_users = self.get_target_users(announcement)
            
            # Send to each user
            for user in target_users:
                async_to_sync(channel_layer.group_send)(
                    f'announcements_{user.id}',
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
            
            logger.info(f"🎯 WebSocket broadcast to {target_users.count()} users")
                
        except Exception as e:
            logger.error(f"❌ WebSocket broadcast failed: {str(e)}")
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['class_level_choices'] = [
            ('P1', 'Primary 1'), ('P2', 'Primary 2'), ('P3', 'Primary 3'),
            ('P4', 'Primary 4'), ('P5', 'Primary 5'), ('P6', 'Primary 6'),
            ('J1', 'JHS 1'), ('J2', 'JHS 2'), ('J3', 'JHS 3')
        ]
        return context


class UpdateAnnouncementView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Announcement
    template_name = 'core/announcements/update_announcement.html'
    form_class = AnnouncementForm
    success_url = reverse_lazy('announcement_list')
    
    def test_func(self):
        return self.request.user.is_staff or hasattr(self.request.user, 'teacher')
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(self.request, "Announcement updated successfully!")
        return response
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['class_level_choices'] = [
            ('P1', 'Primary 1'), ('P2', 'Primary 2'), ('P3', 'Primary 3'),
            ('P4', 'Primary 4'), ('P5', 'Primary 5'), ('P6', 'Primary 6'),
            ('J1', 'JHS 1'), ('J2', 'JHS 2'), ('J3', 'JHS 3')
        ]
        
        context['views_count'] = UserAnnouncementView.objects.filter(
            announcement=self.object
        ).count()
        
        return context

class DeleteAnnouncementView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Announcement
    template_name = 'core/announcements/delete_announcement.html'
    success_url = reverse_lazy('announcement_list')
    
    def test_func(self):
        return self.request.user.is_staff or hasattr(self.request.user, 'teacher')
    
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
            filtered_announcements = []
            for announcement in announcements:
                target_class_levels = announcement.get_target_class_levels()
                if not target_class_levels or student.class_level in target_class_levels:
                    filtered_announcements.append(announcement)
            announcements = filtered_announcements
        
        # If user is teacher/staff, show all announcements
        elif request.user.is_staff or hasattr(request.user, 'teacher'):
            pass
        else:
            # For other users (like parents), show only school-wide announcements
            filtered_announcements = []
            for announcement in announcements:
                target_class_levels = announcement.get_target_class_levels()
                if not target_class_levels:  # Only school-wide announcements
                    filtered_announcements.append(announcement)
            announcements = filtered_announcements
        
        announcements = list(announcements)
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
        announcements = Announcement.objects.filter(
            is_active=True,
            start_date__lte=timezone.now(),
        ).filter(
            models.Q(end_date__isnull=True) | models.Q(end_date__gte=timezone.now())
        )
        
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