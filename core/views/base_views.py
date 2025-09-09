from django.shortcuts import render, redirect
from django.http import Http404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse_lazy
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from ..models import Student, Teacher, Subject, AuditLog, ClassAssignment, Assignment, StudentAssignment, Grade
import logging
from django.db.models import Avg
from ..models import Fee



logger = logging.getLogger(__name__)

# Permission functions
def is_admin(user):
    return user.is_authenticated and (user.is_staff or user.is_superuser)

def is_teacher(user):
    return user.is_authenticated and hasattr(user, 'teacher')

def is_student(user):
    return user.is_authenticated and hasattr(user, 'student')

def is_parent(user):
    return user.is_authenticated and hasattr(user, 'parentguardian')

# Base views
def home(request):
    if request.user.is_authenticated:
        if is_admin(request.user):
            return redirect('admin_dashboard')
        elif is_teacher(request.user):
            return redirect('teacher_dashboard')
        elif is_student(request.user):
            return redirect('student_dashboard')
    return render(request, 'core/home.html')

@login_required
def admin_dashboard(request):
    if not is_admin(request.user):
        raise PermissionDenied
    
    # Dashboard statistics
    total_students = Student.objects.count()
    total_teachers = Teacher.objects.count()
    total_subjects = Subject.objects.count()
    
    # Recent activities
    recent_logs = AuditLog.objects.order_by('-timestamp')[:10]
    
    context = {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_subjects': total_subjects,
        'recent_logs': recent_logs,
    }
    return render(request, 'core/admin/admin_dashboard.html', context)

@login_required
def teacher_dashboard(request):
    if not is_teacher(request.user):
        raise PermissionDenied
    
    teacher = request.user.teacher
    current_classes = ClassAssignment.objects.filter(teacher=teacher)
    recent_assignments = Assignment.objects.filter(class_assignment__teacher=teacher).order_by('-due_date')[:5]
    
    context = {
        'teacher': teacher,
        'current_classes': current_classes,
        'recent_assignments': recent_assignments,
    }
    return render(request, 'core/hr/teacher_dashboard.html', context)

@login_required
def student_dashboard(request):
    if not is_student(request.user):
        raise PermissionDenied
    
    student = request.user.student
    current_assignments = StudentAssignment.objects.filter(student=student).order_by('assignment__due_date')
    
    # Calculate statistics for the dashboard
    pending_assignments = current_assignments.filter(
        status__in=['PENDING', 'LATE']
    ).count()
    
    # Calculate average grade
    grades = Grade.objects.filter(student=student)
    average_grade = grades.aggregate(Avg('total_score'))['total_score__avg']
    
    # Get fee status
    fees = Fee.objects.filter(student=student)
    fee_status = 'PAID'
    if fees.filter(payment_status='UNPAID').exists():
        fee_status = 'UNPAID'
    elif fees.filter(payment_status='PARTIAL').exists():
        fee_status = 'PARTIAL'
    
    # Get recent grades (last 5)
    recent_grades = Grade.objects.filter(student=student).order_by('-last_updated')[:5]
    
    context = {
        'student': student,
        'current_assignments': current_assignments,
        'pending_assignments': pending_assignments,
        'average_grade': round(average_grade, 1) if average_grade else 'N/A',
        'fee_status': fee_status,
        'recent_grades': recent_grades,
    }
    return render(request, 'core/students/student_dashboard.html', context)