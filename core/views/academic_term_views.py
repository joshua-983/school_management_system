"""
ACADEMIC TERM MANAGEMENT VIEWS
Professional school management system for academic period administration - UPDATED FOR STANDALONE SYSTEM
"""
import logging
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import (
    ListView, DetailView, CreateView, UpdateView, DeleteView,
    TemplateView, FormView, View
)
from django.views.generic.edit import FormMixin
from django.urls import reverse_lazy, reverse
from django.db.models import Q, Count
from django.http import JsonResponse, HttpResponse
from django.core.exceptions import ValidationError
from django.utils import timezone
from django import forms
import json
from datetime import date, datetime, timedelta
from core.models.academic_term import AcademicTerm, AcademicYear
from core.models.subject import Subject
from core.utils.academic_term import get_current_academic_year_string
from core.forms.academic_term_forms import (
    AcademicTermForm, AcademicYearCreationForm,
    TermBulkCreationForm, TermLockForm
)

logger = logging.getLogger(__name__)


class AcademicDashboardView(LoginRequiredMixin, TemplateView):
    """Academic dashboard with overview of all academic periods"""
    template_name = 'core/academics/academic_dashboard.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # AUTO-SYNC: Ensure academic years exist before displaying
        try:
            AcademicYear.ensure_years_exist(years_ahead=2)
        except Exception as e:
            logger.error(f"Error auto-syncing academic years: {str(e)}")
        
        # Get current academic year OBJECT
        current_academic_year = AcademicYear.get_current_year()
        current_academic_year_str = get_current_academic_year_string()
        
        # Get all academic years (objects)
        academic_years = AcademicYear.objects.all().order_by('-start_date')
        
        # Get current active term
        current_term = AcademicTerm.get_current_term()
        
        # Get terms for current academic year
        if current_academic_year:
            current_year_terms = AcademicTerm.objects.filter(
                academic_year=current_academic_year
            ).order_by('sequence_num')
        else:
            current_year_terms = AcademicTerm.objects.none()
        
        # Get upcoming terms
        today = timezone.now().date()
        upcoming_terms = AcademicTerm.objects.filter(
            start_date__gt=today
        ).order_by('start_date')[:5]
        
        # Get recently completed terms
        completed_terms = AcademicTerm.objects.filter(
            end_date__lt=today,
            is_locked=True
        ).order_by('-end_date')[:5]
        
        # Statistics
        total_terms = AcademicTerm.objects.count()
        active_terms = AcademicTerm.objects.filter(is_active=True).count()
        locked_terms = AcademicTerm.objects.filter(is_locked=True).count()
        upcoming_count = AcademicTerm.objects.filter(start_date__gt=today).count()
        
        # Prepare academic years list for template
        academic_years_list = []
        for year in academic_years:
            term_count = year.terms.count()
            completed_terms_count = year.terms.filter(is_locked=True).count()
            academic_years_list.append({
                'obj': year,
                'name': year.name,
                'term_count': term_count,
                'completed_count': completed_terms_count,
                'is_current': year == current_academic_year,
                'start_date': year.start_date,
                'end_date': year.end_date,
                'progress': year.get_progress_percentage(),
            })
        
        # Calculate academic year totals (365 days system)
        current_year_data = None
        if current_academic_year:
            terms_data = []
            total_teaching_days = 0
            for term in current_year_terms:
                term_days = term.get_total_days()
                total_teaching_days += term_days
                terms_data.append({
                    'term': term,
                    'days': term_days,
                    'remaining_days': term.get_remaining_days(),
                    'progress': term.get_progress_percentage(),
                })
            
            current_year_data = {
                'total_teaching_days': total_teaching_days,
                'total_days': current_academic_year.get_total_days(),  # Should be 365
                'vacation_days': current_academic_year.get_total_days() - total_teaching_days,
                'terms': terms_data,
            }
        
        context.update({
            'current_academic_year': current_academic_year,
            'current_academic_year_str': current_academic_year_str,
            'academic_years': academic_years_list,
            'current_term': current_term,
            'current_year_terms': current_year_terms,
            'upcoming_terms': upcoming_terms,
            'completed_terms': completed_terms,
            'total_terms': total_terms,
            'active_terms': active_terms,
            'locked_terms': locked_terms,
            'upcoming_count': upcoming_count,
            'today': today,
            'current_year_data': current_year_data,
        })
        
        return context


