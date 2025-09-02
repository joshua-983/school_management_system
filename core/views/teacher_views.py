from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from .base_views import *
from ..models import Teacher
from ..forms import TeacherRegistrationForm


class TeacherListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Teacher
    template_name = 'core/hr/teacher_list.html'
    context_object_name = 'teachers'
    
    def test_func(self):
        return is_admin(self.request.user)

class TeacherCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Teacher
    form_class = TeacherRegistrationForm  # Changed from TeacherForm to TeacherRegistrationForm
    template_name = 'core/hr/teacher_form.html'
    success_url = reverse_lazy('teacher_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Teacher created successfully')
        return super().form_valid(form)

class TeacherUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Teacher
    form_class = TeacherRegistrationForm
    template_name = 'core/hr/teacher_form.html'
    success_url = reverse_lazy('teacher_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Teacher updated successfully')
        return super().form_valid(form)

class TeacherDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Teacher
    template_name = 'core/hr/teacher_confirm_delete.html'
    success_url = reverse_lazy('teacher_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Teacher deleted successfully')
        return super().delete(request, *args, **kwargs)
