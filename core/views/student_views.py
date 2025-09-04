from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.utils.decorators import method_decorator
from django.views.decorators.cache import cache_page
from django.db.models import Q, Count
from django.contrib import messages
from django.urls import reverse_lazy

from .base_views import *
from ..models import Student, ClassAssignment, StudentAttendance
from ..forms import StudentRegistrationForm

# Add the global CLASS_LEVEL_CHOICES constant (from your previous code)
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

@method_decorator(cache_page(60*15), name='dispatch')
class StudentListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    model = Student
    template_name = 'core/students/student_list.html'
    context_object_name = 'students'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_queryset(self):
        queryset = super().get_queryset()
        class_level = self.request.GET.get('class_level')
        if class_level:
            queryset = queryset.filter(class_level=class_level)
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['class_levels'] = CLASS_LEVEL_CHOICES  # Use the global constant
        
        # Calculate statistics
        queryset = self.get_queryset()
        
        # Total students count
        context['total_students'] = queryset.count()
        
        # Gender counts
        context['male_count'] = queryset.filter(gender='M').count()
        context['female_count'] = queryset.filter(gender='F').count()
        
        # Count distinct active classes
        context['class_count'] = queryset.values('class_level').distinct().count()
        
        # Class distribution for chart (optional)
        class_distribution = queryset.values('class_level').annotate(
            count=Count('id')
        ).order_by('class_level')
        context['class_distribution'] = {
            item['class_level']: item['count'] for item in class_distribution
        }
        
        return context

class StudentDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Student
    template_name = 'core/students/student_detail.html'
    context_object_name = 'student'
    
    def test_func(self):
        if is_admin(self.request.user):
            return True
        elif is_teacher(self.request.user):
            student = self.get_object()
            return ClassAssignment.objects.filter(
                class_level=student.class_level,
                teacher=self.request.user.teacher
            ).exists()
        elif is_student(self.request.user):
            return self.request.user.student == self.get_object()
        return False
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        student = self.get_object()
        context['present_count'] = student.attendances.filter(status='present').count()
        context['absent_count'] = student.attendances.filter(status='absent').count()
        context['total_count'] = student.attendances.count()
        return context

class StudentCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Student
    form_class = StudentRegistrationForm
    template_name = 'core/students/student_form.html'
    success_url = reverse_lazy('student_list')
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Student created successfully')
        return super().form_valid(form)

class StudentUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Student
    form_class = StudentRegistrationForm
    template_name = 'core/students/student_form.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_success_url(self):
        return reverse_lazy('student_detail', kwargs={'pk': self.object.pk})
    
    def form_valid(self, form):
        messages.success(self.request, 'Student updated successfully')
        return super().form_valid(form)

class StudentDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Student
    template_name = 'core/students/student_confirm_delete.html'
    success_url = reverse_lazy('student_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Student deleted successfully')
        return super().delete(request, *args, **kwargs)