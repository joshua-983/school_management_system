from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from core.permissions import is_parent, is_admin, is_teacher
from core.utils.logger import log_view_exception
from django.db.models import Max, Min

from django.shortcuts import render, redirect
from django.http import Http404, JsonResponse
from django.contrib.auth.decorators import login_required, user_passes_test
from django.urls import reverse_lazy
from django.core.exceptions import PermissionDenied
from django.utils import timezone
from django.db.models import Avg, Sum, Count, Q
from django.contrib import messages
import logging
from datetime import datetime, timedelta

from core.models import (
    Student, Teacher, Subject, AuditLog, ClassAssignment, 
    Assignment, StudentAssignment, Grade, Fee, ParentGuardian, 
    ParentAnnouncement, ParentMessage, Bill, BillPayment,
    StudentAttendance, ParentEvent, AcademicTerm, ReportCard
)

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

# Utility functions for grade views
def get_current_academic_year():
    """Get current academic year in YYYY/YYYY format"""
    now = timezone.now()
    year = now.year
    # Assuming academic year runs from September to August
    if now.month >= 9:  # September or later
        return f"{year}/{year + 1}"
    else:  # January to August
        return f"{year - 1}/{year}"

def get_class_level_choices():
    """Return standardized class level choices"""
    return (
        ('P1', 'Primary 1'),
        ('P2', 'Primary 2'), 
        ('P3', 'Primary 3'),
        ('P4', 'Primary 4'),
        ('P5', 'Primary 5'),
        ('P6', 'Primary 6'),
        ('J1', 'JHS 1'),
        ('J2', 'JHS 2'),
        ('J3', 'JHS 3'),
    )

# Base views
def home(request):
    """Public homepage with role-based redirects for authenticated users"""
    if request.user.is_authenticated:
        # Check if user has a specific role that should go to dashboard
        if (hasattr(request.user, 'teacher') or 
            hasattr(request.user, 'student') or 
            hasattr(request.user, 'parentguardian') or
            (hasattr(request.user, 'is_staff') and request.user.is_staff)):
            return redirect('dashboard')
        else:
            # Regular authenticated user without specific role - show home page with info
            try:
                context = {
            'user': request.user,

                    'current_year': timezone.now().year,
                    'featured_stats': {
                        'total_students': Student.objects.filter(is_active=True).count(),
                        'total_teachers': Teacher.objects.filter(is_active=True).count(),
                        'total_subjects': Subject.objects.count(),
                    }
                }
            except Exception as e:
                logger.error(f"Error loading home page stats: {str(e)}")
                context = {
                    'current_year': timezone.now().year,
                    'featured_stats': {
                        'total_students': 0,
                        'total_teachers': 0,
                        'total_subjects': 0,
                    }
                }
            return render(request, 'core/home.html', context)
    
    # Show public homepage for unauthenticated users
    try:
        context = {
            'current_year': timezone.now().year,
            'featured_stats': {
                'total_students': Student.objects.filter(is_active=True).count(),
                'total_teachers': Teacher.objects.filter(is_active=True).count(),
                'total_subjects': Subject.objects.count(),
            }
        }
    except Exception as e:
        logger.error(f"Error loading home page stats: {str(e)}")
        context = {
            'current_year': timezone.now().year,
            'featured_stats': {
                'total_students': 0,
                'total_teachers': 0,
                'total_subjects': 0,
            }
        }
    
    return render(request, 'core/home.html', context)

@login_required
def dashboard(request):
    """Main dashboard that redirects based on user role"""
    if hasattr(request.user, 'is_staff') and request.user.is_staff:
        return redirect('admin_dashboard')
    elif hasattr(request.user, 'teacher'):
        return redirect('teacher_dashboard')
    elif hasattr(request.user, 'student'):
        return redirect('student_dashboard')
    elif hasattr(request.user, 'parentguardian'):
        return redirect('parent_dashboard')
    else:
        # If user doesn't have a specific role, show home with message
        messages.info(request, "Your account is pending role assignment. Please contact school administration.")
        return redirect('home')

