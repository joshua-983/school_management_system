from django.shortcuts import render, redirect
from django.contrib.auth import login, logout, authenticate, update_session_auth_hash
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.views import View
from django.urls import reverse_lazy
from django.contrib.auth.decorators import login_required, user_passes_test
from django.utils.decorators import method_decorator
from .forms import CustomUserCreationForm, CustomAuthenticationForm

def is_admin_user(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)

class SignUpView(View):
    template_name = 'accounts/signup.html'
    form_class = CustomUserCreationForm
    
    @method_decorator(user_passes_test(is_admin_user, login_url='signin'))
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = self.form_class(request.POST)
        if form.is_valid():
            user = form.save()
            
            # FIX: Specify the backend when logging in (for admin creating users)
            backend = 'django.contrib.auth.backends.ModelBackend'
            user.backend = backend
            
            messages.success(request, f'Account created successfully for {user.username}!')
            return redirect('admin_dashboard')
        
        messages.error(request, 'Please correct the errors below.')
        return render(request, self.template_name, {'form': form})

class SignInView(View):
    template_name = 'accounts/signin.html'
    form_class = CustomAuthenticationForm
    
    def dispatch(self, request, *args, **kwargs):
        if request.user.is_authenticated:
            return self._redirect_to_dashboard(request.user)
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        form = self.form_class()
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = self.form_class(request, data=request.POST)
        if form.is_valid():
            user = form.get_user()
            login(request, user)
            
            # FIXED: School-specific welcome messages
            if hasattr(user, 'teacher'):
                welcome_msg = f'Welcome back, Teacher {user.teacher.get_full_name() or user.username}!'
            elif hasattr(user, 'student'):
                welcome_msg = f'Welcome back, Student {user.student.get_full_name() or user.username}!'
            elif hasattr(user, 'parentguardian'):
                # FIXED: Use get_user_full_name() instead of get_full_name()
                welcome_msg = f'Welcome back, Parent {user.parentguardian.get_user_full_name() or user.username}!'
            elif user.is_staff:
                welcome_msg = f'Welcome back, Administrator {user.username}!'
            else:
                welcome_msg = f'Welcome back, {user.username}!'
                
            messages.success(request, welcome_msg)
            return self._redirect_to_dashboard(user)
        
        messages.error(request, 'Invalid username or password. Please try again.')
        return render(request, self.template_name, {'form': form})
    
    def _redirect_to_dashboard(self, user):
        """Redirect user to appropriate dashboard based on role"""
        if hasattr(user, 'is_staff') and user.is_staff:
            return redirect('admin_dashboard')
        elif hasattr(user, 'teacher'):
            return redirect('teacher_dashboard')
        elif hasattr(user, 'student'):
            return redirect('student_dashboard')
        elif hasattr(user, 'parentguardian'):
            return redirect('parent_dashboard')
        else:
            # Regular users go to home with info message
            messages.info(request, 'Please contact school administration to assign you a role (Student, Teacher, or Parent).')
            return redirect('home')


class SignOutView(View):
    success_url = reverse_lazy('home')
    
    def get(self, request):
        if request.user.is_authenticated:
            # School-specific logout message
            if hasattr(request.user, 'teacher'):
                logout_msg = 'Teacher account logged out successfully'
            elif hasattr(request.user, 'student'):
                logout_msg = 'Student account logged out successfully'
            elif hasattr(request.user, 'parentguardian'):
                logout_msg = 'Parent account logged out successfully'
            else:
                logout_msg = 'You have been logged out successfully'
                
            logout(request)
            messages.success(request, logout_msg)
        return redirect(self.success_url)


# Password Change Views
@login_required
def password_change(request):
    """
    Custom password change view for all user types
    """
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            # Update session to prevent logout
            update_session_auth_hash(request, user)
            
            # Role-specific success messages
            if hasattr(request.user, 'teacher'):
                success_msg = 'Teacher password updated successfully!'
            elif hasattr(request.user, 'student'):
                success_msg = 'Student password updated successfully!'
            elif hasattr(request.user, 'parentguardian'):
                success_msg = 'Parent password updated successfully!'
            else:
                success_msg = 'Password updated successfully!'
                
            messages.success(request, success_msg)
            return redirect('password_change_done')
    else:
        form = PasswordChangeForm(request.user)
    
    # Determine template based on user role
    if hasattr(request.user, 'parentguardian'):
        template = 'accounts/parent_password_change.html'
    elif hasattr(request.user, 'student'):
        template = 'accounts/student_password_change.html'
    elif hasattr(request.user, 'teacher'):
        template = 'accounts/teacher_password_change.html'
    else:
        template = 'accounts/password_change.html'
    
    return render(request, template, {'form': form})


@login_required
def password_change_done(request):
    """
    Password change success page
    """
    # Determine redirect URL based on user role
    if hasattr(request.user, 'parentguardian'):
        redirect_url = 'parent_dashboard'
        success_msg = 'Your parent account password has been updated successfully.'
    elif hasattr(request.user, 'student'):
        redirect_url = 'student_dashboard'
        success_msg = 'Your student account password has been updated successfully.'
    elif hasattr(request.user, 'teacher'):
        redirect_url = 'teacher_dashboard'
        success_msg = 'Your teacher account password has been updated successfully.'
    elif request.user.is_staff:
        redirect_url = 'admin_dashboard'
        success_msg = 'Your administrator password has been updated successfully.'
    else:
        redirect_url = 'home'
        success_msg = 'Your password has been updated successfully.'
    
    messages.success(request, success_msg)
    return redirect(redirect_url)


class PasswordChangeView(View):
    """
    Class-based view for password change
    """
    template_name = 'accounts/password_change.html'
    
    @method_decorator(login_required)
    def dispatch(self, request, *args, **kwargs):
        return super().dispatch(request, *args, **kwargs)
    
    def get(self, request):
        form = PasswordChangeForm(request.user)
        
        # Set appropriate template based on user role
        if hasattr(request.user, 'parentguardian'):
            self.template_name = 'accounts/parent_password_change.html'
        elif hasattr(request.user, 'student'):
            self.template_name = 'accounts/student_password_change.html'
        elif hasattr(request.user, 'teacher'):
            self.template_name = 'accounts/teacher_password_change.html'
        
        return render(request, self.template_name, {'form': form})
    
    def post(self, request):
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)
            
            # Role-specific success message
            if hasattr(request.user, 'parentguardian'):
                success_msg = 'Parent password updated successfully!'
            elif hasattr(request.user, 'student'):
                success_msg = 'Student password updated successfully!'
            elif hasattr(request.user, 'teacher'):
                success_msg = 'Teacher password updated successfully!'
            else:
                success_msg = 'Password updated successfully!'
                
            messages.success(request, success_msg)
            return redirect('password_change_done')
        
        # Re-render form with errors
        if hasattr(request.user, 'parentguardian'):
            self.template_name = 'accounts/parent_password_change.html'
        elif hasattr(request.user, 'student'):
            self.template_name = 'accounts/student_password_change.html'
        elif hasattr(request.user, 'teacher'):
            self.template_name = 'accounts/teacher_password_change.html'
            
        return render(request, self.template_name, {'form': form})


# Public registration disabled view
def public_signup_disabled(request):
    """View to show when public registration is disabled"""
    messages.error(request, "Public registration is disabled. Please contact the school administration for account access.")
    return redirect('home')