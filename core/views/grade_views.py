# grade_views.py - Complete and Functional Implementation
from django.contrib.auth.mixins import UserPassesTestMixin, LoginRequiredMixin
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import JsonResponse, HttpResponse, Http404
from django.db.models import Avg, Max, Min, Count, Sum, Q
from django.core.files.base import ContentFile
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.urls import reverse_lazy
from django.utils import timezone
from django.contrib.auth.models import User
from django.db.models import F, ExpressionWrapper, FloatField

# ADD ALL REQUIRED IMPORTS
from django.views.generic import ListView, CreateView, UpdateView, DeleteView, TemplateView, DetailView, View
from django.views import View

import json
import logging
from openpyxl import load_workbook
from io import BytesIO, StringIO
import csv
from decimal import Decimal, InvalidOperation
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync
import re

# Import your mixins and models
from ..mixins import TwoFactorLoginRequiredMixin, AdminRequiredMixin, AuditLogMixin
from .base_views import *
from ..models import (
    Grade, Assignment, StudentAssignment, ReportCard, Student, 
    Subject, ClassAssignment, AcademicTerm, AuditLog, Teacher,
    CLASS_LEVEL_CHOICES
)
from ..forms import GradeEntryForm, ReportCardForm, ReportCardFilterForm, BulkGradeUploadForm
from ..utils import is_admin, is_teacher, is_student, is_parent

logger = logging.getLogger(__name__)

# Custom exception for notification errors
class NotificationException(Exception):
    pass

# Enhanced GradeListView with proper error handling
class GradeListView(TwoFactorLoginRequiredMixin, UserPassesTestMixin, ListView):
    """
    Enhanced Grade List View with comprehensive filtering, search, 
    role-based access control, and professional UI integration.
    """
    model = Grade
    template_name = 'core/academics/grades/grade_list.html'
    context_object_name = 'grades'
    paginate_by = 25
    ordering = ['-created_at']  # Default ordering

    def test_func(self):
        """
        Comprehensive permission checking with detailed logging
        """
        try:
            user = self.request.user
            
            # Superusers, admins, and teachers can access
            if user.is_superuser or is_admin(user) or is_teacher(user):
                logger.debug(f"Access granted for grade list - User: {user}, Role: {getattr(user, 'role', 'unknown')}")
                return True
            
            # Students and parents cannot access grade list (they have their own views)
            logger.warning(f"Unauthorized access attempt - User: {user}, Role: {getattr(user, 'role', 'unknown')}")
            return False
            
        except Exception as e:
            logger.error(f"Permission check failed: {str(e)}", exc_info=True)
            return False

    def get_queryset(self):
        """
        Safe queryset filtering with validation and optimization
        """
        try:
            queryset = super().get_queryset().select_related(
                'student', 
                'subject', 
                'class_assignment',
                'class_assignment__teacher',
                'recorded_by'
            ).prefetch_related('student__parents')
            
            # Apply filters and search
            queryset = self.apply_filters(queryset)
            queryset = self.apply_search(queryset)
            queryset = self.apply_role_based_filtering(queryset)
            queryset = self.apply_ordering(queryset)
            
            return queryset.distinct()
            
        except Exception as e:
            logger.error(f"Error building grade queryset: {str(e)}", exc_info=True)
            messages.error(self.request, 'Error loading grades. Please try again.')
            return Grade.objects.none()

    def apply_filters(self, queryset):
        """
        Apply filters with validation and error handling
        """
        try:
            filter_params = {
                'student': self.request.GET.get('student'),
                'subject': self.request.GET.get('subject'),
                'class_level': self.request.GET.get('class_level'),
                'academic_year': self.request.GET.get('academic_year'),
                'term': self.request.GET.get('term'),
                'teacher': self.request.GET.get('teacher'),
                'ges_grade': self.request.GET.get('ges_grade'),
                'min_score': self.request.GET.get('min_score'),
                'max_score': self.request.GET.get('max_score'),
            }

            # Student filter
            if filter_params['student']:
                try:
                    student = Student.objects.get(pk=filter_params['student'])
                    queryset = queryset.filter(student=student)
                except (Student.DoesNotExist, ValueError):
                    messages.warning(self.request, 'Invalid student selected.')

            # Subject filter
            if filter_params['subject']:
                try:
                    subject = Subject.objects.get(pk=filter_params['subject'])
                    queryset = queryset.filter(subject=subject)
                except (Subject.DoesNotExist, ValueError):
                    messages.warning(self.request, 'Invalid subject selected.')

            # Class level filter
            if filter_params['class_level'] and filter_params['class_level'] in dict(CLASS_LEVEL_CHOICES):
                queryset = queryset.filter(student__class_level=filter_params['class_level'])

            # Academic year filter
            if filter_params['academic_year']:
                if re.match(r'^\d{4}/\d{4}$', filter_params['academic_year']):
                    queryset = queryset.filter(academic_year=filter_params['academic_year'])
                else:
                    messages.warning(self.request, 'Invalid academic year format. Use YYYY/YYYY.')

            # Term filter
            if filter_params['term'] and filter_params['term'].isdigit():
                term = int(filter_params['term'])
                if 1 <= term <= 3:
                    queryset = queryset.filter(term=term)
                else:
                    messages.warning(self.request, 'Invalid term selected. Must be 1, 2, or 3.')

            # Teacher filter
            if filter_params['teacher']:
                try:
                    teacher = Teacher.objects.get(pk=filter_params['teacher'])
                    queryset = queryset.filter(class_assignment__teacher=teacher)
                except (Teacher.DoesNotExist, ValueError):
                    messages.warning(self.request, 'Invalid teacher selected.')

            # GES grade filter
            if filter_params['ges_grade'] and filter_params['ges_grade'] in dict(Grade.GES_GRADE_CHOICES):
                queryset = queryset.filter(ges_grade=filter_params['ges_grade'])

            # Score range filters
            if filter_params['min_score']:
                try:
                    min_score = Decimal(filter_params['min_score'])
                    if 0 <= min_score <= 100:
                        queryset = queryset.filter(total_score__gte=min_score)
                    else:
                        messages.warning(self.request, 'Minimum score must be between 0 and 100.')
                except (InvalidOperation, ValueError):
                    messages.warning(self.request, 'Invalid minimum score format.')

            if filter_params['max_score']:
                try:
                    max_score = Decimal(filter_params['max_score'])
                    if 0 <= max_score <= 100:
                        queryset = queryset.filter(total_score__lte=max_score)
                    else:
                        messages.warning(self.request, 'Maximum score must be between 0 and 100.')
                except (InvalidOperation, ValueError):
                    messages.warning(self.request, 'Invalid maximum score format.')

            return queryset

        except Exception as e:
            logger.error(f"Error applying filters: {str(e)}", exc_info=True)
            return queryset

    def apply_search(self, queryset):
        """
        Apply search functionality across multiple fields
        """
        search_query = self.request.GET.get('search', '').strip()
        
        if not search_query:
            return queryset

        try:
            # Build search conditions
            search_conditions = Q()
            
            # Search in student names
            search_conditions |= Q(student__first_name__icontains=search_query)
            search_conditions |= Q(student__last_name__icontains=search_query)
            search_conditions |= Q(student__student_id__icontains=search_query)
            
            # Search in subject names
            search_conditions |= Q(subject__name__icontains=search_query)
            search_conditions |= Q(subject__code__icontains=search_query)
            
            # Search in teacher names
            search_conditions |= Q(class_assignment__teacher__user__first_name__icontains=search_query)
            search_conditions |= Q(class_assignment__teacher__user__last_name__icontains=search_query)
            
            # Search in academic year
            search_conditions |= Q(academic_year__icontains=search_query)
            
            # Search in remarks
            search_conditions |= Q(remarks__icontains=search_query)
            
            return queryset.filter(search_conditions)
            
        except Exception as e:
            logger.error(f"Error applying search: {str(e)}")
            return queryset

    def apply_role_based_filtering(self, queryset):
        """
        Apply role-based filtering safely
        """
        try:
            user = self.request.user
            
            if is_teacher(user):
                # Teachers can only see grades for their assigned classes and subjects
                teacher_classes = ClassAssignment.objects.filter(
                    teacher=user.teacher,
                    is_active=True
                ).values_list('class_level', 'subject')
                
                # Create Q objects for each class-subject combination
                class_subject_conditions = Q()
                for class_level, subject in teacher_classes:
                    class_subject_conditions |= Q(
                        student__class_level=class_level,
                        subject=subject
                    )
                
                if class_subject_conditions:
                    queryset = queryset.filter(class_subject_conditions)
                else:
                    queryset = queryset.none()
                    
                logger.debug(f"Teacher filtering applied - {user.teacher}, Classes: {len(teacher_classes)}")
                
            elif is_student(user):
                # Students can only see their own grades
                queryset = queryset.filter(student=user.student)
                
            # Admins and superusers see all grades (no additional filtering)
            
            return queryset.filter(
                student__is_active=True,
                subject__is_active=True
            )
            
        except Exception as e:
            logger.error(f"Role-based filtering failed: {str(e)}")
            return queryset.none()

    def apply_ordering(self, queryset):
        """
        Apply dynamic ordering based on request parameters
        """
        order_by = self.request.GET.get('order_by', '-created_at')
        valid_ordering_fields = [
            'student__last_name', 'student__first_name', 'subject__name',
            'total_score', 'ges_grade', 'academic_year', 'term', 'created_at'
        ]
        
        # Handle descending order
        if order_by.startswith('-'):
            field = order_by[1:]
            if field in valid_ordering_fields:
                return queryset.order_by(order_by)
        
        # Handle ascending order
        elif order_by in valid_ordering_fields:
            return queryset.order_by(order_by)
        
        # Default ordering
        return queryset.order_by('-created_at')

    def get_context_data(self, **kwargs):
        """
        Enhanced context with comprehensive data for the template
        """
        try:
            context = super().get_context_data(**kwargs)
            
            # Get the filtered queryset for statistics
            queryset = self.get_queryset()
            
            # Calculate statistics from the FILTERED data
            total_grades = queryset.count()
            
            # Calculate average score - handle None values properly
            avg_result = queryset.aggregate(avg_score=Avg('total_score'))
            average_score = avg_result['avg_score'] or 0
            
            # Get unique students in the filtered results
            student_ids = queryset.values_list('student_id', flat=True).distinct()
            total_students = Student.objects.filter(id__in=student_ids, is_active=True).count()
            
            # Get unique subjects in the filtered results
            subject_ids = queryset.values_list('subject_id', flat=True).distinct()
            total_subjects = Subject.objects.filter(id__in=subject_ids, is_active=True).count()
            
            # Add filter context
            context.update(self.get_filter_context())
            
            # Add statistics context
            context.update({
                'total_students': total_students,
                'total_grades': total_grades,
                'total_subjects': total_subjects,
                'average_grade': round(average_score, 1),
            })
            
            # Add UI context
            context.update(self.get_ui_context())
            
            return context
            
        except Exception as e:
            logger.error(f"Error preparing context: {str(e)}", exc_info=True)
            messages.error(self.request, 'Error loading grade data.')
            # Return basic context even if there's an error
            context = super().get_context_data(**kwargs)
            context.update({
                'total_students': 0,
                'total_grades': 0,
                'total_subjects': 0,
                'average_grade': 0,
                'current_filters': {},
                'students': Student.objects.none(),
                'subjects': Subject.objects.none(),
                'class_levels': CLASS_LEVEL_CHOICES,
            })
            return context

    def get_filter_context(self):
        """
        Prepare filter-related context data
        """
        current_filters = {
            'student': self.request.GET.get('student', ''),
            'subject': self.request.GET.get('subject', ''),
            'class_level': self.request.GET.get('class_level', ''),
            'academic_year': self.request.GET.get('academic_year', ''),
            'term': self.request.GET.get('term', ''),
            'teacher': self.request.GET.get('teacher', ''),
            'ges_grade': self.request.GET.get('ges_grade', ''),
            'min_score': self.request.GET.get('min_score', ''),
            'max_score': self.request.GET.get('max_score', ''),
            'search': self.request.GET.get('search', ''),
            'order_by': self.request.GET.get('order_by', '-created_at'),
        }
        
        # Get available filter options based on user role
        students = self.get_available_students()
        subjects = self.get_available_subjects()
        
        return {
            'current_filters': current_filters,
            'students': students,
            'subjects': subjects,
            'class_levels': CLASS_LEVEL_CHOICES,
            'has_active_filters': any(value for key, value in current_filters.items() if key not in ['order_by']),
        }

    def get_available_subjects(self):
        """
        Get subjects based on user role
        """
        try:
            if is_teacher(self.request.user):
                return Subject.objects.filter(
                    classassignment__teacher=self.request.user.teacher,
                    classassignment__is_active=True,
                    is_active=True
                ).distinct().order_by('name')
            else:
                return Subject.objects.filter(is_active=True).order_by('name')
        except Exception as e:
            logger.error(f"Error fetching subjects: {str(e)}")
            return Subject.objects.none()

    def get_available_students(self):
        """
        Get students based on user role
        """
        try:
            if is_teacher(self.request.user):
                teacher_classes = ClassAssignment.objects.filter(
                    teacher=self.request.user.teacher,
                    is_active=True
                ).values_list('class_level', flat=True).distinct()
                
                return Student.objects.filter(
                    class_level__in=teacher_classes,
                    is_active=True
                ).order_by('last_name', 'first_name')
                
            elif is_admin(self.request.user) or self.request.user.is_superuser:
                return Student.objects.filter(is_active=True).order_by('last_name', 'first_name')
                
            else:
                return Student.objects.none()
                
        except Exception as e:
            logger.error(f"Error fetching students: {str(e)}")
            return Student.objects.none()

    def get_available_teachers(self):
        """
        Get teachers for filter dropdown
        """
        try:
            if is_admin(self.request.user) or self.request.user.is_superuser:
                return Teacher.objects.filter(is_active=True).select_related('user').order_by('user__last_name')
            else:
                return Teacher.objects.none()
        except Exception as e:
            logger.error(f"Error fetching teachers: {str(e)}")
            return Teacher.objects.none()

    def get_academic_years(self):
        """
        Get distinct academic years from existing grades
        """
        try:
            years = Grade.objects.values_list('academic_year', flat=True).distinct()
            return [(year, year) for year in sorted(years, reverse=True)]
        except Exception as e:
            logger.error(f"Error fetching academic years: {str(e)}")
            return []

    def get_statistics_context(self):
        """
        Calculate and prepare statistics for display
        """
        try:
            queryset = self.get_queryset()
            total_grades = queryset.count()
            
            if total_grades > 0:
                # Calculate average score
                avg_result = queryset.aggregate(avg_score=Avg('total_score'))
                average_score = avg_result['avg_score'] or 0
                
                # Calculate grade distribution
                grade_distribution = queryset.values('ges_grade').annotate(
                    count=Count('id'),
                    percentage=ExpressionWrapper(
                        Count('id') * 100.0 / total_grades,
                        output_field=FloatField()
                    )
                ).order_by('ges_grade')
                
                # Calculate passing rate (GES standard: 40% and above)
                passing_count = queryset.filter(total_score__gte=40).count()
                passing_rate = (passing_count / total_grades * 100) if total_grades > 0 else 0
                
                # Get top performers
                top_performers = queryset.order_by('-total_score')[:5]
                
            else:
                average_score = 0
                grade_distribution = []
                passing_rate = 0
                top_performers = []
            
            return {
                'total_grades': total_grades,
                'average_score': round(average_score, 2),
                'passing_rate': round(passing_rate, 1),
                'grade_distribution': grade_distribution,
                'top_performers': top_performers,
                'has_data': total_grades > 0,
            }
            
        except Exception as e:
            logger.error(f"Error calculating statistics: {str(e)}")
            return {
                'total_grades': 0,
                'average_score': 0,
                'passing_rate': 0,
                'grade_distribution': [],
                'top_performers': [],
                'has_data': False,
            }

    def get_ui_context(self):
        """
        Prepare UI-related context data
        """
        return {
            'is_admin': is_admin(self.request.user),
            'is_teacher': is_teacher(self.request.user),
            'is_student': is_student(self.request.user),
            'can_export': is_admin(self.request.user) or is_teacher(self.request.user),
            'can_bulk_upload': is_admin(self.request.user),
            'page_title': 'Grade Management',
            'current_view': 'grade_list',
        }

    def get_paginate_by(self, queryset):
        """
        Allow dynamic pagination
        """
        paginate_by = self.request.GET.get('paginate_by', self.paginate_by)
        try:
            return int(paginate_by)
        except (ValueError, TypeError):
            return self.paginate_by

    def handle_no_permission(self):
        """
        Custom handling for permission denied with proper redirects
        """
        user = self.request.user
        logger.warning(
            f"Unauthorized access attempt to grade list - User: {user.username}, "
            f"Role: {getattr(user, 'role', 'unknown')}"
    )
    
        messages.error(self.request, "You don't have permission to access the grade management system.")
    
        # Use the CORRECT URL name that we confirmed works
        return redirect('student_dashboard')  # ✅ This will work!


    def render_to_response(self, context, **response_kwargs):
        """
        Override to add additional response handling
        """
        response = super().render_to_response(context, **response_kwargs)
        
        # Add cache control headers
        response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        
        return response


