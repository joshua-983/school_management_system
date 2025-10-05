from django.shortcuts import render, redirect
from django.http import Http404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse_lazy
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Avg, Sum, Count, Q
from django.contrib import messages
import logging

from ..models import Student, Teacher, Subject, AuditLog, ClassAssignment, Assignment, StudentAssignment, Grade, Fee, ParentGuardian, ParentAnnouncement, ParentMessage

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
        elif is_parent(request.user):
            return redirect('parent_dashboard')
    
    # Show public homepage for unauthenticated users
    return render(request, 'core/home.html')

@login_required
def admin_dashboard(request):
    if not is_admin(request.user):
        raise PermissionDenied
    
    # Dashboard statistics
    total_students = Student.objects.filter(is_active=True).count()
    total_teachers = Teacher.objects.filter(is_active=True).count()
    total_subjects = Subject.objects.count()
    
    # Financial statistics
    fee_stats = Fee.objects.aggregate(
        total_payable=Sum('amount_payable'),
        total_paid=Sum('amount_paid'),
        total_balance=Sum('balance')
    )
    
    # Get counts by payment status
    fee_status_counts = {
        'paid': Fee.objects.filter(payment_status='paid').count(),
        'unpaid': Fee.objects.filter(payment_status='unpaid').count(),
        'partial': Fee.objects.filter(payment_status='partial').count(),
        'overdue': Fee.objects.filter(payment_status='overdue').count(),
    }
    
    # Recent activities
    recent_logs = AuditLog.objects.select_related('user').order_by('-timestamp')[:10]
    
    # Get system alerts (e.g., overdue fees, expiring subscriptions, etc.)
    overdue_fees = Fee.objects.filter(
        payment_status__in=['unpaid', 'partial'],
        due_date__lt=timezone.now().date()
    ).count()
    
    context = {
        'total_students': total_students,
        'total_teachers': total_teachers,
        'total_subjects': total_subjects,
        'fee_stats': fee_stats,
        'fee_status_counts': fee_status_counts,
        'recent_logs': recent_logs,
        'overdue_fees': overdue_fees,
    }
    return render(request, 'core/admin/admin_dashboard.html', context)

@login_required
def teacher_dashboard(request):
    if not is_teacher(request.user):
        raise PermissionDenied
    
    teacher = request.user.teacher
    
    # Get classes taught by this teacher
    current_classes = ClassAssignment.objects.filter(teacher=teacher).select_related('subject')
    
    # Get assignments created by this teacher
    recent_assignments = Assignment.objects.filter(
        class_assignment__teacher=teacher
    ).select_related('class_assignment', 'subject').order_by('-due_date')[:5]
    
    # Get students in teacher's classes
    class_levels = current_classes.values_list('class_level', flat=True)
    student_count = Student.objects.filter(
        class_level__in=class_levels, 
        is_active=True
    ).count()
    
    # Get assignments that need grading
    assignments_to_grade = Assignment.objects.filter(
        class_assignment__teacher=teacher,
        studentassignment__status='SUBMITTED'
    ).distinct().count()
    
    # Get recent student submissions
    recent_submissions = StudentAssignment.objects.filter(
        assignment__class_assignment__teacher=teacher,
        status='SUBMITTED'
    ).select_related('student', 'assignment').order_by('-submitted_date')[:5]
    
    context = {
        'teacher': teacher,
        'current_classes': current_classes,
        'recent_assignments': recent_assignments,
        'student_count': student_count,
        'assignments_to_grade': assignments_to_grade,
        'recent_submissions': recent_submissions,
    }
    return render(request, 'core/teachers/teacher_dashboard.html', context)

