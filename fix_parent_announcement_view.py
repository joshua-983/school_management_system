import re

# Read the current parents_views.py
with open('core/views/parents_views.py', 'r') as file:
    content = file.read()

# Find and replace the ParentAnnouncementListView
old_view = '''class ParentAnnouncementListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ParentAnnouncement
    template_name = 'core/parents/announcement_list.html'
    context_object_name = 'announcements'
    paginate_by = 10
    
    def test_func(self):
        return is_parent(self.request.user)
    
    def get_queryset(self):
        parent = self.request.user.parentguardian
        children = parent.students.all()
        child_classes = children.values_list('class_level', flat=True).distinct()
        
        return ParentAnnouncement.objects.filter(
            Q(target_type='ALL') | 
            Q(target_type='CLASS', target_class__in=child_classes) |
            Q(target_type='INDIVIDUAL', target_parents=parent)
        ).select_related('created_by').order_by('-created_at')'''

new_view = '''class ParentAnnouncementListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    """Announcement list view specifically for parents using the main Announcement model"""
    model = Announcement
    template_name = 'core/parents/announcement_list.html'
    context_object_name = 'announcements'
    paginate_by = 10
    
    def test_func(self):
        return is_parent(self.request.user)
    
    def get_queryset(self):
        parent = self.request.user.parentguardian
        
        # Get all class levels of parent's children
        children_classes = parent.students.values_list('class_level', flat=True).distinct()
        
        # Get announcements that are either:
        # 1. Targeted to the parent's children's classes
        # 2. School-wide announcements (empty target_class_levels)
        # 3. Active and within date range
        from django.utils import timezone
        from django.db.models import Q
        
        queryset = Announcement.objects.filter(
            Q(target_class_levels__in=children_classes) |
            Q(target_class_levels='') |
            Q(target_class_levels__isnull=True)
        ).filter(
            is_active=True,
            start_date__lte=timezone.now(),
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=timezone.now())
        ).select_related('created_by').order_by('-created_at')
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        parent = self.request.user.parentguardian
        context['children'] = parent.students.all()
        return context'''

# Replace the old view with the new one
if old_view in content:
    content = content.replace(old_view, new_view)
    print("✅ ParentAnnouncementListView updated successfully!")
else:
    print("❌ Could not find the old ParentAnnouncementListView to replace")

# Write the updated content back
with open('core/views/parents_views.py', 'w') as file:
    file.write(content)