@login_required
def admin_dashboard(request):
    """Admin dashboard with comprehensive system overview"""
    if not is_admin(request.user):
        raise PermissionDenied("Access denied: Admin privileges required")
    
    try:
        # Dashboard statistics
        total_students = Student.objects.filter(is_active=True).count()
        total_teachers = Teacher.objects.filter(is_active=True).count()
        total_subjects = Subject.objects.count()
        total_parents = ParentGuardian.objects.count()
        
        # Financial statistics with error handling
        fee_stats = Fee.objects.aggregate(
            total_payable=Sum('amount_payable'),
            total_paid=Sum('amount_paid'),
            total_balance=Sum('balance')
        )
        
        # Bill statistics
        bill_stats = Bill.objects.aggregate(
            total_bills=Count('id'),
            paid_bills=Count('id', filter=Q(status='paid')),
            overdue_bills=Count('id', filter=Q(status='overdue'))
        )
        
        # Get counts by payment status
        fee_status_counts = {
            'paid': Fee.objects.filter(payment_status='paid').count(),
            'unpaid': Fee.objects.filter(payment_status='unpaid').count(),
            'partial': Fee.objects.filter(payment_status='partial').count(),
            'overdue': Fee.objects.filter(payment_status='overdue').count(),
        }
        
        # Grade statistics
        grade_stats = Grade.objects.aggregate(
            total_grades=Count('id'),
            average_score=Avg('total_score'),
            recent_grades=Count('id', filter=Q(
                last_updated__gte=timezone.now() - timedelta(days=7)
            ))
        )
        
        # Recent activities with error handling
        recent_logs = AuditLog.objects.select_related('user').filter(user__isnull=False).order_by('-timestamp')[:10]
        
        # Get system alerts
        overdue_fees = Fee.objects.filter(
            payment_status__in=['unpaid', 'partial'],
            due_date__lt=timezone.now().date()
        ).count()
        
        # Pending assignments to grade
        pending_grading = StudentAssignment.objects.filter(
            status__in=['SUBMITTED', 'LATE']
        ).count()
        
        # Recent bills
        recent_bills = Bill.objects.select_related('student').order_by('-issue_date')[:5]
        
        # Upcoming events
        upcoming_events = ParentEvent.objects.filter(
            start_date__gte=timezone.now(),
            start_date__lte=timezone.now() + timedelta(days=30)
        ).order_by('start_date')[:5]
        
        # Attendance statistics
        today_attendance = StudentAttendance.objects.filter(
            date=timezone.now().date()
        ).aggregate(
            present=Count('id', filter=Q(status='present')),
            absent=Count('id', filter=Q(status='absent')),
            late=Count('id', filter=Q(status='late')),
            total=Count('id')
        )
        
        context = {
            'user': request.user,
            'total_students': total_students,
            'total_teachers': total_teachers,
            'total_subjects': total_subjects,
            'total_parents': total_parents,
            'fee_stats': fee_stats,
            'bill_stats': bill_stats,
            'fee_status_counts': fee_status_counts,
            'grade_stats': grade_stats,
            'recent_logs': recent_logs,
            'overdue_fees': overdue_fees,
            'pending_grading': pending_grading,
            'recent_bills': recent_bills,
            'upcoming_events': upcoming_events,
            'today_attendance': today_attendance,
            'current_academic_year': get_current_academic_year(),
            'current_date': timezone.now(),
        }
        
        return render(request, 'core/admin/admin_dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Error loading admin dashboard: {str(e)}", exc_info=True)
        messages.error(request, "Error loading dashboard data. Please try again.")
        return render(request, 'core/admin/admin_dashboard.html', {
            'current_date': timezone.now(),
            'total_students': 0,
            'total_teachers': 0,
            'total_subjects': 0,
            'total_parents': 0,
        })

@login_required
def teacher_dashboard(request):
    """Teacher dashboard with class and assignment management"""
    if not is_teacher(request.user):
        raise PermissionDenied("Access denied: Teacher privileges required")
    
    try:
        teacher = request.user.teacher
        
        # Get classes taught by this teacher
        current_classes = ClassAssignment.objects.filter(
            teacher=teacher
        ).select_related('subject')
        
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
        
        # FIXED: Use the correct related name 'student_assignments'
        assignments_to_grade = Assignment.objects.filter(
            class_assignment__teacher=teacher,
            student_assignments__status__in=['SUBMITTED', 'LATE']
        ).distinct().count()
        
        # Get recent student submissions
        recent_submissions = StudentAssignment.objects.filter(
            assignment__class_assignment__teacher=teacher,
            status__in=['SUBMITTED', 'LATE']
        ).select_related('student', 'assignment').order_by('-submitted_date')[:5]
        
        # Additional statistics for better dashboard
        total_assignments = Assignment.objects.filter(
            class_assignment__teacher=teacher
        ).count()
        
        # Get pending grading count from StudentAssignment directly
        pending_grading_count = StudentAssignment.objects.filter(
            assignment__class_assignment__teacher=teacher,
            status__in=['SUBMITTED', 'LATE']
        ).count()
        
        # Get upcoming deadlines (next 7 days)
        next_week = timezone.now() + timezone.timedelta(days=7)
        upcoming_deadlines = Assignment.objects.filter(
            class_assignment__teacher=teacher,
            due_date__range=[timezone.now(), next_week]
        ).select_related('subject', 'class_assignment').order_by('due_date')[:5]
        
        # Grade statistics for teacher's classes
        grade_stats = Grade.objects.filter(
            class_assignment__teacher=teacher
        ).aggregate(
            total_grades=Count('id'),
            average_score=Avg('total_score'),
            recent_grades=Count('id', filter=Q(
                last_updated__gte=timezone.now() - timedelta(days=7)
            ))
        )
        
        # Get current term
        current_term = AcademicTerm.objects.filter(is_active=True).first()
        
        # Today's attendance for teacher's classes
        today_attendance = StudentAttendance.objects.filter(
            student__class_level__in=class_levels,
            date=timezone.now().date()
        ).aggregate(
            present=Count('id', filter=Q(status='present')),
            absent=Count('id', filter=Q(status='absent')),
            late=Count('id', filter=Q(status='late')),
            total=Count('id')
        )
        
        context = {
            'teacher': teacher,
            'current_classes': current_classes,
            'recent_assignments': recent_assignments,
            'student_count': student_count,
            'assignments_to_grade': assignments_to_grade,
            'pending_grading_count': pending_grading_count,
            'recent_submissions': recent_submissions,
            'total_assignments': total_assignments,
            'upcoming_deadlines': upcoming_deadlines,
            'grade_stats': grade_stats,
            'today_attendance': today_attendance,
            'current_term': current_term,
            'now': timezone.now(),
            'current_academic_year': get_current_academic_year(),
        }
        
        return render(request, 'core/hr/teacher_dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Error loading teacher dashboard for {request.user}: {str(e)}", exc_info=True)
        messages.error(request, "Error loading dashboard data. Please try again.")
        return render(request, 'core/hr/teacher_dashboard.html', {})

@login_required
def student_dashboard(request):
    """Student dashboard with assignments, grades, and fee information"""
    if not is_student(request.user):
        raise PermissionDenied("Access denied: Student privileges required")
    
    try:
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
                'status': student_assignment.status,
                'is_overdue': assignment.due_date < timezone.now() if assignment.due_date else False,
                'time_remaining': student_assignment.get_time_remaining() if hasattr(student_assignment, 'get_time_remaining') else None,
            })
        
        # Assignment statistics
        pending_assignments = student_assignments.filter(
            status__in=['PENDING', 'LATE']
        ).count()

        # Get assignments due soon (within 3 days)
        due_soon = student_assignments.filter(
            assignment__due_date__lte=timezone.now() + timezone.timedelta(days=3),
            status__in=['PENDING', 'LATE']
        ).count()
        
        # Calculate average grade with error handling
        grades = Grade.objects.filter(student=student)
        average_grade = grades.aggregate(Avg('total_score'))['total_score__avg']
        
        # Get recent grades (last 5)
        recent_grades = Grade.objects.filter(
            student=student
        ).select_related('subject').order_by('-last_updated')[:5]
        
        # Grade statistics by subject
        subject_grades = Grade.objects.filter(
            student=student
        ).values('subject__name').annotate(
            avg_score=Avg('total_score'),
            latest_grade=Max('last_updated')
        ).order_by('-avg_score')[:5]
        
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
        
        # Get recent bills
        recent_bills = Bill.objects.filter(
            student=student
        ).order_by('-issue_date')[:3]
        
        # Get attendance summary for current month
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
        
        # Calculate attendance percentage
        if attendance_summary['total'] > 0:
            attendance_percentage = (attendance_summary['present'] / attendance_summary['total']) * 100
        else:
            attendance_percentage = 0
        
        # Get current term
        current_term = AcademicTerm.objects.filter(is_active=True).first()
        
        context = {
            'student': student,
            'assignments_with_status': assignments_with_status,
            'student_assignments': student_assignments,
            'pending_assignments': pending_assignments,
            'due_soon': due_soon,
            'average_grade': round(average_grade, 1) if average_grade else 'N/A',
            'recent_grades': recent_grades,
            'subject_grades': subject_grades,
            'fee_status': fee_status,
            'total_balance': total_balance,
            'overdue_fees': overdue_fees,
            'recent_bills': recent_bills,
            'attendance_summary': attendance_summary,
            'attendance_percentage': round(attendance_percentage, 1),
            'current_term': current_term,
            'current_academic_year': get_current_academic_year(),
        }
        
        return render(request, 'core/students/student_dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Error loading student dashboard for {request.user}: {str(e)}", exc_info=True)
        messages.error(request, "Error loading dashboard data. Please try again.")
        return render(request, 'core/students/student_dashboard.html', {})

@login_required
def parent_dashboard(request):
    """Parent dashboard with children's academic and fee information"""
    if not is_parent(request.user):
        raise PermissionDenied("Access denied: Parent privileges required")
    
    try:
        parent = request.user.parentguardian
        
        # Get all children of this parent
        children = parent.students.all().select_related('user')
        
        if not children.exists():
            messages.info(request, "No children are currently associated with your account.")
        
        # Prepare data for each child
        children_data = []
        total_outstanding_fees = 0
        
        for child in children:
            # Get recent grades
            recent_grades = Grade.objects.filter(
                student=child
            ).select_related('subject').order_by('-last_updated')[:3]
            
            # Calculate average grade
            avg_grade = Grade.objects.filter(
                student=child
            ).aggregate(avg_score=Avg('total_score'))['avg_score']
            
            # Get attendance summary for current month
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
            
            # Calculate attendance percentage
            if attendance_summary['total'] > 0:
                attendance_percentage = (attendance_summary['present'] / attendance_summary['total']) * 100
            else:
                attendance_percentage = 0
            
            # Get fee status
            fee_summary = Fee.objects.filter(
                student=child
            ).aggregate(
                total_due=Sum('balance'),
                total_payable=Sum('amount_payable'),
                total_paid=Sum('amount_paid'),
                overdue_count=Count('id', filter=Q(
                    due_date__lt=timezone.now().date(),
                    payment_status__in=['unpaid', 'partial']
                ))
            )
            
            total_outstanding_fees += fee_summary['total_due'] or 0
            
            # Get recent assignments
            recent_assignments = StudentAssignment.objects.filter(
                student=child
            ).select_related('assignment').order_by('-assignment__due_date')[:3]
            
            children_data.append({
                'child': child,
                'recent_grades': recent_grades,
                'average_grade': round(avg_grade, 1) if avg_grade else 'N/A',
                'attendance': attendance_summary,
                'attendance_percentage': round(attendance_percentage, 1),
                'fee_summary': fee_summary,
                'recent_assignments': recent_assignments,
            })
        
        # Get recent announcements
        child_classes = children.values_list('class_level', flat=True).distinct()
        
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
        
        # Get upcoming events (next 30 days)
        next_month = timezone.now() + timezone.timedelta(days=30)
        upcoming_events = ParentEvent.objects.filter(
            Q(is_whole_school=True) | Q(class_level__in=child_classes),
            start_date__gte=timezone.now(),
            start_date__lte=next_month
        ).order_by('start_date')[:5]
        
        # Get recent bills across all children
        recent_bills = Bill.objects.filter(
            student__in=children
        ).select_related('student').order_by('-issue_date')[:3]
        
        context = {
            'parent': parent,
            'children_data': children_data,
            'total_children': children.count(),
            'total_outstanding_fees': total_outstanding_fees,
            'recent_announcements': recent_announcements,
            'unread_messages': unread_messages,
            'upcoming_events': upcoming_events,
            'recent_bills': recent_bills,
            'current_academic_year': get_current_academic_year(),
        }
        
        return render(request, 'core/parents/parent_dashboard.html', context)
        
    except Exception as e:
        logger.error(f"Error loading parent dashboard for {request.user}: {str(e)}", exc_info=True)
        messages.error(request, "Error loading dashboard data. Please try again.")
        return render(request, 'core/parents/parent_dashboard.html', {})

# API endpoints for dashboard widgets
@login_required
def dashboard_stats_api(request):
    """API endpoint for dashboard statistics"""
    try:
        if is_admin(request.user):
            stats = {
                'total_students': Student.objects.filter(is_active=True).count(),
                'total_teachers': Teacher.objects.filter(is_active=True).count(),
                'overdue_fees': Fee.objects.filter(
                    payment_status__in=['unpaid', 'partial'],
                    due_date__lt=timezone.now().date()
                ).count(),
                'pending_assignments': StudentAssignment.objects.filter(
                    status__in=['SUBMITTED', 'LATE']
                ).count(),
            }
        elif is_teacher(request.user):
            teacher = request.user.teacher
            stats = {
                'student_count': Student.objects.filter(
                    class_level__in=ClassAssignment.objects.filter(
                        teacher=teacher
                    ).values_list('class_level', flat=True),
                    is_active=True
                ).count(),
                'assignments_to_grade': Assignment.objects.filter(
                    class_assignment__teacher=teacher,
                    student_assignments__status__in=['SUBMITTED', 'LATE']
                ).distinct().count(),
                'total_assignments': Assignment.objects.filter(
                    class_assignment__teacher=teacher
                ).count(),
            }
        elif is_student(request.user):
            student = request.user.student
            stats = {
                'pending_assignments': StudentAssignment.objects.filter(
                    student=student,
                    status__in=['PENDING', 'LATE']
                ).count(),
                'average_grade': Grade.objects.filter(
                    student=student
                ).aggregate(avg=Avg('total_score'))['avg'] or 0,
                'fee_balance': Fee.objects.filter(
                    student=student
                ).aggregate(total=Sum('balance'))['total'] or 0,
            }
        else:
            stats = {}
        
        return JsonResponse({'success': True, 'stats': stats})
        
    except Exception as e:
        logger.error(f"Error in dashboard stats API: {str(e)}")
        return JsonResponse({'success': False, 'error': str(e)})

# Error handlers
def handler403(request, exception):
    """Custom 403 error handler"""
    logger.warning(f"403 error for {request.user}: {exception}")
    return render(request, 'core/errors/403.html', status=403)

def handler404(request, exception):
    """Custom 404 error handler"""
    logger.warning(f"404 error for {request.user}: {exception}")
    return render(request, 'core/errors/404.html', status=404)

def handler500(request):
    """Custom 500 error handler"""
    logger.error("500 error occurred", exc_info=True)
    return render(request, 'core/errors/500.html', status=500)

# Maintenance mode view
def maintenance_mode(request):
    """Maintenance mode page for system downtime"""
    return render(request, 'core/errors/maintenance.html', status=503)

# Health check endpoint
def health_check(request):
    """Simple health check endpoint for monitoring"""
    try:
        # Basic database check
        Student.objects.exists()
        return JsonResponse({
            'status': 'healthy',
            'timestamp': timezone.now().isoformat(),
            'database': 'connected'
        })
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        return JsonResponse({
            'status': 'unhealthy',
            'timestamp': timezone.now().isoformat(),
            'error': str(e)
        }, status=500)


class ParentBaseMixin(LoginRequiredMixin, UserPassesTestMixin):
    """Base mixin for all parent portal views"""
    
    def test_func(self):
        """Override to check if user is a parent"""
        return is_parent(self.request.user)
    
    def get_parent(self):
        """Get the parent object for the current user"""
        return self.request.user.parentguardian
    
    def get_children(self):
        """Get all children for the current parent"""
        return self.get_parent().students.all()
    
    @classmethod
    def as_view(cls, **initkwargs):
        """Apply logging decorator to the view"""
        view = super().as_view(**initkwargs)
        return log_view_exception(cls.__name__)(view)

class ParentChildAccessMixin(ParentBaseMixin):
    """Mixin for views that access specific child data"""
    
    def test_func(self):
        """Check parent permission and child ownership"""
        if not super().test_func():
            return False
        
        # Check if accessing specific child
        child_id = self.kwargs.get('pk') or self.kwargs.get('student_id')
        if child_id:
            parent = self.request.user.parentguardian
            return parent.students.filter(pk=child_id).exists()
        
        return True
    
    def get_child(self):
        """Get the child object with permission check"""
        child_id = self.kwargs.get('pk') or self.kwargs.get('student_id')
        if child_id:
            parent = self.request.user.parentguardian
            from django.shortcuts import get_object_or_404
            return get_object_or_404(parent.students, pk=child_id)
        return None

# Base view classes
class ParentListView(ParentBaseMixin, ListView):
    """Base list view for parent portal"""
    paginate_by = 20
    template_name_suffix = '_list'
    
    def get_queryset(self):
        """Default to filtering by parent's children"""
        queryset = super().get_queryset()
        # Filter by parent's children if model has student field
        if hasattr(queryset.model, 'student'):
            return queryset.filter(student__in=self.get_children())
        return queryset

class ParentDetailView(ParentChildAccessMixin, DetailView):
    """Base detail view for parent portal"""
    template_name_suffix = '_detail'

class ParentCreateView(ParentBaseMixin, CreateView):
    """Base create view for parent portal"""
    template_name_suffix = '_form'

class ParentUpdateView(ParentChildAccessMixin, UpdateView):
    """Base update view for parent portal"""
    template_name_suffix = '_form'

class ParentDeleteView(ParentChildAccessMixin, DeleteView):
    """Base delete view for parent portal"""
    template_name_suffix = '_confirm_delete'