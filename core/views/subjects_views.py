from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from .base_views import *
from ..models import Subject
from ..forms import SubjectForm

# Subject Views
class SubjectListView(LoginRequiredMixin, ListView):
    model = Subject
    template_name = 'core/academics/subjects/subject_list.html'
    context_object_name = 'subjects'
    paginate_by = 20

class SubjectDetailView(LoginRequiredMixin, DetailView):
    model = Subject
    template_name = 'core/academics/subjects/subject_detail.html'
    context_object_name = 'subject'

class SubjectCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Subject
    form_class = SubjectForm
    template_name = 'core/academics/subjects/subject_form.html'
    success_url = reverse_lazy('subject_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Subject created successfully')
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['is_create'] = True
        return context

class SubjectUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Subject
    form_class = SubjectForm
    template_name = 'core/academics/subjects/subject_form.html'
    success_url = reverse_lazy('subject_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def form_valid(self, form):
        messages.success(self.request, 'Subject updated successfully')
        return super().form_valid(form)
    
    def get_object(self, queryset=None):
        try:
            return super().get_object(queryset)
        except Http404:
            messages.error(self.request, "Subject not found")
            raise

class SubjectDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Subject
    template_name = 'core/academics/subjects/subject_confirm_delete.html'
    success_url = reverse_lazy('subject_list')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        messages.success(request, 'Subject deleted successfully')
        return super().delete(request, *args, **kwargs)
    
    def get_object(self, queryset=None):
        try:
            return super().get_object(queryset)
        except Http404:
            messages.error(self.request, "Subject not found")
            raise
# Note: Ensure to add corresponding URL patterns and templates for these views.