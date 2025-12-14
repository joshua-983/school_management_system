# core/views/budget_views.py
"""
Budget Management Views - Separated to avoid circular imports
"""
import logging
import json
from django.utils import timezone
from datetime import datetime, timedelta
from decimal import Decimal
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import CreateView, TemplateView, UpdateView, DeleteView
from django.shortcuts import render, redirect
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Sum, Count, Q
from django.http import HttpResponse, JsonResponse

from .base_views import is_admin
from ..models import Budget, Expense, FeeCategory
from ..forms import BudgetForm
from ..constants.financial import BUDGET_CATEGORY_CHOICES

logger = logging.getLogger(__name__)


class BudgetManagementView(LoginRequiredMixin, UserPassesTestMixin, TemplateView):
    """View for managing budgets - separated from fee_views.py"""
    template_name = 'core/finance/reports/budget_management.html'
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        
        # Get year from request or use current year
        current_year = self.request.GET.get('year')
        try:
            current_year = int(current_year) if current_year else timezone.now().year
        except (ValueError, TypeError):
            current_year = timezone.now().year
        
        # Get enhanced budget data with real calculations
        budget_data = self.get_enhanced_budget_data(current_year)
        
        # Calculate summary statistics
        total_budget = sum(item['budget'] for item in budget_data)
        total_actual = sum(item['actual'] for item in budget_data)
        total_variance = total_actual - total_budget
        total_variance_percent = (total_variance / total_budget * 100) if total_budget > 0 else 0
        utilization_rate = (total_actual / total_budget * 100) if total_budget > 0 else 0
        
        # Critical variance alerts
        critical_variance = self.get_critical_variance_alerts(budget_data)
        
        # Historical spending data
        historical_spending = self.get_historical_spending_data()
        
        # Monthly data for trend chart
        monthly_data = self.get_monthly_budget_data(current_year)
        
        # Available years for filter
        available_years = self.get_available_years()
        
        # Fee categories for budget creation
        fee_categories = FeeCategory.objects.filter(is_active=True)
        
        # Get existing budgets for the current year
        current_academic_year = f"{current_year}/{current_year + 1}"
        existing_budgets = Budget.objects.filter(academic_year=current_academic_year)
        
        # Budget Trends for Major Categories
        budget_trends = self.get_budget_trends_for_major_categories(current_year)
        
        context.update({
            'current_year': current_year,
            'budget_data': budget_data,
            'historical_spending': historical_spending,
            'monthly_data': monthly_data,
            'available_years': available_years,
            'fee_categories': fee_categories,
            'existing_budgets': existing_budgets,
            'total_budget': total_budget,
            'total_actual': total_actual,
            'total_variance': total_variance,
            'total_variance_percent': total_variance_percent,
            'utilization_rate': utilization_rate,
            'critical_alerts': critical_variance,
            'budget_trends': budget_trends,
            'alert_count': len(critical_variance),
        })
        
        return context
    
    def get_enhanced_budget_data(self, year):
        """Get enhanced budget vs actual data with real calculations"""
        # Use the same academic year format as Budget model
        academic_year = f"{year}/{year + 1}"
        
        # First, try to get data from Budget model
        budgets = Budget.objects.filter(academic_year=academic_year)
        
        if budgets.exists():
            budget_data = []
            colors = [
                'rgba(58, 123, 213, 1)', 'rgba(40, 167, 69, 1)', 
                'rgba(255, 193, 7, 1)', 'rgba(220, 53, 69, 1)', 
                'rgba(23, 162, 184, 1)', 'rgba(108, 117, 125, 1)',
                'rgba(111, 66, 193, 1)', 'rgba(253, 126, 20, 1)'
            ]
            
            for i, budget in enumerate(budgets):
                try:
                    # Calculate actual spending from fee payments for this category and year
                    actual_spending = Expense.objects.filter(
                        category=budget.category,
                        date__year=year
                    ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                    
                    variance = actual_spending - budget.allocated_amount
                    variance_percent = (variance / budget.allocated_amount * 100) if budget.allocated_amount > 0 else 0
                    
                    budget_data.append({
                        'category': budget.category,
                        'budget': budget.allocated_amount,
                        'actual': actual_spending,
                        'variance': variance,
                        'variance_percent': variance_percent,
                        'color': colors[i % len(colors)],
                        'has_budget_record': True
                    })
                    
                except Exception as e:
                    logger.error(f"Error processing budget data for category {budget.category}: {str(e)}")
                    continue
            
            return budget_data
        
        # Fallback to budget categories if no budgets exist
        budget_data = []
        colors = [
            'rgba(58, 123, 213, 1)', 'rgba(40, 167, 69, 1)', 
            'rgba(255, 193, 7, 1)', 'rgba(220, 53, 69, 1)', 
            'rgba(23, 162, 184, 1)', 'rgba(108, 117, 125, 1)',
            'rgba(111, 66, 193, 1)', 'rgba(253, 126, 20, 1)'
        ]
        
        for i, category_data in enumerate(BUDGET_CATEGORY_CHOICES[:6]):  # Limit to 6 categories
            try:
                category_name = category_data[1]
                budget_amount = Decimal('10000.00') * Decimal(str(i + 1))  # Sample budget
                actual_spending = budget_amount * Decimal('0.8')  # Sample actual
                
                variance = actual_spending - budget_amount
                variance_percent = (variance / budget_amount * 100) if budget_amount > 0 else 0
                
                budget_data.append({
                    'category': {'name': category_name},
                    'budget': budget_amount,
                    'actual': actual_spending,
                    'variance': variance,
                    'variance_percent': variance_percent,
                    'color': colors[i % len(colors)],
                    'has_budget_record': False
                })
                
            except Exception as e:
                logger.error(f"Error processing budget data for category {category_name}: {str(e)}")
                continue
        
        return budget_data
    
    def get_critical_variance_alerts(self, budget_data, threshold=20):
        """Identify categories with significant budget variances"""
        critical_alerts = []
        
        for item in budget_data:
            variance_percent = abs(item['variance_percent'])
            
            # Check if variance exceeds threshold
            if variance_percent > threshold:
                alert_level = 'high' if variance_percent > 50 else 'medium'
                
                critical_alerts.append({
                    'category': item['category'],
                    'budget': item['budget'],
                    'actual': item['actual'],
                    'variance': item['variance'],
                    'variance_percent': item['variance_percent'],
                    'alert_level': alert_level,
                    'message': self.get_alert_message(item, variance_percent),
                    'recommendation': self.get_alert_recommendation(item, variance_percent)
                })
        
        # Sort by severity (highest variance first)
        critical_alerts.sort(key=lambda x: abs(x['variance_percent']), reverse=True)
        
        return critical_alerts
    
    def get_alert_message(self, item, variance_percent):
        """Generate appropriate alert message based on variance"""
        if isinstance(item['category'], dict):
            category_name = item['category']['name']
        else:
            category_name = item['category'].name
            
        variance_amount = abs(item['variance'])
        
        if item['variance'] < 0:
            return (
                f"{category_name} is {abs(variance_percent):.1f}% OVER budget "
                f"(GH₵{variance_amount:,.2f} over planned amount)"
            )
        else:
            return (
                f"{category_name} is {variance_percent:.1f}% UNDER budget "
                f"(GH₵{variance_amount:,.2f} below planned amount)"
            )
    
    def get_alert_recommendation(self, item, variance_percent):
        """Generate recommendations for addressing variances"""
        if item['variance'] < 0:  # Over budget
            if variance_percent > 50:
                return "Immediate review required. Consider reallocating funds or investigating unexpected expenses."
            elif variance_percent > 30:
                return "Review spending patterns and implement cost controls."
            else:
                return "Monitor closely and adjust future budget allocations."
        else:  # Under budget
            if variance_percent > 50:
                return "Significant under-utilization. Consider reallocating surplus to other categories."
            elif variance_percent > 30:
                return "Good cost control. Evaluate if budget can be reduced for next period."
            else:
                return "Healthy performance. Maintain current budget levels."
    
    def get_budget_trends_for_major_categories(self, current_year, years=3):
        """Get budget performance trends for major categories over multiple years"""
        major_categories = FeeCategory.objects.filter(
            is_active=True
        ).annotate(
            total_budget=Sum('budget__allocated_amount')
        ).order_by('-total_budget')[:5]
        
        trends_data = {}
        
        for category in major_categories:
            trends_data[category.name] = self.get_budget_trends(category, current_year, years)
        
        return trends_data
    
    def get_budget_trends(self, category, current_year, years=3):
        """Show budget performance trends for a specific category over multiple years"""
        trend_data = []
        
        for year_offset in range(years - 1, -1, -1):
            year = current_year - year_offset
            
            try:
                # Get budget amount for this year
                academic_year = f"{year}/{year + 1}"
                budget = Budget.objects.filter(
                    category=category,
                    academic_year=academic_year
                ).first()
                
                budget_amount = budget.allocated_amount if budget else Decimal('0.00')
                
                # Get actual spending
                actual_spending = Expense.objects.filter(
                    category=category.name,  # Expense uses string category
                    date__year=year
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                
                variance = actual_spending - budget_amount
                variance_percent = (variance / budget_amount * 100) if budget_amount > 0 else 0
                
                trend_data.append({
                    'year': year,
                    'academic_year': academic_year,
                    'budget': budget_amount,
                    'actual': actual_spending,
                    'variance': variance,
                    'variance_percent': variance_percent,
                    'utilization_rate': (actual_spending / budget_amount * 100) if budget_amount > 0 else 0
                })
            except Exception as e:
                logger.error(f"Error getting trend data for {category.name} in {year}: {str(e)}")
                trend_data.append({
                    'year': year,
                    'academic_year': f"{year}/{year + 1}",
                    'budget': Decimal('0.00'),
                    'actual': Decimal('0.00'),
                    'variance': Decimal('0.00'),
                    'variance_percent': 0.0,
                    'utilization_rate': 0.0,
                    'data_available': False
                })
        
        return trend_data
    
    def get_historical_spending_data(self):
        """Get historical spending data for the last 5 years"""
        current_year = timezone.now().year
        historical_data = []
        
        for year in range(current_year - 4, current_year + 1):
            try:
                yearly_spending = Expense.objects.filter(
                    date__year=year
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                
                historical_data.append({
                    'date__year': year,
                    'total': float(yearly_spending)
                })
            except Exception as e:
                logger.error(f"Error getting historical data for {year}: {str(e)}")
                historical_data.append({
                    'date__year': year,
                    'total': 0.0
                })
        
        return historical_data
    
    def get_monthly_budget_data(self, year):
        """Get monthly budget vs actual data for trend chart"""
        monthly_data = []
        
        for month in range(1, 13):
            try:
                # Monthly actual spending
                monthly_actual = Expense.objects.filter(
                    date__year=year,
                    date__month=month
                ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
                
                # Monthly budget estimate (based on annual budget / 12)
                total_annual_budget = Budget.objects.filter(
                    academic_year=f"{year}/{year + 1}"
                ).aggregate(total=Sum('allocated_amount'))['total'] or Decimal('0.00')
                
                monthly_budget = total_annual_budget / Decimal('12') if total_annual_budget > 0 else Decimal('50000.00')
                
                monthly_data.append({
                    'month': month,
                    'budget': float(monthly_budget),
                    'actual': float(monthly_actual)
                })
                
            except Exception as e:
                logger.error(f"Error getting monthly data for month {month}: {str(e)}")
                monthly_data.append({
                    'month': month,
                    'budget': 50000.0,
                    'actual': 45000.0
                })
        
        return monthly_data
    
    def get_available_years(self):
        """Get available years for filter dropdown"""
        current_year = timezone.now().year
        return list(range(current_year - 4, current_year + 1))


class BudgetCreateView(LoginRequiredMixin, UserPassesTestMixin, CreateView):
    """Create new budget - separated from fee_views.py"""
    model = Budget
    form_class = BudgetForm
    template_name = 'core/finance/reports/budget_form.html'
    success_url = reverse_lazy('budget_management')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Create New Budget'
        return context
    
    def form_valid(self, form):
        # Check for duplicate budget
        academic_year = form.cleaned_data['academic_year']
        category = form.cleaned_data['category']
        
        existing_budget = Budget.objects.filter(
            academic_year=academic_year,
            category=category
        ).exists()
        
        if existing_budget:
            form.add_error(None, f'A budget already exists for {category.name} in {academic_year}')
            return self.form_invalid(form)
        
        messages.success(
            self.request, 
            f'Budget created successfully: GH₵{form.instance.allocated_amount:,.2f} for {form.instance.category.name}'
        )
        return super().form_valid(form)
    
    def form_invalid(self, form):
        messages.error(self.request, 'Please correct the errors below.')
        return super().form_invalid(form)


class BudgetUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    """Update existing budget"""
    model = Budget
    form_class = BudgetForm
    template_name = 'core/finance/reports/budget_form.html'
    success_url = reverse_lazy('budget_management')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['title'] = 'Update Budget'
        return context


class BudgetDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    """Delete budget"""
    model = Budget
    template_name = 'core/finance/reports/budget_confirm_delete.html'
    success_url = reverse_lazy('budget_management')
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def delete(self, request, *args, **kwargs):
        budget = self.get_object()
        messages.success(
            request, 
            f'Budget for {budget.category.name} ({budget.academic_year}) deleted successfully'
        )
        return super().delete(request, *args, **kwargs)