class AcademicTermListView(LoginRequiredMixin, ListView):
    """List all academic terms with filtering"""
    model = AcademicTerm
    template_name = 'core/academics/academic_term_list.html'
    context_object_name = 'terms'
    paginate_by = 20
    
    def get_queryset(self):
        queryset = AcademicTerm.objects.select_related('academic_year').all().order_by('-academic_year__start_date', 'sequence_num')
        
        # Filter by academic year (using ID)
        academic_year_id = self.request.GET.get('academic_year')
        if academic_year_id and academic_year_id.isdigit():
            queryset = queryset.filter(academic_year_id=int(academic_year_id))
        
        # Filter by period system
        period_system = self.request.GET.get('period_system')
        if period_system:
            queryset = queryset.filter(period_system=period_system)
        
        # Filter by status
        status = self.request.GET.get('status')
        if status == 'active':
            queryset = queryset.filter(is_active=True)
        elif status == 'locked':
            queryset = queryset.filter(is_locked=True)
        elif status == 'upcoming':
            today = timezone.now().date()
            queryset = queryset.filter(start_date__gt=today)
        elif status == 'completed':
            today = timezone.now().date()
            queryset = queryset.filter(end_date__lt=today, is_locked=True)
        
        # Search
        search_query = self.request.GET.get('search', '')
        if search_query:
            queryset = queryset.filter(
                Q(academic_year__name__icontains=search_query) |
                Q(name__icontains=search_query) |
                Q(period_system__icontains=search_query)
            )
        
        return queryset
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # AUTO-SYNC: Ensure academic years exist
        try:
            AcademicYear.ensure_years_exist(years_ahead=1)
        except Exception as e:
            logger.error(f"Error syncing academic years in term list: {str(e)}")
        
        # Get unique academic years for filter
        academic_years = AcademicYear.objects.all().order_by('-start_date')
        
        # Get period system choices
        from core.models.base import ACADEMIC_PERIOD_SYSTEM_CHOICES
        period_systems = ACADEMIC_PERIOD_SYSTEM_CHOICES
        
        # Get current academic year object
        current_academic_year = AcademicYear.get_current_year()
        
        context.update({
            'academic_years': academic_years,
            'period_systems': period_systems,
            'current_academic_year': current_academic_year,
            'search_query': self.request.GET.get('search', ''),
            'selected_academic_year_id': self.request.GET.get('academic_year', ''),
            'selected_period_system': self.request.GET.get('period_system', ''),
            'selected_status': self.request.GET.get('status', ''),
        })
        
        return context



class AcademicTermDetailView(LoginRequiredMixin, DetailView):
    """Detailed view of an academic term"""
    model = AcademicTerm
    template_name = 'core/academics/academic_term_detail.html'
    context_object_name = 'term'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        term = self.object
        
        # Calculate statistics
        today = timezone.now().date()
        
        # Term progress
        if term.start_date and term.end_date:
            if today < term.start_date:
                progress = 0
                status = "Upcoming"
            elif today > term.end_date:
                progress = 100
                status = "Completed"
            else:
                total_days = (term.end_date - term.start_date).days
                days_passed = (today - term.start_date).days
                progress = min(100, round((days_passed / total_days) * 100, 1))
                status = "In Progress"
        else:
            progress = 0
            status = "Not Started"
        
        # Get related data counts (you'll need to implement these)
        from core.models import Grade, Fee, Assignment
        grade_count = Grade.objects.filter(
            academic_year=term.academic_year.name if term.academic_year else '',
            term=term.period_number
        ).count() if term.period_system == 'TERM' else 0
        
        fee_count = Fee.objects.filter(
            academic_year=term.academic_year.name if term.academic_year else '',
            term=term.period_number
        ).count() if term.period_system == 'TERM' else 0
        
        # Get next and previous terms in the same academic year and period system
        if term.academic_year:
            next_term = AcademicTerm.objects.filter(
                academic_year=term.academic_year,
                period_system=term.period_system,
                sequence_num__gt=term.sequence_num
            ).order_by('sequence_num').first()
            
            previous_term = AcademicTerm.objects.filter(
                academic_year=term.academic_year,
                period_system=term.period_system,
                sequence_num__lt=term.sequence_num
            ).order_by('-sequence_num').first()
        else:
            next_term = None
            previous_term = None
        
        context.update({
            'progress': progress,
            'status': status,
            'grade_count': grade_count,
            'fee_count': fee_count,
            'next_term': next_term,
            'previous_term': previous_term,
            'today': today,
            'remaining_days': term.get_remaining_days(),
        })
        
        return context


class AcademicTermCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Create a new academic term"""
    model = AcademicTerm
    form_class = AcademicTermForm
    template_name = 'core/academics/academic_term_form.html'
    success_url = reverse_lazy('academic_term_list')
    
    def test_func(self):
        # Only staff can create academic terms
        return self.request.user.is_staff
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs
    
    def form_valid(self, form):
        term = form.save(commit=False)
        
        # Check for overlapping terms
        overlapping = AcademicTerm.objects.filter(
            academic_year=term.academic_year,
            period_system=term.period_system,
            start_date__lt=term.end_date,
            end_date__gt=term.start_date
        )
        
        if overlapping.exists():
            form.add_error(None, 
                f"Dates overlap with existing {term.get_period_system_display()}: "
                f"{overlapping.first()}"
            )
            return self.form_invalid(form)
        
        # If setting as active, deactivate others in the same academic year
        if term.is_active and term.academic_year:
            AcademicTerm.objects.filter(
                academic_year=term.academic_year,
                is_active=True
            ).update(is_active=False)
        
        messages.success(self.request, 
            f"Academic term created successfully: {term}"
        )
        return super().form_valid(form)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create Academic Term'
        context['submit_text'] = 'Create Term'
        return context


class AcademicTermUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Update an existing academic term"""
    model = AcademicTerm
    form_class = AcademicTermForm
    template_name = 'core/academics/academic_term_form.html'
    
    def test_func(self):
        # Only staff can update academic terms
        return self.request.user.is_staff
    
    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        kwargs['instance'] = self.object
        return kwargs
    
    def form_valid(self, form):
        term = form.save(commit=False)
        
        # Don't allow editing locked terms
        if term.is_locked and not self.request.user.is_superuser:
            form.add_error(None, 
                "Cannot edit locked academic terms. "
                "Please unlock the term first or contact an administrator."
            )
            return self.form_invalid(form)
        
        # Check for overlapping terms
        overlapping = AcademicTerm.objects.filter(
            academic_year=term.academic_year,
            period_system=term.period_system,
            start_date__lt=term.end_date,
            end_date__gt=term.start_date
        ).exclude(pk=term.pk)
        
        if overlapping.exists():
            form.add_error(None, 
                f"Dates overlap with existing {term.get_period_system_display()}: "
                f"{overlapping.first()}"
            )
            return self.form_invalid(form)
        
        # If setting as active, deactivate others in the same academic year
        if term.is_active and term.academic_year:
            AcademicTerm.objects.filter(
                academic_year=term.academic_year,
                is_active=True
            ).exclude(pk=term.pk).update(is_active=False)
        
        messages.success(self.request, 
            f"Academic term updated successfully: {term}"
        )
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('academic_term_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Academic Term'
        context['submit_text'] = 'Update Term'
        context['is_locked'] = self.object.is_locked
        return context


class AcademicTermDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Delete an academic term"""
    model = AcademicTerm
    template_name = 'core/academics/academic_term_confirm_delete.html'
    success_url = reverse_lazy('academic_term_list')
    
    def test_func(self):
        # Only superusers can delete academic terms
        return self.request.user.is_superuser
    
    def form_valid(self, form):
        term = self.get_object()
        
        # Check if term has associated data
        from core.models import Grade, Fee
        has_grades = Grade.objects.filter(
            academic_year=term.academic_year.name if term.academic_year else '',
            term=term.period_number
        ).exists() if term.period_system == 'TERM' else False
        
        has_fees = Fee.objects.filter(
            academic_year=term.academic_year.name if term.academic_year else '',
            term=term.period_number
        ).exists() if term.period_system == 'TERM' else False
        
        if has_grades or has_fees:
            messages.error(self.request,
                f"Cannot delete {term}. It has associated "
                f"{'grades' if has_grades else ''}"
                f"{' and ' if has_grades and has_fees else ''}"
                f"{'fees' if has_fees else ''}. "
                f"Please remove all associated data first or lock the term instead."
            )
            return redirect('academic_term_detail', pk=term.pk)
        
        messages.success(self.request,
            f"Academic term deleted successfully: {term}"
        )
        return super().form_valid(form)


class AcademicYearCreationView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """Create a complete academic year with all terms"""
    template_name = 'core/academics/academic_year_create.html'
    form_class = AcademicYearCreationForm
    success_url = reverse_lazy('academic_term_list')
    
    def test_func(self):
        # Only staff can create academic years
        return self.request.user.is_staff
    
    def form_valid(self, form):
        try:
            # Use the new method from the form
            academic_year, terms = form.create_academic_year_with_terms()
            
            messages.success(self.request,
                f"Successfully created academic year {academic_year.name} "
                f"with {len(terms)} terms"
            )
            
            return super().form_valid(form)
            
        except Exception as e:
            logger.error(f"Error creating academic year: {str(e)}")
            messages.error(self.request,
                f"Error creating academic year: {str(e)}"
            )
            return self.form_invalid(form)


class TermLockUnlockView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Lock or unlock an academic term"""
    model = AcademicTerm
    form_class = TermLockForm
    template_name = 'core/academics/academic_term_lock.html'
    
    def test_func(self):
        # Only staff can lock/unlock terms
        return self.request.user.is_staff
    
    def form_valid(self, form):
        term = form.save(commit=False)
        action = "locked" if term.is_locked else "unlocked"
        
        # Additional validation for locking
        if term.is_locked and not term.end_date:
            form.add_error('is_locked',
                "Cannot lock a term without an end date"
            )
            return self.form_invalid(form)
        
        # Save the term
        term.save()
        
        messages.success(self.request,
            f"Academic term {action} successfully: {term}"
        )
        
        return super().form_valid(form)
    
    def get_success_url(self):
        return reverse('academic_term_detail', kwargs={'pk': self.object.pk})
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        term = self.object
        context['action'] = 'Lock' if not term.is_locked else 'Unlock'
        context['warning'] = (
            "⚠️ Locking a term will prevent modifications to: "
            "Grades, Attendance, Assignments, and Fees for this term."
        ) if not term.is_locked else (
            "⚠️ Unlocking a term will allow modifications. Use with caution."
        )
        return context


class SetActiveTermView(LoginRequiredMixin, UserPassesTestMixin, View):
    """Set a term as active"""
    
    def test_func(self):
        return self.request.user.is_staff
    
    def post(self, request, pk):
        term = get_object_or_404(AcademicTerm, pk=pk)
        
        # Deactivate all other terms in the same academic year
        AcademicTerm.objects.filter(
            academic_year=term.academic_year,
            is_active=True
        ).exclude(pk=pk).update(is_active=False)
        
        # Activate this term
        term.is_active = True
        term.save()
        
        messages.success(request,
            f"Set active term to: {term}"
        )
        
        return redirect('academic_term_detail', pk=pk)


class AcademicCalendarView(LoginRequiredMixin, TemplateView):
    """Academic calendar view showing all terms"""
    template_name = 'core/academics/academic_calendar.html'
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get terms for the next 2 years
        current_year = timezone.now().year
        academic_years = []
        
        for year_offset in range(-1, 3):  # Previous year to next 2 years
            year = current_year + year_offset
            academic_year_str = f"{year}/{year + 1}"
            
            # Try to get the AcademicYear object
            try:
                academic_year_obj = AcademicYear.objects.get(name=academic_year_str)
                terms = academic_year_obj.terms.all().order_by('sequence_num')
                if terms.exists():
                    academic_years.append({
                        'academic_year': academic_year_obj,
                        'terms': terms,
                        'is_current': academic_year_obj.is_active
                    })
            except AcademicYear.DoesNotExist:
                continue
        
        context['academic_years'] = academic_years
        context['current_academic_year'] = AcademicYear.get_current_year()
        
        return context


class TermProgressAPIView(LoginRequiredMixin, View):
    """API endpoint for term progress data"""
    
    def get(self, request, pk):
        term = get_object_or_404(AcademicTerm, pk=pk)
        
        data = {
            'id': term.pk,
            'name': str(term),
            'progress': term.get_progress_percentage(),
            'remaining_days': term.get_remaining_days(),
            'total_days': (term.end_date - term.start_date).days if term.end_date and term.start_date else 0,
            'is_active': term.is_active,
            'is_locked': term.is_locked,
            'start_date': term.start_date.isoformat() if term.start_date else None,
            'end_date': term.end_date.isoformat() if term.end_date else None,
            'today': timezone.now().date().isoformat(),
        }
        
        return JsonResponse(data)


class TermBulkActionsView(LoginRequiredMixin, UserPassesTestMixin, FormView):
    """Bulk actions for academic terms"""
    template_name = 'core/academics/academic_term_bulk_actions.html'
    form_class = TermBulkCreationForm
    success_url = reverse_lazy('academic_term_list')
    
    def test_func(self):
        return self.request.user.is_staff
    
    def form_valid(self, form):
        action = form.cleaned_data['action']
        academic_years_str = form.cleaned_data['academic_years']
        period_system = form.cleaned_data['period_system']
        
        if action == 'create':
            # Create multiple academic years
            created_terms = 0
            for academic_year_str in academic_years_str:
                # Check if AcademicYear exists
                try:
                    academic_year_obj = AcademicYear.objects.get(name=academic_year_str)
                except AcademicYear.DoesNotExist:
                    # Create the AcademicYear
                    year1, year2 = map(int, academic_year_str.split('/'))
                    academic_year_obj = AcademicYear.objects.create(
                        name=academic_year_str,
                        start_date=date(year1, 9, 1),
                        end_date=date(year2, 8, 31)
                    )
                
                # Check if terms already exist
                existing_terms = academic_year_obj.terms.filter(period_system=period_system).count()
                if existing_terms == 0:
                    # Create default terms
                    terms = AcademicTerm.create_default_terms(academic_year_obj, period_system)
                    created_terms += len(terms)
            
            messages.success(self.request,
                f"Created {created_terms} terms across {len(academic_years_str)} academic years"
            )
        
        elif action == 'lock':
            # Lock all terms in selected academic years
            locked_count = 0
            for academic_year_str in academic_years_str:
                try:
                    academic_year_obj = AcademicYear.objects.get(name=academic_year_str)
                    terms = academic_year_obj.terms.all()
                    for term in terms:
                        if term.end_date and term.end_date <= timezone.now().date():
                            term.lock_term()
                            locked_count += 1
                except AcademicYear.DoesNotExist:
                    continue
            
            messages.success(self.request,
                f"Locked {locked_count} terms"
            )
        
        elif action == 'unlock':
            # Unlock all terms in selected academic years
            unlocked_count = 0
            for academic_year_str in academic_years_str:
                try:
                    academic_year_obj = AcademicYear.objects.get(name=academic_year_str)
                    terms = academic_year_obj.terms.all()
                    for term in terms:
                        term.unlock_term()
                        unlocked_count += 1
                except AcademicYear.DoesNotExist:
                    continue
            
            messages.success(self.request,
                f"Unlocked {unlocked_count} terms"
            )
        
        return super().form_valid(form)


class AutoSyncAcademicYearsView(LoginRequiredMixin, UserPassesTestMixin, View):
    """View to manually trigger academic year auto-sync"""
    
    def test_func(self):
        return self.request.user.is_staff
    
    def get(self, request):
        try:
            created_years = AcademicYear.ensure_years_exist(years_ahead=2)
            
            if created_years:
                messages.success(request, 
                    f"✅ Successfully created {len(created_years)} academic years and their terms"
                )
            else:
                messages.info(request, 
                    "✅ Academic years are already up-to-date. No changes made."
                )
            
        except Exception as e:
            logger.error(f"Error in auto-sync view: {str(e)}")
            messages.error(request, 
                f"❌ Error syncing academic years: {str(e)}"
            )
        
        return redirect('academic_dashboard')


# Update the quick actions to include auto-sync
def quick_sync_academic_years(request):
    """Quick action to sync academic years"""
    if not request.user.is_staff:
        messages.error(request, "Permission denied")
        return redirect('academic_term_list')
    
    try:
        created_years = AcademicYear.ensure_years_exist(years_ahead=2)
        
        if created_years:
            messages.success(request, 
                f"✅ Successfully synced academic years. Created {len(created_years)} new years."
            )
        else:
            messages.info(request, 
                "✅ Academic years are already synced. No changes needed."
            )
            
    except Exception as e:
        logger.error(f"Error in quick sync: {str(e)}")
        messages.error(request, 
            f"❌ Error syncing academic years: {str(e)}"
        )
    
    if request.META.get('HTTP_REFERER'):
        return redirect(request.META.get('HTTP_REFERER'))
    return redirect('academic_dashboard')

# Quick actions views
def quick_set_active_term(request, pk):
    """Quick action to set a term as active"""
    if not request.user.is_staff:
        messages.error(request, "Permission denied")
        return redirect('academic_term_list')
    
    term = get_object_or_404(AcademicTerm, pk=pk)
    
    # Deactivate all other terms in the same academic year
    AcademicTerm.objects.filter(
        academic_year=term.academic_year
    ).exclude(pk=pk).update(is_active=False)
    
    # Activate this term
    term.is_active = True
    term.save()
    
    messages.success(request, f"Set active term to: {term}")
    
    if request.META.get('HTTP_REFERER'):
        return redirect(request.META.get('HTTP_REFERER'))
    return redirect('academic_term_detail', pk=pk)


def quick_lock_term(request, pk):
    """Quick action to lock a term"""
    if not request.user.is_staff:
        messages.error(request, "Permission denied")
        return redirect('academic_term_list')
    
    term = get_object_or_404(AcademicTerm, pk=pk)
    
    if term.end_date and term.end_date <= timezone.now().date():
        term.is_locked = True
        term.save()
        messages.success(request, f"Locked term: {term}")
    else:
        messages.error(request, 
            f"Cannot lock term that hasn't ended yet. End date: {term.end_date}"
        )
    
    if request.META.get('HTTP_REFERER'):
        return redirect(request.META.get('HTTP_REFERER'))
    return redirect('academic_term_detail', pk=pk)


def quick_unlock_term(request, pk):
    """Quick action to unlock a term"""
    if not request.user.is_staff:
        messages.error(request, "Permission denied")
        return redirect('academic_term_list')
    
    term = get_object_or_404(AcademicTerm, pk=pk)
    term.is_locked = False
    term.save()
    
    messages.warning(request, 
        f"Unlocked term: {term}. Use with caution!"
    )
    
    if request.META.get('HTTP_REFERER'):
        return redirect(request.META.get('HTTP_REFERER'))
    return redirect('academic_term_detail', pk=pk)


# AJAX/JSON endpoints - UPDATED FOR STANDALONE SYSTEM
def get_academic_years_json(request):
    """Get academic years for dropdowns"""
    years = AcademicYear.objects.all().order_by('-start_date')
    
    data = [
        {
            'id': year.id,
            'name': year.name,
            'is_active': year.is_active
        }
        for year in years
    ]
    
    return JsonResponse(data, safe=False)


def get_terms_for_year_json(request, year_id):
    """Get terms for a specific academic year (using ID)"""
    try:
        academic_year = AcademicYear.objects.get(id=year_id)
        terms = academic_year.terms.all().order_by('sequence_num')
        
        data = [
            {
                'id': term.id,
                'name': str(term),
                'period_number': term.period_number,
                'period_system': term.period_system,
                'start_date': term.start_date.isoformat() if term.start_date else None,
                'end_date': term.end_date.isoformat() if term.end_date else None,
                'is_active': term.is_active,
                'is_locked': term.is_locked,
            }
            for term in terms
        ]
        
        return JsonResponse(data, safe=False)
    except AcademicYear.DoesNotExist:
        return JsonResponse([], safe=False)


def check_term_availability(request):
    """Check if a term period is available"""
    academic_year_id = request.GET.get('academic_year')
    period_system = request.GET.get('period_system')
    period_number = request.GET.get('period_number')
    exclude_id = request.GET.get('exclude_id')
    
    if not all([academic_year_id, period_system, period_number]):
        return JsonResponse({'error': 'Missing parameters'}, status=400)
    
    try:
        academic_year = AcademicYear.objects.get(id=int(academic_year_id))
        period_number = int(period_number)
    except (ValueError, AcademicYear.DoesNotExist):
        return JsonResponse({'error': 'Invalid parameters'}, status=400)
    
    queryset = AcademicTerm.objects.filter(
        academic_year=academic_year,
        period_system=period_system,
        period_number=period_number
    )
    
    if exclude_id:
        queryset = queryset.exclude(pk=exclude_id)
    
    available = not queryset.exists()
    
    return JsonResponse({
        'available': available,
        'message': 'Period available' if available else 'Period already exists'
    })