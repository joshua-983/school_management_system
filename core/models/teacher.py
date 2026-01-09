# core/models/teacher.py - UPDATED
"""
Teacher management models.
"""
import logging
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.utils import timezone

from core.models.base import GENDER_CHOICES

# CHANGE THESE IMPORTS:
# OLD: from core.models.academic import Subject, ClassAssignment
# NEW:
from core.models.subject import Subject  # Import from new location
# Don't import ClassAssignment here to avoid circular import

logger = logging.getLogger(__name__)
User = get_user_model()


class Teacher(models.Model):
    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE, 
        related_name='teacher'
    )
    
    employee_id = models.CharField(
        max_length=20, 
        unique=True,
        null=False,
        blank=False,
        editable=False,
        default='temporary'
    )
    
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    phone_number = models.CharField(
        max_length=10, 
        validators=[RegexValidator(r'^0[235][0-9]{8}$')],
        help_text="10-digit Ghana number (e.g., 0245846641)"
    )
    address = models.TextField()
    subjects = models.ManyToManyField(Subject, related_name='teachers')
    class_levels = models.CharField(max_length=50, help_text="Comma-separated list of class levels")
    qualification = models.CharField(max_length=200)
    date_of_joining = models.DateField(default=timezone.now)
    is_class_teacher = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Teacher"
        verbose_name_plural = "Teachers"
        ordering = ['user__last_name', 'user__first_name']
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.employee_id})"
    
    def get_full_name(self):
        return f"{self.user.first_name} {self.user.last_name}"
    
    def save(self, *args, **kwargs):
        # Generate employee_id only when creating a new teacher
        if self._state.adding or self.employee_id == 'temporary':
            current_year = str(timezone.now().year)
            
            # Find the highest sequence number for the current year
            last_teacher = Teacher.objects.filter(
                employee_id__startswith=f'TCH{current_year}'
            ).exclude(employee_id='temporary').order_by('-employee_id').first()
            
            if last_teacher:
                try:
                    last_sequence = int(last_teacher.employee_id[7:10])
                    new_sequence = last_sequence + 1
                except (ValueError, IndexError):
                    new_sequence = 1
            else:
                new_sequence = 1
            
            # Format: TCH + Year + 3-digit sequence
            self.employee_id = f'TCH{current_year}{new_sequence:03d}'
            
            # Ensure uniqueness in case of race conditions
            counter = 1
            original_id = self.employee_id
            while Teacher.objects.filter(employee_id=self.employee_id).exclude(pk=self.pk).exists():
                new_sequence += 1
                self.employee_id = f'TCH{current_year}{new_sequence:03d}'
                counter += 1
                if counter > 1000:
                    raise ValueError("Could not generate unique employee ID")
        
        super().save(*args, **kwargs)
    
    def get_assigned_classes(self):
        """Get classes assigned to this teacher"""
        # Import here to avoid circular import
        from core.models.class_assignment import ClassAssignment
        return ClassAssignment.objects.filter(teacher=self)
    
    def get_students_count(self):
        """Get count of students taught by this teacher"""
        from core.models.student import Student
        
        if self.class_levels:
            class_levels = [level.strip() for level in self.class_levels.split(',')]
            return Student.objects.filter(class_level__in=class_levels, is_active=True).count()
        return 0