# core/parent_auth_views.py
from django.contrib.auth import login, authenticate, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse_lazy
from django.utils.decorators import method_decorator
from django.views.generic import CreateView, FormView, TemplateView, UpdateView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView

from .models import ParentGuardian
from .parent_forms import ParentRegistrationForm, ParentLoginForm, ParentProfileForm

class ParentRegistrationView(CreateView):
    """View for parent registration"""
    model = ParentGuardian
    form_class = ParentRegistrationForm
    template_name = 'core/parents/auth/register.html'
    success_url = reverse_lazy('parent_registration_success')
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['request'] = self.request
        return kwargs
    
    def form_valid(self, form):
        response = super().form_valid(form)
        messages.success(
            self.request, 
            'Parent account created successfully! You can now login.'
        )
        return response
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)

class ParentLoginView(LoginView):
    """Custom login view for parents"""
    form_class = ParentLoginForm
    template_name = 'core/parents/auth/login.html'
    
    def get_success_url(self):
        # Update parent login stats
        if hasattr(self.request.user, 'parentguardian'):
            self.request.user.parentguardian.update_login_stats()
        
        messages.success(self.request, f'Welcome back, {self.request.user.get_full_name()}!')
        return reverse_lazy('parent_dashboard')

class ParentLogoutView(LoginRequiredMixin, TemplateView):
    """Logout view for parents"""
    
    def get(self, request, *args, **kwargs):
        logout(request)
        messages.success(request, 'You have been successfully logged out.')
        return redirect('parent_login')

class ParentProfileView(LoginRequiredMixin, UpdateView):
    """View for parents to update their profile"""
    model = ParentGuardian
    form_class = ParentProfileForm
    template_name = 'core/parents/auth/profile.html'
    
    def get_object(self):
        return self.request.user.parentguardian
    
    def get_success_url(self):
        messages.success(self.request, 'Profile updated successfully!')
        return reverse_lazy('parent_profile')
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['parent'] = self.get_object()
        return context

class ParentRegistrationSuccessView(TemplateView):
    """Success page after parent registration"""
    template_name = 'core/parents/auth/registration_success.html'

class ParentPasswordResetView(FormView):
    """View for parent password reset"""
    template_name = 'core/parents/auth/password_reset.html'
    success_url = reverse_lazy('parent_password_reset_done')
    
    def form_valid(self, form):
        # Implement password reset logic here
        messages.success(
            self.request,
            'Password reset instructions have been sent to your email.'
        )
        return super().form_valid(form)

# Decorator to ensure only parents can access certain views
def parent_required(view_func):
    """Decorator to ensure user is a parent"""
    def wrapped_view(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('parent_login')
        
        if not hasattr(request.user, 'parentguardian'):
            messages.error(request, 'Access denied. Parent account required.')
            return redirect('home')
        
        return view_func(request, *args, **kwargs)
    return wrapped_view

class ParentRequiredMixin(LoginRequiredMixin):
    """Mixin to ensure only parents can access the view"""
    
    def dispatch(self, request, *args, **kwargs):
        if not hasattr(request.user, 'parentguardian'):
            messages.error(request, 'Access denied. Parent account required.')
            return redirect('home')
        return super().dispatch(request, *args, **kwargs)