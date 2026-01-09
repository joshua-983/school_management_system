# core/models/class_assignment.py
"""
Class Assignment Model
Links teachers to classes and subjects
"""
import re
import logging
from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone

from core.models.base import CLASS_LEVEL_CHOICES
from core.models.subject import Subject
from core.models.teacher import Teacher

logger = logging.getLogger(__name__)


class ClassAssignment(models.Model):
    class_level = models.CharField(
        max_length=20,  # Increased from 2 to handle longer class names
        choices=CLASS_LEVEL_CHOICES,
        verbose_name="Class Level"
    )
    subject = models.ForeignKey(
        Subject,
        on_delete=models.CASCADE,
        related_name='class_assignments',
        verbose_name="Subject"
    )
    teacher = models.ForeignKey(
        Teacher,
        on_delete=models.CASCADE,
        related_name='class_assignments',
        verbose_name="Teacher"
    )
    academic_year = models.CharField(
        max_length=9, 
        validators=[RegexValidator(r'^\d{4}/\d{4}$')],
        verbose_name="Academic Year"
    )
    is_active = models.BooleanField(
        default=True,
        verbose_name="Active"
    )
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At"
    )
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Updated At"
    )
    
    class Meta:
        unique_together = ('class_level', 'subject', 'academic_year')
        verbose_name = 'Class Assignment'
        verbose_name_plural = 'Class Assignments'
        ordering = ['academic_year', 'class_level', 'subject']
        indexes = [
            models.Index(fields=['class_level', 'subject', 'academic_year']),
            models.Index(fields=['teacher', 'is_active']),
            models.Index(fields=['is_active', 'academic_year']),
            models.Index(fields=['class_level', 'is_active']),
            models.Index(fields=['subject', 'academic_year']),
        ]

    def __str__(self):
        return f"{self.get_class_level_display()} - {self.subject} - {self.teacher} ({self.academic_year})"
    
    def clean(self):
        """Validate class assignment"""
        errors = {}
        
        # Validate academic year format
        if self.academic_year and not re.match(r'^\d{4}/\d{4}$', self.academic_year):
            errors['academic_year'] = 'Academic year must be in format YYYY/YYYY'
        
        if errors:
            raise ValidationError(errors)
    
    def get_students(self):
        """Get all students in this class"""
        from core.models.student import Student
        return Student.objects.filter(class_level=self.class_level, is_active=True)
    
    def get_students_count(self):
        """Get count of students in this class"""
        return self.get_students().count()
    
    def get_grades(self):
        """Get all grades for this class assignment"""
        from core.models.grades import Grade
        return Grade.objects.filter(
            class_assignment=self,
            academic_year=self.academic_year
        )
    
    def get_average_score(self):
        """Get average score for this class assignment"""
        from core.models.grades import Grade
        avg = self.get_grades().aggregate(models.Avg('total_score'))['total_score__avg']
        return avg if avg else 0
    
    def get_student_count_with_grades(self):
        """Get count of students who have grades in this assignment"""
        from core.models.grades import Grade
        return self.get_grades().values('student').distinct().count()
    
    def is_teacher_qualified(self):
        """Check if teacher is qualified to teach this subject"""
        return self.subject in self.teacher.subjects.all()
    
    def deactivate(self):
        """Deactivate class assignment"""
        self.is_active = False
        self.save()
        return True
    
    def activate(self):
        """Activate class assignment"""
        self.is_active = True
        self.save()
        return True
    
    def get_or_create_for_student(self, student):
        """Get or create class assignment for a specific student"""
        # Check if this assignment matches the student's class level
        if student.class_level != self.class_level:
            logger.warning(
                f"Student {student} is in class {student.class_level}, "
                f"but assignment is for {self.class_level}"
            )
            return None
        
        # Check if grade already exists
        from core.models.grades import Grade
        grade = Grade.objects.filter(
            student=student,
            subject=self.subject,
            academic_year=self.academic_year,
            class_assignment=self
        ).first()
        
        return grade
    
    @classmethod
    def find_for_student_subject(cls, student, subject, academic_year):
        """Find class assignment for student and subject"""
        return cls.objects.filter(
            class_level=student.class_level,
            subject=subject,
            academic_year=academic_year,
            is_active=True
        ).first()
    
    @classmethod
    def get_assignments_for_teacher(cls, teacher, academic_year=None):
        """Get all assignments for a teacher"""
        queryset = cls.objects.filter(teacher=teacher, is_active=True)
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)
        return queryset
    
    @classmethod
    def get_assignments_for_class(cls, class_level, academic_year=None):
        """Get all assignments for a class"""
        queryset = cls.objects.filter(class_level=class_level, is_active=True)
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)
        return queryset


# Export
__all__ = ['ClassAssignment']