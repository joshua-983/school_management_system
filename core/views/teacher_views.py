from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib import messages  # Add this import
from django.urls import reverse_lazy  # Ensure this is imported
from .base_views import *
from ..models import Teacher
from ..forms import TeacherRegistrationForm
from django.apps import apps
from django.contrib.auth import get_user_model

class TeacherListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Teacher
    template_name = 'core/hr/teacher_list.html'
    context_object_name = 'teachers'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        print(f"DEBUG: {context['teachers'].count()} teachers in context")
        for teacher in context['teachers']:
            print(f"DEBUG: Teacher {teacher.id} - User: {teacher.user}")
            if teacher.user:
                print(f"DEBUG: -> Name: '{teacher.user.get_full_name()}', Email: '{teacher.user.email}'")
        return context

class TeacherCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Teacher
    form_class = TeacherRegistrationForm
    template_name = 'core/hr/teacher_form.html'
    success_url = reverse_lazy('teacher_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def form_valid(self, form):
        try:
            # Check if teacher with this email already exists
            email = form.cleaned_data.get('email')
            User = get_user_model()  # SIMPLER AND CLEANER
            
            if User.objects.filter(email=email).exists():
                form.add_error('email', 'A teacher with this email already exists.')
                return self.form_invalid(form)
            
            # Save the form (this will create both user and teacher)
            teacher = form.save()
            
            messages.success(self.request, f'Teacher {teacher.user.get_full_name()} created successfully!')
            return super().form_valid(form)
            
        except Exception as e:
            print(f"DEBUG: Error creating teacher - {str(e)}")
            error_message = f'Error creating teacher: {str(e)}'
            if 'email' in str(e).lower():
                error_message = 'Email already exists or is invalid. Please use a different email.'
            elif 'username' in str(e).lower():
                error_message = 'Username already exists. Please choose a different username.'
                
            messages.error(self.request, error_message)
            return self.form_invalid(form)
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