class GradeCreateView(TwoFactorLoginRequiredMixin, UserPassesTestMixin, CreateView):
    """
    Enhanced Grade Create View with comprehensive validation,
    transaction safety, and professional UI integration.
    """
    model = Grade
    form_class = GradeEntryForm
    template_name = 'core/academics/grades/grade_form.html'
    success_url = reverse_lazy('grade_list')
    success_message = "Grade created successfully."

    def test_func(self):
        """
        Permission checking for grade creation
        """
        try:
            user = self.request.user
            return user.is_superuser or is_admin(user) or is_teacher(user)
        except Exception as e:
            logger.error(f"Permission check failed: {str(e)}")
            return False

    def get_form_kwargs(self):
        """Add user to form kwargs"""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def get_context_data(self, **kwargs):
        """Enhanced context with additional information"""
        context = super().get_context_data(**kwargs)
        
        # Add student and subject information if provided via GET parameters
        student_id = self.request.GET.get('student')
        subject_id = self.request.GET.get('subject')
        
        if student_id:
            try:
                context['selected_student'] = Student.objects.get(pk=student_id)
            except Student.DoesNotExist:
                pass
        
        if subject_id:
            try:
                context['selected_subject'] = Subject.objects.get(pk=subject_id)
            except Subject.DoesNotExist:
                pass
        
        context.update({
            'is_teacher': is_teacher(self.request.user),
            'page_title': 'Create New Grade',
            'current_view': 'grade_create',
        })
        
        return context

    @transaction.atomic
    def form_valid(self, form):
        """
        Handle form validation with comprehensive transaction safety
        """
        try:
            # Pre-save validation
            validation_errors = self._validate_grade_creation(form.cleaned_data)
            if validation_errors:
                for field, error in validation_errors.items():
                    form.add_error(field, error)
                return self.form_invalid(form)
            
            # Set recorded_by user
            form.instance.recorded_by = self.request.user
            
            # Save the form
            response = super().form_valid(form)
            
            # Post-save operations
            self._handle_post_save_operations()
            
            messages.success(
                self.request, 
                f'Grade successfully created for {self.object.student.get_full_name()}! '
                f'Total: {self.object.total_score} - {self.object.get_ges_grade_display()}'
            )
            
            return response
            
        except ValidationError as e:
            logger.warning(f"Grade creation validation failed: {str(e)}")
            messages.error(self.request, f"Validation error: {str(e)}")
            return self.form_invalid(form)
        except Exception as e:
            logger.error(f"Error creating grade: {str(e)}", exc_info=True)
            messages.error(self.request, 'Failed to create grade. Please try again.')
            return self.form_invalid(form)

    def _validate_grade_creation(self, cleaned_data):
        """
        Comprehensive validation for grade creation
        """
        errors = {}
        
        student = cleaned_data.get('student')
        subject = cleaned_data.get('subject')
        academic_year = cleaned_data.get('academic_year')
        term = cleaned_data.get('term')
        
        # Check for duplicate grade
        if student and subject and academic_year and term:
            existing_grade = Grade.objects.filter(
                student=student,
                subject=subject,
                academic_year=academic_year,
                term=term
            ).exists()
            
            if existing_grade:
                errors['__all__'] = (
                    f"A grade already exists for {student.get_full_name()} in {subject.name} "
                    f"for {academic_year} Term {term}. Please update the existing grade instead."
                )
        
        # Validate score limits
        max_scores = {
            'classwork_score': 30,
            'homework_score': 10,
            'test_score': 10,
            'exam_score': 50
        }
        
        for field, max_score in max_scores.items():
            score = cleaned_data.get(field, 0)
            if score < 0:
                errors[field] = f"{field.replace('_', ' ').title()} cannot be negative"
            elif score > max_score:
                errors[field] = f"{field.replace('_', ' ').title()} cannot exceed {max_score}%"
        
        # Validate total score doesn't exceed 100%
        total_score = sum(cleaned_data.get(field, 0) for field in max_scores.keys())
        if total_score > 100:
            errors['__all__'] = f"Total score cannot exceed 100%. Current total: {total_score}%"
        
        return errors

    def _handle_post_save_operations(self):
        """
        Handle operations after successful grade creation
        """
        try:
            # Log the creation
            self._log_grade_creation()
            
            # Send notifications
            self._send_creation_notifications()
            
            # Update analytics cache
            self._update_analytics_cache()
            
        except Exception as e:
            logger.error(f"Post-save operations failed: {str(e)}")
            # Don't raise exception here as the grade was already created successfully

    def _log_grade_creation(self):
        """Log grade creation for audit purposes"""
        try:
            AuditLog.objects.create(
                user=self.request.user,
                action='CREATE',
                model_name='Grade',
                object_id=self.object.id,
                details={
                    'student_id': self.object.student.id,
                    'student_name': self.object.student.get_full_name(),
                    'subject_id': self.object.subject.id,
                    'subject_name': self.object.subject.name,
                    'academic_year': self.object.academic_year,
                    'term': self.object.term,
                    'total_score': float(self.object.total_score) if self.object.total_score else 0,
                    'ges_grade': self.object.ges_grade,
                    'class_level': self.object.student.class_level,
                    'created_by': self.request.user.get_full_name()
                },
                ip_address=self._get_client_ip()
            )
            
        except Exception as e:
            logger.error(f"Failed to log grade creation: {str(e)}")

    def _get_client_ip(self):
        """Get client IP address for audit logging"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip

    def _send_creation_notifications(self):
        """Send notifications about grade creation"""
        try:
            student = self.object.student
            subject = self.object.subject
            
            # Send notification to student
            notification_data = {
                'type': 'send_notification',
                'notification_type': 'GRADE_CREATED',
                'title': 'New Grade Recorded',
                'message': f'A new grade has been recorded for {subject.name}',
                'related_object_id': self.object.id,
                'timestamp': timezone.now().isoformat(),
                'icon': 'bi-journal-plus',
                'color': 'info',
                'action_url': self._get_grade_detail_url()
            }
            
            self._send_websocket_notification(
                f'notifications_{student.user.id}',
                notification_data
            )
            
        except Exception as e:
            logger.error(f"Failed to send creation notifications: {str(e)}")

    def _send_websocket_notification(self, group_name, notification_data):
        """Send WebSocket notification with error handling"""
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                group_name,
                notification_data
            )
        except Exception as e:
            logger.error(f"WebSocket notification failed: {str(e)}")

    def _update_analytics_cache(self):
        """Update analytics cache after grade creation"""
        try:
            from django.core.cache import cache
            
            # Clear relevant cache keys
            cache_keys_to_clear = [
                f"class_performance_{self.object.subject.id}_{self.object.student.class_level}_{self.object.academic_year}_{self.object.term}",
                f"student_progress_{self.object.student.id}_{self.object.academic_year}",
                f"term_report_{self.object.student.class_level}_{self.object.academic_year}_{self.object.term}"
            ]
            
            for cache_key in cache_keys_to_clear:
                cache.delete(cache_key)
            
        except Exception as e:
            logger.warning(f"Failed to update analytics cache: {str(e)}")

    def _get_grade_detail_url(self):
        """Get URL for grade detail page"""
        try:
            return reverse_lazy('grade_detail', kwargs={'pk': self.object.pk})
        except:
            return self.get_success_url()

    def form_invalid(self, form):
        """Enhanced form invalid handling"""
        logger.warning(f"Grade creation form invalid - Errors: {form.errors}")
        
        # Add generic error message if no specific field errors
        if not form.errors:
            messages.error(self.request, "Please correct the errors below.")
        
        return super().form_invalid(form)

class GradeUpdateView(TwoFactorLoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """
    Enhanced Grade Update View with comprehensive error handling,
    transaction safety, and professional notification system.
    """
    model = Grade
    form_class = GradeEntryForm
    template_name = 'core/academics/grades/grade_form.html'
    success_url = reverse_lazy('grade_list')

    def dispatch(self, request, *args, **kwargs):
        """
        Override dispatch to handle all exceptions at the entry point
        """
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            logger.warning(f"Grade not found - User: {request.user}, Grade ID: {kwargs.get('pk')}")
            messages.error(request, "The requested grade record does not exist or has been deleted.")
            return redirect('grade_list')
        except PermissionDenied:
            logger.warning(f"Permission denied for grade update - User: {request.user}")
            messages.error(request, "You don't have permission to update this grade.")
            return redirect('grade_list')
        except Exception as e:
            logger.error(f"Unexpected error in grade update dispatch: {str(e)}", exc_info=True)
            messages.error(request, "An unexpected error occurred. Please try again.")
            return redirect('grade_list')

    def get_object(self, queryset=None):
        """
        Safely retrieve the grade object with comprehensive error handling
        """
        try:
            if queryset is None:
                queryset = self.get_queryset()
            
            # Use select_related to optimize database queries
            queryset = queryset.select_related(
                'student', 
                'subject', 
                'class_assignment',
                'student__user'
            )
            
            obj = super().get_object(queryset)
            
            # Additional validation for the retrieved object
            self._validate_grade_object(obj)
            
            logger.info(f"Grade object retrieved successfully - ID: {obj.id}, Student: {obj.student}")
            return obj
            
        except Http404:
            logger.error(
                f"Grade not found - PK: {self.kwargs.get('pk')}, "
                f"User: {self.request.user}, URL: {self.request.path}"
            )
            messages.error(self.request, "The requested grade record was not found.")
            raise
        except ValidationError as e:
            logger.error(f"Grade validation failed: {str(e)}")
            messages.error(self.request, "Invalid grade data. Please contact administrator.")
            raise Http404("Invalid grade data")
        except Exception as e:
            logger.error(f"Unexpected error retrieving grade: {str(e)}", exc_info=True)
            messages.error(self.request, "Error loading grade record. Please try again.")
            raise Http404("Error loading grade")

    def _validate_grade_object(self, grade):
        """
        Validate the grade object before proceeding with operations
        """
        if not grade.student.is_active:
            raise ValidationError("Cannot update grade for inactive student")
        
        if not grade.subject.is_active:
            raise ValidationError("Cannot update grade for inactive subject")
        
        # Check if the academic term is still editable
        if self._is_term_locked(grade.academic_year, grade.term):
            raise ValidationError("Cannot update grades for locked academic term")

    def _is_term_locked(self, academic_year, term):
        """
        Check if the academic term is locked for editing
        """
        # Implement your term locking logic here
        # This could check against a configuration or academic calendar
        try:
            term_obj = AcademicTerm.objects.filter(
                academic_year=academic_year,
                term=term
            ).first()
            
            if term_obj and hasattr(term_obj, 'is_locked'):
                return term_obj.is_locked
                
            return False
        except Exception as e:
            logger.warning(f"Error checking term lock status: {str(e)}")
            return False

    def get_queryset(self):
        """
        Optimize queryset based on user role and permissions
        """
        queryset = super().get_queryset()
        
        if is_teacher(self.request.user):
            # Teachers can only see grades for their assigned classes
            teacher_classes = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            ).values_list('class_level', flat=True)
            
            queryset = queryset.filter(
                student__class_level__in=teacher_classes
            )
        
        return queryset.filter(
            student__is_active=True,
            subject__is_active=True
        )

    def test_func(self):
        """
        Comprehensive permission checking with detailed logging
        """
        try:
            user = self.request.user
            
            # Superusers and admins have full access
            if user.is_superuser or is_admin(user):
                logger.debug(f"Admin access granted for grade update - User: {user}")
                return True
            
            # Teachers need specific permissions
            if is_teacher(user):
                grade = self.get_object()
                return self._check_teacher_permissions(user.teacher, grade)
            
            # Students and parents cannot update grades
            logger.warning(f"Unauthorized access attempt - User: {user}, Role: {getattr(user, 'role', 'unknown')}")
            return False
            
        except Exception as e:
            logger.error(f"Permission check failed: {str(e)}", exc_info=True)
            return False

    def _check_teacher_permissions(self, teacher, grade):
        """
        Check if teacher has permission to update this specific grade
        """
        try:
            has_permission = ClassAssignment.objects.filter(
                Q(class_level=grade.student.class_level) &
                Q(teacher=teacher) &
                Q(subject=grade.subject) &
                Q(academic_year=grade.academic_year) &
                Q(is_active=True)
            ).exists()
            
            if has_permission:
                logger.info(f"Teacher permission granted - Teacher: {teacher}, Grade: {grade.id}")
            else:
                logger.warning(
                    f"Teacher permission denied - Teacher: {teacher}, "
                    f"Grade: {grade.id}, Class: {grade.student.class_level}, "
                    f"Subject: {grade.subject.name}"
                )
            
            return has_permission
            
        except Exception as e:
            logger.error(f"Teacher permission check failed: {str(e)}")
            return False

    @transaction.atomic
    def form_valid(self, form):
        """
        Handle form validation with comprehensive transaction safety
        and business logic validation
        """
        try:
            # Store original state for comparison and audit
            original_grade = Grade.objects.get(pk=self.object.pk)
            original_scores = self._get_original_scores(original_grade)
            
            # Pre-save validation
            validation_errors = self._validate_grade_update(form.cleaned_data)
            if validation_errors:
                for field, error in validation_errors.items():
                    form.add_error(field, error)
                return self.form_invalid(form)
            
            # Save the grade with automatic calculations
            response = super().form_valid(form)
            
            # Post-save operations
            self._handle_post_save_operations(original_scores, form.cleaned_data)
            
            return response
            
        except ValidationError as e:
            logger.warning(f"Grade validation failed: {str(e)}")
            messages.error(self.request, f"Validation error: {str(e)}")
            return self.form_invalid(form)
        except Exception as e:
            logger.error(f"Error saving grade: {str(e)}", exc_info=True)
            messages.error(self.request, 'Failed to update grade. Please try again.')
            # Transaction will be rolled back automatically
            return self.form_invalid(form)

    def _get_original_scores(self, original_grade):
        """
        Capture original scores for change detection and audit
        """
        return {
            'homework': original_grade.homework_score,
            'classwork': original_grade.classwork_score,
            'test': original_grade.test_score,
            'exam': original_grade.exam_score,
            'total': original_grade.total_score,
            'ges_grade': original_grade.ges_grade
        }

    def _validate_grade_update(self, cleaned_data):
        """
        Comprehensive validation for grade updates
        """
        errors = {}
        
        # Validate score limits
        max_scores = {
            'classwork_score': 30,
            'homework_score': 10,
            'test_score': 10,
            'exam_score': 50
        }
        
        for field, max_score in max_scores.items():
            score = cleaned_data.get(field, 0)
            if score < 0:
                errors[field] = f"{field.replace('_', ' ').title()} cannot be negative"
            elif score > max_score:
                errors[field] = f"{field.replace('_', ' ').title()} cannot exceed {max_score}%"
        
        # Validate total score doesn't exceed 100%
        total_score = sum(cleaned_data.get(field, 0) for field in max_scores.keys())
        if total_score > 100:
            errors['__all__'] = f"Total score cannot exceed 100%. Current total: {total_score}%"
        
        # Check for significant changes that might need approval
        if self._requires_approval(cleaned_data):
            errors['__all__'] = "This grade change requires administrative approval."
        
        return errors

    def _requires_approval(self, cleaned_data):
        """
        Determine if grade change requires administrative approval
        """
        try:
            original_grade = Grade.objects.get(pk=self.object.pk)
            
            # Check for significant score changes (more than 20 points)
            score_changes = []
            for score_type in ['classwork', 'homework', 'test', 'exam']:
                original = getattr(original_grade, f"{score_type}_score", 0)
                new = cleaned_data.get(f"{score_type}_score", 0)
                if abs(float(new) - float(original)) > 20:
                    score_changes.append(score_type)
            
            return len(score_changes) > 0
            
        except Exception as e:
            logger.warning(f"Error checking approval requirements: {str(e)}")
            return False

    def _handle_post_save_operations(self, original_scores, new_scores):
        """
        Handle all operations that should occur after successful grade update
        """
        try:
            # Refresh the object to get calculated fields
            self.object.refresh_from_db()
            
            # Check for significant changes
            score_changed = self._detect_score_changes(original_scores, new_scores)
            grade_changed = original_scores['ges_grade'] != self.object.ges_grade
            
            # Log the update
            self._log_grade_update(original_scores, score_changed, grade_changed)
            
            # Send notifications if changes occurred
            if score_changed or grade_changed:
                self._send_notifications(score_changed, grade_changed)
                
                # Update analytics cache
                self._update_analytics_cache()
                
                messages.success(
                    self.request, 
                    'Grade updated successfully. ' +
                    ('Notifications sent.' if score_changed else '')
                )
            else:
                messages.info(self.request, 'Grade saved with no changes to scores.')
                
        except Exception as e:
            logger.error(f"Post-save operations failed: {str(e)}", exc_info=True)
            # Don't raise exception here as the grade was already saved successfully
            messages.warning(self.request, 'Grade updated but some follow-up operations failed.')

    def _detect_score_changes(self, original_scores, new_scores):
        """
        Detect if any scores have actually changed
        """
        for score_type in ['homework', 'classwork', 'test', 'exam']:
            original = str(original_scores[score_type])
            new = str(new_scores.get(f"{score_type}_score", 0))
            if original != new:
                return True
        return False

    def _log_grade_update(self, original_scores, score_changed, grade_changed):
        """
        Log grade update for audit purposes
        """
        try:
            changes = {}
            if score_changed:
                for score_type in ['homework', 'classwork', 'test', 'exam']:
                    original = original_scores[score_type]
                    new = getattr(self.object, f"{score_type}_score")
                    if str(original) != str(new):
                        changes[f"{score_type}_score"] = {
                            'from': float(original) if original else 0,
                            'to': float(new) if new else 0
                        }
            
            if grade_changed:
                changes['ges_grade'] = {
                    'from': original_scores['ges_grade'],
                    'to': self.object.ges_grade
                }
            
            AuditLog.objects.create(
                user=self.request.user,
                action='UPDATE',
                model_name='Grade',
                object_id=self.object.id,
                details={
                    'changes': changes,
                    'student_id': self.object.student.id,
                    'subject_id': self.object.subject.id,
                    'academic_year': self.object.academic_year,
                    'term': self.object.term
                },
                ip_address=self._get_client_ip()
            )
            
            logger.info(
                f"Grade update logged - Grade ID: {self.object.id}, "
                f"Student: {self.object.student}, Changes: {len(changes)}"
            )
            
        except Exception as e:
            logger.error(f"Failed to log grade update: {str(e)}")

    def _get_client_ip(self):
        """
        Get client IP address for audit logging
        """
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip

    def _send_notifications(self, score_changed, grade_changed):
        """
        Send appropriate notifications based on changes
        """
        try:
            if score_changed:
                self._send_grade_update_notification()
            
            if grade_changed:
                self._send_grade_change_notification()
            
            # Notify administrators for significant changes
            if self._is_significant_change():
                self._notify_administrators()
                
        except Exception as e:
            logger.error(f"Notification sending failed: {str(e)}")
            raise NotificationException(f"Failed to send notifications: {str(e)}")

    def _send_grade_update_notification(self):
        """
        Send notification to student about grade update
        """
        try:
            student = self.object.student
            subject = self.object.subject
            
            notification_data = {
                'type': 'send_notification',
                'notification_type': 'GRADE_UPDATE',
                'title': 'Grade Updated',
                'message': f'Your {subject.name} grade has been updated',
                'related_object_id': self.object.id,
                'timestamp': timezone.now().isoformat(),
                'icon': 'bi-journal-check',
                'color': 'info',
                'action_url': self._get_grade_detail_url()
            }
            
            self._send_websocket_notification(
                f'notifications_{student.user.id}',
                notification_data
            )
            
            logger.info(f"Grade update notification sent to student {student.student_id}")
            
        except Exception as e:
            logger.error(f"Failed to send grade update notification: {str(e)}")
            raise

    def _send_grade_change_notification(self):
        """
        Send notification about grade letter change
        """
        try:
            student = self.object.student
            
            notification_data = {
                'type': 'send_notification',
                'notification_type': 'GRADE_CHANGE',
                'title': 'Grade Level Changed',
                'message': f'Your {self.object.subject.name} grade level has changed to {self.object.get_ges_grade_display()}',
                'related_object_id': self.object.id,
                'timestamp': timezone.now().isoformat(),
                'icon': 'bi-graph-up',
                'color': 'warning' if self.object.ges_grade in ['7', '8', '9'] else 'success',
                'action_url': self._get_grade_detail_url()
            }
            
            self._send_websocket_notification(
                f'notifications_{student.user.id}',
                notification_data
            )
            
        except Exception as e:
            logger.error(f"Failed to send grade change notification: {str(e)}")

    def _notify_administrators(self):
        """
        Notify administrators about significant grade changes
        """
        try:
            if not is_teacher(self.request.user):
                return  # Only notify when teachers make changes
            
            admins = User.objects.filter(
                Q(is_superuser=True) | Q(is_staff=True)
            ).distinct()
            
            notification_data = {
                'type': 'send_notification',
                'notification_type': 'GRADE_MODIFIED',
                'title': 'Grade Modified by Teacher',
                'message': f'{self.request.user.get_full_name()} updated grade for {self.object.student.get_full_name()} in {self.object.subject.name}',
                'related_object_id': self.object.id,
                'timestamp': timezone.now().isoformat(),
                'icon': 'bi-shield-check',
                'color': 'warning',
                'action_url': self.get_success_url()
            }
            
            for admin in admins:
                self._send_websocket_notification(
                    f'notifications_{admin.id}',
                    notification_data
                )
            
            logger.info(f"Admin notifications sent for grade update - Grade ID: {self.object.id}")
            
        except Exception as e:
            logger.error(f"Failed to send admin notifications: {str(e)}")

    def _send_websocket_notification(self, group_name, notification_data):
        """
        Send WebSocket notification with error handling
        """
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                group_name,
                notification_data
            )
        except Exception as e:
            logger.error(f"WebSocket notification failed for group {group_name}: {str(e)}")
            raise NotificationException(f"WebSocket notification failed: {str(e)}")

    def _is_significant_change(self):
        """
        Determine if the change is significant enough for admin notification
        """
        # Implement logic for significant changes
        # Example: grade change from passing to failing or vice versa
        try:
            original_grade = Grade.objects.get(pk=self.object.pk)
            was_passing = original_grade.is_passing()
            is_passing_now = self.object.is_passing()
            
            return was_passing != is_passing_now
        except Exception as e:
            logger.warning(f"Error determining significant change: {str(e)}")
            return False

    def _update_analytics_cache(self):
        """
        Update analytics cache after grade changes
        """
        try:
            from django.core.cache import cache
            
            # Clear relevant cache keys
            cache_keys_to_clear = [
                f"class_performance_{self.object.subject.id}_{self.object.student.class_level}_{self.object.academic_year}_{self.object.term}",
                f"student_progress_{self.object.student.id}_{self.object.academic_year}",
                f"term_report_{self.object.student.class_level}_{self.object.academic_year}_{self.object.term}"
            ]
            
            for cache_key in cache_keys_to_clear:
                cache.delete(cache_key)
            
            logger.debug(f"Analytics cache cleared for grade update - Grade ID: {self.object.id}")
            
        except Exception as e:
            logger.warning(f"Failed to update analytics cache: {str(e)}")

    def _get_grade_detail_url(self):
        """
        Get URL for grade detail page (if available)
        """
        try:
            return reverse_lazy('grade_detail', kwargs={'pk': self.object.pk})
        except:
            return self.get_success_url()

    def form_invalid(self, form):
        """
        Enhanced form invalid handling with better error reporting
        """
        logger.warning(
            f"Grade update form invalid - User: {self.request.user}, "
            f"Errors: {form.errors}"
        )
        
        # Add generic error message if no specific field errors
        if not form.errors:
            messages.error(self.request, "Please correct the errors below.")
        
        return super().form_invalid(form)

    def get_context_data(self, **kwargs):
        """
        Enhanced context with additional information for the template
        """
        context = super().get_context_data(**kwargs)
        
        try:
            context.update({
                'student': self.object.student,
                'subject': self.object.subject,
                'is_teacher': is_teacher(self.request.user),
                'academic_year': self.object.academic_year,
                'term': self.object.term,
                'can_edit': self._can_edit_grade(),
                'grade_history': self._get_grade_history(),
                'max_scores': {
                    'classwork': 30,
                    'homework': 10,
                    'test': 10,
                    'exam': 50
                }
            })
        except Exception as e:
            logger.error(f"Error preparing context data: {str(e)}")
            # Ensure basic context is still available
            context.update({
                'student': getattr(self.object, 'student', None),
                'subject': getattr(self.object, 'subject', None),
                'is_teacher': is_teacher(self.request.user)
            })
        
        return context

    def _can_edit_grade(self):
        """
        Check if the grade can still be edited (not locked, etc.)
        """
        try:
            return not self._is_term_locked(self.object.academic_year, self.object.term)
        except:
            return True

    def _get_grade_history(self):
        """
        Get grade history for context (optional)
        """
        try:
            return AuditLog.objects.filter(
                object_id=self.object.id,
                model_name='Grade'
            ).order_by('-timestamp')[:5]
        except:
            return []

    def get_success_url(self):
        """
        Determine success URL with optional redirect parameter
        """
        try:
            # Allow redirect back to referring page if available
            redirect_to = self.request.GET.get('next') or self.request.POST.get('next')
            if redirect_to and redirect_to.startswith('/'):
                return redirect_to
        except:
            pass
        
        return super().get_success_url()

class GradeDetailView(TwoFactorLoginRequiredMixin, UserPassesTestMixin, DetailView):
    """Grade Detail View for viewing individual grade records"""
    model = Grade
    template_name = 'core/academics/grades/grade_detail.html'
    context_object_name = 'grade'

    def test_func(self):
        """Permission check for viewing grade details"""
        user = self.request.user
        grade = self.get_object()
        
        if user.is_superuser or is_admin(user):
            return True
        
        if is_teacher(user):
            # Teachers can view grades for their classes
            return ClassAssignment.objects.filter(
                teacher=user.teacher,
                class_level=grade.student.class_level,
                subject=grade.subject
            ).exists()
        
        if is_student(user):
            # Students can only view their own grades
            return user.student == grade.student
        
        return False

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        grade = self.get_object()
    
        context.update({
            'student': grade.student,
            'subject': grade.subject,
            'can_edit': self.request.user.is_superuser or is_admin(self.request.user),
            'score_breakdown': {
                'classwork': grade.classwork_score,
                'homework': grade.homework_score,
                'test': grade.test_score,
                'exam': grade.exam_score,
            },
            'performance_level': grade.get_performance_level_display(),  # Use the model method
        })
        return context


    def get_performance_level(self, score):
        """Get performance level category"""
        if score >= 80: return 'Excellent'
        elif score >= 70: return 'Very Good'
        elif score >= 60: return 'Good'
        elif score >= 50: return 'Satisfactory' 
        elif score >= 40: return 'Fair'
        else: return 'Poor'

class BulkGradeUploadView(TwoFactorLoginRequiredMixin, UserPassesTestMixin, View):
    template_name = 'core/academics/grades/bulk_grade_upload.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get(self, request):
        """Handle GET request with proper form initialization"""
        try:
            form = BulkGradeUploadForm(request=request)
            return render(request, self.template_name, {'form': form})
        except Exception as e:
            logger.error(f"Error loading bulk upload form: {str(e)}", exc_info=True)
            messages.error(request, 'Error loading upload form. Please try again.')
            return redirect('grade_list')
    
    @transaction.atomic
    def post(self, request):
        """Handle file upload with comprehensive error handling"""
        form = BulkGradeUploadForm(request.POST, request.FILES, request=request)
        
        if not form.is_valid():
            return render(request, self.template_name, {'form': form})
        
        try:
            result = self.process_uploaded_file(
                form.cleaned_data['file'],
                form.cleaned_data['assignment'],
                form.cleaned_data['term']
            )
            
            self.handle_upload_result(request, result)
            return redirect('grade_list')
            
        except Exception as e:
            logger.error(f"Bulk grade upload failed: {str(e)}", exc_info=True)
            messages.error(request, 'Failed to process uploaded file. Please check the format and try again.')
            return render(request, self.template_name, {'form': form})
    
    def process_uploaded_file(self, file, assignment, term):
        """Process uploaded file with validation"""
        success_count = 0
        error_messages = []
        
        file_extension = file.name.split('.')[-1].lower()
        
        try:
            if file_extension == 'csv':
                result = self.process_csv_file(file, assignment, term)
            elif file_extension in ['xlsx', 'xls']:
                result = self.process_excel_file(file, assignment, term)
            else:
                raise ValidationError("Unsupported file format. Please upload CSV or Excel files.")
            
            return result
            
        except Exception as e:
            logger.error(f"File processing error: {str(e)}", exc_info=True)
            raise ValidationError(f"Error processing file: {str(e)}")
    
    def process_csv_file(self, file, assignment, term):
        """Process CSV file with proper encoding handling"""
        success_count = 0
        error_messages = []
        
        try:
            # Try different encodings
            for encoding in ['utf-8', 'latin-1', 'cp1252']:
                try:
                    decoded_file = file.read().decode(encoding).splitlines()
                    reader = csv.DictReader(decoded_file)
                    break
                except UnicodeDecodeError:
                    continue
            else:
                raise ValidationError("Unable to decode file. Please use UTF-8 encoding.")
            
            for row_num, row in enumerate(reader, 2):
                try:
                    self.process_grade_row(row, assignment, term)
                    success_count += 1
                except Exception as e:
                    error_messages.append(f"Row {row_num}: {str(e)}")
            
            return {'success_count': success_count, 'error_messages': error_messages}
            
        except Exception as e:
            logger.error(f"CSV processing failed: {str(e)}", exc_info=True)
            raise
    
    def process_excel_file(self, file, assignment, term):
        """Process Excel file with error handling"""
        success_count = 0
        error_messages = []
        
        try:
            wb = load_workbook(filename=BytesIO(file.read()))
            sheet = wb.active
            
            if sheet.max_row < 2:
                raise ValidationError("Excel file must contain data rows.")
            
            headers = [cell.value for cell in sheet[1]]
            required_headers = ['student_id', 'score']
            
            for required in required_headers:
                if required not in [h.lower() for h in headers]:
                    raise ValidationError(f"Missing required column: {required}")
            
            for row_num, row in enumerate(sheet.iter_rows(min_row=2), 2):
                try:
                    row_data = dict(zip(headers, [cell.value for cell in row]))
                    self.process_grade_row(row_data, assignment, term)
                    success_count += 1
                except Exception as e:
                    error_messages.append(f"Row {row_num}: {str(e)}")
            
            return {'success_count': success_count, 'error_messages': error_messages}
            
        except Exception as e:
            logger.error(f"Excel processing failed: {str(e)}", exc_info=True)
            raise
    
    def process_grade_row(self, row, assignment, term):
        """Process individual grade row with validation"""
        try:
            # Normalize column names
            row = {k.lower().strip(): v for k, v in row.items() if k is not None}
            
            # Validate required fields
            student_id = row.get('student_id') or row.get('student id')
            if not student_id:
                raise ValueError("Missing student ID")
            
            # Get student with validation
            try:
                student = Student.objects.get(student_id=str(student_id).strip())
            except Student.DoesNotExist:
                raise ValueError(f"Student with ID '{student_id}' not found")
            except Student.MultipleObjectsReturned:
                raise ValueError(f"Multiple students found with ID '{student_id}'")
            
            # Validate score
            score_str = row.get('score')
            if not score_str:
                raise ValueError("Missing score")
            
            try:
                score = float(score_str)
                if score < 0 or score > assignment.max_score:
                    raise ValueError(f"Score {score} is outside valid range (0-{assignment.max_score})")
            except (ValueError, TypeError):
                raise ValueError(f"Invalid score format: '{score_str}'. Must be a number.")
            
            # Process the grade
            self.create_or_update_grade(student, assignment, term, score)
            
        except Exception as e:
            logger.warning(f"Grade row processing failed: {str(e)}")
            raise
    
    def create_or_update_grade(self, student, assignment, term, score):
        """Create or update grade record atomically"""
        academic_year = assignment.class_assignment.academic_year.replace('-', '/')
        
        # Update or create Grade record
        grade, created = Grade.objects.update_or_create(
            student=student,
            subject=assignment.subject,
            class_assignment=assignment.class_assignment,
            academic_year=academic_year,
            term=term,
            defaults=self.get_grade_defaults(assignment, score)
        )
        
        # Update student assignment
        StudentAssignment.objects.update_or_create(
            student=student,
            assignment=assignment,
            defaults={
                'score': score,
                'status': 'GRADED',
                'graded_at': timezone.now()
            }
        )
    
    def get_grade_defaults(self, assignment, score):
        """Get default values for grade based on assignment type"""
        score_field = f"{assignment.assignment_type.lower()}_score"
        defaults = {
            'homework_score': 0,
            'classwork_score': 0,
            'test_score': 0,
            'exam_score': 0,
        }
        defaults[score_field] = score
        return defaults
    
    def handle_upload_result(self, request, result):
        """Handle upload results and display appropriate messages"""
        if result['success_count'] > 0:
            messages.success(
                request, 
                f'Successfully processed {result["success_count"]} grade records.'
            )
        
        if result['error_messages']:
            # Show first 5 errors
            for msg in result['error_messages'][:5]:
                messages.warning(request, msg)
            
            if len(result['error_messages']) > 5:
                messages.warning(
                    request, 
                    f'... and {len(result["error_messages"]) - 5} more errors. '
                    'Please check the file format and try again.'
                )
            
            messages.info(
                request,
                'Some records could not be processed. Please correct the errors and try again.'
            )

class GradeUploadTemplateView(View):
    def get(self, request):
        # Create a CSV file in memory
        buffer = StringIO()
        writer = csv.writer(buffer)
        
        # Write header row
        writer.writerow(['student_id', 'score'])
        
        # Create the response
        response = HttpResponse(buffer.getvalue(), content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="grade_upload_template.csv"'
        return response

# In core/views/grade_views.py - Update GradeEntryView

# In core/views/grade_views.py - Update GradeEntryView

# In grade_views.py - Update GradeEntryView class
class GradeEntryView(TwoFactorLoginRequiredMixin, UserPassesTestMixin, CreateView):
    model = Grade
    form_class = GradeEntryForm
    template_name = 'core/academics/grades/grade_entry.html'
    success_url = reverse_lazy('grade_list')

    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)

    def get_initial(self):
        """Set initial data based on GET parameters with class level auto-matching"""
        initial = super().get_initial()
        student_id = self.request.GET.get('student')
        subject_id = self.request.GET.get('subject')
        
        print(f"DEBUG GradeEntryView: GET params - student: {student_id}, subject: {subject_id}")
        
        if student_id:
            try:
                student = Student.objects.get(pk=student_id)
                initial['student'] = student
                # CRITICAL: Auto-set class level to match student's actual class
                initial['class_level'] = student.class_level
                print(f"DEBUG: Auto-setting class level to {student.class_level} for student {student.get_full_name()}")
                
                # Set current academic year if not provided
                current_year = timezone.now().year
                initial['academic_year'] = f"{current_year}/{current_year + 1}"
                initial['term'] = 1  # Default to first term
                
            except (Student.DoesNotExist, ValueError) as e:
                print(f"DEBUG: Error loading student {student_id}: {e}")
                messages.warning(self.request, 'Selected student not found.')
        
        if subject_id:
            try:
                subject = Subject.objects.get(pk=subject_id)
                initial['subject'] = subject
                print(f"DEBUG: Setting subject to {subject.name}")
            except (Subject.DoesNotExist, ValueError) as e:
                print(f"DEBUG: Error loading subject {subject_id}: {e}")
        
        return initial

    def get_form_kwargs(self):
        """Add user and ensure proper initial data"""
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        
        # Ensure initial data is passed correctly for GET requests
        if self.request.method == 'GET':
            initial = self.get_initial()
            kwargs['initial'] = initial
            print(f"DEBUG: Form kwargs initial - {initial}")
        
        return kwargs

    def get_context_data(self, **kwargs):
        """Enhanced context with student and subject information"""
        context = super().get_context_data(**kwargs)
        
        # Get selected student and subject for template context
        student_id = self.request.GET.get('student')
        subject_id = self.request.GET.get('subject')
        
        selected_student = None
        selected_subject = None
        
        if student_id:
            try:
                selected_student = Student.objects.get(pk=student_id)
                print(f"DEBUG: Context - selected_student: {selected_student}")
            except Student.DoesNotExist:
                pass
        
        if subject_id:
            try:
                selected_subject = Subject.objects.get(pk=subject_id)
                print(f"DEBUG: Context - selected_subject: {selected_subject}")
            except Subject.DoesNotExist:
                pass
        
        # Get available subjects based on user role for template display
        if is_teacher(self.request.user):
            teacher = self.request.user.teacher
            try:
                class_assignments = ClassAssignment.objects.filter(
                    teacher=teacher,
                    is_active=True
                ).select_related('subject')
                
                subject_ids = class_assignments.values_list('subject_id', flat=True).distinct()
                
                available_subjects = Subject.objects.filter(
                    id__in=subject_ids,
                    is_active=True
                ).distinct().order_by('name')
                
                # Fallbacks if no subjects found
                if not available_subjects.exists():
                    available_subjects = teacher.subjects.filter(is_active=True).order_by('name')
                
                if not available_subjects.exists():
                    available_subjects = Subject.objects.filter(is_active=True).order_by('name')
                    
            except Exception as e:
                print(f"DEBUG GradeEntryView: Error getting available subjects: {e}")
                available_subjects = Subject.objects.filter(is_active=True).order_by('name')
        else:
            available_subjects = Subject.objects.filter(is_active=True).order_by('name')
        
        # Get students based on user role for template context
        if is_teacher(self.request.user):
            teacher_classes = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher,
                is_active=True
            ).values_list('class_level', flat=True).distinct()
            
            students = Student.objects.filter(
                class_level__in=teacher_classes, 
                is_active=True
            ).order_by('last_name', 'first_name')
        else:
            students = Student.objects.filter(is_active=True).order_by('last_name', 'first_name')
        
        context.update({
            'selected_student': selected_student,
            'selected_subject': selected_subject,
            'available_subjects': available_subjects,
            'students': students,
            'class_levels': CLASS_LEVEL_CHOICES,
            'is_teacher': is_teacher(self.request.user),
            'is_admin': is_admin(self.request.user),
        })
        
        print(f"DEBUG GradeEntryView: Available subjects count: {available_subjects.count()}")
        print(f"DEBUG GradeEntryView: Students count: {students.count()}")
        print(f"DEBUG GradeEntryView: Selected student: {selected_student}")
        print(f"DEBUG GradeEntryView: Selected subject: {selected_subject}")
                
        return context

    @transaction.atomic
    def form_valid(self, form):
        """
        Handle form validation with class level enforcement
        """
        try:
            # CRITICAL: Double-check that class level matches student's class
            student = form.cleaned_data.get('student')
            selected_class_level = form.cleaned_data.get('class_level')
            
            if student and selected_class_level and student.class_level != selected_class_level:
                print(f"DEBUG: Class level mismatch detected! Student: {student.class_level}, Selected: {selected_class_level}")
                form.add_error('class_level', 
                    f'Class level must match student\'s current class ({student.get_class_level_display()})')
                return self.form_invalid(form)
            
            # Force class level to match student (safety measure)
            if student:
                form.instance.class_level = student.class_level
                print(f"DEBUG: Ensuring class level is set to {student.class_level} for student {student.get_full_name()}")
            
            # Set recorded_by user
            form.instance.recorded_by = self.request.user
            
            # Let the form handle class assignment creation and grade calculation
            response = super().form_valid(form)
            
            # Success message with details
            messages.success(
                self.request, 
                f'✅ Grade successfully recorded for {self.object.student.get_full_name()}! '
                f'Total Score: {self.object.total_score} - {self.object.get_ges_grade_display()} '
                f'({self.object.subject.name}, {self.object.academic_year} Term {self.object.term})'
            )
            
            # Log the creation
            self._log_grade_creation()
            
            return response
            
        except Exception as e:
            print(f"DEBUG GradeEntryView: Error saving grade: {str(e)}")
            logger.error(f"Error saving grade: {str(e)}", exc_info=True)
            messages.error(self.request, 
                'Error saving grade. Please check that all information is correct and try again.')
            return self.form_invalid(form)

    def form_invalid(self, form):
        """Enhanced form invalid handling with specific error messages"""
        print(f"DEBUG GradeEntryView: Form invalid - Errors: {form.errors}")
        logger.warning(f"Grade entry form invalid - Errors: {form.errors}")
        
        # Add specific error messages for common issues
        if 'class_level' in form.errors:
            messages.error(self.request, 
                "Class level error. Please ensure the class level matches the student's current class.")
        elif 'student' in form.errors:
            messages.error(self.request, 
                "Student selection error. Please verify the student exists and is active.")
        elif 'subject' in form.errors:
            messages.error(self.request, 
                "Subject selection error. Please verify the subject is available for this class level.")
        elif any(field in form.errors for field in ['classwork_score', 'homework_score', 'test_score', 'exam_score']):
            messages.error(self.request, 
                "Please check the score values. They must be within the allowed ranges.")
        elif '__all__' in form.errors:
            # Show non-field errors
            for error in form.errors['__all__']:
                messages.error(self.request, error)
        else:
            messages.error(self.request, "Please correct the errors below.")
        
        return super().form_invalid(form)

    def _log_grade_creation(self):
        """Log grade creation for audit purposes"""
        try:
            AuditLog.objects.create(
                user=self.request.user,
                action='CREATE',
                model_name='Grade',
                object_id=self.object.id,
                details={
                    'student_id': self.object.student.id,
                    'student_name': self.object.student.get_full_name(),
                    'subject_id': self.object.subject.id,
                    'subject_name': self.object.subject.name,
                    'class_level': self.object.class_level,
                    'academic_year': self.object.academic_year,
                    'term': self.object.term,
                    'total_score': float(self.object.total_score) if self.object.total_score else 0,
                    'ges_grade': self.object.ges_grade,
                    'score_breakdown': {
                        'classwork': float(self.object.classwork_score) if self.object.classwork_score else 0,
                        'homework': float(self.object.homework_score) if self.object.homework_score else 0,
                        'test': float(self.object.test_score) if self.object.test_score else 0,
                        'exam': float(self.object.exam_score) if self.object.exam_score else 0,
                    },
                    'created_by': self.request.user.get_full_name()
                },
                ip_address=self._get_client_ip()
            )
            print(f"DEBUG: Grade creation logged for {self.object.student.get_full_name()}")
            
        except Exception as e:
            print(f"DEBUG: Failed to log grade creation: {str(e)}")
            logger.error(f"Failed to log grade creation: {str(e)}")

    def _get_client_ip(self):
        """Get client IP address for audit logging"""
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip
    

class GradeReportView(TwoFactorLoginRequiredMixin, UserPassesTestMixin, TemplateView):
    template_name = 'core/academics/grades/grade_report.html'
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get filter parameters
        subject_id = self.request.GET.get('subject')
        class_level = self.request.GET.get('class_level')
        academic_year = self.request.GET.get('academic_year')
        term = self.request.GET.get('term')
        
        # Get available filter options
        if is_teacher(self.request.user):
            context['subjects'] = self.request.user.teacher.subjects.all()
            context['class_levels'] = ClassAssignment.objects.filter(
                teacher=self.request.user.teacher
            ).values_list('class_level', flat=True).distinct()
        else:
            context['subjects'] = Subject.objects.all()
            context['class_levels'] = CLASS_LEVEL_CHOICES
        
        # Apply filters if provided
        if subject_id and class_level and academic_year and term:
            subject = get_object_or_404(Subject, pk=subject_id)
            
            # Get grades
            grades = Grade.objects.filter(
                subject=subject,
                student__class_level=class_level,
                academic_year=academic_year,
                term=term
            ).select_related('student').order_by('student__last_name')
            
            # Calculate statistics
            class_average = grades.aggregate(Avg('total_score'))['total_score__avg']
            grade_distribution = grades.values('ges_grade').annotate(
                count=Count('id'),
                percentage=ExpressionWrapper(
                    Count('id') * 100.0 / grades.count(),
                    output_field=FloatField()
                )
            ).order_by('ges_grade')
            
            passing_rate = grades.filter(total_score__gte=50).count() / grades.count() * 100 if grades.count() > 0 else 0
            
            context.update({
                'selected_subject': subject,
                'selected_class_level': class_level,
                'selected_academic_year': academic_year,
                'selected_term': term,
                'grades': grades,
                'class_average': class_average,
                'grade_distribution': grade_distribution,
                'passing_rate': passing_rate,
                'show_results': True
            })
        
        return context

class BestStudentsView(TwoFactorLoginRequiredMixin, TemplateView):
    template_name = 'core/academics/grades/best_students.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get current academic year
        current_year = timezone.now().year
        academic_year = f"{current_year}/{current_year + 1}"
        
        # Get top students by average grade
        top_students = Student.objects.annotate(
            avg_grade=Avg('grade__total_score')
        ).filter(
            grade__academic_year=academic_year,
            is_active=True
        ).order_by('-avg_grade')[:10]
        
        context.update({
            'top_students': top_students,
            'current_year': current_year,
            'academic_year': academic_year
        })
        return context

class GradeDeleteView(TwoFactorLoginRequiredMixin, AdminRequiredMixin, AuditLogMixin, DeleteView):
    """
    Enhanced Grade Delete View with comprehensive error handling,
    transaction safety, audit logging, and professional UI integration.
    """
    model = Grade
    template_name = 'core/academics/grades/grade_confirm_delete.html'
    success_url = reverse_lazy('grade_list')
    success_message = "Grade record deleted successfully."
    error_message = "Failed to delete grade record. Please try again."

    def dispatch(self, request, *args, **kwargs):
        """
        Override dispatch to handle all exceptions at the entry point
        """
        try:
            return super().dispatch(request, *args, **kwargs)
        except Http404:
            logger.warning(f"Grade not found for deletion - User: {request.user}, Grade ID: {kwargs.get('pk')}")
            messages.error(request, "The requested grade record does not exist or has been deleted.")
            return redirect('grade_list')
        except PermissionDenied:
            logger.warning(f"Permission denied for grade deletion - User: {request.user}")
            messages.error(request, "You don't have permission to delete this grade.")
            return redirect('grade_list')
        except Exception as e:
            logger.error(f"Unexpected error in grade delete dispatch: {str(e)}", exc_info=True)
            messages.error(request, "An unexpected error occurred. Please try again.")
            return redirect('grade_list')

    def get_object(self, queryset=None):
        """
        Safely retrieve the grade object with comprehensive error handling
        """
        try:
            if queryset is None:
                queryset = self.get_queryset()
            
            # Use select_related to optimize database queries
            queryset = queryset.select_related(
                'student', 
                'subject', 
                'class_assignment',
                'student__user',
                'recorded_by'
            )
            
            obj = super().get_object(queryset)
            
            # Additional validation for the retrieved object
            self._validate_grade_object(obj)
            
            logger.info(f"Grade object retrieved for deletion - ID: {obj.id}, Student: {obj.student}")
            return obj
            
        except Http404:
            logger.error(
                f"Grade not found for deletion - PK: {self.kwargs.get('pk')}, "
                f"User: {self.request.user}, URL: {self.request.path}"
            )
            messages.error(self.request, "The requested grade record was not found.")
            raise
        except ValidationError as e:
            logger.error(f"Grade validation failed for deletion: {str(e)}")
            messages.error(self.request, f"Cannot delete grade: {str(e)}")
            raise Http404("Invalid grade data")
        except Exception as e:
            logger.error(f"Unexpected error retrieving grade for deletion: {str(e)}", exc_info=True)
            messages.error(self.request, "Error loading grade record. Please try again.")
            raise Http404("Error loading grade")

    def _validate_grade_object(self, grade):
        """
        Validate the grade object before proceeding with deletion
        """
        if not grade.student.is_active:
            raise ValidationError("Cannot delete grade for inactive student")
        
        if not grade.subject.is_active:
            raise ValidationError("Cannot delete grade for inactive subject")
        
        # Check if the academic term is locked
        if self._is_term_locked(grade.academic_year, grade.term):
            raise ValidationError("Cannot delete grades for locked academic term")
        
        # Check if grade is part of a published report card
        if self._is_grade_published(grade):
            raise ValidationError("Cannot delete grade that is part of a published report card")
        
        # Check if grade is locked
        if grade.is_locked:
            raise ValidationError("Cannot delete a locked grade record")

    def _is_term_locked(self, academic_year, term):
        """
        Check if the academic term is locked for editing
        """
        try:
            term_obj = AcademicTerm.objects.filter(
                academic_year=academic_year,
                term=term
            ).first()
            
            if term_obj and hasattr(term_obj, 'is_locked'):
                return term_obj.is_locked
                
            return False
            
        except Exception as e:
            logger.warning(f"Error checking term lock status: {str(e)}")
            return True  # Default to locked if there's an error

    def _is_grade_published(self, grade):
        """
        Check if grade is part of a published report card
        """
        try:
            return ReportCard.objects.filter(
                student=grade.student,
                academic_year=grade.academic_year,
                term=grade.term,
                is_published=True
            ).exists()
        except Exception as e:
            logger.warning(f"Error checking if grade is published: {str(e)}")
            return True  # Default to published if there's an error

    def get_queryset(self):
        """
        Optimize queryset based on user role and permissions
        """
        queryset = super().get_queryset()
        
        # Admins can see all grades, but apply basic filters
        return queryset.filter(
            student__is_active=True,
            subject__is_active=True
        ).select_related(
            'student', 'subject', 'class_assignment', 'recorded_by'
        )

    def get_context_data(self, **kwargs):
        """
        Enhanced context with additional information for the template
        """
        context = super().get_context_data(**kwargs)
        
        try:
            grade = self.get_object()
            
            # Calculate deletion restrictions
            is_term_locked = self._is_term_locked(grade.academic_year, grade.term)
            is_grade_published = self._is_grade_published(grade)
            can_delete = not (is_term_locked or is_grade_published or grade.is_locked)
            
            context.update({
                'student': grade.student,
                'subject': grade.subject,
                'academic_year': grade.academic_year,
                'term': grade.term,
                'total_score': grade.total_score,
                'ges_grade': grade.ges_grade,
                'ges_grade_display': grade.get_ges_grade_display(),
                'can_delete': can_delete,
                'is_term_locked': is_term_locked,
                'is_grade_published': is_grade_published,
                'is_grade_locked': grade.is_locked,
                'class_level': grade.student.get_class_level_display(),
                'recorded_by': grade.recorded_by.get_full_name() if grade.recorded_by else 'System',
                'created_at': grade.created_at.strftime('%Y-%m-%d %H:%M') if grade.created_at else 'Unknown',
                'score_breakdown': grade.score_breakdown
            })
            
        except Exception as e:
            logger.error(f"Error preparing context data for deletion: {str(e)}")
            # Ensure basic context is still available
            context.update({
                'student': getattr(self.object, 'student', None),
                'subject': getattr(self.object, 'subject', None),
                'can_delete': False,
                'is_term_locked': True,
                'is_grade_published': False,
                'is_grade_locked': True,
                'ges_grade_display': 'Unknown'
            })
        
        return context

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        """
        Handle grade deletion with comprehensive transaction safety
        and audit logging
        """
        try:
            grade = self.get_object()
            
            # Get deletion reason from form
            deletion_reason = request.POST.get('deletion_reason', '').strip()
            if not deletion_reason:
                messages.error(request, "Deletion reason is required.")
                return self.render_to_response(self.get_context_data())
            
            # Validate deletion one more time
            if not self._can_delete_grade(grade):
                raise ValidationError("Grade cannot be deleted due to restrictions")
            
            # Store grade details for audit logging and notifications
            grade_details = self._get_grade_details(grade)
            
            # Perform the deletion
            response = super().delete(request, *args, **kwargs)
            
            # Send notifications and update cache
            self._handle_post_deletion_operations(grade_details, deletion_reason)
            
            messages.success(
                request, 
                self.success_message
            )
            
            logger.info(
                f"Grade deleted successfully - Grade ID: {grade_details['id']}, "
                f"Student: {grade_details['student_name']}, "
                f"Subject: {grade_details['subject_name']}, "
                f"Deleted by: {request.user.get_full_name()}"
            )
            
            return response
            
        except ValidationError as e:
            logger.warning(f"Grade deletion validation failed: {str(e)}")
            messages.error(self.request, f"Cannot delete grade: {str(e)}")
            return self.render_to_response(self.get_context_data())
        except Exception as e:
            logger.error(f"Error deleting grade: {str(e)}", exc_info=True)
            messages.error(self.request, self.error_message)
            # Transaction will be rolled back automatically
            return self.render_to_response(self.get_context_data())

    def _get_grade_details(self, grade):
        """Get comprehensive grade details for audit logging"""
        return {
            'id': grade.id,
            'student_id': grade.student.id,
            'student_name': grade.student.get_full_name(),
            'student_code': grade.student.student_id,
            'subject_id': grade.subject.id,
            'subject_name': grade.subject.name,
            'academic_year': grade.academic_year,
            'term': grade.term,
            'class_level': grade.student.class_level,
            'total_score': float(grade.total_score) if grade.total_score else 0,
            'ges_grade': grade.ges_grade,
            'ges_grade_display': grade.get_ges_grade_display(),
            'classwork_score': float(grade.classwork_score) if grade.classwork_score else 0,
            'homework_score': float(grade.homework_score) if grade.homework_score else 0,
            'test_score': float(grade.test_score) if grade.test_score else 0,
            'exam_score': float(grade.exam_score) if grade.exam_score else 0,
            'recorded_by': grade.recorded_by.get_full_name() if grade.recorded_by else 'Unknown',
            'created_at': grade.created_at.isoformat() if grade.created_at else 'Unknown',
            'updated_at': grade.updated_at.isoformat() if grade.updated_at else 'Unknown',
            'remarks': grade.remarks or ''
        }

    def _can_delete_grade(self, grade):
        """
        Check if the grade can be deleted
        """
        try:
            return not (
                self._is_term_locked(grade.academic_year, grade.term) or 
                self._is_grade_published(grade) or
                grade.is_locked
            )
        except Exception as e:
            logger.error(f"Error checking if grade can be deleted: {str(e)}")
            return False

    def _handle_post_deletion_operations(self, grade_details, deletion_reason):
        """
        Handle all operations that should occur after successful grade deletion
        """
        try:
            # Create detailed audit log
            self._create_deletion_audit_log(grade_details, deletion_reason)
            
            # Send notifications
            self._send_deletion_notifications(grade_details)
            
            # Update analytics cache
            self._update_analytics_cache(grade_details)
            
            # Update any related student assignment status if needed
            self._update_student_assignments(grade_details)
            
        except Exception as e:
            logger.error(f"Post-deletion operations failed: {str(e)}")
            # Don't raise exception here as the grade was already deleted successfully

    def _create_deletion_audit_log(self, grade_details, deletion_reason):
        """
        Create detailed audit log for grade deletion
        """
        try:
            AuditLog.objects.create(
                user=self.request.user,
                action='DELETE',
                model_name='Grade',
                object_id=grade_details['id'],
                details={
                    'deleted_grade': grade_details,
                    'deletion_reason': deletion_reason,
                    'ip_address': self._get_client_ip(),
                    'timestamp': timezone.now().isoformat(),
                    'user_agent': self.request.META.get('HTTP_USER_AGENT', ''),
                    'deleted_by': self.request.user.get_full_name(),
                    'deleted_by_username': self.request.user.username,
                    'deleted_by_role': 'Admin'
                },
                ip_address=self._get_client_ip()
            )
            
            logger.info(
                f"Grade deletion logged - Grade ID: {grade_details['id']}, "
                f"Student: {grade_details['student_name']}, "
                f"Subject: {grade_details['subject_name']}, "
                f"Reason: {deletion_reason}"
            )
            
        except Exception as e:
            logger.error(f"Failed to create deletion audit log: {str(e)}")

    def _get_client_ip(self):
        """
        Get client IP address for audit logging
        """
        x_forwarded_for = self.request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = self.request.META.get('REMOTE_ADDR')
        return ip

    def _send_deletion_notifications(self, grade_details):
        """
        Send notifications about grade deletion
        """
        try:
            # Notify administrators
            self._notify_administrators(grade_details)
            
        except Exception as e:
            logger.error(f"Deletion notification failed: {str(e)}")

    def _notify_administrators(self, grade_details):
        """
        Notify administrators about grade deletion
        """
        try:
            admins = User.objects.filter(
                Q(is_superuser=True) | Q(is_staff=True)
            ).distinct()
            
            notification_data = {
                'type': 'send_notification',
                'notification_type': 'GRADE_DELETED',
                'title': 'Grade Deleted by Administrator',
                'message': f'{self.request.user.get_full_name()} deleted grade for {grade_details["student_name"]} in {grade_details["subject_name"]}',
                'related_object_id': grade_details['id'],
                'timestamp': timezone.now().isoformat(),
                'icon': 'bi-trash',
                'color': 'danger',
                'action_url': self.get_success_url(),
                'metadata': {
                    'student_name': grade_details['student_name'],
                    'subject_name': grade_details['subject_name'],
                    'deleted_by': self.request.user.get_full_name(),
                    'academic_year': grade_details['academic_year'],
                    'term': grade_details['term']
                }
            }
            
            for admin in admins:
                self._send_websocket_notification(
                    f'notifications_{admin.id}',
                    notification_data
                )
            
            logger.info(f"Admin notifications sent for grade deletion - Grade ID: {grade_details['id']}")
            
        except Exception as e:
            logger.error(f"Failed to send admin notifications for deletion: {str(e)}")

    def _send_websocket_notification(self, group_name, notification_data):
        """
        Send WebSocket notification with error handling
        """
        try:
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                group_name,
                notification_data
            )
        except Exception as e:
            logger.error(f"WebSocket notification failed for group {group_name}: {str(e)}")

    def _update_analytics_cache(self, grade_details):
        """
        Update analytics cache after grade deletion
        """
        try:
            from django.core.cache import cache
            
            # Clear relevant cache keys
            cache_keys_to_clear = [
                f"class_performance_{grade_details['subject_id']}_{grade_details['class_level']}_{grade_details['academic_year']}_{grade_details['term']}",
                f"student_progress_{grade_details['student_id']}_{grade_details['academic_year']}",
                f"term_report_{grade_details['class_level']}_{grade_details['academic_year']}_{grade_details['term']}",
                f"subject_stats_{grade_details['subject_id']}",
                f"student_grades_{grade_details['student_id']}",
                f"teacher_dashboard_{self.request.user.id}"
            ]
            
            for cache_key in cache_keys_to_clear:
                cache.delete(cache_key)
            
            logger.debug(f"Analytics cache cleared for grade deletion - Grade ID: {grade_details['id']}")
            
        except Exception as e:
            logger.warning(f"Failed to update analytics cache after deletion: {str(e)}")

    def _update_student_assignments(self, grade_details):
        """
        Update related student assignments if needed
        """
        try:
            # If this grade was linked to specific assignments, update their status
            StudentAssignment.objects.filter(
                student_id=grade_details['student_id'],
                assignment__subject_id=grade_details['subject_id'],
                assignment__class_assignment__academic_year=grade_details['academic_year'],
                assignment__class_assignment__term=grade_details['term']
            ).update(
                status='PENDING',  # Reset status
                graded_at=None,
                score=None
            )
            
        except Exception as e:
            logger.warning(f"Failed to update student assignments after grade deletion: {str(e)}")

    def get_success_url(self):
        """
        Determine success URL with optional redirect parameter
        """
        try:
            # Allow redirect back to referring page if available
            redirect_to = self.request.GET.get('next') or self.request.POST.get('next')
            if redirect_to and redirect_to.startswith('/'):
                return redirect_to
        except:
            pass
        
        return super().get_success_url()

# Function-based view wrapper for URL compatibility
def grade_delete(request, pk):
    """
    Function-based wrapper for GradeDeleteView
    """
    return GradeDeleteView.as_view()(request, pk=pk)

# Additional utility functions for grade management
def student_grade_summary(request, student_id):
    """Get grade summary for a specific student"""
    try:
        student = get_object_or_404(Student, pk=student_id)
        grades = Grade.objects.filter(student=student).select_related('subject')
        
        summary = {
            'student': student,
            'total_subjects': grades.count(),
            'average_score': grades.aggregate(Avg('total_score'))['total_score__avg'],
            'grades_by_term': {},
        }
        
        return JsonResponse(summary)
    except Exception as e:
        logger.error(f"Error getting student grade summary: {str(e)}")
        return JsonResponse({'error': 'Unable to fetch grade summary'}, status=500)

def get_students_by_class(request):
    """Get students by class level for AJAX requests"""
    class_level = request.GET.get('class_level')
    if class_level:
        students = Student.objects.filter(
            class_level=class_level, 
            is_active=True
        ).order_by('last_name', 'first_name')
        student_list = list(students.values('id', 'first_name', 'last_name', 'student_id'))
        return JsonResponse(student_list, safe=False)
    return JsonResponse([], safe=False)

def get_subjects_by_class(request):
    """Get subjects by class level for AJAX requests"""
    class_level = request.GET.get('class_level')
    if class_level:
        subjects = Subject.objects.filter(
            classassignment__class_level=class_level,
            classassignment__is_active=True
        ).distinct().order_by('name')
        subject_list = list(subjects.values('id', 'name', 'code'))
        return JsonResponse(subject_list, safe=False)
    return JsonResponse([], safe=False)

def check_existing_grade(request):
    """Check if a grade already exists for the given parameters"""
    try:
        student_id = request.GET.get('student_id')
        subject_id = request.GET.get('subject_id')
        academic_year = request.GET.get('academic_year')
        term = request.GET.get('term')
        
        if all([student_id, subject_id, academic_year, term]):
            exists = Grade.objects.filter(
                student_id=student_id,
                subject_id=subject_id,
                academic_year=academic_year,
                term=term
            ).exists()
            
            return JsonResponse({'exists': exists})
        
        return JsonResponse({'exists': False})
    except Exception as e:
        logger.error(f"Error checking existing grade: {str(e)}")
        return JsonResponse({'exists': False})

def calculate_total_score(request):
    """Calculate total score from individual component scores"""
    try:
        classwork = float(request.GET.get('classwork', 0))
        homework = float(request.GET.get('homework', 0))
        test = float(request.GET.get('test', 0))
        exam = float(request.GET.get('exam', 0))
        
        total_score = classwork + homework + test + exam
        
        return JsonResponse({
            'total_score': total_score,
            'is_valid': total_score <= 100
        })
    except Exception as e:
        logger.error(f"Error calculating total score: {str(e)}")
        return JsonResponse({'error': 'Invalid input'}, status=400)

def lock_grade(request, pk):
    """Lock a grade to prevent further modifications"""
    try:
        grade = get_object_or_404(Grade, pk=pk)
        if request.user.is_superuser or is_admin(request.user):
            grade.is_locked = True
            grade.save()
            messages.success(request, 'Grade locked successfully.')
        else:
            messages.error(request, 'You do not have permission to lock grades.')
    except Exception as e:
        logger.error(f"Error locking grade: {str(e)}")
        messages.error(request, 'Error locking grade.')
    
    return redirect('grade_list')

def unlock_grade(request, pk):
    """Unlock a grade to allow modifications"""
    try:
        grade = get_object_or_404(Grade, pk=pk)
        if request.user.is_superuser or is_admin(request.user):
            grade.is_locked = False
            grade.save()
            messages.success(request, 'Grade unlocked successfully.')
        else:
            messages.error(request, 'You do not have permission to unlock grades.')
    except Exception as e:
        logger.error(f"Error unlocking grade: {str(e)}")
        messages.error(request, 'Error unlocking grade.')
    
    return redirect('grade_list')

def mark_grade_for_review(request, pk):
    """Mark a grade for administrative review"""
    try:
        grade = get_object_or_404(Grade, pk=pk)
        if request.user.is_superuser or is_admin(request.user) or is_teacher(request.user):
            grade.requires_review = True
            grade.save()
            messages.success(request, 'Grade marked for review.')
        else:
            messages.error(request, 'You do not have permission to mark grades for review.')
    except Exception as e:
        logger.error(f"Error marking grade for review: {str(e)}")
        messages.error(request, 'Error marking grade for review.')
    
    return redirect('grade_list')

def clear_grade_review(request, pk):
    """Clear the review flag from a grade"""
    try:
        grade = get_object_or_404(Grade, pk=pk)
        if request.user.is_superuser or is_admin(request.user):
            grade.requires_review = False
            grade.review_notes = ''
            grade.save()
            messages.success(request, 'Grade review cleared.')
        else:
            messages.error(request, 'You do not have permission to clear grade reviews.')
    except Exception as e:
        logger.error(f"Error clearing grade review: {str(e)}")
        messages.error(request, 'Error clearing grade review.')
    
    return redirect('grade_list')


# In grade_views.py - Update the CalculateGradeAPI class
class CalculateGradeAPI(TwoFactorLoginRequiredMixin, View):
    """
    API endpoint for calculating grades in real-time based on system configuration
    """
    def post(self, request):
        try:
            data = json.loads(request.body)
            
            # Calculate total score
            classwork = float(data.get('classwork_score', 0))
            homework = float(data.get('homework_score', 0)) 
            test = float(data.get('test_score', 0))
            exam = float(data.get('exam_score', 0))
            
            total_score = classwork + homework + test + exam
            
            # Get both grades
            from core.grading_utils import get_all_grades, get_grading_system, get_grade_descriptions, get_display_grade, get_grade_description
            
            grading_system = get_grading_system()
            grades = get_all_grades(total_score)
            descriptions = get_grade_descriptions()
            
            response_data = {
                'total_score': round(total_score, 1),
                'is_passing': grades['is_passing'],
                'grading_system': grading_system,
                'ges_grade': grades['ges_grade'],
                'letter_grade': grades['letter_grade'],
            }
            
            # Add display information based on active system
            response_data['display_grade'] = get_display_grade(grades['ges_grade'], grades['letter_grade'])
            response_data['grade_description'] = get_grade_description(grades['ges_grade'], grades['letter_grade'])
            response_data['performance_level'] = self.get_performance_level(total_score)
            response_data['grade_color'] = self.get_grade_color(grades['ges_grade'])
            
            return JsonResponse(response_data)
            
        except Exception as e:
            logger.error(f"Error calculating grade: {str(e)}")
            return JsonResponse({'error': 'Invalid data provided'}, status=400)
    
    def get_performance_level(self, score):
        """Get performance level category"""
        if score >= 80: return 'Excellent'
        elif score >= 70: return 'Very Good'
        elif score >= 60: return 'Good'
        elif score >= 50: return 'Satisfactory' 
        elif score >= 40: return 'Fair'
        else: return 'Poor'
    
    def get_grade_color(self, ges_grade):
        """Get color for grade display"""
        colors = {
            '1': 'success',    # Green
            '2': 'success',    # Green
            '3': 'info',       # Blue
            '4': 'info',       # Blue
            '5': 'warning',    # Yellow
            '6': 'warning',    # Yellow
            '7': 'danger',     # Red
            '8': 'danger',     # Red
            '9': 'danger',     # Red
        }
        return colors.get(ges_grade, 'secondary')



class GradeExportView(TwoFactorLoginRequiredMixin, UserPassesTestMixin, View):
    """
    Optimized Grade Export View for CSV, Excel and PDF exports with performance improvements
    """
    
    # Performance settings
    MAX_EXPORT_RECORDS = 50000
    EXCEL_BATCH_SIZE = 1000
    
    def test_func(self):
        return is_admin(self.request.user) or is_teacher(self.request.user)
    
    def get(self, request, *args, **kwargs):
        export_type = request.GET.get('export', 'csv')
        
        # Check data size before processing
        queryset = self.get_optimized_queryset(request)
        record_count = queryset.count()
        
        if record_count > self.MAX_EXPORT_RECORDS:
            messages.error(request, 
                f'Too many records ({record_count}) for export. '
                f'Please use filters to reduce the data size to under {self.MAX_EXPORT_RECORDS} records.'
            )
            return redirect('grade_list')
        
        if record_count > 10000:
            messages.warning(request, 
                f'Large export in progress ({record_count} records). '
                'This may take a few moments...'
            )
        
        if export_type == 'csv':
            return self.export_grades_csv(request)
        elif export_type == 'excel':
            return self.export_grades_excel(request)
        elif export_type == 'pdf':
            return self.export_grades_pdf(request)
        else:
            messages.error(request, 'Invalid export type')
            return redirect('grade_list')
    
    def export_grades_csv(self, request):
        """
        Optimized CSV export with better performance
        """
        try:
            from core.grading_utils import get_grading_system
            
            response = HttpResponse(
                content_type='text/csv; charset=utf-8',
            )
            
            filename = f"grades_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.csv"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            
            # BOM for UTF-8 Excel compatibility
            response.write('\ufeff')
            writer = csv.writer(response)
            
            grading_system = get_grading_system()
            
            # Simplified headers for performance
            headers = [
                'Student ID', 
                'Student Name', 
                'Class Level', 
                'Subject', 
                'Academic Year', 
                'Term', 
                'Total Score (%)'
            ]
            
            if grading_system == 'GES':
                headers.extend(['GES Grade', 'Status'])
            elif grading_system == 'LETTER':
                headers.extend(['Letter Grade', 'Status'])
            else:  # BOTH
                headers.extend(['GES Grade', 'Letter Grade', 'Status'])
            
            writer.writerow(headers)
            
            # Get optimized queryset
            grades = self.get_optimized_queryset(request)
            
            # Batch processing for memory efficiency
            batch_size = 2000
            for i in range(0, grades.count(), batch_size):
                batch = grades[i:i + batch_size]
                for grade in batch:
                    total_score = grade.total_score or 0
                    is_passing = total_score >= 40.0
                    
                    row = [
                        grade.student.student_id,
                        grade.student.get_full_name(),
                        grade.student.class_level,  # Use raw value for performance
                        grade.subject.name,
                        grade.academic_year,
                        f'Term {grade.term}',
                        f'{total_score:.1f}',
                    ]
                    
                    if grading_system == 'GES':
                        row.extend([
                            grade.ges_grade or 'N/A',
                            'PASS' if is_passing else 'FAIL'
                        ])
                    elif grading_system == 'LETTER':
                        row.extend([
                            grade.letter_grade or 'N/A',
                            'PASS' if is_passing else 'FAIL'
                        ])
                    else:  # BOTH
                        row.extend([
                            grade.ges_grade or 'N/A',
                            grade.letter_grade or 'N/A',
                            'PASS' if is_passing else 'FAIL'
                        ])
                    
                    writer.writerow(row)
            
            logger.info(f"Optimized CSV export completed - {grades.count()} records")
            return response
            
        except Exception as e:
            logger.error(f"CSV export failed: {str(e)}", exc_info=True)
            messages.error(request, 'Failed to generate CSV export. Please try again.')
            return redirect('grade_list')
    
    def export_grades_excel(self, request):
        """
        Highly optimized Excel export with performance improvements
        """
        try:
            from openpyxl import Workbook
            from openpyxl.styles import Font, Alignment, PatternFill
            from openpyxl.utils import get_column_letter
            from core.grading_utils import get_grading_system
            
            # Create workbook with optimized settings
            wb = Workbook()
            ws = wb.active
            ws.title = "Grades Export"
            
            grading_system = get_grading_system()
            
            # SIMPLIFIED HEADERS - Remove unnecessary columns
            headers = [
                'Student ID', 
                'Student Name', 
                'Class Level', 
                'Subject', 
                'Academic Year', 
                'Term', 
                'Total Score'
            ]
            
            if grading_system == 'GES':
                headers.extend(['GES Grade', 'Status'])
            elif grading_system == 'LETTER':
                headers.extend(['Letter Grade', 'Status'])
            else:  # BOTH
                headers.extend(['GES Grade', 'Letter Grade', 'Status'])
            
            # Write headers with basic styling
            for col, header in enumerate(headers, 1):
                cell = ws.cell(row=1, column=col, value=header)
                cell.font = Font(bold=True)
                cell.fill = PatternFill(start_color="366092", end_color="366092", fill_type="solid")
                cell.alignment = Alignment(horizontal="center")
            
            # Get OPTIMIZED queryset
            grades = self.get_optimized_queryset(request)
            
            # Batch processing to avoid memory issues
            row_num = 2
            batch_size = self.EXCEL_BATCH_SIZE
            
            for i in range(0, grades.count(), batch_size):
                batch = grades[i:i + batch_size]
                
                for grade in batch:
                    total_score = grade.total_score or 0
                    is_passing = total_score >= 40.0
                    
                    # Minimal data collection
                    row_data = [
                        grade.student.student_id,
                        grade.student.get_full_name(),
                        grade.student.class_level,  # Raw value for performance
                        grade.subject.name,
                        grade.academic_year,
                        f'Term {grade.term}',
                        float(total_score),
                    ]
                    
                    if grading_system == 'GES':
                        row_data.extend([
                            grade.ges_grade or 'N/A',
                            'PASS' if is_passing else 'FAIL'
                        ])
                    elif grading_system == 'LETTER':
                        row_data.extend([
                            grade.letter_grade or 'N/A',
                            'PASS' if is_passing else 'FAIL'
                        ])
                    else:  # BOTH
                        row_data.extend([
                            grade.ges_grade or 'N/A',
                            grade.letter_grade or 'N/A',
                            'PASS' if is_passing else 'FAIL'
                        ])
                    
                    # Write row without individual cell styling for performance
                    for col, value in enumerate(row_data, 1):
                        ws.cell(row=row_num, column=col, value=value)
                    
                    row_num += 1
                
                # Log progress for large exports
                if i % 5000 == 0 and i > 0:
                    logger.info(f"Excel export progress: {i} records processed")
            
            # Apply basic formatting to entire columns (more efficient)
            status_col = len(headers)  # Last column is status
            
            # Format status column
            for row in range(2, row_num):
                cell = ws.cell(row=row, column=status_col)
                if cell.value == 'PASS':
                    cell.fill = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid")
                    cell.font = Font(color="155724", bold=True)
                else:
                    cell.fill = PatternFill(start_color="F8D7DA", end_color="F8D7DA", fill_type="solid")
                    cell.font = Font(color="721C24", bold=True)
            
            # Format total score column
            total_score_col = 7  # Column G
            for row in range(2, row_num):
                cell = ws.cell(row=row, column=total_score_col)
                if isinstance(cell.value, (int, float)):
                    cell.number_format = '0.00'
                    if cell.value >= 80:
                        cell.fill = PatternFill(start_color="E6F3FF", end_color="E6F3FF", fill_type="solid")
                    elif cell.value >= 60:
                        cell.fill = PatternFill(start_color="F0FFF0", end_color="F0FFF0", fill_type="solid")
                    elif cell.value >= 40:
                        cell.fill = PatternFill(start_color="FFF9E6", end_color="FFF9E6", fill_type="solid")
                    else:
                        cell.fill = PatternFill(start_color="FFE6E6", end_color="FFE6E6", fill_type="solid")
            
            # Auto-adjust column widths (only once at the end)
            for column in ws.columns:
                max_length = 0
                column_letter = get_column_letter(column[0].column)
                for cell in column:
                    try:
                        max_length = max(max_length, len(str(cell.value)))
                    except:
                        pass
                adjusted_width = min((max_length + 2), 30)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            # Create response
            response = HttpResponse(
                content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
            )
            filename = f"grades_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            
            wb.save(response)
            
            logger.info(f"Optimized Excel export completed - {grades.count()} records")
            return response
            
        except ImportError:
            logger.error("OpenPyXL not installed for Excel export")
            messages.error(request, 'Excel export requires OpenPyXL. Please install it: pip install openpyxl')
            return redirect('grade_list')
        except Exception as e:
            logger.error(f"Excel export failed: {str(e)}", exc_info=True)
            messages.error(request, 'Failed to generate Excel export. Please try again.')
            return redirect('grade_list')
    
    def export_grades_pdf(self, request):
        """
        Optimized PDF export with performance improvements
        """
        try:
            from reportlab.lib.pagesizes import A4
            from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib import colors
            from io import BytesIO
            from core.grading_utils import get_grading_system
            
            buffer = BytesIO()
            
            doc = SimpleDocTemplate(
                buffer,
                pagesize=A4,
                rightMargin=36,  # Reduced margins for more space
                leftMargin=36,
                topMargin=36,
                bottomMargin=36,
                title="Grades Export Report"
            )
            
            elements = []
            styles = getSampleStyleSheet()
            
            # Simplified title
            title_style = ParagraphStyle(
                'CustomTitle',
                parent=styles['Heading1'],
                fontSize=14,
                spaceAfter=20,
                alignment=1,
                textColor=colors.HexColor('#366092')
            )
            
            title = Paragraph("GRADES EXPORT", title_style)
            elements.append(title)
            
            # Basic info
            info_style = ParagraphStyle(
                'InfoStyle',
                parent=styles['Normal'],
                fontSize=8,
                textColor=colors.gray,
                alignment=1,
            )
            
            grading_system = get_grading_system()
            export_info = Paragraph(
                f"System: {grading_system} | "
                f"Date: {timezone.now().strftime('%Y-%m-%d %H:%M')} | "
                f"By: {request.user.get_full_name()}",
                info_style
            )
            elements.append(export_info)
            elements.append(Spacer(1, 15))
            
            # Get optimized data
            grades = self.get_optimized_queryset(request)
            
            # Simplified table headers
            if grading_system == 'GES':
                table_headers = ['Student', 'Class', 'Subject', 'Score', 'Grade', 'Status']
            elif grading_system == 'LETTER':
                table_headers = ['Student', 'Class', 'Subject', 'Score', 'Grade', 'Status']
            else:  # BOTH
                table_headers = ['Student', 'Class', 'Subject', 'Score', 'GES', 'Letter', 'Status']
            
            table_data = [table_headers]
            
            # Add grade data with simplified information
            for grade in grades:
                total_score = grade.total_score or 0
                is_passing = total_score >= 40.0
                
                base_data = [
                    grade.student.get_full_name(),
                    grade.student.class_level,  # Raw class level
                    grade.subject.name,
                    f'{total_score:.1f}%',
                ]
                
                if grading_system == 'GES':
                    base_data.extend([
                        grade.ges_grade or 'N/A',
                        'PASS' if is_passing else 'FAIL'
                    ])
                elif grading_system == 'LETTER':
                    base_data.extend([
                        grade.letter_grade or 'N/A',
                        'PASS' if is_passing else 'FAIL'
                    ])
                else:  # BOTH
                    base_data.extend([
                        grade.ges_grade or 'N/A',
                        grade.letter_grade or 'N/A',
                        'PASS' if is_passing else 'FAIL'
                    ])
                
                table_data.append(base_data)
            
            # Create table with basic styling
            if len(table_data) > 1:
                col_widths = [80, 40, 80, 40, 30, 30]
                if grading_system == 'BOTH':
                    col_widths = [80, 40, 80, 40, 20, 20, 30]
                
                table = Table(table_data, colWidths=col_widths, repeatRows=1)
                table.setStyle(TableStyle([
                    # Header style
                    ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#366092')),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, 0), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 8),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 6),
                    
                    # Data rows style
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 7),
                    ('ALIGN', (0, 1), (-1, -1), 'CENTER'),
                    ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                    
                    # Status column styling
                    ('FONTNAME', (-1, 1), (-1, -1), 'Helvetica-Bold'),
                ]))
                
                elements.append(table)
            else:
                elements.append(Paragraph("No grade data available for export.", styles['Normal']))
            
            # Basic summary
            elements.append(Spacer(1, 15))
            summary_style = ParagraphStyle(
                'SummaryStyle',
                parent=styles['Normal'],
                fontSize=7,
                textColor=colors.gray,
            )
            
            summary_text = f"Total: {len(grades)} records | Generated: {timezone.now().strftime('%Y-%m-%d %H:%M')}"
            summary = Paragraph(summary_text, summary_style)
            elements.append(summary)
            
            # Build PDF
            doc.build(elements)
            pdf = buffer.getvalue()
            buffer.close()
            
            response = HttpResponse(content_type='application/pdf')
            filename = f"grades_export_{timezone.now().strftime('%Y%m%d_%H%M%S')}.pdf"
            response['Content-Disposition'] = f'attachment; filename="{filename}"'
            response.write(pdf)
            
            logger.info(f"Optimized PDF export completed - {grades.count()} records")
            return response
            
        except Exception as e:
            logger.error(f"PDF export failed: {str(e)}", exc_info=True)
            messages.error(request, 'Failed to generate PDF export. Please try again.')
            return redirect('grade_list')
    
    def get_optimized_queryset(self, request):
        """
        Highly optimized queryset for exports - only necessary fields
        """
        try:
            # Use only() to select only necessary fields
            queryset = Grade.objects.select_related(
                'student', 'subject'
            ).only(
                'student__student_id',
                'student__first_name', 
                'student__last_name',
                'student__class_level',
                'subject__name',
                'academic_year',
                'term',
                'total_score',
                'ges_grade',
                'letter_grade'
            ).filter(
                student__is_active=True,
                subject__is_active=True
            )
            
            # Apply role-based filtering
            if is_teacher(request.user):
                teacher_classes = ClassAssignment.objects.filter(
                    teacher=request.user.teacher
                ).values_list('class_level', flat=True)
                queryset = queryset.filter(student__class_level__in=teacher_classes)
            
            # Build efficient filter conditions
            filters = Q()
            
            student_filter = request.GET.get('student')
            if student_filter:
                filters &= Q(student_id=student_filter)
            
            subject_filter = request.GET.get('subject')
            if subject_filter:
                filters &= Q(subject_id=subject_filter)
            
            class_level_filter = request.GET.get('class_level')
            if class_level_filter:
                filters &= Q(student__class_level=class_level_filter)
            
            academic_year_filter = request.GET.get('academic_year')
            if academic_year_filter:
                filters &= Q(academic_year=academic_year_filter)
            
            term_filter = request.GET.get('term')
            if term_filter and term_filter.isdigit():
                filters &= Q(term=int(term_filter))
            
            # Apply all filters at once
            if filters:
                queryset = queryset.filter(filters)
            
            # Apply score filters separately to avoid complex Q objects
            min_score_filter = request.GET.get('min_score')
            if min_score_filter:
                try:
                    min_score = Decimal(min_score_filter)
                    queryset = queryset.filter(total_score__gte=min_score)
                except (InvalidOperation, ValueError):
                    pass
            
            max_score_filter = request.GET.get('max_score')
            if max_score_filter:
                try:
                    max_score = Decimal(max_score_filter)
                    queryset = queryset.filter(total_score__lte=max_score)
                except (InvalidOperation, ValueError):
                    pass
            
            # Apply search filter last
            search_filter = request.GET.get('search')
            if search_filter:
                search_conditions = Q()
                search_conditions |= Q(student__first_name__icontains=search_filter)
                search_conditions |= Q(student__last_name__icontains=search_filter)
                search_conditions |= Q(student__student_id__icontains=search_filter)
                search_conditions |= Q(subject__name__icontains=search_filter)
                queryset = queryset.filter(search_conditions)
            
            # Check record count and apply limits if needed
            record_count = queryset.count()
            if record_count > self.MAX_EXPORT_RECORDS:
                logger.warning(f"Export limited: {record_count} records, exporting first {self.MAX_EXPORT_RECORDS}")
                queryset = queryset[:self.MAX_EXPORT_RECORDS]
            
            return queryset.order_by('student__last_name', 'student__first_name', 'subject__name')
            
        except Exception as e:
            logger.error(f"Error getting optimized queryset: {str(e)}")
            return Grade.objects.none()

# Simple function wrapper for URL compatibility
def export_grades(request):
    """
    Function-based wrapper for GradeExportView
    """
    return GradeExportView.as_view()(request)