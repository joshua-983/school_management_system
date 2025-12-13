# core/api_views.py
from django.http import JsonResponse
from django.views import View
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_POST
from django.utils.decorators import method_decorator
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.decorators import login_required
from django.utils import timezone
from django.db.models import Q, Avg, Max, Min, Count, Sum
from django.shortcuts import get_object_or_404
import json

from .models import (
    Student, AcademicTerm, ParentGuardian, Grade, 
    StudentAttendance, Fee, StudentAssignment, Assignment
)

# Permission functions
def is_admin(user):
    """Check if user is an admin/superuser"""
    return user.is_authenticated and (user.is_superuser or user.is_staff)

def is_teacher(user):
    """Check if user is a teacher"""
    return user.is_authenticated and hasattr(user, 'teacher') and user.teacher is not None

def is_parent(user):
    """Check if user is a parent"""
    return user.is_authenticated and hasattr(user, 'parentguardian') and user.parentguardian is not None

def is_student(user):
    """Check if user is a student"""
    return user.is_authenticated and hasattr(user, 'student') and user.student is not None

# ==============================
# STUDENT API ENDPOINTS
# ==============================

class StudentAssignmentFilterAPI(LoginRequiredMixin, View):
    """API endpoint for student assignment filtering"""
    
    def get(self, request):
        try:
            if not is_student(request.user):
                return JsonResponse({
                    'error': 'Only students can access this endpoint',
                    'redirect_url': '/student/assignments/'
                }, status=403)
            
            student = request.user.student
            assignments = StudentAssignment.objects.filter(
                student=student
            ).select_related(
                'assignment',
                'assignment__subject',
                'assignment__class_assignment'
            )
            
            # Apply filters
            has_document = request.GET.get('has_document')
            if has_document == 'yes':
                assignments = assignments.filter(assignment__attachment__isnull=False)
            elif has_document == 'no':
                assignments = assignments.filter(assignment__attachment__isnull=True)
            
            status_filter = request.GET.get('status')
            if status_filter:
                assignments = assignments.filter(status=status_filter)
            
            subject_filter = request.GET.get('subject')
            if subject_filter:
                assignments = assignments.filter(assignment__subject_id=subject_filter)
            
            search_query = request.GET.get('q')
            if search_query:
                assignments = assignments.filter(
                    Q(assignment__title__icontains=search_query) |
                    Q(assignment__description__icontains=search_query)
                )
            
            # Sort by due date
            assignments = assignments.order_by('assignment__due_date')
            
            assignment_data = []
            for sa in assignments:
                assignment_data.append({
                    'id': sa.id,
                    'assignment_id': sa.assignment.id,
                    'title': sa.assignment.title,
                    'description': sa.assignment.description,
                    'status': sa.status,
                    'status_display': sa.get_status_display(),
                    'score': float(sa.score) if sa.score else None,
                    'max_score': sa.assignment.max_score,
                    'has_document': sa.assignment.attachment is not None,
                    'due_date': sa.assignment.due_date.isoformat() if sa.assignment.due_date else None,
                    'submitted_date': sa.submitted_date.isoformat() if sa.submitted_date else None,
                    'graded_date': sa.graded_date.isoformat() if sa.graded_date else None,
                    'subject': sa.assignment.subject.name if sa.assignment.subject else None,
                    'subject_id': sa.assignment.subject.id if sa.assignment.subject else None,
                    'feedback': sa.feedback,
                    'is_overdue': sa.assignment.due_date < timezone.now() if sa.assignment.due_date else False,
                    'can_submit': sa.status in ['PENDING', 'LATE'] and (
                        sa.assignment.due_date is None or 
                        sa.assignment.due_date > timezone.now()
                    ),
                    'document_url': sa.get_assignment_document_url() if sa.assignment.attachment else None,
                })
            
            # Statistics
            stats = {
                'total': len(assignment_data),
                'with_documents': len([a for a in assignment_data if a['has_document']]),
                'pending': len([a for a in assignment_data if a['status'] in ['PENDING', 'LATE']]),
                'submitted': len([a for a in assignment_data if a['status'] in ['SUBMITTED', 'LATE']]),
                'graded': len([a for a in assignment_data if a['status'] == 'GRADED']),
                'overdue': len([a for a in assignment_data if a['is_overdue']]),
            }
            
            return JsonResponse({
                'assignments': assignment_data,
                'stats': stats,
                'student': {
                    'id': student.id,
                    'name': student.get_full_name(),
                    'student_id': student.student_id,
                    'class_level': student.get_class_level_display(),
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class StudentProfileAPI(LoginRequiredMixin, View):
    """API endpoint for student profile data"""
    
    def get(self, request):
        try:
            if not is_student(request.user):
                return JsonResponse({
                    'error': 'Only students can access this endpoint',
                    'redirect_url': '/student/profile/'
                }, status=403)
            
            student = request.user.student
            
            # Get comprehensive profile data
            profile_data = {
                'student_id': student.student_id,
                'full_name': student.get_full_name(),
                'first_name': student.first_name,
                'last_name': student.last_name,
                'middle_name': student.middle_name,
                'class_level': student.class_level,
                'class_level_display': student.get_class_level_display(),
                'enrollment_date': student.enrollment_date.isoformat() if student.enrollment_date else None,
                'date_of_birth': student.date_of_birth.isoformat() if student.date_of_birth else None,
                'age': student.get_age(),
                'gender': student.gender,
                'gender_display': student.get_gender_display(),
                'email': student.user.email if student.user else None,
                'phone_number': student.phone_number,
                'address': student.address,
                'is_active': student.is_active,
                'profile_picture': student.profile_picture.url if student.profile_picture else None,
            }
            
            # Get parent information
            parents = student.parents.all()
            profile_data['parents'] = [
                {
                    'id': parent.id,
                    'full_name': parent.get_user_full_name(),
                    'relationship': parent.get_relationship_display(),
                    'email': parent.email,
                    'phone_number': parent.phone_number,
                    'account_status': parent.get_account_status_display(),
                }
                for parent in parents
            ]
            
            return JsonResponse(profile_data)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class StudentGradesAPI(LoginRequiredMixin, View):
    """API endpoint for student grades"""
    
    def get(self, request):
        try:
            if not is_student(request.user):
                return JsonResponse({
                    'error': 'Only students can access this endpoint',
                    'redirect_url': '/student/grades/'
                }, status=403)
            
            student = request.user.student
            grades = Grade.objects.filter(student=student).select_related('subject')
            
            # Apply filters
            academic_year = request.GET.get('academic_year')
            term = request.GET.get('term')
            subject_id = request.GET.get('subject_id')
            
            if academic_year:
                grades = grades.filter(academic_year=academic_year)
            if term:
                grades = grades.filter(term=term)
            if subject_id:
                grades = grades.filter(subject_id=subject_id)
            
            grades = grades.order_by('-academic_year', '-term', 'subject__name')
            
            grade_data = []
            for grade in grades:
                grade_data.append({
                    'id': grade.id,
                    'subject': grade.subject.name,
                    'subject_code': grade.subject.code,
                    'academic_year': grade.academic_year,
                    'term': grade.term,
                    'total_score': float(grade.total_score) if grade.total_score else None,
                    'display_grade': grade.get_display_grade(),
                    'performance_level': grade.get_performance_level_display(),
                    'grade_point': float(grade.grade_point) if grade.grade_point else None,
                    'remarks': grade.remarks,
                    'last_updated': grade.last_updated.isoformat() if grade.last_updated else None,
                })
            
            # Calculate statistics
            if grades.exists():
                stats = grades.aggregate(
                    average_score=Avg('total_score'),
                    highest_score=Max('total_score'),
                    lowest_score=Min('total_score'),
                    total_grades=Count('id'),
                    distinct_subjects=Count('subject', distinct=True)
                )
                
                # Group by academic year and term
                term_summary = {}
                for grade in grades:
                    key = f"{grade.academic_year} - Term {grade.term}"
                    if key not in term_summary:
                        term_summary[key] = {
                            'grades': [],
                            'average': 0,
                            'count': 0
                        }
                    term_summary[key]['grades'].append(float(grade.total_score) if grade.total_score else 0)
                
                # Calculate averages for each term
                for term_key, term_data in term_summary.items():
                    if term_data['grades']:
                        term_data['average'] = sum(term_data['grades']) / len(term_data['grades'])
                        term_data['count'] = len(term_data['grades'])
            else:
                stats = {}
                term_summary = {}
            
            return JsonResponse({
                'grades': grade_data,
                'stats': stats,
                'term_summary': term_summary,
                'student': {
                    'id': student.id,
                    'name': student.get_full_name(),
                    'student_id': student.student_id,
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class StudentAttendanceAPI(LoginRequiredMixin, View):
    """API endpoint for student attendance"""
    
    def get(self, request):
        try:
            if not is_student(request.user):
                return JsonResponse({
                    'error': 'Only students can access this endpoint',
                    'redirect_url': '/student/attendance/'
                }, status=403)
            
            student = request.user.student
            attendance = StudentAttendance.objects.filter(student=student)
            
            # Apply filters
            date_from = request.GET.get('date_from')
            date_to = request.GET.get('date_to')
            status_filter = request.GET.get('status')
            term_id = request.GET.get('term_id')
            
            if date_from:
                attendance = attendance.filter(date__gte=date_from)
            if date_to:
                attendance = attendance.filter(date__lte=date_to)
            if status_filter:
                attendance = attendance.filter(status=status_filter)
            if term_id:
                attendance = attendance.filter(term_id=term_id)
            
            attendance = attendance.order_by('-date')
            
            attendance_data = []
            for record in attendance:
                attendance_data.append({
                    'id': record.id,
                    'date': record.date.isoformat(),
                    'status': record.status,
                    'status_display': record.get_status_display(),
                    'period': record.period.name if record.period else None,
                    'term': str(record.term) if record.term else None,
                    'notes': record.notes,
                    'marked_by': record.marked_by.get_full_name() if record.marked_by else None,
                    'time_in': record.time_in.isoformat() if record.time_in else None,
                    'time_out': record.time_out.isoformat() if record.time_out else None,
                })
            
            # Calculate statistics
            stats = attendance.aggregate(
                total=Count('id'),
                present=Count('id', filter=Q(status='present')),
                absent=Count('id', filter=Q(status='absent')),
                late=Count('id', filter=Q(status='late')),
                excused=Count('id', filter=Q(status='excused')),
            )
            
            # Calculate percentages
            if stats['total'] > 0:
                stats['present_percentage'] = (stats['present'] / stats['total']) * 100
                stats['absent_percentage'] = (stats['absent'] / stats['total']) * 100
                stats['late_percentage'] = (stats['late'] / stats['total']) * 100
            else:
                stats['present_percentage'] = 0
                stats['absent_percentage'] = 0
                stats['late_percentage'] = 0
            
            # Monthly summary (last 6 months)
            six_months_ago = timezone.now() - timezone.timedelta(days=180)
            monthly_summary = []
            
            for i in range(6):
                month_start = timezone.now() - timezone.timedelta(days=30 * (5 - i))
                month_end = month_start + timezone.timedelta(days=30)
                
                month_attendance = attendance.filter(
                    date__range=[month_start, month_end]
                )
                
                month_stats = month_attendance.aggregate(
                    present=Count('id', filter=Q(status='present')),
                    total=Count('id')
                )
                
                monthly_summary.append({
                    'month': month_start.strftime('%b %Y'),
                    'present': month_stats['present'] or 0,
                    'total': month_stats['total'] or 0,
                    'percentage': round((month_stats['present'] / month_stats['total'] * 100), 1) 
                                if month_stats['total'] and month_stats['total'] > 0 else 0
                })
            
            return JsonResponse({
                'attendance': attendance_data,
                'stats': stats,
                'monthly_summary': monthly_summary,
                'student': {
                    'id': student.id,
                    'name': student.get_full_name(),
                    'student_id': student.student_id,
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class StudentFeeAPI(LoginRequiredMixin, View):
    """API endpoint for student fees"""
    
    def get(self, request):
        try:
            if not is_student(request.user):
                return JsonResponse({
                    'error': 'Only students can access this endpoint',
                    'redirect_url': '/student/fees/'
                }, status=403)
            
            student = request.user.student
            fees = Fee.objects.filter(student=student).select_related('category')
            
            # Apply filters
            academic_year = request.GET.get('academic_year')
            term = request.GET.get('term')
            status_filter = request.GET.get('status')
            
            if academic_year:
                fees = fees.filter(academic_year=academic_year)
            if term:
                fees = fees.filter(term=term)
            if status_filter:
                fees = fees.filter(payment_status=status_filter)
            
            fees = fees.order_by('-academic_year', '-term', 'due_date')
            
            fee_data = []
            for fee in fees:
                fee_data.append({
                    'id': fee.id,
                    'category': fee.category.name if fee.category else None,
                    'description': fee.description,
                    'academic_year': fee.academic_year,
                    'term': fee.term,
                    'amount_payable': float(fee.amount_payable) if fee.amount_payable else 0,
                    'amount_paid': float(fee.amount_paid) if fee.amount_paid else 0,
                    'balance': float(fee.balance) if fee.balance else 0,
                    'payment_status': fee.payment_status,
                    'payment_status_display': fee.get_payment_status_display(),
                    'due_date': fee.due_date.isoformat() if fee.due_date else None,
                    'is_overdue': fee.due_date < timezone.now().date() if fee.due_date else False,
                    'last_payment_date': fee.last_payment_date.isoformat() if fee.last_payment_date else None,
                    'discount_amount': float(fee.discount_amount) if fee.discount_amount else 0,
                    'discount_reason': fee.discount_reason,
                })
            
            # Calculate statistics
            stats = fees.aggregate(
                total_payable=Sum('amount_payable'),
                total_paid=Sum('amount_paid'),
                total_balance=Sum('balance'),
                total_fees=Count('id'),
                overdue_count=Count('id', filter=Q(
                    due_date__lt=timezone.now().date(),
                    payment_status__in=['UNPAID', 'PARTIAL']
                )),
                paid_count=Count('id', filter=Q(payment_status='PAID')),
                partial_count=Count('id', filter=Q(payment_status='PARTIAL')),
                unpaid_count=Count('id', filter=Q(payment_status='UNPAID')),
            )
            
            # Summary by term
            term_summary = []
            for term_data in fees.values('academic_year', 'term').annotate(
                payable=Sum('amount_payable'),
                paid=Sum('amount_paid'),
                balance=Sum('balance'),
                count=Count('id')
            ).order_by('-academic_year', '-term'):
                term_summary.append({
                    'academic_year': term_data['academic_year'],
                    'term': term_data['term'],
                    'payable': float(term_data['payable']) if term_data['payable'] else 0,
                    'paid': float(term_data['paid']) if term_data['paid'] else 0,
                    'balance': float(term_data['balance']) if term_data['balance'] else 0,
                    'count': term_data['count'],
                })
            
            return JsonResponse({
                'fees': fee_data,
                'stats': stats,
                'term_summary': term_summary,
                'student': {
                    'id': student.id,
                    'name': student.get_full_name(),
                    'student_id': student.student_id,
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

# ==============================
# EXISTING CODE - PRESERVED
# ==============================

class StudentListAPIView(LoginRequiredMixin, View):
    def get(self, request):
        try:
            if is_student(request.user):
                # Return only the student's own data
                student = request.user.student
                student_data = [{
                    'id': student.id,
                    'student_id': student.student_id,
                    'name': f"{student.get_full_name()} ({student.student_id}) - {student.get_class_level_display()}",
                    'full_name': student.get_full_name(),
                    'class_level': student.class_level,
                    'class_level_display': student.get_class_level_display(),
                    'email': student.user.email if student.user else None,
                    'phone': student.phone_number,
                    'is_active': student.is_active,
                    'gender': student.gender,
                    'enrollment_date': student.enrollment_date.isoformat() if student.enrollment_date else None,
                }]
                
                return JsonResponse({
                    'students': student_data,
                    'count': 1,
                    'is_student': True
                })
            
            elif is_admin(request.user) or is_teacher(request.user):
                # Admin/Teacher: Full student list with filters
                students = Student.objects.filter(is_active=True)
                
                # Apply filters
                class_level = request.GET.get('class_level')
                status_filter = request.GET.get('status')
                search = request.GET.get('search')
                
                if class_level:
                    students = students.filter(class_level=class_level)
                
                if status_filter:
                    if status_filter == 'active':
                        students = students.filter(is_active=True)
                    elif status_filter == 'inactive':
                        students = students.filter(is_active=False)
                
                if search:
                    students = students.filter(
                        Q(student_id__icontains=search) |
                        Q(first_name__icontains=search) |
                        Q(last_name__icontains=search)
                    )
                
                student_data = []
                for student in students:
                    student_data.append({
                        'id': student.id,
                        'name': f"{student.get_full_name()} ({student.student_id}) - {student.get_class_level_display()}",
                        'full_name': student.get_full_name(),
                        'student_id': student.student_id,
                        'class_level': student.class_level,
                        'class_level_display': student.get_class_level_display(),
                        'email': student.user.email if student.user else None,
                        'phone': student.phone_number,
                        'is_active': student.is_active,
                        'gender': student.gender,
                        'gender_display': student.get_gender_display(),
                        'enrollment_date': student.enrollment_date.isoformat() if student.enrollment_date else None,
                    })
                
                return JsonResponse({
                    'students': student_data,
                    'count': len(student_data),
                    'is_admin': is_admin(request.user),
                    'is_teacher': is_teacher(request.user)
                })
            
            else:
                return JsonResponse({
                    'error': 'Unauthorized access',
                    'redirect_url': '/'
                }, status=403)
                
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

class AcademicTermAPIView(LoginRequiredMixin, View):
    def get(self, request):
        try:
            # Generate academic years (current year and 2 years back)
            current_year = timezone.now().year
            academic_years = []
            
            for i in range(3):
                year = current_year - i
                academic_years.append(f"{year}/{year+1}")
            
            return JsonResponse({'academic_years': academic_years})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=400)

# NEW API ENDPOINTS FOR PARENT AUTHENTICATION SYSTEM

@method_decorator(csrf_exempt, name='dispatch')
class ActiveStudentsAPIView(View):
    """API endpoint to get active students for parent registration"""
    
    def get(self, request):
        try:
            search = request.GET.get('search', '')
            
            # Get active students
            students = Student.objects.filter(is_active=True).select_related('user')
            
            # Apply search filter
            if search:
                students = students.filter(
                    Q(first_name__icontains=search) |
                    Q(last_name__icontains=search) |
                    Q(middle_name__icontains=search) |
                    Q(student_id__icontains=search)
                )
            
            student_data = []
            for student in students:
                student_data.append({
                    'id': student.student_id,  # Using student_id as identifier for registration
                    'full_name': student.get_full_name(),
                    'first_name': student.first_name,
                    'last_name': student.last_name,
                    'student_id': student.student_id,
                    'class_level': student.get_class_level_display(),
                    'gender': student.get_gender_display(),
                    'class_code': student.class_level,  # For filtering
                })
            
            return JsonResponse(student_data, safe=False)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class ParentChildrenAPIView(LoginRequiredMixin, View):
    """API endpoint to get parent's children data"""
    
    def get(self, request):
        try:
            if not is_parent(request.user):
                return JsonResponse({'error': 'Parent account required'}, status=403)
            
            parent = request.user.parentguardian
            children = parent.students.all().select_related('user')
            
            children_data = []
            for child in children:
                # Get recent academic performance
                recent_grades = Grade.objects.filter(
                    student=child
                ).select_related('subject').order_by('-last_updated')[:3]
                
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
                
                # Get fee summary
                fee_summary = Fee.objects.filter(
                    student=child,
                    payment_status__in=['unpaid', 'partial']
                ).aggregate(
                    total_due=Sum('balance'),
                    unpaid_count=Count('id')
                )
                
                children_data.append({
                    'id': child.id,
                    'student_id': child.student_id,
                    'full_name': child.get_full_name(),
                    'first_name': child.first_name,
                    'last_name': child.last_name,
                    'class_level': child.get_class_level_display(),
                    'class_code': child.class_level,
                    'gender': child.get_gender_display(),
                    'admission_date': child.admission_date.isoformat() if child.admission_date else None,
                    'recent_grades': [
                        {
                            'subject': grade.subject.name,
                            'score': float(grade.total_score) if grade.total_score else 0,
                            'grade': grade.get_display_grade(),
                            'date': grade.last_updated.isoformat()
                        }
                        for grade in recent_grades
                    ],
                    'attendance': {
                        'present': attendance_summary['present'] or 0,
                        'absent': attendance_summary['absent'] or 0,
                        'late': attendance_summary['late'] or 0,
                        'total': attendance_summary['total'] or 0,
                        'percentage': round(
                            (attendance_summary['present'] or 0) / (attendance_summary['total'] or 1) * 100, 
                            1
                        ) if attendance_summary['total'] else 0
                    },
                    'fees': {
                        'total_due': float(fee_summary['total_due'] or 0),
                        'unpaid_count': fee_summary['unpaid_count'] or 0
                    }
                })
            
            return JsonResponse({
                'children': children_data,
                'parent': {
                    'full_name': parent.get_user_full_name(),
                    'relationship': parent.get_relationship_display(),
                    'account_status': parent.get_account_status_display()
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class ParentDashboardAPIView(LoginRequiredMixin, View):
    """API endpoint for parent dashboard data"""
    
    def get(self, request):
        try:
            if not is_parent(request.user):
                return JsonResponse({'error': 'Parent account required'}, status=403)
            
            parent = request.user.parentguardian
            children = parent.students.all()
            
            # Dashboard statistics
            dashboard_stats = {
                'total_children': children.count(),
                'children_with_low_attendance': 0,
                'children_with_pending_fees': 0,
                'unread_messages': 0,  # You can implement message counting
                'upcoming_events': 0,  # You can implement event counting
            }
            
            # Children overview with key metrics
            children_overview = []
            for child in children:
                # Current term grades average
                current_term = AcademicTerm.objects.filter(is_active=True).first()
                if current_term:
                    term_grades = Grade.objects.filter(
                        student=child,
                        academic_year=current_term.academic_year,
                        term=current_term.term
                    )
                    average_grade = term_grades.aggregate(avg=Avg('total_score'))['avg'] or 0
                else:
                    average_grade = 0
                
                # Recent attendance (last 30 days)
                thirty_days_ago = timezone.now().date() - timezone.timedelta(days=30)
                recent_attendance = StudentAttendance.objects.filter(
                    student=child,
                    date__gte=thirty_days_ago
                ).aggregate(
                    present=Count('id', filter=Q(status='present')),
                    total=Count('id')
                )
                
                attendance_rate = round(
                    (recent_attendance['present'] or 0) / (recent_attendance['total'] or 1) * 100, 
                    1
                ) if recent_attendance['total'] else 0
                
                # Outstanding fees
                outstanding_fees = Fee.objects.filter(
                    student=child,
                    payment_status__in=['unpaid', 'partial']
                ).aggregate(total=Sum('balance'))['total'] or 0
                
                children_overview.append({
                    'id': child.id,
                    'name': child.get_full_name(),
                    'class_level': child.get_class_level_display(),
                    'average_grade': round(float(average_grade), 1),
                    'attendance_rate': attendance_rate,
                    'outstanding_fees': float(outstanding_fees),
                    'has_issues': attendance_rate < 80 or outstanding_fees > 0
                })
                
                # Update dashboard stats
                if attendance_rate < 80:
                    dashboard_stats['children_with_low_attendance'] += 1
                if outstanding_fees > 0:
                    dashboard_stats['children_with_pending_fees'] += 1
            
            return JsonResponse({
                'dashboard_stats': dashboard_stats,
                'children_overview': children_overview,
                'parent': {
                    'full_name': parent.get_user_full_name(),
                    'login_count': parent.login_count,
                    'last_login': parent.last_login_date.isoformat() if parent.last_login_date else None,
                    'account_created': parent.account_created.isoformat() if parent.account_created else None
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class ParentProfileAPIView(LoginRequiredMixin, View):
    """API endpoint for parent profile management"""
    
    def get(self, request):
        try:
            if not is_parent(request.user):
                return JsonResponse({'error': 'Parent account required'}, status=403)
            
            parent = request.user.parentguardian
            
            profile_data = {
                'parent': {
                    'first_name': parent.user.first_name,
                    'last_name': parent.user.last_name,
                    'email': parent.user.email,
                    'phone_number': parent.phone_number,
                    'occupation': parent.occupation,
                    'address': parent.address,
                    'relationship': parent.relationship,
                    'is_emergency_contact': parent.is_emergency_contact,
                    'emergency_contact_priority': parent.emergency_contact_priority,
                    'account_status': parent.get_account_status_display(),
                    'login_count': parent.login_count,
                    'last_login': parent.last_login_date.isoformat() if parent.last_login_date else None,
                },
                'children': [
                    {
                        'id': child.id,
                        'name': child.get_full_name(),
                        'student_id': child.student_id,
                        'class_level': child.get_class_level_display(),
                        'gender': child.get_gender_display(),
                    }
                    for child in parent.students.all()
                ]
            }
            
            return JsonResponse(profile_data)
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def post(self, request):
        """Update parent profile"""
        try:
            if not is_parent(request.user):
                return JsonResponse({'error': 'Parent account required'}, status=403)
            
            parent = request.user.parentguardian
            data = json.loads(request.body)
            
            # Update user information
            if 'first_name' in data:
                parent.user.first_name = data['first_name']
            if 'last_name' in data:
                parent.user.last_name = data['last_name']
            parent.user.save()
            
            # Update parent information
            update_fields = [
                'phone_number', 'occupation', 'address', 
                'relationship', 'is_emergency_contact', 'emergency_contact_priority'
            ]
            
            for field in update_fields:
                if field in data:
                    setattr(parent, field, data[field])
            
            parent.save()
            
            return JsonResponse({'message': 'Profile updated successfully'})
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class ParentAccountStatusAPIView(LoginRequiredMixin, View):
    """API endpoint for admin to manage parent account status"""
    
    def get(self, request):
        try:
            if not is_admin(request.user):
                return JsonResponse({'error': 'Admin access required'}, status=403)
            
            status_filter = request.GET.get('status', '')
            search = request.GET.get('search', '')
            
            parents = ParentGuardian.objects.select_related('user').prefetch_related('students')
            
            # Apply filters
            if status_filter:
                parents = parents.filter(account_status=status_filter)
            
            if search:
                parents = parents.filter(
                    Q(user__first_name__icontains=search) |
                    Q(user__last_name__icontains=search) |
                    Q(user__email__icontains=search) |
                    Q(phone_number__icontains=search)
                )
            
            parent_data = []
            for parent in parents:
                parent_data.append({
                    'id': parent.id,
                    'user': {
                        'id': parent.user.id,
                        'first_name': parent.user.first_name,
                        'last_name': parent.user.last_name,
                        'email': parent.user.email,
                        'is_active': parent.user.is_active,
                    },
                    'phone_number': parent.phone_number,
                    'relationship': parent.get_relationship_display(),
                    'occupation': parent.occupation,
                    'account_status': parent.account_status,
                    'account_status_display': parent.get_account_status_display(),
                    'login_count': parent.login_count,
                    'last_login': parent.last_login_date.isoformat() if parent.last_login_date else None,
                    'account_created': parent.account_created.isoformat(),
                    'students': [
                        {
                            'id': student.id,
                            'name': student.get_full_name(),
                            'student_id': student.student_id,
                            'class_level': student.get_class_level_display(),
                        }
                        for student in parent.students.all()
                    ],
                    'students_count': parent.students.count()
                })
            
            # Statistics
            stats = {
                'total': ParentGuardian.objects.count(),
                'active': ParentGuardian.objects.filter(account_status='active').count(),
                'pending': ParentGuardian.objects.filter(account_status='pending').count(),
                'inactive': ParentGuardian.objects.filter(account_status='inactive').count(),
                'suspended': ParentGuardian.objects.filter(account_status='suspended').count(),
            }
            
            return JsonResponse({
                'parents': parent_data,
                'stats': stats,
                'filters': {
                    'status': status_filter,
                    'search': search
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    
    def post(self, request, parent_id=None):
        """Update parent account status"""
        try:
            if not is_admin(request.user):
                return JsonResponse({'error': 'Admin access required'}, status=403)
            
            data = json.loads(request.body)
            action = data.get('action')
            
            if parent_id:
                parent = get_object_or_404(ParentGuardian, id=parent_id)
                
                if action == 'activate':
                    parent.account_status = 'active'
                    parent.save()
                    return JsonResponse({'message': f'Account for {parent.get_user_full_name()} activated'})
                
                elif action == 'suspend':
                    parent.account_status = 'suspended'
                    parent.save()
                    return JsonResponse({'message': f'Account for {parent.get_user_full_name()} suspended'})
                
                elif action == 'deactivate':
                    parent.account_status = 'inactive'
                    parent.save()
                    return JsonResponse({'message': f'Account for {parent.get_user_full_name()} deactivated'})
                
                else:
                    return JsonResponse({'error': 'Invalid action'}, status=400)
            
            else:
                return JsonResponse({'error': 'Parent ID required'}, status=400)
                
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class ParentRegistrationAPIView(View):
    """API endpoint for parent registration"""
    
    @method_decorator(csrf_exempt)
    def dispatch(self, *args, **kwargs):
        return super().dispatch(*args, **kwargs)
    
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # Validate required fields
            required_fields = ['first_name', 'last_name', 'email', 'phone_number', 'relationship', 'student_ids']
            for field in required_fields:
                if field not in data or not data[field]:
                    return JsonResponse({'error': f'{field.replace("_", " ").title()} is required'}, status=400)
            
            # Check if email already exists
            if ParentGuardian.objects.filter(email=data['email']).exists():
                return JsonResponse({'error': 'Email is already registered'}, status=400)
            
            # Check if user with email already exists
            from django.contrib.auth import get_user_model
            User = get_user_model()
            if User.objects.filter(email=data['email']).exists():
                return JsonResponse({'error': 'Email is already associated with an existing account'}, status=400)
            
            # Validate student IDs
            student_ids = [sid.strip() for sid in data['student_ids'].split(',') if sid.strip()]
            students = Student.objects.filter(student_id__in=student_ids, is_active=True)
            
            if students.count() != len(student_ids):
                found_ids = set(students.values_list('student_id', flat=True))
                missing_ids = set(student_ids) - found_ids
                return JsonResponse({
                    'error': f'Some student IDs not found: {", ".join(missing_ids)}'
                }, status=400)
            
            # Create parent
            parent = ParentGuardian(
                first_name=data['first_name'],
                last_name=data['last_name'],
                email=data['email'],
                phone_number=data['phone_number'],
                relationship=data['relationship'],
                occupation=data.get('occupation', ''),
                address=data.get('address', ''),
                is_emergency_contact=data.get('is_emergency_contact', False),
                emergency_contact_priority=data.get('emergency_contact_priority', 1),
                account_status='active'  # Auto-activate for now, can be changed to 'pending' for approval
            )
            
            # Create user account
            password = data.get('password', User.objects.make_random_password())
            parent.create_user_account(password)
            
            # Assign students
            parent.save()
            parent.students.set(students)
            
            return JsonResponse({
                'message': 'Parent account created successfully',
                'parent_id': parent.id,
                'user_id': parent.user.id,
                'auto_generated_password': not data.get('password')  # Indicate if password was auto-generated
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

# Utility API endpoints for frontend
class ParentStatsAPIView(LoginRequiredMixin, View):
    """API endpoint for parent engagement statistics"""
    
    def get(self, request):
        try:
            if not is_admin(request.user):
                return JsonResponse({'error': 'Admin access required'}, status=403)
            
            # Parent engagement by class
            class_engagement = []
            from .models import CLASS_LEVEL_CHOICES
            
            for class_code, class_name in CLASS_LEVEL_CHOICES:
                class_parents = ParentGuardian.objects.filter(
                    students__class_level=class_code
                ).distinct()
                
                active_class_parents = class_parents.filter(
                    account_status='active',
                    last_login_date__gte=timezone.now() - timezone.timedelta(days=30)
                )
                
                engagement_rate = (
                    (active_class_parents.count() / class_parents.count() * 100) 
                    if class_parents.count() > 0 else 0
                )
                
                class_engagement.append({
                    'class_level': class_name,
                    'class_code': class_code,
                    'total_parents': class_parents.count(),
                    'active_parents': active_class_parents.count(),
                    'engagement_rate': round(engagement_rate, 1)
                })
            
            # Recent parent activity
            recent_activity = ParentGuardian.objects.filter(
                last_login_date__isnull=False
            ).select_related('user').order_by('-last_login_date')[:10]
            
            recent_activity_data = []
            for parent in recent_activity:
                recent_activity_data.append({
                    'parent_name': parent.get_user_full_name(),
                    'login_time': parent.last_login_date.isoformat(),
                    'students': [s.get_full_name() for s in parent.students.all()],
                    'login_count': parent.login_count
                })
            
            return JsonResponse({
                'class_engagement': class_engagement,
                'recent_activity': recent_activity_data,
                'overall_stats': {
                    'total_parents': ParentGuardian.objects.count(),
                    'active_today': ParentGuardian.objects.filter(
                        last_login_date__date=timezone.now().date()
                    ).count(),
                    'active_this_week': ParentGuardian.objects.filter(
                        last_login_date__gte=timezone.now() - timezone.timedelta(days=7)
                    ).count(),
                    'active_this_month': ParentGuardian.objects.filter(
                        last_login_date__gte=timezone.now() - timezone.timedelta(days=30)
                    ).count(),
                }
            })
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

# Additional utility APIs for parent portal
class ParentAttendanceAPIView(LoginRequiredMixin, View):
    """API endpoint for parent to view children's attendance"""
    
    def get(self, request):
        try:
            if not is_parent(request.user):
                return JsonResponse({'error': 'Parent account required'}, status=403)
            
            parent = request.user.parentguardian
            child_id = request.GET.get('child_id')
            date_from = request.GET.get('date_from')
            date_to = request.GET.get('date_to')
            
            # Get attendance for all children or specific child
            if child_id:
                children = parent.students.filter(id=child_id)
            else:
                children = parent.students.all()
            
            attendance_data = []
            for child in children:
                attendance_records = StudentAttendance.objects.filter(student=child)
                
                # Apply date filters
                if date_from:
                    attendance_records = attendance_records.filter(date__gte=date_from)
                if date_to:
                    attendance_records = attendance_records.filter(date__lte=date_to)
                
                attendance_records = attendance_records.order_by('-date')[:50]  # Limit to recent 50
                
                child_attendance = {
                    'child_id': child.id,
                    'child_name': child.get_full_name(),
                    'records': [
                        {
                            'date': record.date.isoformat(),
                            'status': record.status,
                            'status_display': record.get_status_display(),
                            'notes': record.notes,
                            'term': str(record.term) if record.term else None,
                        }
                        for record in attendance_records
                    ],
                    'summary': attendance_records.aggregate(
                        present=Count('id', filter=Q(status='present')),
                        absent=Count('id', filter=Q(status='absent')),
                        late=Count('id', filter=Q(status='late')),
                        excused=Count('id', filter=Q(status='excused')),
                        total=Count('id')
                    )
                }
                attendance_data.append(child_attendance)
            
            return JsonResponse({'attendance': attendance_data})
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)

class ParentGradesAPIView(LoginRequiredMixin, View):
    """API endpoint for parent to view children's grades"""
    
    def get(self, request):
        try:
            if not is_parent(request.user):
                return JsonResponse({'error': 'Parent account required'}, status=403)
            
            parent = request.user.parentguardian
            child_id = request.GET.get('child_id')
            academic_year = request.GET.get('academic_year')
            term = request.GET.get('term')
            
            # Get grades for all children or specific child
            if child_id:
                children = parent.students.filter(id=child_id)
            else:
                children = parent.students.all()
            
            grades_data = []
            for child in children:
                grades = Grade.objects.filter(student=child).select_related('subject')
                
                # Apply filters
                if academic_year:
                    grades = grades.filter(academic_year=academic_year)
                if term:
                    grades = grades.filter(term=term)
                
                child_grades = {
                    'child_id': child.id,
                    'child_name': child.get_full_name(),
                    'grades': [
                        {
                            'subject': grade.subject.name,
                            'subject_code': grade.subject.code,
                            'total_score': float(grade.total_score) if grade.total_score else 0,
                            'display_grade': grade.get_display_grade(),
                            'academic_year': grade.academic_year,
                            'term': grade.term,
                            'last_updated': grade.last_updated.isoformat(),
                            'performance_level': grade.get_performance_level_display(),
                        }
                        for grade in grades
                    ],
                    'summary': grades.aggregate(
                        average_score=Avg('total_score'),
                        highest_score=Max('total_score'),
                        lowest_score=Min('total_score'),
                        total_subjects=Count('id')
                    )
                }
                grades_data.append(child_grades)
            
            return JsonResponse({'grades': grades_data})
            
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)