@login_required
def student_dashboard(request):
    if not is_student(request.user):
        raise PermissionDenied
    
    student = request.user.student
    
    # FIX: Get assignments for student's class level
    class_assignments = Assignment.objects.filter(
        class_assignment__class_level=student.class_level
    ).select_related('subject', 'class_assignment').order_by('due_date')
    
    # FIX: Get student's specific assignment records
    student_assignments = StudentAssignment.objects.filter(student=student)
    
    # Create mapping and assignments with status
    assignment_status_map = {sa.assignment_id: sa for sa in student_assignments}
    assignments_with_status = []
    
    for assignment in class_assignments:
        student_assignment = assignment_status_map.get(assignment.id)
        if not student_assignment:
            # Create missing student assignment
            student_assignment = StudentAssignment.objects.create(
                student=student,
                assignment=assignment,
                status='PENDING'
            )
        
        assignments_with_status.append({
            'assignment': assignment,
            'student_assignment': student_assignment,
            'status': student_assignment.status
        })
    
    # Rest of your existing logic...
    pending_assignments = student_assignments.filter(
        status__in=['PENDING', 'LATE']
    ).count()

    # Get assignments due soon (within 3 days)
    due_soon = student_assignments.filter(
        assignment__due_date__lte=timezone.now() + timezone.timedelta(days=3),
        status__in=['PENDING', 'LATE']
    ).count()
    
    # Calculate average grade
    grades = Grade.objects.filter(student=student)
    average_grade = grades.aggregate(Avg('total_score'))['total_score__avg']
    
    # Get fee status and details
    fees = Fee.objects.filter(student=student)
    total_payable = fees.aggregate(Sum('amount_payable'))['amount_payable__sum'] or 0
    total_paid = fees.aggregate(Sum('amount_paid'))['amount_paid__sum'] or 0
    total_balance = total_payable - total_paid
    
    # Determine fee status
    if total_balance <= 0:
        fee_status = 'PAID'
    elif total_paid > 0:
        fee_status = 'PARTIAL'
    else:
        fee_status = 'UNPAID'
    
    # Check for overdue fees
    overdue_fees = fees.filter(
        due_date__lt=timezone.now().date(),
        payment_status__in=['unpaid', 'partial']
    ).exists()
    
    # Get recent grades (last 5)
    recent_grades = Grade.objects.filter(
        student=student
    ).select_related('subject').order_by('-last_updated')[:5]
    
    # Get attendance summary for current month
    from ..models import StudentAttendance
    current_month = timezone.now().month
    current_year = timezone.now().year
    
    attendance_summary = StudentAttendance.objects.filter(
        student=student,
        date__month=current_month,
        date__year=current_year
    ).aggregate(
        present=Count('id', filter=Q(status='present')),
        absent=Count('id', filter=Q(status='absent')),
        late=Count('id', filter=Q(status='late')),
        total=Count('id')
    )
    
    context = {
        'student': student,
        'assignments_with_status': assignments_with_status,
        'student_assignments': student_assignments,
        'pending_assignments': pending_assignments,
        'due_soon': due_soon,
        'average_grade': round(average_grade, 1) if average_grade else 'N/A',
        'fee_status': fee_status,
        'total_balance': total_balance,
        'overdue_fees': overdue_fees,
        'recent_grades': recent_grades,
        'attendance_summary': attendance_summary,
    }
    return render(request, 'core/students/student_dashboard.html', context)

@login_required
def parent_dashboard(request):
    if not is_parent(request.user):
        raise PermissionDenied
    
    parent = request.user.parentguardian
    
    # Get all children of this parent
    children = parent.students.all().select_related('user')
    
    # Prepare data for each child
    children_data = []
    for child in children:
        # Get recent grades
        recent_grades = Grade.objects.filter(
            student=child
        ).select_related('subject').order_by('-last_updated')[:3]
        
        # Get attendance summary for current month
        from ..models import StudentAttendance
        current_month = timezone.now().month
        current_year = timezone.now().year
        
        attendance_summary = StudentAttendance.objects.filter(
            student=child,
            date__month=current_month,
            date__year=current_year
        ).aggregate(
            present=Count('id', filter=Q(status='present')),
            absent=Count('id', filter=Q(status='absent')),
            late=Count('id', filter=Q(status='late')),
            total=Count('id')
        )
        
        # Get fee status
        fee_status = Fee.objects.filter(
            student=child,
            payment_status__in=['unpaid', 'partial']
        ).aggregate(
            total_due=Sum('balance'),
            count=Count('id')
        )
        
        children_data.append({
            'child': child,
            'recent_grades': recent_grades,
            'attendance': attendance_summary,
            'fee_status': fee_status
        })
    
    # Get upcoming events (next 7 days)
    next_week = timezone.now() + timezone.timedelta(days=7)
    child_classes = children.values_list('class_level', flat=True).distinct()
    
    # Get recent announcements
    recent_announcements = ParentAnnouncement.objects.filter(
        Q(target_type='ALL') | 
        Q(target_type='CLASS', target_class__in=child_classes) |
        Q(target_type='INDIVIDUAL', target_parents=parent)
    ).order_by('-created_at')[:5]
    
    # Get unread messages
    unread_messages = ParentMessage.objects.filter(
        receiver=request.user,
        is_read=False
    ).count()
    
    # Get upcoming events
    from ..models import ParentEvent
    upcoming_events = ParentEvent.objects.filter(
        Q(is_whole_school=True) | Q(class_level__in=child_classes),
        start_date__gte=timezone.now(),
        start_date__lte=next_week
    ).order_by('start_date')[:5]
    
    context = {
        'parent': parent,
        'children_data': children_data,
        'recent_announcements': recent_announcements,
        'unread_messages': unread_messages,
        'upcoming_events': upcoming_events,
    }
    return render(request, 'core/parents/parent_dashboard.html', context)

# Error handlers
def handler403(request, exception):
    return render(request, 'core/errors/403.html', status=403)

def handler404(request, exception):
    return render(request, 'core/errors/404.html', status=404)

def handler500(request):
    return render(request, 'core/errors/500.html', status=500)