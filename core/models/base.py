# core/models/base.py
"""
Base models, mixins, and constants for the school management system.
"""

from django.db import models
from django.utils import timezone
from django.core.validators import MinValueValidator, MaxValueValidator
import os
from datetime import datetime

# ============================================================================
# CONSTANTS
# ============================================================================

# Gender choices
GENDER_CHOICES = [
    ('M', 'Male'),
    ('F', 'Female'),
    ('O', 'Other'),
    ('N', 'Prefer not to say'),
]

# Class level choices (Nursery through SHS)
CLASS_LEVEL_CHOICES = [
    ('NURSERY', 'Nursery'),
    ('KG', 'Kindergarten'),
    ('PRIMARY_1', 'Primary 1'),
    ('PRIMARY_2', 'Primary 2'),
    ('PRIMARY_3', 'Primary 3'),
    ('PRIMARY_4', 'Primary 4'),
    ('PRIMARY_5', 'Primary 5'),
    ('PRIMARY_6', 'Primary 6'),
    ('JHS_1', 'JHS 1'),
    ('JHS_2', 'JHS 2'),
    ('JHS_3', 'JHS 3'),
    ('SHS_1', 'SHS 1'),
    ('SHS_2', 'SHS 2'),
    ('SHS_3', 'SHS 3'),
]

# Class level display mapping
CLASS_LEVEL_DISPLAY_MAP = dict(CLASS_LEVEL_CHOICES)

# Term choices (Ghana system)
TERM_CHOICES = [
    (1, 'First Term'),
    (2, 'Second Term'),
    (3, 'Third Term'),
]

# Academic period system choices (for flexibility)
ACADEMIC_PERIOD_SYSTEM_CHOICES = [
    ('TERM', 'Term System (3 terms)'),
    ('SEMESTER', 'Semester System (2 semesters)'),
    ('QUARTER', 'Quarter System (4 quarters)'),
    ('TRIMESTER', 'Trimester System (3 trimesters)'),
]

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_period_choices_for_system(system):
    """Get period choices based on the academic period system."""
    if system == 'TERM':
        return [(1, 'First Term'), (2, 'Second Term'), (3, 'Third Term')]
    elif system == 'SEMESTER':
        return [(1, 'First Semester'), (2, 'Second Semester')]
    elif system == 'QUARTER':
        return [(1, 'First Quarter'), (2, 'Second Quarter'), 
                (3, 'Third Quarter'), (4, 'Fourth Quarter')]
    elif system == 'TRIMESTER':
        return [(1, 'First Trimester'), (2, 'Second Trimester'), 
                (3, 'Third Trimester')]
    else:
        return TERM_CHOICES  # Default to term system

def get_period_display(system, period_number):
    """Get display name for a period in a given system."""
    choices = get_period_choices_for_system(system)
    for num, name in choices:
        if num == period_number:
            return name
    return f"Period {period_number}"

def get_current_academic_year():
    """
    Determine the current academic year based on current date.
    Assumes academic year runs from September to August.
    """
    now = timezone.now()
    current_year = now.year
    current_month = now.month
    
    if current_month >= 9:  # September to December
        return f"{current_year}/{current_year + 1}"
    else:  # January to August
        return f"{current_year - 1}/{current_year}"

# ============================================================================
# IMAGE PATH FUNCTIONS
# ============================================================================

def student_image_path(instance, filename):
    """Generate upload path for student images."""
    ext = filename.split('.')[-1]
    filename = f"student_{instance.student_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
    return os.path.join('students', filename)

def teacher_image_path(instance, filename):
    """Generate upload path for teacher images."""
    ext = filename.split('.')[-1]
    filename = f"teacher_{instance.teacher_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
    return os.path.join('teachers', filename)

def parent_image_path(instance, filename):
    """Generate upload path for parent images."""
    ext = filename.split('.')[-1]
    filename = f"parent_{instance.parent_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{ext}"
    return os.path.join('parents', filename)

# ============================================================================
# MIXINS AND BASE CLASSES
# ============================================================================

class BaseModel(models.Model):
    """Base model with common fields."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        abstract = True
    
    def save(self, *args, **kwargs):
        """Override save to update timestamps."""
        self.updated_at = timezone.now()
        super().save(*args, **kwargs)
    
    def soft_delete(self):
        """Soft delete the record."""
        self.is_active = False
        self.save()

class TimeStampedModel(models.Model):
    """Model with only timestamp fields."""
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        abstract = True

class StatusMixin(models.Model):
    """Mixin for models with status field."""
    STATUS_CHOICES = [
        ('DRAFT', 'Draft'),
        ('PENDING', 'Pending'),
        ('ACTIVE', 'Active'),
        ('INACTIVE', 'Inactive'),
        ('COMPLETED', 'Completed'),
        ('ARCHIVED', 'Archived'),
    ]
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default='ACTIVE'
    )
    
    class Meta:
        abstract = True

class GhanaEducationMixin(models.Model):
    """Mixin for Ghana-specific education fields."""
    class_level = models.CharField(
        max_length=20,
        choices=CLASS_LEVEL_CHOICES,
        verbose_name="Class Level"
    )
    
    academic_year = models.CharField(
        max_length=9,
        help_text="Format: YYYY/YYYY (e.g., 2024/2025)",
        verbose_name="Academic Year",
        default='2024/2025'
    )
    
    term = models.PositiveSmallIntegerField(
        choices=TERM_CHOICES,
        verbose_name="Term"
    )
    
    class Meta:
        abstract = True
    
    @property
    def class_level_display(self):
        """Get display name for class level."""
        return CLASS_LEVEL_DISPLAY_MAP.get(self.class_level, self.class_level)
    
    @property
    def term_display(self):
        """Get display name for term."""
        for term_num, term_name in TERM_CHOICES:
            if term_num == self.term:
                return term_name
        return f"Term {self.term}"
    
    def get_academic_period_display(self):
        """Get combined academic period display."""
        return f"{self.academic_year} - {self.term_display}"