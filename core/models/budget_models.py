"""
Budget and Expense models for financial management.
"""
import logging
from django.db import models
from django.utils import timezone
from django.db.models import Sum
from django.core.validators import MinValueValidator
from decimal import Decimal
from django.conf import settings

logger = logging.getLogger(__name__)


class Budget(models.Model):
    """Model for budget planning and tracking"""
    # Use CharField instead of ForeignKey to avoid circular imports
    category = models.CharField(max_length=100, help_text="Budget category")
    academic_year = models.CharField(max_length=9)
    notes = models.TextField(blank=True, null=True)
    allocated_amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    actual_spent = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        default=Decimal('0.00')
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('academic_year', 'category')
        verbose_name = 'Budget'
        verbose_name_plural = 'Budgets'
        ordering = ['academic_year', 'category']
    
    def __str__(self):
        return f"{self.category} - {self.academic_year}"
    
    @property
    def remaining_budget(self):
        return self.allocated_amount - self.actual_spent
    
    @property
    def utilization_percentage(self):
        if self.allocated_amount > 0:
            return (self.actual_spent / self.allocated_amount) * 100
        return 0


class Expense(models.Model):
    """Model for tracking expenses"""
    EXPENSE_CATEGORIES = [
        ('SALARIES', 'Salaries & Wages'),
        ('UTILITIES', 'Utilities'),
        ('MAINTENANCE', 'Maintenance & Repairs'),
        ('SUPPLIES', 'Teaching Supplies'),
        ('EQUIPMENT', 'Equipment & Furniture'),
        ('TRANSPORT', 'Transportation'),
        ('PROFESSIONAL', 'Professional Development'),
        ('OTHER', 'Other Expenses'),
    ]
    
    category = models.CharField(max_length=20, choices=EXPENSE_CATEGORIES)
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    date = models.DateField()
    description = models.TextField()
    receipt_number = models.CharField(max_length=50, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.PROTECT,
        null=True
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-date']
        verbose_name = 'Expense'
        verbose_name_plural = 'Expenses'
        indexes = [
            models.Index(fields=['date', 'category']),
        ]
    
    def __str__(self):
        return f"{self.get_category_display()} - GH₵{self.amount} - {self.date}"
    
    def save(self, *args, **kwargs):
        # Update related budget if exists
        super().save(*args, **kwargs)
        self.update_budget_tracking()
    
    def update_budget_tracking(self):
        """Update budget tracking for this expense category"""
        try:
            budget_year = f"{self.date.year}/{self.date.year + 1}"
            
            # Try to find or create budget for this academic year and category
            budget, created = Budget.objects.get_or_create(
                academic_year=budget_year,
                category=self.get_category_display(),
                defaults={'allocated_amount': Decimal('0.00')}
            )
            
            # Recalculate actual spent for this budget category
            total_spent = Expense.objects.filter(
                category=self.category,
                date__year=self.date.year
            ).aggregate(total=Sum('amount'))['total'] or Decimal('0.00')
            
            budget.actual_spent = total_spent
            budget.save()
            
        except Exception as e:
            logger.error(f"Error updating budget tracking: {e}")
