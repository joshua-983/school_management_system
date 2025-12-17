"""
Student management models: Student model and related functionality.
"""
import logging
from datetime import date
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.db.models import Q

from core.models.base import (
    GENDER_CHOICES,
    CLASS_LEVEL_CHOICES,
    student_image_path,
    TERM_CHOICES
)

logger = logging.getLogger(__name__)
User = get_user_model()


class Student(models.Model):
    student_id = models.CharField(max_length=20, unique=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student')
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    nationality = models.CharField(max_length=100, default='Ghanaian')
    ethnicity = models.CharField(max_length=100, blank=True)
    religion = models.CharField(max_length=100, blank=True)
    place_of_birth = models.CharField(max_length=100)
    residential_address = models.TextField()
    phone_number = models.CharField(
        max_length=10,
        validators=[
            RegexValidator(
                r'^0\d{9}$',
                message="Phone number must be 10 digits starting with 0 (e.g., 0245478847)"
            )
        ],
        blank=True,
        help_text="10-digit phone number starting with 0 (e.g., 0245478847)"
    )
    profile_picture = models.ImageField(upload_to=student_image_path, blank=True, null=True)
    class_level = models.CharField(max_length=2, choices=CLASS_LEVEL_CHOICES)
    admission_date = models.DateField(default=timezone.now)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['class_level', 'last_name', 'first_name']
        verbose_name = 'Student'
        verbose_name_plural = 'Students'
        indexes = [
            models.Index(fields=['student_id']),
            models.Index(fields=['class_level', 'is_active']),
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['is_active', 'class_level']),
        ]
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.student_id}) - {self.get_class_level_display()}"
    
    def get_full_name(self):
        return f"{self.first_name} {self.middle_name} {self.last_name}".strip()
    
    def get_age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))
    
    def get_current_class(self):
        return self.get_class_level_display()
    
    def get_academic_progress(self):
        """Get student's academic progress summary"""
        from core.models.academic import AcademicTerm
        from core.models.grades import Grade
        
        current_term = AcademicTerm.objects.filter(is_active=True).first()
        if not current_term:
            return None
        
        return {
            'term': current_term,
            'attendance_rate': self.get_attendance_rate(current_term),
            'average_grade': self.get_average_grade(current_term),
        }
    
    def get_attendance_rate(self, term=None):
        """Get attendance rate for this student"""
        from core.models.attendance import StudentAttendance
        
        if not term:
            from core.models.academic import AcademicTerm
            term = AcademicTerm.objects.filter(is_active=True).first()
        
        if not term:
            return 0
        
        attendance_data = self.get_term_attendance_data(term)
        return attendance_data['attendance_rate']
    
    def get_term_attendance_data(self, term=None):
        """Calculate attendance data for a specific term"""
        from core.models.attendance import StudentAttendance
        
        try:
            if not term:
                from core.models.academic import AcademicTerm
                term = AcademicTerm.objects.filter(is_active=True).first()
            
            if not term:
                return {
                    'attendance_rate': 0, 
                    'total_days': 0, 
                    'present_days': 0, 
                    'absence_count': 0,
                    'late_count': 0,
                    'excused_count': 0
                }
            
            attendance_records = StudentAttendance.objects.filter(
                student=self,
                term=term
            )
            
            total_days = attendance_records.count()
            if total_days == 0:
                return {
                    'attendance_rate': 0, 
                    'total_days': 0, 
                    'present_days': 0, 
                    'absence_count': 0,
                    'late_count': 0,
                    'excused_count': 0
                }
            
            present_days = attendance_records.filter(
                Q(status='present') | Q(status='late') | Q(status='excused')
            ).count()
            
            absence_count = attendance_records.filter(status='absent').count()
            late_count = attendance_records.filter(status='late').count()
            excused_count = attendance_records.filter(status='excused').count()
            
            attendance_rate = round((present_days / total_days) * 100, 1) if total_days > 0 else 0
            
            return {
                'attendance_rate': attendance_rate,
                'total_days': total_days,
                'present_days': present_days,
                'absence_count': absence_count,
                'late_count': late_count,
                'excused_count': excused_count
            }
            
        except Exception as e:
            logger.error(f"Error calculating attendance data for student {self.id}: {e}")
            return {
                'attendance_rate': 0, 
                'total_days': 0, 
                'present_days': 0, 
                'absence_count': 0,
                'late_count': 0,
                'excused_count': 0
            }
    
    def get_ges_attendance_status(self, term=None):
        """Get GES-compliant attendance status description"""
        attendance_rate = self.get_attendance_rate(term)
        
        if attendance_rate >= 90:
            return "Excellent"
        elif attendance_rate >= 80:
            return "Good - GES Compliant"
        elif attendance_rate >= 70:
            return "Satisfactory"
        elif attendance_rate >= 60:
            return "Fair - Needs Improvement"
        else:
            return "Poor - Requires Intervention"
    
    def is_ges_compliant(self, term=None):
        """Check if attendance meets GES minimum requirement (80%)"""
        attendance_rate = self.get_attendance_rate(term)
        return attendance_rate >= 80.0
    
    def get_attendance_summary(self, term=None):
        """Get comprehensive attendance summary including GES compliance"""
        attendance_data = self.get_term_attendance_data(term)
        
        return {
            **attendance_data,
            'attendance_status': self.get_ges_attendance_status(term),
            'is_ges_compliant': self.is_ges_compliant(term),
            'term': term
        }
    
    def get_average_grade(self, term=None):
        """Get average grade for this student"""
        from core.models.grades import Grade
        
        if not term:
            from core.models.academic import AcademicTerm
            term = AcademicTerm.objects.filter(is_active=True).first()
        
        if not term:
            return None
        
        grades = Grade.objects.filter(student=self, term=term)
        if grades.exists():
            total_score = sum(float(grade.total_score) for grade in grades if grade.total_score)
            return round(total_score / grades.count(), 2)
        return None

    def clean(self):
        """Additional validation for phone number"""
        if self.phone_number:
            cleaned_phone = self.phone_number.replace(' ', '').replace('-', '')
            if len(cleaned_phone) != 10 or not cleaned_phone.startswith('0'):
                raise ValidationError({
                    'phone_number': 'Phone number must be exactly 10 digits starting with 0'
                })
            self.phone_number = cleaned_phone

    def save(self, *args, **kwargs):
        # Generate student ID if this is a new student
        if not self.student_id:
            current_year = str(timezone.now().year)
            class_level = self.class_level
            
            last_student = Student.objects.filter(
                student_id__startswith=f'STUD{current_year}{class_level}'
            ).order_by('-student_id').first()
            
            if last_student:
                try:
                    last_sequence = int(last_student.student_id[-3:])
                    new_sequence = last_sequence + 1
                except ValueError:
                    new_sequence = 1
            else:
                new_sequence = 1
                
            self.student_id = f'STUD{current_year}{class_level}{new_sequence:03d}'
        
        # Clean phone number before saving
        if self.phone_number:
            self.phone_number = self.phone_number.replace(' ', '').replace('-', '')
            
        super().save(*args, **kwargs)