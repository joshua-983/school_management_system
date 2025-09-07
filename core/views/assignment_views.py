from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView, View
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from ..models import Assignment, StudentAssignment, ClassAssignment, Subject, Student, CLASS_LEVEL_CHOICES  # Add CLASS_

from .base_views import *
from ..models import Assignment, StudentAssignment, ClassAssignment, Subject, Student
from ..forms import AssignmentForm, StudentAssignmentForm




# Assignment Views
class AssignmentListView(LoginRequiredMixin, ListView):
    model = Assignment
    template_name = 'core/academics/assignments/assignment_list.html'
    context_object_name = 'assignments'
    paginate_by = 10
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related(
            'subject', 'class_assignment', 'class_assignment__teacher'
        )
        
        # Apply filters
        subject_id = self.request.GET.get('subject')
        class_level = self.request.GET.get('class_level')
        assignment_type = self.request.GET.get('assignment_type')
        
        if subject_id:
            queryset = queryset.filter(subject_id=subject_id)
        if class_level:
            queryset = queryset.filter(class_assignment__class_level=class_level)
        if assignment_type:
            queryset = queryset.filter(assignment_type=assignment_type)
        
        # User-specific filtering
        if is_teacher(self.request.user):
            queryset = queryset.filter(class_assignment__teacher=self.request.user.teacher)
        elif is_student(self.request.user):
            queryset = queryset.filter(class_assignment__class_level=self.request.user.student.class_level)
        
        return queryset.order_by('-due_date')

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['time_now'] = timezone.now()  # Keep as datetime for template
        context['class_levels'] = CLASS_LEVEL_CHOICES
        context['assignment_types'] = Assignment.ASSIGNMENT_TYPES
        
        if is_teacher(self.request.user):
            context['subjects'] = Subject.objects.filter(teachers=self.request.user.teacher)
        elif is_student(self.request.user):
            context['subjects'] = Subject.objects.filter(
                classassignment__class_level=self.request.user.student.class_level
            ).distinct()
        else:  # Admin
            context['subjects'] = Subject.objects.all()
        
        # Add stats for the template
        queryset = self.get_queryset()
        context['assignments_count'] = queryset.count()
        
        # Get current date for comparison
        current_date = timezone.now().date()
        
        # Get student assignments for status counts
        if self.request.user.is_authenticated:
            if is_student(self.request.user):
                student_assignments = StudentAssignment.objects.filter(
                    student=self.request.user.student,
                    assignment__in=queryset
                )
                context['completed_count'] = student_assignments.filter(status='GRADED').count()
                context['pending_count'] = student_assignments.filter(status='PENDING').count()
                
                # Calculate overdue count - FIXED: Compare date parts only
                overdue_count = 0
                for assignment in queryset:
                    if (assignment.due_date.date() < current_date and 
                        not student_assignments.filter(assignment=assignment, status='GRADED').exists()):
                        overdue_count += 1
                context['overdue_count'] = overdue_count
            else:
                # For teachers/admins, show general stats
                context['completed_count'] = StudentAssignment.objects.filter(
                    assignment__in=queryset, status='GRADED'
                ).count()
                context['pending_count'] = StudentAssignment.objects.filter(
                    assignment__in=queryset, status='PENDING'
                ).count()
                
                # Calculate overdue count - FIXED: Compare date parts only
                overdue_count = 0
                for assignment in queryset:
                    if (assignment.due_date.date() < current_date and 
                        not StudentAssignment.objects.filter(assignment=assignment, status='GRADED').exists()):
                        overdue_count += 1
                context['overdue_count'] = overdue_count
        else:
            context['completed_count'] = 0
            context['pending_count'] = 0
            context['overdue_count'] = 0
        
        return context
    
    
class AssignmentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Assignment
    form_class = AssignmentForm
    template_name = 'core/academics/assignments/assignment_form.html'  # Fixed path
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        if is_teacher(self.request.user):
            form.instance.teacher = self.request.user.teacher
        
        messages.success(self.request, 'Assignment created successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('assignment_detail', kwargs={'pk': self.object.pk})

class AssignmentDetailView(LoginRequiredMixin, DetailView):
    model = Assignment
    template_name = 'core/academics/assignments/assignment_detail.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        if is_teacher(self.request.user):
            context['can_edit'] = True
        return context

class AssignmentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Assignment
    form_class = AssignmentForm
    template_name = 'core/academics/assignments/assignment_form.html'  # Same template for create/update
    
    def test_func(self):
        assignment = self.get_object()
        user = self.request.user
        
        # Admin can edit any assignment
        if is_admin(user):
            return True
        
        # Teacher can only edit their own assignments
        if is_teacher(user) and assignment.teacher == user.teacher:
            return True
        
        return False
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        messages.success(self.request, 'Assignment updated successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('assignment_detail', kwargs={'pk': self.object.pk})

class AssignmentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Assignment
    template_name = 'core/academics/assignment_confirm_delete.html'
    success_url = reverse_lazy('assignment_list')
    
    def test_func(self):
        if is_admin(self.request.user):
            return True
        if is_teacher(self.request.user):
            return self.get_object().teacher == self.request.user.teacher
        return False
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Assignment deleted successfully!')
        return super().delete(request, *args, **kwargs)
