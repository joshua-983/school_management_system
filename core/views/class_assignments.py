from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .base_views import *
from ..models import ClassAssignment
from ..forms import ClassAssignmentForm
from django.contrib import messages
from django.urls import reverse_lazy  # Make sure this import is at the top


# Class Assignment Views
class ClassAssignmentListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = ClassAssignment
    template_name = 'core/academics/classes/class_assignment_list.html'  # Make sure this path is correct
    context_object_name = 'class_assignments'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_queryset(self):
        queryset = super().get_queryset().select_related('teacher', 'subject')
        if is_teacher(self.request.user):
            queryset = queryset.filter(teacher=self.request.user.teacher)
        return queryset
    
    def get_queryset(self):
        print(f"User: {self.request.user}, Is teacher: {is_teacher(self.request.user)}")
        queryset = super().get_queryset().select_related('teacher', 'subject')
        if is_teacher(self.request.user):
            print("Filtering for teacher's classes")
            queryset = queryset.filter(teacher=self.request.user.teacher)
        print(f"QuerySet count: {queryset.count()}")
        return queryset
    
    
    # Add this method to provide context data
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Add any additional context you might need
        return context

class ClassAssignmentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = ClassAssignment
    form_class = ClassAssignmentForm
    template_name = 'core/academics/classes/class_assignment_form.html'
    success_url = reverse_lazy('class_assignment_list')  # ADD THIS LINE
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        # Always set the teacher - either from the form or from the current user
        if not form.instance.teacher:
            if is_teacher(self.request.user):
                form.instance.teacher = self.request.user.teacher
            else:
                # For admins, you might want to handle this differently
                # Maybe add the teacher field to the form for admins
                form.add_error(None, "Teacher is required")
                return self.form_invalid(form)
        
        messages.success(self.request, 'Class assignment created successfully!')
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)
    

class ClassAssignmentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = ClassAssignment
    form_class = ClassAssignmentForm
    template_name = 'core/academics/classes/class_assignment_form.html'
    
    def test_func(self):
        if is_admin(self.request.user):
            return True
        if is_teacher(self.request.user):
            return self.get_object().teacher == self.request.user.teacher
        return False
    
    def form_valid(self, form):
        messages.success(self.request, 'Class assignment updated successfully!')
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse_lazy('class_assignment_list')

class ClassAssignmentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = ClassAssignment
    template_name = 'core/academics/classes/class_assignment_confirm_delete.html'
    success_url = reverse_lazy('class_assignment_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Class assignment deleted successfully')
        return super().delete(request, *args, **kwargs)
