from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate
from django.contrib import messages
from django.views import View
from django.urls import reverse_lazy
from .forms import CustomUserCreationForm, CustomAuthenticationForm

class SignUpView(View):
    template_name = 'accounts/signup.html'
    form_class = CustomUserCreationForm
    success_url = reverse_lazy('home')
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, 'Account created successfully!')
            return redirect(self.success_url)
        return render(request, self.template_name, {'form': form})

class SignInView(View):
    template_name = 'accounts/signin.html'
    form_class = CustomAuthenticationForm
    success_url = reverse_lazy('home')
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return redirect(self.success_url)
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = self.form_class(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            messages.success(request, f'Welcome back, {user.username}!')
            return redirect(self.success_url)
        
        messages.error(request, 'Invalid username or password')
        return render(request, self.template_name, {'form': form})

class SignOutView(View):
    success_url = reverse_lazy('home')
    
    def get(self, request):
        if request.user.is_authenticated:
            logout(request)
            messages.success(request, 'You have been logged out successfully')
        return redirect(self.success_url)