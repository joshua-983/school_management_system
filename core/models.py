import os
import logging
import re
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator,
    RegexValidator,
)
from django.utils import timezone
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.conf import settings
from django.utils.safestring import mark_safe
from django.apps import apps
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from django.db.models import Q, Count, Avg, Sum
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.utils.translation import gettext_lazy as _

from django.core.files.storage import default_storage
from django.db.models.functions import ExtractYear, ExtractMonth

logger = logging.getLogger(__name__)
User = get_user_model()

# ===== SHARED CONSTANTS =====
GENDER_CHOICES = [
    ('M', 'Male'),
    ('F', 'Female'),
]

CLASS_LEVEL_CHOICES = [
    ('P1', 'Primary 1'),
    ('P2', 'Primary 2'),
    ('P3', 'Primary 3'),
    ('P4', 'Primary 4'),
    ('P5', 'Primary 5'),
    ('P6', 'Primary 6'),
    ('J1', 'JHS 1'),
    ('J2', 'JHS 2'),
    ('J3', 'JHS 3'),
]

CLASS_LEVEL_DISPLAY_MAP = dict(CLASS_LEVEL_CHOICES)

TERM_CHOICES = [
    (1, 'Term 1'),
    (2, 'Term 2'),
    (3, 'Term 3'),
]

# Image path functions
def student_image_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{instance.student_id}.{ext}"
    return os.path.join('students', filename)

def teacher_image_path(instance, filename):
    return f'teachers/{instance.employee_id}/{filename}'

def parent_image_path(instance, filename):
    return f'parents/{instance.parent_id}/{filename}'

class GhanaEducationMixin:
    """Mixin for Ghana Education Service specific functionality"""
    
    def get_ghana_academic_calendar(self):
        """Get current Ghana academic calendar structure"""
        current_year = timezone.now().year
        next_year = current_year + 1
        
        # Ghana Education Service Standard Calendar
        ghana_calendar = {
            'academic_year': f"{current_year}/{next_year}",
            'terms': {
                1: {
                    'name': 'Term 1',
                    'start_date': date(current_year, 9, 2),  # Early September
                    'end_date': date(current_year, 12, 18),  # Mid-December
                    'mid_term_break': date(current_year, 10, 16),
                },
                2: {
                    'name': 'Term 2', 
                    'start_date': date(next_year, 1, 8),     # Early January
                    'end_date': date(next_year, 4, 1),       # Early April
                    'mid_term_break': date(next_year, 2, 15),
                },
                3: {
                    'name': 'Term 3',
                    'start_date': date(next_year, 4, 21),    # Late April
                    'end_date': date(next_year, 7, 23),      # Late July
                    'mid_term_break': date(next_year, 6, 1),
                }
            }
        }
        return ghana_calendar
    
    def is_ghana_school_day(self, check_date):
        """
        Check if date is a valid school day in Ghana
        - Monday to Friday are school days
        - Exclude public holidays
        """
        # Monday = 0, Friday = 4, Saturday = 5, Sunday = 6
        if check_date.weekday() >= 5:  # Weekend
            return False
        
        # Ghana public holidays
        ghana_holidays = [
            date(check_date.year, 1, 1),   # New Year
            date(check_date.year, 3, 6),   # Independence Day
            date(check_date.year, 5, 1),   # Workers Day
            date(check_date.year, 7, 1),   # Republic Day
            date(check_date.year, 12, 25), # Christmas
            date(check_date.year, 12, 26), # Boxing Day
        ]
        
        return check_date not in ghana_holidays

# ===== ACADEMIC MODELS =====


class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True, editable=False)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        verbose_name = 'Subject'
        verbose_name_plural = 'Subjects'

    def __str__(self):
        return f"{self.name} ({self.code})"
    
    def get_assignment_count(self):
        """Get number of assignments for this subject"""
        return self.classassignment_set.filter(is_active=True).count()
    
    def generate_subject_code(self):
        """Generate a 3-letter subject code from the name"""
        # Remove common words and get first letters
        common_words = ['and', 'the', 'of', 'for', 'in', 'with', 'to', 'on', 'at', 'from', 'by', 'about', 'as', 'into', 'like', 'through', 'after', 'over', 'between', 'out', 'against', 'during', 'without', 'before', 'under', 'around', 'among']
        
        words = self.name.upper().split()
        meaningful_words = [word for word in words if word.lower() not in common_words]
        
        if meaningful_words:
            # If single word, take first 3 letters
            if len(meaningful_words) == 1:
                code = meaningful_words[0][:3]
            else:
                # If multiple words, take first letter of each (max 3)
                code = ''.join(word[0] for word in meaningful_words[:3])
        else:
            # Fallback: take first 3 letters of first word
            code = words[0][:3] if words else 'SUB'
        
        # Ensure code is exactly 3 characters
        code = code.ljust(3, 'X')[:3]
        
        # Make unique if code already exists
        base_code = code
        counter = 1
        while Subject.objects.filter(code=code).exclude(pk=self.pk).exists():
            code = f"{base_code}{counter}"
            counter += 1
        
        return code
    
    def save(self, *args, **kwargs):
        if not self.code:
            self.code = self.generate_subject_code()
        super().save(*args, **kwargs)


class AcademicTerm(models.Model):
    TERM_CHOICES = [
        (1, 'Term 1'),
        (2, 'Term 2'),
        (3, 'Term 3'),
    ]
    
    term = models.PositiveSmallIntegerField(choices=TERM_CHOICES)
    academic_year = models.CharField(max_length=9, validators=[RegexValidator(r'^\d{4}/\d{4}$')])
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('term', 'academic_year')
        ordering = ['-academic_year', 'term']
        verbose_name = 'Academic Term'
        verbose_name_plural = 'Academic Terms'
    
    def __str__(self):
        return f"{self.get_term_display()} {self.academic_year}"
    
    def clean(self):
        if self.start_date > self.end_date:
            raise ValidationError("End date must be after start date")
        
        # Ensure term duration is reasonable (3-4 months)
        if (self.end_date - self.start_date).days > 150:
            raise ValidationError("Term duration should not exceed 5 months")
        
        # Ensure only one active term per academic year
        if self.is_active:
            AcademicTerm.objects.filter(
                academic_year=self.academic_year,
                is_active=True
            ).exclude(pk=self.pk).update(is_active=False)
    
    def get_total_school_days(self):
        """Calculate total school days in the term"""
        total_days = 0
        current_date = self.start_date
        
        while current_date <= self.end_date:
            if current_date.weekday() < 5:  # Monday to Friday
                total_days += 1
            current_date += timedelta(days=1)
        
        return total_days
    
    def get_progress_percentage(self):
        """Get term progress percentage"""
        today = timezone.now().date()
        if today < self.start_date:
            return 0
        elif today > self.end_date:
            return 100
        
        total_days = (self.end_date - self.start_date).days
        days_passed = (today - self.start_date).days
        return min(100, round((days_passed / total_days) * 100, 1))
    
    def get_remaining_days(self):
        """Get remaining days in term"""
        today = timezone.now().date()
        if today > self.end_date:
            return 0
        return (self.end_date - today).days

# ===== STUDENT MANAGEMENT =====

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
            # NEW indexes
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
        current_term = AcademicTerm.objects.filter(is_active=True).first()
        if not current_term:
            return None
        
        return {
            'term': current_term,
            'attendance_rate': self.get_attendance_rate(current_term),
            'average_grade': self.get_average_grade(current_term),
        }
    
    def get_attendance_rate(self, term=None):
        """
        Get attendance rate for this student based on ACTUAL recorded days
        (GES standard - calculates based on days when attendance was actually taken)
        """
        if not term:
            term = AcademicTerm.objects.filter(is_active=True).first()
        
        if not term:
            return 0
        
        # Use the same logic as get_term_attendance_data for consistency
        attendance_data = self.get_term_attendance_data(term)
        return attendance_data['attendance_rate']
    
    def get_term_attendance_data(self, term=None):
        """
        Calculate attendance data for a specific term based on ACTUAL recorded days
        (GES standard - calculates based on days when attendance was actually taken)
        """
        try:
            if not term:
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
            
            # Calculate attendance records for this term using the database
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
            
            # Use database aggregation for better performance
            from django.db.models import Count, Q
            
            # GES counts present, late, and excused as present
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
        """
        Get GES-compliant attendance status description
        """
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
        """
        Check if attendance meets GES minimum requirement (80%)
        """
        attendance_rate = self.get_attendance_rate(term)
        return attendance_rate >= 80.0
    
    def get_attendance_summary(self, term=None):
        """
        Get comprehensive attendance summary including GES compliance
        """
        attendance_data = self.get_term_attendance_data(term)
        
        return {
            **attendance_data,
            'attendance_status': self.get_ges_attendance_status(term),
            'is_ges_compliant': self.is_ges_compliant(term),
            'term': term
        }
    
    def get_average_grade(self, term=None):
        """Get average grade for this student"""
        if not term:
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
            # Remove any spaces or dashes that might have been entered
            cleaned_phone = self.phone_number.replace(' ', '').replace('-', '')
            if len(cleaned_phone) != 10 or not cleaned_phone.startswith('0'):
                raise ValidationError({
                    'phone_number': 'Phone number must be exactly 10 digits starting with 0'
                })
            # Update the field with cleaned value
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


# ===== TEACHER MANAGEMENT =====


class Teacher(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
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
                    # Extract the sequence number from the employee_id
                    # Format: TCH2025001 -> extract "001"
                    last_sequence = int(last_teacher.employee_id[7:10])  # TCH2025[001]
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
                if counter > 1000:  # Safety limit
                    raise ValueError("Could not generate unique employee ID")
        
        super().save(*args, **kwargs)
    
    def get_assigned_classes(self):
        """Get classes assigned to this teacher"""
        return ClassAssignment.objects.filter(teacher=self)
    
    def get_students_count(self):
        """Get count of students taught by this teacher"""
        if self.class_levels:
            class_levels = [level.strip() for level in self.class_levels.split(',')]
            return Student.objects.filter(class_level__in=class_levels, is_active=True).count()
        return 0


# ===== PARENT/GUARDIAN MANAGEMENT =====

# In core/models.py - Update ParentGuardian model

class ParentGuardian(models.Model):
    RELATIONSHIP_CHOICES = [
        ('F', 'Father'),
        ('M', 'Mother'),
        ('B', 'Brother'),
        ('S', 'Sister'),
        ('G', 'Guardian'),
        ('O', 'Other Relative'),
    ]
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parentguardian', null=True, blank=True)
    students = models.ManyToManyField(Student, related_name='parents')
    occupation = models.CharField(max_length=100, blank=True)
    relationship = models.CharField(max_length=1, choices=RELATIONSHIP_CHOICES)
    phone_number = models.CharField(
        max_length=10, 
        validators=[
            RegexValidator(
                r'^0\d{9}$',
                message="Phone number must be 10 digits starting with 0 (e.g., 0245478847)"
            )
        ],
        help_text="10-digit phone number starting with 0 (e.g., 0245478847)"
    )
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_emergency_contact = models.BooleanField(default=False)
    emergency_contact_priority = models.PositiveSmallIntegerField(
        default=1, 
        validators=[MinValueValidator(1), MaxValueValidator(5)]
    )
    
    # NEW FIELDS FOR ACCOUNT MANAGEMENT
    account_status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending Activation'),
            ('active', 'Active'),
            ('inactive', 'Inactive'),
            ('suspended', 'Suspended'),
        ],
        default='pending'
    )
    last_login_date = models.DateTimeField(null=True, blank=True)
    login_count = models.PositiveIntegerField(default=0)
    account_created = models.DateTimeField(auto_now_add=True)
    account_updated = models.DateTimeField(auto_now=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['emergency_contact_priority', 'user__last_name']
        verbose_name_plural = "Parents/Guardians"
        verbose_name = "Parent/Guardian"
        
    def __str__(self):
        student_names = ", ".join([student.get_full_name() for student in self.students.all()])
        if self.user:
            return f"{self.user.get_full_name()} ({self.get_relationship_display()}) - {student_names}"
        return f"{self.get_relationship_display()} - {student_names}"
    
    def get_user_full_name(self):
        if self.user:
            return self.user.get_full_name()
        return "No User Account"
    
    def has_active_account(self):
        """Check if parent has an active user account"""
        return self.user is not None and self.account_status == 'active'
    
    def can_login(self):
        """Check if parent can login"""
        return self.has_active_account() and self.account_status == 'active'
    
    def get_children(self):
        """Get all children/students associated with this parent"""
        return self.students.all()
    
    def get_children_count(self):
        """Get number of children"""
        return self.students.count()
    
    def update_login_stats(self):
        """Update login statistics"""
        if self.user:
            self.last_login_date = timezone.now()
            self.login_count += 1
            self.save(update_fields=['last_login_date', 'login_count', 'account_updated'])
    
    def create_user_account(self, password=None):
        """Create a user account for this parent"""
        if self.user:
            return self.user  # Account already exists
            
        if not self.email:
            raise ValueError("Email is required to create a user account")
        
        # Generate username from email
        base_username = self.email.split('@')[0]
        username = base_username
        counter = 1
        while User.objects.filter(username=username).exists():
            username = f"{base_username}{counter}"
            counter += 1
        
        # Create user
        user = User.objects.create_user(
            username=username,
            email=self.email,
            password=password or User.objects.make_random_password(),
            first_name="Parent",  # Will be updated with actual data
            last_name=self.email.split('@')[0]
        )
        
        self.user = user
        self.account_status = 'active'
        self.save()
        
        return user

    def clean(self):
        # Validate email uniqueness
        if self.email:
            existing = ParentGuardian.objects.filter(
                email=self.email
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError({'email': 'This email is already registered'})
        
        # Additional phone number validation
        if self.phone_number:
            # Remove any spaces or dashes that might have been entered
            cleaned_phone = self.phone_number.replace(' ', '').replace('-', '')
            if len(cleaned_phone) != 10 or not cleaned_phone.startswith('0'):
                raise ValidationError({
                    'phone_number': 'Phone number must be exactly 10 digits starting with 0'
                })
            # Update the field with cleaned value
            self.phone_number = cleaned_phone


@receiver(post_save, sender=ParentGuardian)
def handle_parent_user_account(sender, instance, created, **kwargs):
    """
    Automatically create user account for parents with email
    Enhanced version with better error handling
    """
    if created and instance.email and not instance.user:
        try:
            # Check if user already exists with this email
            user = User.objects.filter(email=instance.email).first()
            if user:
                # Link existing user
                instance.user = user
                instance.account_status = 'active'
                instance.save(update_fields=['user', 'account_status'])
            else:
                # Create new user account
                instance.create_user_account()
                
                # Send activation email (you can implement this)
                # send_parent_account_activation_email(instance)
                
        except Exception as e:
            logger.error(f"Error creating user for parent {instance.email}: {e}")
            # Don't raise exception to prevent save failure

@receiver(post_save, sender=User)
def update_parent_login_stats(sender, instance, **kwargs):
    """
    Update parent login statistics when user logs in
    """
    try:
        if hasattr(instance, 'parentguardian'):
            parent = instance.parentguardian
            parent.update_login_stats()
    except ParentGuardian.DoesNotExist:
        pass



# ===== PARENT COMMUNICATION MODELS =====

class ParentAnnouncement(models.Model):
    TARGET_TYPES = [
        ('ALL', 'All Parents'),
        ('CLASS', 'Specific Class'),
        ('INDIVIDUAL', 'Individual Parents'),
    ]
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    target_type = models.CharField(max_length=20, choices=TARGET_TYPES, default='ALL')
    target_class = models.CharField(max_length=50, blank=True, null=True)
    target_parents = models.ManyToManyField('ParentGuardian', blank=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    is_important = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Parent Announcement'
        verbose_name_plural = 'Parent Announcements'
    
    def __str__(self):
        return self.title

class ParentMessage(models.Model):
    sender = models.ForeignKey(User, on_delete=models.CASCADE, related_name='sent_parent_messages')
    receiver = models.ForeignKey(User, on_delete=models.CASCADE, related_name='received_parent_messages')
    parent = models.ForeignKey('ParentGuardian', on_delete=models.CASCADE, null=True, blank=True)
    teacher = models.ForeignKey('Teacher', on_delete=models.CASCADE, null=True, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    timestamp = models.DateTimeField(auto_now_add=True)
    is_read = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Parent Message'
        verbose_name_plural = 'Parent Messages'
    
    def __str__(self):
        return f"{self.subject} - {self.sender} to {self.receiver}"

class ParentEvent(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    location = models.CharField(max_length=200, blank=True)
    is_whole_school = models.BooleanField(default=False)
    class_level = models.CharField(max_length=50, blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['start_date']
        verbose_name = 'Parent Event'
        verbose_name_plural = 'Parent Events'
    
    def __str__(self):
        return self.title

# ===== CLASS ASSIGNMENT =====

class ClassAssignment(models.Model):
    class_level = models.CharField(max_length=2, choices=CLASS_LEVEL_CHOICES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    academic_year = models.CharField(max_length=9, validators=[RegexValidator(r'^\d{4}/\d{4}$')])
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('class_level', 'subject', 'academic_year')
        verbose_name = 'Class Assignment'
        verbose_name_plural = 'Class Assignments'
        ordering = ['class_level', 'subject']
        indexes = [
            # NEW indexes
            models.Index(fields=['class_level', 'subject', 'academic_year']),
            models.Index(fields=['teacher', 'is_active']),
            models.Index(fields=['is_active', 'academic_year']),
            models.Index(fields=['class_level', 'is_active']),
        ]

    def __str__(self):
        return f"{self.get_class_level_display()} - {self.subject} - {self.teacher} ({self.academic_year})"
    
    def get_students(self):
        """Get all students in this class"""
        return Student.objects.filter(class_level=self.class_level, is_active=True)
    
    def get_students_count(self):
        """Get count of students in this class"""
        return self.get_students().count()

# ===== ATTENDANCE MANAGEMENT =====

class AttendancePeriod(models.Model):
    PERIOD_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('custom', 'Custom'),
    ]
    
    period_type = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    name = models.CharField(max_length=100, blank=True, help_text="Custom name for the period")
    term = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE, related_name='attendance_periods')
    start_date = models.DateField()
    end_date = models.DateField()
    is_locked = models.BooleanField(default=False, help_text="Lock period to prevent modifications")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('period_type', 'term', 'start_date')
        ordering = ['-start_date']
        verbose_name = 'Attendance Period'
        verbose_name_plural = 'Attendance Periods'
    
    def __str__(self):
        if self.name:
            return f"{self.name} ({self.start_date} to {self.end_date})"
        return f"{self.get_period_type_display()} ({self.start_date} to {self.end_date})"
    
    def clean(self):
        if self.start_date > self.end_date:
            raise ValidationError("End date must be after start date")
        
        if (self.start_date < self.term.start_date or 
            self.end_date > self.term.end_date):
            raise ValidationError("Period must be within term dates")
        
        overlapping = AttendancePeriod.objects.filter(
            period_type=self.period_type,
            term=self.term,
            start_date__lte=self.end_date,
            end_date__gte=self.start_date
        ).exclude(pk=self.pk)
        
        if overlapping.exists():
            raise ValidationError("This period overlaps with an existing period")
    
    def get_total_school_days(self):
        """Calculate total school days in the period"""
        total_days = 0
        current_date = self.start_date
        
        while current_date <= self.end_date:
            if current_date.weekday() < 5:
                total_days += 1
            current_date += timedelta(days=1)
        
        return total_days

class StudentAttendance(models.Model, GhanaEducationMixin):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
        ('sick', 'Sick'),
        ('other', 'Other'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendances')
    date = models.DateField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    period = models.ForeignKey(AttendancePeriod, on_delete=models.CASCADE, null=True, blank=True)
    term = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name='Recorded By'
    )
    notes = models.TextField(blank=True, help_text="Additional notes about attendance")
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('student', 'date', 'period')
        ordering = ['-date', 'student__last_name']
        verbose_name = 'Student Attendance'
        verbose_name_plural = 'Student Attendances'
        indexes = [
            models.Index(fields=['student', 'date']),
            models.Index(fields=['date', 'status']),
            models.Index(fields=['term', 'student']),
        ]
    
    def __str__(self):
        return f"{self.student} - {self.date} - {self.get_status_display()}"
    
    def clean(self):
        if not (self.term.start_date <= self.date <= self.term.end_date):
            raise ValidationError("Date must be within the term dates")
        
        if self.period and not (self.period.start_date <= self.date <= self.period.end_date):
            raise ValidationError("Date must be within the period dates")
        
        if self.period and self.period.is_locked:
            if self.pk is None:
                raise ValidationError("Cannot create attendance for a locked period")
            else:
                original = StudentAttendance.objects.get(pk=self.pk)
                if original.period != self.period or original.date != self.date:
                    raise ValidationError("Cannot modify attendance for a locked period")
    
    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self.update_attendance_summary()
    
    def update_attendance_summary(self):
        """Update attendance summary for this student and term"""
        from datetime import date
        
        # Update term summary
        term_summary, created = AttendanceSummary.objects.get_or_create(
            student=self.student,
            term=self.term,
            period=None
        )
        term_summary.calculate_summary()
        
        # Update period summary if period exists
        if self.period:
            period_summary, created = AttendanceSummary.objects.get_or_create(
                student=self.student,
                term=self.term,
                period=self.period
            )
            period_summary.calculate_summary()
    
    def is_ghana_school_day(self):
        """Check if the attendance date is a valid Ghana school day"""
        if self.date.weekday() >= 5:
            return False
        
        ghana_holidays = [
            date(self.date.year, 1, 1),
            date(self.date.year, 3, 6),
            date(self.date.year, 5, 1),
            date(self.date.year, 7, 1),
            date(self.date.year, 12, 25),
            date(self.date.year, 12, 26),
        ]
        
        return self.date not in ghana_holidays
    
    @property
    def is_present(self):
        """Check if student is considered present (includes late and excused)"""
        return self.status in ['present', 'late', 'excused']

class AttendanceSummary(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='attendance_summaries')
    term = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE)
    period = models.ForeignKey(AttendancePeriod, on_delete=models.CASCADE, null=True, blank=True)
    
    # Counts
    days_present = models.PositiveIntegerField(default=0)
    days_absent = models.PositiveIntegerField(default=0)
    days_late = models.PositiveIntegerField(default=0)
    days_excused = models.PositiveIntegerField(default=0)
    days_sick = models.PositiveIntegerField(default=0)
    days_other = models.PositiveIntegerField(default=0)
    
    # Calculated fields
    total_days = models.PositiveIntegerField(default=0)
    attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    present_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('student', 'term', 'period')
        verbose_name_plural = 'Attendance Summaries'
        ordering = ['student__last_name', 'student__first_name']
    
    def __str__(self):
        period_name = self.period.name if self.period else 'Term'
        return f"{self.student} - {period_name} - {self.attendance_rate}%"
    
    def calculate_summary(self):
        """Calculate and update attendance summary"""
        filters = {
            'student': self.student,
            'term': self.term,
        }
        
        if self.period:
            filters['period'] = self.period
            attendance_records = StudentAttendance.objects.filter(
                **filters,
                date__range=[self.period.start_date, self.period.end_date]
            )
        else:
            attendance_records = StudentAttendance.objects.filter(
                **filters,
                date__range=[self.term.start_date, self.term.end_date]
            )
        
        # Count by status
        self.days_present = attendance_records.filter(status='present').count()
        self.days_absent = attendance_records.filter(status='absent').count()
        self.days_late = attendance_records.filter(status='late').count()
        self.days_excused = attendance_records.filter(status='excused').count()
        self.days_sick = attendance_records.filter(status='sick').count()
        self.days_other = attendance_records.filter(status='other').count()
        
        # Calculate totals and rates
        self.total_days = attendance_records.count()
        
        if self.total_days > 0:
            present_days = self.days_present + self.days_late + self.days_excused
            self.present_rate = (present_days / self.total_days) * 100
            self.attendance_rate = (self.days_present / self.total_days) * 100
        
        self.save()
    
    def get_ges_compliance(self):
        """Check if attendance meets Ghana Education Service requirements (80% minimum)"""
        return self.present_rate >= 80.0
    
    def get_status_display(self):
        """Get display status for the summary"""
        if self.present_rate >= 90:
            return "Excellent"
        elif self.present_rate >= 80:
            return "Good"
        elif self.present_rate >= 70:
            return "Fair"
        else:
            return "Poor"

# ===== GRADE MANAGEMENT =====

# In core/models.py - Complete updated Grade class
# In core/models.py - Complete updated Grade model with enhanced class assignment logic

class Grade(models.Model):
    """
    Enhanced Grade Model with comprehensive validation, business logic,
    and professional error handling for Ghana Education Service standards.
    """
    
    # Ghana Education Service Standard Weights
    HOMEWORK_WEIGHT = Decimal('10.00')  # 10%
    CLASSWORK_WEIGHT = Decimal('30.00')  # 30%  
    TEST_WEIGHT = Decimal('10.00')       # 10%
    EXAM_WEIGHT = Decimal('50.00')       # 50%

    # GES Grade Choices with detailed descriptions
    GES_GRADE_CHOICES = [
        ('1', '1 (90-100%) - Outstanding - Excellent performance'),
        ('2', '2 (80-89%) - Excellent - Strong performance'), 
        ('3', '3 (70-79%) - Very Good - Above average performance'),
        ('4', '4 (60-69%) - Good - Meets expectations'),
        ('5', '5 (50-59%) - Satisfactory - Needs improvement'),
        ('6', '6 (40-49%) - Fair - Below expectations'),
        ('7', '7 (30-39%) - Weak - Significant improvement needed'),
        ('8', '8 (20-29%) - Very Weak - Concerning performance'),
        ('9', '9 (0-19%) - Fail - Immediate intervention required'),
        ('N/A', 'Not Available'),
    ]

    # Letter Grade Choices
    LETTER_GRADE_CHOICES = [
        ('A+', 'A+ (90-100%) - Outstanding - Excellent performance'),
        ('A', 'A (80-89%) - Excellent - Strong performance'),
        ('B+', 'B+ (70-79%) - Very Good - Above average performance'),
        ('B', 'B (60-69%) - Good - Meets expectations'),
        ('C+', 'C+ (50-59%) - Satisfactory - Needs improvement'),
        ('C', 'C (40-49%) - Fair - Below expectations'),
        ('D+', 'D+ (30-39%) - Weak - Significant improvement needed'),
        ('D', 'D (20-29%) - Very Weak - Concerning performance'),
        ('F', 'F (0-19%) - Fail - Immediate intervention required'),
        ('N/A', 'Not Available'),
    ]

    # Model Fields
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='grades')
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE, related_name='grades')
    class_assignment = models.ForeignKey(
        'ClassAssignment', 
        on_delete=models.CASCADE, 
        related_name='grades',
        null=True,
        blank=True
    )
    academic_year = models.CharField(
        max_length=9, 
        validators=[RegexValidator(r'^\d{4}/\d{4}$', 'Academic year must be in format YYYY/YYYY')]
    )
    term = models.PositiveSmallIntegerField(choices=[
        (1, 'Term 1'),
        (2, 'Term 2'), 
        (3, 'Term 3')
    ])

    # Score fields with comprehensive validators
    classwork_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.00'), 'Score cannot be negative'),
            MaxValueValidator(CLASSWORK_WEIGHT, f'Classwork score cannot exceed {CLASSWORK_WEIGHT}%')
        ],
        verbose_name="Classwork Score (30%)",
        default=Decimal('0.00'),
        help_text="Classwork assessment score (0-30%)"
    )
    
    homework_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.00'), 'Score cannot be negative'),
            MaxValueValidator(HOMEWORK_WEIGHT, f'Homework score cannot exceed {HOMEWORK_WEIGHT}%')
        ],
        verbose_name="Homework Score (10%)",
        default=Decimal('0.00'),
        help_text="Homework assignment score (0-10%)"
    )
    
    test_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.00'), 'Score cannot be negative'),
            MaxValueValidator(TEST_WEIGHT, f'Test score cannot exceed {TEST_WEIGHT}%')
        ],
        verbose_name="Test Score (10%)", 
        default=Decimal('0.00'),
        help_text="Test/examination score (0-10%)"
    )
    
    exam_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        validators=[
            MinValueValidator(Decimal('0.00'), 'Score cannot be negative'),
            MaxValueValidator(EXAM_WEIGHT, f'Exam score cannot exceed {EXAM_WEIGHT}%')
        ],
        verbose_name="Exam Score (50%)",
        default=Decimal('0.00'),
        help_text="Final examination score (0-50%)"
    )

    # Calculated fields
    total_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        editable=False, 
        null=True, 
        blank=True,
        verbose_name="Total Score",
        help_text="Automatically calculated total score"
    )
    
    ges_grade = models.CharField(
        max_length=3, 
        choices=GES_GRADE_CHOICES, 
        editable=False, 
        default='N/A',
        verbose_name="GES Grade",
        help_text="Automatically determined GES grade"
    )
    
    letter_grade = models.CharField(
        max_length=3,
        choices=LETTER_GRADE_CHOICES,
        editable=False,
        blank=True,
        null=True,
        verbose_name="Letter Grade",
        help_text="Automatically determined letter grade"
    )
    
    remarks = models.TextField(
        blank=True,
        verbose_name="Teacher Remarks",
        help_text="Additional comments or notes about the grade"
    )
    
    # NEW: Class level field to help with class assignment creation
    class_level = models.CharField(
        max_length=2,
        choices=CLASS_LEVEL_CHOICES,
        blank=True,
        null=True,
        verbose_name="Class Level",
        help_text="Student's class level (auto-set from student)"
    )
    
    # Audit fields
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL, 
        null=True,
        verbose_name="Recorded By",
        help_text="User who recorded this grade"
    )
    
    last_updated = models.DateTimeField(
        auto_now=True,
        verbose_name="Last Updated"
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Created At"
    )
    
    # Status fields
    is_locked = models.BooleanField(
        default=False,
        verbose_name="Is Locked",
        help_text="Prevent further modifications to this grade"
    )
    
    requires_review = models.BooleanField(
        default=False,
        verbose_name="Requires Review",
        help_text="Flag for administrative review"
    )
    
    review_notes = models.TextField(
        blank=True,
        verbose_name="Review Notes",
        help_text="Notes from administrative review"
    )

    class Meta:
        unique_together = ('student', 'subject', 'academic_year', 'term')
        ordering = ['academic_year', 'term', 'student__last_name', 'subject__name']
        verbose_name = 'Grade'
        verbose_name_plural = 'Grades'
        indexes = [
            # Existing indexes
            models.Index(fields=['student', 'academic_year', 'term']),
            models.Index(fields=['subject', 'academic_year']),
            models.Index(fields=['class_assignment', 'term']),
            models.Index(fields=['total_score']),
            models.Index(fields=['ges_grade']),
            models.Index(fields=['letter_grade']),
            
            # NEW indexes for better performance
            models.Index(fields=['student', 'subject', 'academic_year', 'term']),
            models.Index(fields=['total_score', 'ges_grade']),
            models.Index(fields=['created_at']),
            models.Index(fields=['class_assignment', 'academic_year', 'term']),
            models.Index(fields=['student', 'class_assignment']),
            models.Index(fields=['academic_year', 'term', 'class_level']),
        ]
    def __str__(self):
        """Fixed: Use get_display_grade method for consistent grade display"""
        grade_display = self.get_display_grade()
        return f"{self.student.get_full_name()} - {self.subject.name} ({self.academic_year} Term {self.term}): {grade_display}"

    def clean(self):
        """
        Comprehensive validation for grade data with detailed error handling
        """
        errors = {}
        
        try:
            # Validate basic field presence
            if not self.student_id:
                errors['student'] = 'Student is required'
            
            if not self.subject_id:
                errors['subject'] = 'Subject is required'
            
            # Validate academic year format and logic
            if self.academic_year:
                if not re.match(r'^\d{4}/\d{4}$', self.academic_year):
                    errors['academic_year'] = 'Academic year must be in format YYYY/YYYY'
                else:
                    # Validate consecutive years
                    try:
                        year1, year2 = map(int, self.academic_year.split('/'))
                        if year2 != year1 + 1:
                            errors['academic_year'] = 'The second year must be exactly one year after the first year'
                    except (ValueError, IndexError):
                        errors['academic_year'] = 'Invalid academic year format'
            
            # Validate term range
            if self.term and self.term not in [1, 2, 3]:
                errors['term'] = 'Term must be 1, 2, or 3'
            
            # Validate score limits with precise decimal validation
            score_fields = {
                'classwork_score': self.CLASSWORK_WEIGHT,
                'homework_score': self.HOMEWORK_WEIGHT,
                'test_score': self.TEST_WEIGHT,
                'exam_score': self.EXAM_WEIGHT,
            }
            
            for field_name, max_score in score_fields.items():
                score = getattr(self, field_name, Decimal('0.00'))
                if score is None:
                    continue
                    
                try:
                    score_decimal = Decimal(str(score))
                    if score_decimal < Decimal('0.00'):
                        errors[field_name] = 'Score cannot be negative'
                    elif score_decimal > max_score:
                        errors[field_name] = f'Score cannot exceed {max_score}%'
                    # Validate decimal precision
                    if abs(score_decimal - score_decimal.quantize(Decimal('0.01'))) > Decimal('0.001'):
                        errors[field_name] = 'Score must have at most 2 decimal places'
                except (InvalidOperation, TypeError, ValueError) as e:
                    errors[field_name] = 'Invalid score format'
                    logger.warning(f"Invalid score format in {field_name}: {score} - {e}")
            
            # Validate total score consistency
            if not errors:
                total_calculated = self._calculate_total_score_safe()
                if total_calculated is not None and total_calculated > Decimal('100.00'):
                    errors['__all__'] = f'Total score cannot exceed 100%. Current calculated total: {total_calculated}%'
            
            # Validate business rules
            self._validate_business_rules(errors)
            
            # Validate against existing grades for uniqueness
            if not errors and self.pk is None:  # Only for new instances
                self._validate_unique_grade(errors)
            
        except Exception as e:
            logger.error(f"Unexpected error during grade validation: {str(e)}", exc_info=True)
            errors['__all__'] = 'An unexpected validation error occurred. Please try again.'
        
        if errors:
            logger.warning(
                f"Grade validation failed - Student: {getattr(self.student, 'id', 'Unknown')}, "
                f"Subject: {getattr(self.subject, 'name', 'Unknown')}, Errors: {errors}"
            )
            raise ValidationError(errors)

    def _validate_business_rules(self, errors):
        """
        Validate business rules and constraints
        """
        try:
            # Check if student is active
            if self.student_id and not self.student.is_active:
                errors['student'] = 'Cannot assign grade to inactive student'
            
            # Check if subject is active
            if self.subject_id and not self.subject.is_active:
                errors['subject'] = 'Cannot assign grade for inactive subject'
            
            # Check if academic term is editable
            if self._is_term_locked():
                errors['__all__'] = 'Cannot modify grades for locked academic term'
            
            # Check if class assignment exists and validate it
            if self.class_assignment_id:
                if self.student_id and self.student.class_level != self.class_assignment.class_level:
                    errors['class_assignment'] = 'Class assignment does not match student class level'
                if self.subject_id and self.subject != self.class_assignment.subject:
                    errors['class_assignment'] = 'Class assignment does not match subject'
            
            # Check for significant changes if updating existing grade
            if self.pk:
                self._validate_grade_changes(errors)
                
        except Exception as e:
            logger.error(f"Business rule validation failed: {str(e)}")
            errors['__all__'] = 'Error validating business rules'

    def _validate_unique_grade(self, errors):
        """
        Validate grade uniqueness constraint
        """
        try:
            existing_grade = Grade.objects.filter(
                student=self.student,
                subject=self.subject,
                academic_year=self.academic_year,
                term=self.term
            ).exists()
            
            if existing_grade:
                errors['__all__'] = (
                    'A grade already exists for this student, subject, term, and academic year. '
                    'Please update the existing grade instead.'
                )
        except Exception as e:
            logger.error(f"Unique grade validation failed: {str(e)}")
            errors['__all__'] = 'Error checking for duplicate grades'

    def _validate_grade_changes(self, errors):
        """
        Validate changes to existing grade for significant modifications
        """
        try:
            original_grade = Grade.objects.get(pk=self.pk)
            
            # Check if grade is locked
            if original_grade.is_locked:
                errors['__all__'] = 'This grade is locked and cannot be modified'
                return
            
            # Check for significant score changes
            significant_changes = []
            score_fields = ['classwork_score', 'homework_score', 'test_score', 'exam_score']
            
            for field in score_fields:
                original_value = getattr(original_grade, field, Decimal('0.00'))
                new_value = getattr(self, field, Decimal('0.00'))
                
                if abs(float(new_value) - float(original_value)) > 20.0:
                    significant_changes.append(field.replace('_score', ''))
            
            if significant_changes:
                self.requires_review = True
                logger.info(
                    f"Grade marked for review due to significant changes - "
                    f"Grade ID: {self.pk}, Changes: {significant_changes}"
                )
                
        except Grade.DoesNotExist:
            logger.warning(f"Original grade not found during change validation - PK: {self.pk}")
        except Exception as e:
            logger.error(f"Grade change validation failed: {str(e)}")

    def _is_term_locked(self):
        """
        Check if the academic term is locked for editing
        """
        try:
            from .models import AcademicTerm
            term_obj = AcademicTerm.objects.filter(
                academic_year=self.academic_year,
                term=self.term
            ).first()
            
            if term_obj and getattr(term_obj, 'is_locked', False):
                return True
                
            return False
        except Exception as e:
            logger.warning(f"Error checking term lock status: {str(e)}")
            return False

    def _calculate_total_score_safe(self):
        """
        Safely calculate total score without side effects
        """
        try:
            scores = [
                self.classwork_score or Decimal('0.00'),
                self.homework_score or Decimal('0.00'),
                self.test_score or Decimal('0.00'),
                self.exam_score or Decimal('0.00')
            ]
            
            total = sum(score for score in scores if score is not None)
            return total.quantize(Decimal('0.01'))
            
        except (TypeError, InvalidOperation, ValueError) as e:
            logger.error(f"Error in safe total score calculation: {str(e)}")
            return None

    def get_or_create_class_assignment(self):
        """
        Enhanced class assignment creation with comprehensive error handling
        and teacher assignment logic
        """
        from django.db import transaction
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            # Validate required fields
            if not all([self.student, self.subject, self.academic_year]):
                raise ValueError(
                    "Missing required fields for class assignment: "
                    "student, subject, and academic year are required"
                )
            
            # Determine target class level
            target_class_level = self.class_level or getattr(self.student, 'class_level', None)
            if not target_class_level:
                raise ValueError("No class level specified for class assignment")
            
            # Format academic year consistently (YYYY/YYYY -> YYYY-YYYY)
            formatted_academic_year = self.academic_year.replace('/', '-')
            
            logger.debug(
                f"Creating class assignment - Class: {target_class_level}, "
                f"Subject: {self.subject.name}, Year: {formatted_academic_year}"
            )
            
            # Look for existing active class assignment
            class_assignment = ClassAssignment.objects.filter(
                class_level=target_class_level,
                subject=self.subject,
                academic_year=formatted_academic_year,
                is_active=True
            ).select_related('teacher', 'teacher__user').first()
            
            if class_assignment:
                logger.debug(f"Found existing class assignment: {class_assignment}")
                return class_assignment
            
            # No existing assignment found - create a new one
            logger.debug("No existing class assignment found, creating new one")
            
            # Find appropriate teacher using multiple strategies
            teacher = self._find_appropriate_teacher(target_class_level)
            
            if not teacher:
                # Create a temporary teacher if none found
                teacher = self._create_temporary_teacher()
            
            # Create the class assignment
            with transaction.atomic():
                class_assignment = ClassAssignment.objects.create(
                    class_level=target_class_level,
                    subject=self.subject,
                    teacher=teacher,
                    academic_year=formatted_academic_year,
                    is_active=True
                )
                
                logger.info(
                    f"Created new class assignment - ID: {class_assignment.id}, "
                    f"Class: {target_class_level}, Subject: {self.subject.name}, "
                    f"Teacher: {teacher.employee_id}, Year: {formatted_academic_year}"
                )
                
                # Update analytics cache
                self._update_class_assignment_cache(class_assignment)
                
                return class_assignment
                
        except Exception as e:
            logger.error(
                f"Failed to get/create class assignment - "
                f"Student: {getattr(self.student, 'id', 'Unknown')}, "
                f"Subject: {getattr(self.subject, 'name', 'Unknown')}, "
                f"Error: {str(e)}",
                exc_info=True
            )
            raise
    
    def _find_appropriate_teacher(self, class_level):
        """
        Find appropriate teacher for the class assignment using multiple strategies
        """
        try:
            # Strategy 1: Find teachers who teach this subject
            subject_teachers = Teacher.objects.filter(
                subjects=self.subject,
                is_active=True
            ).select_related('user')
            
            if subject_teachers.exists():
                # Strategy 1a: Find teachers who already teach this class level
                for teacher in subject_teachers:
                    # Safely handle class_levels field (could be None or empty)
                    if teacher.class_levels:
                        teacher_classes = [cls.strip() for cls in teacher.class_levels.split(',')]
                        if class_level in teacher_classes:
                            logger.debug(f"Found teacher {teacher.employee_id} for class {class_level}")
                            return teacher
                
                # Strategy 1b: Use first available subject teacher
                teacher = subject_teachers.first()
                logger.debug(f"Using subject teacher {teacher.employee_id} for class {class_level}")
                return teacher
            
            # Strategy 2: Find teachers who teach this class level
            class_teachers = Teacher.objects.filter(
                is_active=True
            ).select_related('user')
            
            for teacher in class_teachers:
                if teacher.class_levels:
                    teacher_classes = [cls.strip() for cls in teacher.class_levels.split(',')]
                    if class_level in teacher_classes:
                        logger.debug(f"Found class teacher {teacher.employee_id} for class {class_level}")
                        return teacher
            
            # Strategy 3: Find any active teacher
            any_teacher = Teacher.objects.filter(is_active=True).first()
            if any_teacher:
                logger.debug(f"Using available teacher {any_teacher.employee_id} for class {class_level}")
                return any_teacher
            
            logger.warning(f"No active teachers found for class {class_level}")
            return None
            
        except Exception as e:
            logger.error(f"Error finding appropriate teacher: {str(e)}", exc_info=True)
            return None
    
    def _create_temporary_teacher(self):
        """
        Create a temporary teacher record when no teachers are available
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        try:
            # Find or create a system user for temporary teachers
            system_user, created = User.objects.get_or_create(
                username='system_teacher',
                defaults={
                    'email': 'system@school.edu',
                    'first_name': 'System',
                    'last_name': 'Teacher',
                    'is_active': True,
                    'is_staff': True
                }
            )
            
            # Generate temporary employee ID
            current_year = str(timezone.now().year)
            teacher_count = Teacher.objects.count()
            employee_id = f"TEMP{current_year}{teacher_count + 1:04d}"
            
            # Create temporary teacher
            teacher = Teacher.objects.create(
                user=system_user,
                employee_id=employee_id,
                date_of_birth=date(1980, 1, 1),
                gender='M',
                phone_number='0240000000',
                address='Temporary System Teacher',
                qualification='System Generated',
                class_levels='P1,P2,P3,P4,P5,P6,J1,J2,J3',  # All classes
                is_active=True
            )
            
            # Add subject to teacher
            teacher.subjects.add(self.subject)
            
            logger.warning(f"Created temporary teacher {employee_id} for subject {self.subject.name}")
            
            return teacher
            
        except Exception as e:
            logger.error(f"Failed to create temporary teacher: {str(e)}", exc_info=True)
            # Last resort: return any teacher or None
            return Teacher.objects.filter(is_active=True).first()
    
    def _update_class_assignment_cache(self, class_assignment):
        """Update cache after creating class assignment"""
        try:
            from django.core.cache import cache
            
            # Clear cache for this class level and subject
            cache_key = f"class_assignments_{class_assignment.class_level}_{class_assignment.subject_id}"
            cache.delete(cache_key)
            
            # Clear teacher assignment cache
            teacher_cache_key = f"teacher_assignments_{class_assignment.teacher_id}"
            cache.delete(teacher_cache_key)
            
        except Exception as e:
            logger.warning(f"Failed to update class assignment cache: {str(e)}")

    @transaction.atomic
    def save(self, *args, **kwargs):
        """
        Enhanced save method with comprehensive error handling, validation,
        and business logic execution.
        """
        try:
            # Pre-save validation
            is_new = self.pk is None
            
            # Set class_level from student if not set
            if self.student and not self.class_level:
                self.class_level = self.student.class_level
            
            # Auto-create class_assignment if not set
            if not self.class_assignment_id and self.student and self.subject and self.academic_year:
                try:
                    self.class_assignment = self.get_or_create_class_assignment()
                except Exception as e:
                    logger.warning(f"Could not auto-create class assignment: {e}")
                    # Don't fail the save - class_assignment can be set later
            
            # Run full validation
            self.full_clean()
            
            # Pre-save calculations
            self._pre_save_calculations()
            
            # Determine if this is an update and capture changes
            if not is_new:
                self._capture_changes_for_audit()
            
            # Save the instance
            super().save(*args, **kwargs)
            
            # Post-save operations
            self._post_save_operations(is_new)
            
            logger.info(
                f"Grade saved successfully - ID: {self.pk}, "
                f"Student: {self.student_id}, Subject: {self.subject_id}, "
                f"Total Score: {self.total_score}, GES Grade: {self.ges_grade}, Letter Grade: {self.letter_grade}"
            )
            
        except ValidationError as e:
            logger.error(
                f"Grade validation failed during save - "
                f"Student: {getattr(self.student, 'id', 'Unknown')}, "
                f"Subject: {getattr(self.subject, 'name', 'Unknown')}, "
                f"Errors: {e.message_dict}"
            )
            raise
        except Exception as e:
            logger.error(
                f"Unexpected error saving grade - "
                f"Student: {getattr(self.student, 'id', 'Unknown')}, "
                f"Subject: {getattr(self.subject, 'name', 'Unknown')}, "
                f"Error: {str(e)}",
                exc_info=True
            )
            raise

    def _pre_save_calculations(self):
        """
        Perform all calculations before saving
        """
        try:
            # Calculate total score
            self.calculate_total_score()
            
            # Determine both GES and Letter grades
            self.determine_grades()
            
            # Set recorded_by if not set and we have a request context
            if not self.recorded_by and hasattr(self, '_request_user'):
                self.recorded_by = self._request_user
            
            # Update timestamps
            if not self.pk:
                self.created_at = timezone.now()
            
        except Exception as e:
            logger.error(f"Pre-save calculations failed: {str(e)}")
            raise

    def _capture_changes_for_audit(self):
        """
        Capture changes for audit logging (called before update)
        """
        try:
            if self.pk:
                original = Grade.objects.get(pk=self.pk)
                self._changes = self._get_field_changes(original)
        except Grade.DoesNotExist:
            self._changes = {}
        except Exception as e:
            logger.warning(f"Failed to capture changes for audit: {str(e)}")
            self._changes = {}

    def _get_field_changes(self, original):
        """
        Get dictionary of changed fields and their values
        """
        changes = {}
        fields = ['classwork_score', 'homework_score', 'test_score', 'exam_score', 'total_score', 'ges_grade', 'letter_grade']
        
        for field in fields:
            original_value = getattr(original, field)
            new_value = getattr(self, field)
            
            if str(original_value) != str(new_value):
                changes[field] = {
                    'from': original_value,
                    'to': new_value
                }
        
        return changes

    def _post_save_operations(self, is_new):
        """
        Execute post-save operations like audit logging and cache updates
        """
        try:
            # Create audit log entry
            self._create_audit_log_entry(is_new)
            
            # Update analytics cache
            self._update_analytics_cache()
            
            # Send notifications for significant changes
            if not is_new and hasattr(self, '_changes') and self._changes:
                self._send_change_notifications()
                
        except Exception as e:
            logger.error(f"Post-save operations failed: {str(e)}")
            # Don't raise exception as the grade was saved successfully

    def _create_audit_log_entry(self, is_new):
        """
        Create audit log entry for grade creation or modification
        """
        try:
            from .models import AuditLog
            
            action = 'CREATE' if is_new else 'UPDATE'
            details = {
                'student_id': self.student_id,
                'subject_id': self.subject_id,
                'academic_year': self.academic_year,
                'term': self.term,
                'total_score': float(self.total_score) if self.total_score else None,
                'ges_grade': self.ges_grade,
                'letter_grade': self.letter_grade,
            }
            
            if hasattr(self, '_changes'):
                details['changes'] = self._changes
            
            AuditLog.objects.create(
                user=self.recorded_by,
                action=action,
                model_name='Grade',
                object_id=self.id,
                details=details,
                timestamp=timezone.now()
            )
            
        except Exception as e:
            logger.error(f"Failed to create audit log entry: {str(e)}")

    def _update_analytics_cache(self):
        """
        Update analytics cache after grade changes
        """
        try:
            from django.core.cache import cache
            
            cache_keys_to_clear = [
                f"class_performance_{self.subject_id}_{self.student.class_level}_{self.academic_year}_{self.term}",
                f"student_progress_{self.student_id}_{self.academic_year}",
                f"term_report_{self.student.class_level}_{self.academic_year}_{self.term}"
            ]
            
            for cache_key in cache_keys_to_clear:
                cache.delete(cache_key)
                
        except Exception as e:
            logger.warning(f"Failed to update analytics cache: {str(e)}")

    def _send_change_notifications(self):
        """
        Send notifications for significant grade changes
        """
        try:
            # This would integrate with your notification system
            # For now, just log the notification requirement
            if hasattr(self, '_changes') and any(
                field in self._changes for field in 
                ['classwork_score', 'homework_score', 'test_score', 'exam_score']
            ):
                logger.info(
                    f"Grade change notifications required - "
                    f"Grade ID: {self.pk}, Student: {self.student_id}"
                )
                
        except Exception as e:
            logger.error(f"Failed to send change notifications: {str(e)}")

    def calculate_total_score(self):
        """
        Calculate total score with comprehensive error handling
        """
        try:
            scores = [
                self.classwork_score,
                self.homework_score, 
                self.test_score,
                self.exam_score
            ]
            
            # Convert to Decimal and handle None values
            decimal_scores = []
            for score in scores:
                if score is None:
                    decimal_scores.append(Decimal('0.00'))
                else:
                    try:
                        decimal_scores.append(Decimal(str(score)))
                    except (InvalidOperation, TypeError, ValueError):
                        decimal_scores.append(Decimal('0.00'))
                        logger.warning(f"Invalid score converted to 0: {score}")
            
            total = sum(decimal_scores)
            self.total_score = total.quantize(Decimal('0.01'))
            
            logger.debug(f"Total score calculated: {self.total_score} for grade {self.pk}")
            
        except Exception as e:
            logger.error(f"Error calculating total score: {str(e)}", exc_info=True)
            self.total_score = None
            raise

    def determine_grades(self):
        """
        Determine both GES and letter grades based on Ghana Education Service standards
        with comprehensive error handling
        """
        try:
            if self.total_score is None:
                self.ges_grade = 'N/A'
                self.letter_grade = 'N/A'
                return

            score = float(self.total_score)
            
            # GES grading standards
            if score >= 90: 
                self.ges_grade = '1'
            elif score >= 80: 
                self.ges_grade = '2'
            elif score >= 70: 
                self.ges_grade = '3'
            elif score >= 60: 
                self.ges_grade = '4' 
            elif score >= 50: 
                self.ges_grade = '5'
            elif score >= 40: 
                self.ges_grade = '6'
            elif score >= 30: 
                self.ges_grade = '7'
            elif score >= 20: 
                self.ges_grade = '8'
            else: 
                self.ges_grade = '9'
            
            # Letter grading standards
            if score >= 90: 
                self.letter_grade = 'A+'
            elif score >= 80: 
                self.letter_grade = 'A'
            elif score >= 70: 
                self.letter_grade = 'B+'
            elif score >= 60: 
                self.letter_grade = 'B'
            elif score >= 50: 
                self.letter_grade = 'C+'
            elif score >= 40: 
                self.letter_grade = 'C'
            elif score >= 30: 
                self.letter_grade = 'D+'
            elif score >= 20: 
                self.letter_grade = 'D'
            else: 
                self.letter_grade = 'F'
                
            logger.debug(f"Grades determined - GES: {self.ges_grade}, Letter: {self.letter_grade} for score {score}")
            
        except (TypeError, ValueError) as e:
            logger.error(f"Error determining grades: {str(e)}")
            self.ges_grade = 'N/A'
            self.letter_grade = 'N/A'
        except Exception as e:
            logger.error(f"Unexpected error determining grades: {str(e)}", exc_info=True)
            self.ges_grade = 'N/A'
            self.letter_grade = 'N/A'

    def get_display_grade(self):
        """
        Get the grade to display based on system configuration
        """
        try:
            from .grading_utils import get_display_grade as get_system_display_grade
            return get_system_display_grade(self.ges_grade, self.letter_grade)
        except Exception as e:
            logger.error(f"Error getting display grade: {str(e)}")
            # Fallback to showing both if there's an error
            if self.ges_grade and self.ges_grade != 'N/A' and self.letter_grade and self.letter_grade != 'N/A':
                return f"{self.ges_grade} ({self.letter_grade})"
            elif self.ges_grade and self.ges_grade != 'N/A':
                return self.ges_grade
            elif self.letter_grade and self.letter_grade != 'N/A':
                return self.letter_grade
            else:
                return 'N/A'

    def get_grade_description(self):
        """
        Get descriptive text for the grade based on active system
        """
        try:
            from .grading_utils import get_grade_description
            return get_grade_description(self.ges_grade, self.letter_grade)
        except Exception as e:
            logger.error(f"Error getting grade description: {str(e)}")
            descriptions = {
                '1': 'Excellent - Outstanding performance',
                '2': 'Very Good - Strong performance', 
                '3': 'Good - Above average performance',
                '4': 'Satisfactory - Meets expectations',
                '5': 'Fair - Needs improvement',
                '6': 'Marginal - Below expectations',
                '7': 'Poor - Significant improvement needed',
                '8': 'Very Poor - Concerning performance',
                '9': 'Fail - Immediate intervention required',
                'N/A': 'Grade not available'
            }
            return descriptions.get(self.ges_grade, 'Unknown grade')

    def get_grade_color(self):
        """
        Get color for grade display
        """
        try:
            from .grading_utils import get_grade_color
            return get_grade_color(self.ges_grade)
        except Exception as e:
            logger.error(f"Error getting grade color: {str(e)}")
            return 'secondary'

    def get_performance_level(self):
        """
        Get performance level category based on current grading system
        """
        try:
            from .grading_utils import get_grading_system
            
            if not self.total_score:
                return 'Unknown'
                
            score = float(self.total_score)
            grading_system = get_grading_system()
            
            if grading_system == 'GES':
                if score >= 80: return 'Excellent'
                elif score >= 70: return 'Very Good'
                elif score >= 60: return 'Good'
                elif score >= 50: return 'Satisfactory'
                elif score >= 40: return 'Fair'
                else: return 'Poor'
            else:  # LETTER or BOTH
                if score >= 80: return 'Excellent'
                elif score >= 70: return 'Very Good'
                elif score >= 60: return 'Good'
                elif score >= 50: return 'Satisfactory'
                elif score >= 40: return 'Fair'
                else: return 'Poor'
                
        except (TypeError, ValueError):
            return 'Unknown'
        except Exception as e:
            logger.error(f"Error getting performance level: {str(e)}")
            return 'Unknown'

    def is_passing(self):
        """
        Check if grade is passing (GES standards - 40% and above)
        """
        try:
            return self.total_score and Decimal(str(self.total_score)) >= Decimal('40.00')
        except (TypeError, ValueError, InvalidOperation):
            return False

    def get_performance_level_display(self):
        """Get performance level display name"""
        if not self.total_score:
            return 'Not Available'
        if self.total_score >= 80: return 'Excellent'
        elif self.total_score >= 70: return 'Very Good'
        elif self.total_score >= 60: return 'Good'
        elif self.total_score >= 50: return 'Satisfactory'
        elif self.total_score >= 40: return 'Fair'
        else: return 'Poor'
    
    def score_breakdown(self):
        """Get score breakdown for templates"""
        return {
            'classwork': self.classwork_score or 0,
            'homework': self.homework_score or 0,
            'test': self.test_score or 0,
            'exam': self.exam_score or 0,
        }

    @classmethod
    def get_subject_statistics(cls, subject, class_level, academic_year, term):
        """
        Get comprehensive statistics for a specific subject, class, and term
        """
        try:
            grades = cls.objects.filter(
                subject=subject,
                student__class_level=class_level,
                academic_year=academic_year,
                term=term
            ).exclude(total_score__isnull=True)
            
            if not grades.exists():
                return None
                
            scores = [float(grade.total_score) for grade in grades if grade.total_score is not None]
            
            return {
                'count': len(scores),
                'average': round(sum(scores) / len(scores), 2),
                'highest': max(scores),
                'lowest': min(scores),
                'passing_rate': round(len([s for s in scores if s >= 40]) / len(scores) * 100, 1),
                'grade_distribution': cls._calculate_grade_distribution(scores),
                'standard_deviation': cls._calculate_standard_deviation(scores),
            }
            
        except Exception as e:
            logger.error(f"Error calculating subject statistics: {str(e)}")
            return None

    @classmethod
    def _calculate_grade_distribution(cls, scores):
        """
        Calculate grade distribution for statistics
        """
        distribution = {}
        boundaries = {
            '1': (90, 100), '2': (80, 89), '3': (70, 79), '4': (60, 69),
            '5': (50, 59), '6': (40, 49), '7': (30, 39), '8': (20, 29), '9': (0, 19)
        }
        
        for grade, (lower, upper) in boundaries.items():
            distribution[grade] = len([s for s in scores if lower <= s <= upper])
            
        return distribution
    
    @classmethod
    def _calculate_standard_deviation(cls, scores):
        """
        Calculate standard deviation of scores
        """
        if len(scores) < 2:
            return 0.0
        
        mean = sum(scores) / len(scores)
        variance = sum((x - mean) ** 2 for x in scores) / len(scores)
        return round(variance ** 0.5, 2)

    @property
    def can_be_modified(self):
        """
        Check if the grade can be modified
        """
        return not self.is_locked and not self._is_term_locked()

    @property
    def score_breakdown(self):
        """
        Get detailed score breakdown
        """
        return {
            'classwork': float(self.classwork_score) if self.classwork_score else 0.0,
            'homework': float(self.homework_score) if self.homework_score else 0.0,
            'test': float(self.test_score) if self.test_score else 0.0,
            'exam': float(self.exam_score) if self.exam_score else 0.0,
            'total': float(self.total_score) if self.total_score else 0.0,
        }


class SchoolConfiguration(models.Model):
    GRADING_SYSTEM_CHOICES = [
        ('GES', 'Ghana Education System (1-9)'),
        ('LETTER', 'Letter Grading System (A-F)'),
        ('BOTH', 'Both Systems'),
    ]
    
    grading_system = models.CharField(
        max_length=10, 
        choices=GRADING_SYSTEM_CHOICES, 
        default='GES'
    )
    is_locked = models.BooleanField(default=False, help_text="Lock the grading system to prevent changes")
    academic_year = models.CharField(max_length=9, default=f"{timezone.now().year}/{timezone.now().year + 1}")
    current_term = models.PositiveSmallIntegerField(choices=TERM_CHOICES, default=1)
    school_name = models.CharField(max_length=200, default="Ghana Education Service School")
    school_address = models.TextField(default="")
    school_phone = models.CharField(
        max_length=10,
        blank=True,
        validators=[
            RegexValidator(
                r'^0\d{9}$',
                message="Phone number must be 10 digits starting with 0 (e.g., 0245478847)"
            )
        ],
        help_text="10-digit phone number starting with 0 (e.g., 0245478847)"
    )
    school_email = models.EmailField(blank=True)
    principal_name = models.CharField(max_length=100, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "School Configuration"
        verbose_name_plural = "School Configuration"
    
    def save(self, *args, **kwargs):
        if SchoolConfiguration.objects.exists() and not self.pk:
            raise ValidationError("Only one school configuration can exist")
        
        # Clean phone number before saving
        if self.school_phone:
            self.school_phone = self.school_phone.replace(' ', '').replace('-', '')
        
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"School Configuration - {self.school_name}"
    
    def clean(self):
        """Additional validation for phone number"""
        if self.school_phone:
            # Remove any spaces or dashes that might have been entered
            cleaned_phone = self.school_phone.replace(' ', '').replace('-', '')
            if len(cleaned_phone) != 10 or not cleaned_phone.startswith('0'):
                raise ValidationError({
                    'school_phone': 'Phone number must be exactly 10 digits starting with 0'
                })
            # Update the field with cleaned value
            self.school_phone = cleaned_phone
    
    @classmethod
    def get_config(cls):
        """Get or create the single configuration instance"""
        obj, created = cls.objects.get_or_create(pk=1)
        return obj
    
    def get_grading_system_display_name(self):
        """Get user-friendly grading system name"""
        return dict(self.GRADING_SYSTEM_CHOICES).get(self.grading_system, 'GES')



# ===== ASSIGNMENT MANAGEMENT =====

class Assignment(models.Model):
    ASSIGNMENT_TYPES = [
        ('HOMEWORK', 'Homework'),
        ('CLASSWORK', 'Classwork'),
        ('TEST', 'Test'),
        ('EXAM', 'Examination'),
    ]
    
    STATUS_CHOICES = [
        ('PENDING', 'Pending'),
        ('SUBMITTED', 'Submitted'),
        ('LATE', 'Late'),
        ('GRADED', 'Graded'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    assignment_type = models.CharField(max_length=10, choices=ASSIGNMENT_TYPES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    class_assignment = models.ForeignKey(ClassAssignment, on_delete=models.CASCADE)
    due_date = models.DateTimeField()
    max_score = models.PositiveSmallIntegerField(default=100)
    weight = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)],
        help_text="Percentage weight of this assignment in the final grade"
    )
    attachment = models.FileField(upload_to='assignment_attachments/', blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-due_date', 'subject']
        verbose_name = 'Assignment'
        verbose_name_plural = 'Assignments'
    
    def __str__(self):
        return f"{self.get_assignment_type_display()} - {self.subject} ({self.class_assignment.get_class_level_display()})"
    
    def clean(self):
        """Model-level validation"""
        super().clean()
        
        # Ensure subject is set if we have class_assignment
        if self.class_assignment and not self.subject_id:
            self.subject = self.class_assignment.subject
        
        # Validate subject is required
        if not self.subject_id:
            raise ValidationError({'subject': 'Subject is required'})
        
        # Validate subject matches class_assignment
        if (self.class_assignment and self.subject_id and 
            self.class_assignment.subject_id != self.subject_id):
            raise ValidationError({
                'subject': f'Subject must match class assignment subject ({self.class_assignment.subject.name})'
            })

    def get_status_summary(self):
        return {
            'total': self.total_students,
            'pending': self.pending_students,
            'graded': self.graded_students,
            'late': self.late_submissions,
            'submitted': self.total_students - self.pending_students
        }
    
    def get_completion_percentage(self):
        summary = self.get_status_summary()
        total = summary['total']
        if total == 0:
            return 0
        
        completed = summary['submitted'] + summary['late'] + summary['graded']
        return round((completed / total) * 100, 1)
    
    def is_overdue(self):
        return self.due_date < timezone.now()

    def save(self, *args, **kwargs):
        """Save assignment with automatic subject setting"""
        is_new = self.pk is None
        
        # ===========================================
        # CRITICAL FIX: Auto-set subject from class_assignment
        # ===========================================
        if self.class_assignment and not self.subject_id:
            self.subject = self.class_assignment.subject
            print(f"DEBUG: Auto-set subject to {self.subject.name} from class_assignment")
        
        # Double-check subject is set (safety check)
        if not self.subject_id:
            raise ValidationError({
                'subject': 'Subject is required. Either set subject directly or provide a class_assignment.'
            })
        
        # Validate subject matches class_assignment subject
        if (self.class_assignment and self.subject_id and 
            self.class_assignment.subject_id != self.subject_id):
            raise ValidationError({
                'subject': f'Subject mismatch. Class assignment is for {self.class_assignment.subject.name}, but assignment subject is {self.subject.name}.'
            })
        
        # Call parent save
        super().save(*args, **kwargs)
        
        # Create student assignments for new assignments
        if is_new:
            from django.db import transaction
            transaction.on_commit(lambda: self.create_student_assignments())
    
    def create_student_assignments(self):
        """Create StudentAssignment records for all students in the class"""
        try:
            students = Student.objects.filter(
                class_level=self.class_assignment.class_level,
                is_active=True
            )
            
            student_assignments = []
            for student in students:
                if not StudentAssignment.objects.filter(
                    student=student, 
                    assignment=self
                ).exists():
                    student_assignments.append(
                        StudentAssignment(
                            student=student,
                            assignment=self,
                            status='PENDING'
                        )
                    )
            
            if student_assignments:
                StudentAssignment.objects.bulk_create(student_assignments)
                logger.info(f"Created {len(student_assignments)} student assignments for assignment {self.id}")
                
        except Exception as e:
            logger.error(f"Error creating student assignments for assignment {self.id}: {str(e)}")
    
    def get_analytics(self, recalculate=False):
        analytics, created = AssignmentAnalytics.objects.get_or_create(
            assignment=self
        )
        
        if created or recalculate or not analytics.last_calculated:
            analytics.calculate_analytics()
            
        return analytics
    
    def update_analytics(self):
        return self.get_analytics(recalculate=True)
    
    def get_quick_stats(self):
        student_assignments = self.student_assignments.all()
            
        return {
            'total_students': student_assignments.count(),
            'submitted': student_assignments.exclude(status='PENDING').count(),
            'graded': student_assignments.filter(status='GRADED').count(),
            'pending': student_assignments.filter(status='PENDING').count(),
        }
    
    def get_student_assignment(self, student):
        """Get or create StudentAssignment for a specific student"""
        student_assignment, created = StudentAssignment.objects.get_or_create(
            assignment=self,
            student=student,
            defaults={'status': 'PENDING'}
        )
        return student_assignment
    
    def can_student_submit(self, student):
        """Check if student can submit this assignment"""
        if not self.is_active:
            return False, "This assignment is no longer active"
        
        if self.due_date < timezone.now():
            return False, "Assignment due date has passed"
        
        student_assignment = self.get_student_assignment(student)
        if student_assignment.status == 'GRADED':
            return False, "Assignment has already been graded"
        
        return True, "Can submit"
    
    def get_teacher_download_url(self, student_assignment):
        """Get download URL for teacher to download student submission"""
        if student_assignment.file:
            return student_assignment.file.url
        return None


class StudentAssignment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE, related_name='student_assignments')
    status = models.CharField(max_length=10, choices=Assignment.STATUS_CHOICES, default='PENDING')
    submitted_date = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)
    file = models.FileField(upload_to='assignments/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('student', 'assignment')
        ordering = ['assignment__due_date', 'student']
        indexes = [
            models.Index(fields=['status']),
            models.Index(fields=['submitted_date']),
            models.Index(fields=['assignment', 'student']),
        ]
        verbose_name = 'Student Assignment'
        verbose_name_plural = 'Student Assignments'
    
    def get_submission_status(self):
        """Get a human-readable status with icons/colors"""
        status_map = {
            'PENDING': ('🔴', 'Pending', 'danger'),
            'SUBMITTED': ('🟡', 'Submitted', 'warning'),
            'LATE': ('🟠', 'Late', 'warning'),
            'GRADED': ('🟢', 'Graded', 'success'),
        }
        icon, text, color = status_map.get(self.status, ('⚪', 'Unknown', 'secondary'))
        return {
            'icon': icon,
            'text': text,
            'color': color,
            'full': f"{icon} {text}"
        }
    
    def get_time_remaining(self):
        """Get time remaining until due date"""
        if not self.assignment.due_date:
            return None
        
        now = timezone.now()
        time_remaining = self.assignment.due_date - now
        
        if time_remaining.total_seconds() <= 0:
            return "Overdue"
        
        days = time_remaining.days
        hours = time_remaining.seconds // 3600
        minutes = (time_remaining.seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d {hours}h remaining"
        elif hours > 0:
            return f"{hours}h {minutes}m remaining"
        else:
            return f"{minutes}m remaining"
    
    def __str__(self):
        return f"{self.student} - {self.assignment} ({self.status})"
    
    def is_late(self):
        if self.submitted_date and self.assignment.due_date:
            return self.submitted_date > self.assignment.due_date
        return False
    
    def save(self, *args, **kwargs):
        if self.submitted_date and not self.status == 'GRADED':
            if self.is_late():
                self.status = 'LATE'
            else:
                self.status = 'SUBMITTED'
        super().save(*args, **kwargs)
    
    def get_assignment_document_url(self):
        """Get URL for student to download original assignment document"""
        if self.assignment.attachment:
            return self.assignment.attachment.url
        return None
    
    def can_student_download_assignment(self):
        """Check if student can download the original assignment"""
        return self.assignment.attachment is not None
    
    def can_student_submit_work(self):
        """Check if student can submit their work"""
        if self.status == 'GRADED':
            return False, "Assignment has already been graded"
        
        if self.assignment.due_date < timezone.now():
            return False, "Assignment due date has passed"
        
        if not self.assignment.is_active:
            return False, "Assignment is no longer active"
        
        return True, "Can submit"
    
    def submit_student_work(self, file, feedback=""):
        """Submit student work with validation"""
        can_submit, message = self.can_student_submit_work()
        if not can_submit:
            raise ValidationError(message)
        
        self.file = file
        self.feedback = feedback
        self.submitted_date = timezone.now()
        
        # Check if submission is late
        if self.submitted_date > self.assignment.due_date:
            self.status = 'LATE'
        else:
            self.status = 'SUBMITTED'
        
        self.save()
        
        # Send notification to teacher
        self.send_submission_notification()
        
        return True

    def send_submission_notification(self):
        """Send notification to teacher when student submits work"""
        try:
            teacher = self.assignment.class_assignment.teacher.user
            create_notification(
                recipient=teacher,
                title="New Assignment Submission",
                message=f"{self.student.get_full_name()} has submitted work for '{self.assignment.title}'",
                notification_type="ASSIGNMENT",
                link=reverse('assignment_detail', kwargs={'pk': self.assignment.pk})
            )
        except Exception as e:
            logger.error(f"Error sending submission notification: {str(e)}")
    

class AssignmentAnalytics(models.Model):
    """Model to track assignment analytics and statistics"""
    assignment = models.OneToOneField(
        Assignment, 
        on_delete=models.CASCADE, 
        related_name='analytics'
    )
    average_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    highest_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    lowest_score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    submission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    on_time_submission_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    total_students = models.PositiveIntegerField(default=0)
    graded_students = models.PositiveIntegerField(default=0)
    pending_students = models.PositiveIntegerField(default=0)
    late_submissions = models.PositiveIntegerField(default=0)
    last_calculated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Assignment Analytics'
        verbose_name_plural = 'Assignment Analytics'
        ordering = ['-last_calculated']
    
    def __str__(self):
        return f"Analytics for {self.assignment.title}"
    
    def calculate_analytics(self):
        """Calculate and update analytics data with error handling"""
        try:
            student_assignments = self.assignment.student_assignments.all()
            self.total_students = student_assignments.count()
            
            # Count students by status
            self.pending_students = student_assignments.filter(status='PENDING').count()
            self.graded_students = student_assignments.filter(status='GRADED').count()
            self.late_submissions = student_assignments.filter(status='LATE').count()
            
            # Calculate score statistics
            graded_with_scores = student_assignments.filter(
                status='GRADED', 
                score__isnull=False
            )
            
            if graded_with_scores.exists():
                scores = [float(sa.score) for sa in graded_with_scores]
                self.average_score = sum(scores) / len(scores)
                self.highest_score = max(scores)
                self.lowest_score = min(scores)
            else:
                self.average_score = None
                self.highest_score = None
                self.lowest_score = None
            
            # Calculate submission rates
            submitted_assignments = student_assignments.exclude(status='PENDING')
            on_time_assignments = student_assignments.filter(
                status__in=['SUBMITTED', 'GRADED'],
                submitted_date__lte=self.assignment.due_date
            ) if self.assignment.due_date else submitted_assignments
            
            if self.total_students > 0:
                self.submission_rate = (submitted_assignments.count() / self.total_students) * 100
                self.on_time_submission_rate = (on_time_assignments.count() / self.total_students) * 100
            
            self.save()
            return True
            
        except Exception as e:
            logger.error(f"Error calculating analytics for assignment {self.assignment.id}: {str(e)}")
            return False
    
    def get_status_summary(self):
        """Get summary of assignment statuses"""
        return {
            'total': self.total_students,
            'pending': self.pending_students,
            'graded': self.graded_students,
            'late': self.late_submissions,
            'submitted': self.total_students - self.pending_students
        }



class AssignmentTemplate(models.Model):
    title = models.CharField(max_length=200)
    description = models.TextField()
    assignment_type = models.CharField(max_length=10, choices=Assignment.ASSIGNMENT_TYPES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    max_score = models.PositiveSmallIntegerField(default=100)
    weight = models.PositiveSmallIntegerField(
        validators=[MinValueValidator(1), MaxValueValidator(100)]
    )
    attachment = models.FileField(upload_to='assignment_templates/', blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_public = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Assignment Template'
        verbose_name_plural = 'Assignment Templates'
    
    def create_assignment_from_template(self, class_levels, due_date):
        """Create actual assignments from this template"""
        assignments = []
        for class_level in class_levels:
            class_assignment = ClassAssignment.objects.filter(
                class_level=class_level,
                subject=self.subject
            ).first()
            
            if class_assignment:
                assignment = Assignment.objects.create(
                    title=self.title,
                    description=self.description,
                    assignment_type=self.assignment_type,
                    subject=self.subject,
                    class_assignment=class_assignment,
                    due_date=due_date,
                    max_score=self.max_score,
                    weight=self.weight,
                    attachment=self.attachment
                )
                assignments.append(assignment)
        
        return assignments


# ===== FEE MANAGEMENT =====

# ===== FEE MANAGEMENT =====

class FeeCategory(models.Model):
    CATEGORY_TYPES = [
        ('TUITION', 'Tuition Fees'),
        ('ADMISSION', 'Admission Fees'),
        ('TRANSPORT', 'Transport Fees'),
        ('TECHNOLOGY', 'Technology Fee'),
        ('EXAMINATION', 'Examination Fees'),
        ('UNIFORM', 'Uniform Fees'),
        ('PTA', 'PTA Fees'),
        ('EXTRA_CLASSES', 'Extra Classes Fees'),
    ]
    
    FREQUENCY_CHOICES = [
        ('one_time', 'One Time'),
        ('termly', 'Per Term'),
        ('monthly', 'Monthly'),
        ('quarterly', 'Quarterly'),
        ('semester', 'Per Semester'),
        ('annual', 'Annual'),
        ('custom', 'Custom'),
    ]
    
    name = models.CharField(max_length=100, choices=CATEGORY_TYPES)
    description = models.TextField(blank=True)
    default_amount = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    frequency = models.CharField(max_length=20, choices=FREQUENCY_CHOICES, default='termly')
    is_mandatory = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    applies_to_all = models.BooleanField(default=True)
    class_levels = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Comma-separated list of class levels this applies to (leave blank for all)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name_plural = "Fee Categories"
        ordering = ['name']
        verbose_name = 'Fee Category'
    
    def __str__(self):
        return self.get_name_display()
    
    def get_frequency_display_with_icon(self):
        """Return frequency with appropriate icon for display"""
        icons = {
            'one_time': '💰',
            'termly': '📚',
            'monthly': '📅',
            'quarterly': '📊',
            'semester': '🎓',
            'annual': '📆',
            'custom': '⚙️',
        }
        return f"{icons.get(self.frequency, '📝')} {self.get_frequency_display()}"
    
    def get_applicable_class_levels(self):
        """Return list of applicable class levels"""
        if not self.class_levels:
            return []
        return [level.strip() for level in self.class_levels.split(',')]
    
    def is_applicable_to_class(self, class_level):
        """Check if this fee applies to a specific class level"""
        if self.applies_to_all or not self.class_levels:
            return True
        return class_level in self.get_applicable_class_levels()
    
    @classmethod
    def setup_default_categories(cls):
        """Create default professional fee categories"""
        categories = [
            {
                'name': 'TUITION',
                'description': 'Core academic instruction fees covering teachers salaries and classroom costs',
                'default_amount': 5000.00,
                'frequency': 'termly',
                'is_mandatory': True,
                'is_active': True,
                'applies_to_all': True,
            },
            {
                'name': 'ADMISSION',
                'description': 'One-time fee charged when a student is newly enrolled in the school',
                'default_amount': 500.00,
                'frequency': 'one_time',
                'is_mandatory': True,
                'is_active': True,
                'applies_to_all': True,
            },
            {
                'name': 'TRANSPORT',
                'description': 'School bus transportation services',
                'default_amount': 800.00,
                'frequency': 'termly',
                'is_mandatory': False,
                'is_active': True,
                'applies_to_all': True,
            },
            {
                'name': 'TECHNOLOGY',
                'description': 'Covers computer labs, software licenses, internet access and educational technology',
                'default_amount': 300.00,
                'frequency': 'termly',
                'is_mandatory': True,
                'is_active': True,
                'applies_to_all': True,
            },
            {
                'name': 'EXAMINATION',
                'description': 'Fees for internal and external examinations and certifications',
                'default_amount': 200.00,
                'frequency': 'termly',
                'is_mandatory': True,
                'is_active': True,
                'applies_to_all': True,
            },
            {
                'name': 'UNIFORM',
                'description': 'School uniform costs',
                'default_amount': 350.00,
                'frequency': 'one_time',
                'is_mandatory': True,
                'is_active': True,
                'applies_to_all': True,
            },
            {
                'name': 'PTA',
                'description': 'Parent-Teacher Association fees for school development projects',
                'default_amount': 100.00,
                'frequency': 'termly',
                'is_mandatory': True,
                'is_active': True,
                'applies_to_all': True,
            },
            {
                'name': 'EXTRA_CLASSES',
                'description': 'Additional tuition and special classes outside regular hours',
                'default_amount': 400.00,
                'frequency': 'termly',
                'is_mandatory': False,
                'is_active': True,
                'applies_to_all': True,
            }
        ]
        
        for category_data in categories:
            category, created = cls.objects.get_or_create(
                name=category_data['name'],
                defaults=category_data
            )
            if not created:
                # Update existing category
                for key, value in category_data.items():
                    if key != 'name':
                        setattr(category, key, value)
                category.save()
        
        return cls.objects.count()


class Bill(models.Model):
    """Represents an invoice sent to a student for specific fees"""
    bill_number = models.CharField(max_length=20, unique=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='bills')
    issue_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    academic_year = models.CharField(max_length=9)
    term = models.PositiveSmallIntegerField(choices=TERM_CHOICES)
    
    # FIXED: Consistent lowercase statuses
    status = models.CharField(
        max_length=10, 
        choices=[
            ('issued', 'Issued'),
            ('paid', 'Paid'),
            ('partial', 'Partially Paid'),
            ('overdue', 'Overdue'),
            ('cancelled', 'Cancelled')
        ], 
        default='issued'
    )
    
    total_amount = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    notes = models.TextField(blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='recorded_bills')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-issue_date']
        verbose_name = 'Bill'
        verbose_name_plural = 'Bills'
        indexes = [
            models.Index(fields=['student', 'academic_year', 'term']),
            models.Index(fields=['status']),
            models.Index(fields=['due_date']),
        ]
    
    def __str__(self):
        return f"Bill #{self.bill_number} - {self.student.get_full_name()}"
    
    def save(self, *args, **kwargs):
        if not self.bill_number:
            current_year = str(timezone.now().year)
            last_bill = Bill.objects.filter(bill_number__startswith=f'BILL{current_year}').order_by('-bill_number').first()
            
            if last_bill:
                try:
                    last_sequence = int(last_bill.bill_number[-6:])
                    new_sequence = last_sequence + 1
                except ValueError:
                    new_sequence = 1
            else:
                new_sequence = 1
                
            self.bill_number = f"BILL{current_year}{new_sequence:06d}"
        
        # FIXED: Ensure all amounts are Decimal before calculation
        total_amount = Decimal(str(self.total_amount)) if self.total_amount else Decimal('0.00')
        amount_paid = Decimal(str(self.amount_paid)) if self.amount_paid else Decimal('0.00')
        
        # Calculate balance
        self.balance = total_amount - amount_paid
        
        # Auto-update status based on payments and due date
        if amount_paid >= total_amount:
            self.status = 'paid'
        elif amount_paid > Decimal('0.00'):
            self.status = 'partial'
        elif timezone.now().date() > self.due_date:
            self.status = 'overdue'
        
        super().save(*args, **kwargs)
    
    def update_status(self):
        """Update bill status based on payments and due date"""
        total_payments = self.bill_payments.aggregate(
            total=Sum('amount')
        )['total'] or Decimal('0.00')
        
        self.amount_paid = total_payments
        self.balance = self.total_amount - self.amount_paid
        
        # Don't update status if cancelled
        if self.status == 'cancelled':
            return
        
        # Determine new status
        if self.amount_paid >= self.total_amount:
            self.status = 'paid'
        elif self.amount_paid > 0:
            self.status = 'partial'
        elif timezone.now().date() > self.due_date:
            self.status = 'overdue'
        else:
            self.status = 'issued'
        
        self.save(update_fields=['status', 'amount_paid', 'balance', 'updated_at'])
    
    def get_payment_progress(self):
        """Get payment progress percentage"""
        if self.total_amount > 0:
            return (self.amount_paid / self.total_amount) * 100
        return 0
    
    def get_remaining_days(self):
        """Get remaining days until due date"""
        today = timezone.now().date()
        remaining = (self.due_date - today).days
        
        if remaining < 0:
            return f"{abs(remaining)} days overdue"
        elif remaining == 0:
            return "Due today"
        else:
            return f"{remaining} days remaining"
    
    @property
    def is_overdue(self):
        """Check if bill is overdue"""
        return self.status == 'overdue' or (self.due_date < timezone.now().date() and self.status != 'paid')
    
    def can_accept_payment(self):
        """Check if bill can accept additional payments"""
        return self.balance > 0 and self.status != 'cancelled'


class BillItem(models.Model):
    """Individual fee items on a bill"""
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='items')
    fee_category = models.ForeignKey(FeeCategory, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Bill Item'
        verbose_name_plural = 'Bill Items'
    
    def __str__(self):
        return f"{self.fee_category.name} - GH₵{self.amount}"

class BillPayment(models.Model):
    PAYMENT_MODES = [
        ('cash', 'Cash'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('cheque', 'Cheque'),
        ('other', 'Other'),
    ]
    
    bill = models.ForeignKey('Bill', on_delete=models.CASCADE, related_name='bill_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default='cash')
    payment_date = models.DateField(default=timezone.now)
    reference_number = models.CharField(max_length=50, blank=True, null=True)
    notes = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date']
        verbose_name = 'Bill Payment'
        verbose_name_plural = 'Bill Payments'
        indexes = [
            models.Index(fields=['bill', 'payment_date']),
        ]

    def __str__(self):
        return f"Payment of GH₵{self.amount:.2f} for Bill #{self.bill.bill_number}"

    def save(self, *args, **kwargs):
        # Update the bill's paid amount when a payment is saved
        super().save(*args, **kwargs)
        self.bill.update_status()



class Fee(models.Model):
    # FIXED: Use lowercase statuses consistently
    PAYMENT_STATUS_CHOICES = [
        ('paid', 'Paid'),
        ('unpaid', 'Unpaid'),
        ('partial', 'Part Payment'),
        ('overdue', 'Overdue'),
    ]
    
    PAYMENT_MODE_CHOICES = [
        ('cash', 'Cash'),
        ('check', 'Check'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('other', 'Other'),
    ]

    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name='fees')
    category = models.ForeignKey(FeeCategory, on_delete=models.PROTECT, related_name='fees')
    academic_year = models.CharField(max_length=9)
    term = models.PositiveSmallIntegerField(choices=TERM_CHOICES)
    
    amount_payable = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])
    balance = models.DecimalField(max_digits=10, decimal_places=2, default=Decimal('0.00'), validators=[MinValueValidator(Decimal('0.00'))])
    
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='unpaid')
    payment_mode = models.CharField(max_length=15, choices=PAYMENT_MODE_CHOICES, blank=True, null=True)
    payment_date = models.DateField(blank=True, null=True)
    due_date = models.DateField()
    
    bill = models.ForeignKey(Bill, on_delete=models.SET_NULL, null=True, blank=True, related_name='fees')
    
    receipt_number = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='recorded_fees')
    date_recorded = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_recorded']
        verbose_name_plural = 'Fees'
        verbose_name = 'Fee'
        indexes = [
            models.Index(fields=['student']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['due_date']),
        ]

    def __str__(self):
        return f"{self.student} - {self.category} ({self.academic_year} Term {self.term})"

    def update_payment_status(self):
        """Update payment status with proper overpayment handling"""
        tolerance = Decimal('1.00')
        grace_period = 5
        today = timezone.now().date()
        effective_due_date = self.due_date + timedelta(days=grace_period)
        
        # Calculate the actual difference
        difference = self.amount_payable - self.amount_paid
        
        # Handle overpayment (amount_paid > amount_payable)
        if self.amount_paid >= self.amount_payable:
            if abs(difference) <= tolerance:
                self.payment_status = 'paid'
            else:
                self.payment_status = 'paid'  # Still mark as paid for overpayment
        elif self.amount_paid > Decimal('0.00'):
            self.payment_status = 'partial'
        elif today > effective_due_date:
            self.payment_status = 'overdue'
        else:
            self.payment_status = 'unpaid'

    @property
    def overpayment_amount(self):
        """Calculate overpayment amount"""
        if self.amount_paid > self.amount_payable:
            return self.amount_paid - self.amount_payable
        return Decimal('0.00')

    @property
    def has_overpayment(self):
        """Check if there's an overpayment"""
        return self.amount_paid > self.amount_payable

    def clean(self):
        """Validate the fee data with overpayment handling"""
        # Allow overpayment but track it
        if self.payment_status == 'paid' and self.amount_paid < self.amount_payable:
            raise ValidationError({
                'payment_status': 'Cannot mark as paid when amount paid is less than payable'
            })
        
        if not self.pk and self.due_date < timezone.now().date():
            raise ValidationError({
                'due_date': 'Due date cannot be in the past for new fees'
            })

    def save(self, *args, **kwargs):
        """Auto-calculate balance and update payment status before saving"""
        # Calculate balance (can be negative for overpayment)
        self.balance = self.amount_payable - self.amount_paid
        
        self.update_payment_status()
        
        if self.payment_status == 'paid' and not self.payment_date:
            self.payment_date = timezone.now().date()
        elif self.payment_status != 'paid' and self.payment_date:
            self.payment_date = None
            
        super().save(*args, **kwargs)

    def get_payment_status_html(self):
        """Get HTML badge for payment status with overpayment indicator"""
        status_display = self.get_payment_status_display()
        if self.has_overpayment:
            status_display += " (Credit)"
            
        color_map = {
            'paid': 'success',
            'unpaid': 'danger',
            'partial': 'warning',
            'overdue': 'dark'
        }
        color = color_map.get(self.payment_status, 'primary')
        return mark_safe(f'<span class="badge bg-{color}">{status_display}</span>')
    
    def can_accept_payment(self):
        """Check if this fee can accept additional payments"""
        return self.balance > 0 and self.payment_status != 'paid'
    
    def get_remaining_days(self):
        """Get remaining days until due date"""
        if not self.due_date:
            return None
        
        today = timezone.now().date()
        remaining = (self.due_date - today).days
        
        if remaining < 0:
            return f"{abs(remaining)} days overdue"
        elif remaining == 0:
            return "Due today"
        else:
            return f"{remaining} days remaining"

class FeePayment(models.Model):
    # FIXED: Use lowercase payment modes consistently
    PAYMENT_MODE_CHOICES = [
        ('cash', 'Cash'),
        ('check', 'Check'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('other', 'Other'),
    ]
    
    fee = models.ForeignKey(Fee, on_delete=models.CASCADE, related_name='payments')
    bill = models.ForeignKey(Bill, on_delete=models.CASCADE, related_name='fee_payments', null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, validators=[MinValueValidator(Decimal('0.01'))])
    payment_date = models.DateTimeField(default=timezone.now)
    payment_mode = models.CharField(max_length=15, choices=PAYMENT_MODE_CHOICES)
    receipt_number = models.CharField(max_length=20, unique=True, blank=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, related_name='recorded_payments')
    notes = models.TextField(blank=True)
    bank_reference = models.CharField(max_length=50, blank=True)
    is_confirmed = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-payment_date']
        verbose_name = 'Fee Payment'
        verbose_name_plural = 'Fee Payments'
    
    def __str__(self):
        return f"Payment of {self.amount} for {self.fee}"
    
    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
        
        if self.bill:
            self.bill.update_status()
            
        super().save(*args, **kwargs)
    
    @classmethod
    def generate_receipt_number(cls):
        from django.utils.crypto import get_random_string
        while True:
            receipt_number = f"RCPT-{get_random_string(10, '0123456789')}"
            if not cls.objects.filter(receipt_number=receipt_number).exists():
                return receipt_number

# NEW: Student Credit Model to track overpayments
class StudentCredit(models.Model):
    """Track student credit balances from overpayments"""
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='credits')
    source_fee = models.ForeignKey(Fee, on_delete=models.CASCADE, null=True, blank=True)
    credit_amount = models.DecimalField(max_digits=10, decimal_places=2)
    reason = models.CharField(max_length=200, default='Overpayment')
    created_date = models.DateTimeField(auto_now_add=True)
    is_used = models.BooleanField(default=False)
    used_date = models.DateTimeField(null=True, blank=True)
    used_for_fee = models.ForeignKey(Fee, on_delete=models.SET_NULL, null=True, blank=True, related_name='applied_credits')
    notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = 'Student Credit'
        verbose_name_plural = 'Student Credits'
        ordering = ['-created_date']
    
    def __str__(self):
        return f"{self.student} - GH₵{self.credit_amount} Credit"

class FeeDiscount(models.Model):
    DISCOUNT_TYPES = [
        ('PERCENT', 'Percentage'),
        ('FIXED', 'Fixed Amount'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='discounts')
    category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE)
    discount_type = models.CharField(max_length=10, choices=DISCOUNT_TYPES)
    amount = models.DecimalField(max_digits=5, decimal_places=2)
    reason = models.TextField()
    approved_by = models.ForeignKey(User, on_delete=models.PROTECT)
    start_date = models.DateField()
    end_date = models.DateField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Fee Discount'
        verbose_name_plural = 'Fee Discounts'
    
    def apply_discount(self, fee_amount):
        if self.discount_type == 'PERCENT':
            return fee_amount * (self.amount / 100)
        return min(fee_amount, self.amount)

class FeeInstallment(models.Model):
    fee = models.ForeignKey(Fee, on_delete=models.CASCADE, related_name='installments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    is_paid = models.BooleanField(default=False)
    payment_date = models.DateField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['due_date']
        verbose_name = 'Fee Installment'
        verbose_name_plural = 'Fee Installments'
        
    def __str__(self):
        return f"Installment of {self.amount} due {self.due_date}"



# ===== REPORT CARD =====

class ReportCard(models.Model):
    TERM_CHOICES = [
        (1, 'Term 1'),
        (2, 'Term 2'),
        (3, 'Term 3'),
    ]
    
    GRADE_CHOICES = [
        ('A+', 'A+ (90-100)'),
        ('A', 'A (80-89)'),
        ('B+', 'B+ (70-79)'),
        ('B', 'B (60-69)'),
        ('C+', 'C+ (50-59)'),
        ('C', 'C (40-49)'),
        ('D+', 'D+ (30-39)'),
        ('D', 'D (20-29)'),
        ('E', 'E (0-19)'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    academic_year = models.CharField(max_length=9, validators=[RegexValidator(r'^\d{4}/\d{4}$')])
    term = models.PositiveSmallIntegerField(choices=TERM_CHOICES, validators=[MinValueValidator(1), MaxValueValidator(3)])
    average_score = models.DecimalField(max_digits=5, decimal_places=2, default=0.00)
    overall_grade = models.CharField(max_length=2, choices=GRADE_CHOICES, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)
    teacher_remarks = models.TextField(blank=True)
    principal_remarks = models.TextField(blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True)
    
    class Meta:
        unique_together = ('student', 'academic_year', 'term')
        ordering = ['-academic_year', '-term']
        verbose_name = 'Report Card'
        verbose_name_plural = 'Report Cards'
    
    def __str__(self):
        return f"{self.student}'s Report Card - {self.academic_year} Term {self.term}"
    
    def save(self, *args, **kwargs):
        if not self.average_score or not self.overall_grade:
            self.calculate_grades()
        super().save(*args, **kwargs)
    
    def calculate_grades(self):
        """Calculate average score and overall grade from student's grades"""
        grades = Grade.objects.filter(
            student=self.student,
            academic_year=self.academic_year,
            term=self.term
        )
        
        if grades.exists():
            total_score = sum(grade.total_score for grade in grades if grade.total_score)
            self.average_score = total_score / grades.count()
            self.overall_grade = self.calculate_grade(self.average_score)
        else:
            self.average_score = 0.00
            self.overall_grade = ''
    
    @staticmethod
    def calculate_grade(score):
        """Calculate letter grade based on score"""
        if not score:
            return ''
            
        score = float(score)
        if score >= 90: return 'A+'
        elif score >= 80: return 'A'
        elif score >= 70: return 'B+'
        elif score >= 60: return 'B'
        elif score >= 50: return 'C+'
        elif score >= 40: return 'C'
        elif score >= 30: return 'D+'
        elif score >= 20: return 'D'
        else: return 'E'
    
    def get_absolute_url(self):
        return reverse('report_card_detail', kwargs={
            'student_id': self.student.id,
            'report_card_id': self.id
        })
    
    def can_user_access(self, user):
        """Check if user has permission to view this report card"""
        from .utils import is_admin, is_student, is_teacher, is_parent
        
        if is_admin(user):
            return True
        if is_student(user) and user.student == self.student:
            return True
        if is_teacher(user):
            return ClassAssignment.objects.filter(
                class_level=self.student.class_level,
                teacher=user.teacher
            ).exists()
        if is_parent(user):
            return self.student in user.parentguardian.students.all()
        return False

# ===== NOTIFICATION SYSTEM =====

class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('GRADE', 'Grade Update'),
        ('FEE', 'Fee Payment'),
        ('ASSIGNMENT', 'Assignment'),
        ('ATTENDANCE', 'Attendance'),
        ('GENERAL', 'General'),
        ('ANNOUNCEMENT', 'Announcement'),
        ('SYSTEM', 'System'),
        ('SECURITY', 'Security'),
    ]
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=20, choices=NOTIFICATION_TYPES, default='GENERAL')
    title = models.CharField(max_length=200)
    message = models.TextField()
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    related_content_type = models.CharField(max_length=50, blank=True)
    link = models.CharField(max_length=500, blank=True, null=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', 'is_read', 'created_at']),
            models.Index(fields=['created_at']),
        ]
        verbose_name = 'Notification'
        verbose_name_plural = 'Notifications'
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.title} - {self.recipient.username}"
    
    def get_absolute_url(self):
        if self.link:
            return self.link
            
        if self.related_object_id and self.related_content_type:
            try:
                from django.apps import apps
                model_class = apps.get_model('core', self.related_content_type)
                obj = model_class.objects.get(pk=self.related_object_id)
                if hasattr(obj, 'get_absolute_url'):
                    return obj.get_absolute_url()
            except Exception as e:
                logger.warning(f"Could not get absolute URL for notification {self.id}: {str(e)}")
        
        from django.urls import reverse
        return reverse('notification_list')
    
    @classmethod
    def get_unread_count_for_user(cls, user):
        """
        Get unread notification count for a specific user
        FIXED: Handles both User objects and request objects safely
        """
        try:
            # Handle different object types safely
            if hasattr(user, 'is_authenticated'):
                # It's a User object
                if not user or not user.is_authenticated:
                    return 0
            elif hasattr(user, 'user'):
                # It's a request object, extract the user
                user = user.user
                if not user or not user.is_authenticated:
                    return 0
            else:
                # Unknown type or None, return 0
                return 0
            
            return cls.objects.filter(recipient=user, is_read=False).count()
            
        except Exception as e:
            logger.error(f"Error getting unread count: {str(e)}")
            return 0
    
    def mark_as_read(self):
        """Mark notification as read and send WebSocket update"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
            self.send_websocket_update()
            return True
        return False
    
    def send_websocket_update(self):
        """Send WebSocket update for this notification"""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'notifications_{self.recipient.id}',
                {
                    'type': 'notification_update',
                    'action': 'single_read',
                    'notification_id': self.id,
                    'unread_count': self.get_unread_count_for_user(self.recipient)  # ✅ FIXED
                }
            )
        except Exception as e:
            logger.error(f"WebSocket update failed for notification {self.id}: {str(e)}")
    
    def send_new_notification_ws(self):
        """Send WebSocket notification when a new notification is created"""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_send)(
                f'notifications_{self.recipient.id}',
                {
                    'type': 'notification_update',
                    'action': 'new_notification',
                    'notification': {
                        'id': self.id,
                        'title': self.title,
                        'message': self.message,
                        'notification_type': self.notification_type,
                        'created_at': self.created_at.isoformat(),
                        'is_read': self.is_read,
                    },
                    'unread_count': self.get_unread_count_for_user(self.recipient)  # ✅ FIXED
                }
            )
        except Exception as e:
            logger.error(f"WebSocket new notification failed: {str(e)}")
    
    @classmethod
    def create_notification(cls, recipient, title, message, notification_type="GENERAL", link=None, related_object=None):
        """Create a notification and send WebSocket update"""
        try:
            notification = cls.objects.create(
                recipient=recipient,
                title=title,
                message=message,
                notification_type=notification_type,
                link=link
            )
            
            if related_object:
                notification.related_object_id = related_object.pk
                notification.related_content_type = related_object._meta.model_name
                notification.save()
            
            # Send WebSocket notification
            notification.send_new_notification_ws()
            
            logger.info(f"Notification created successfully for {recipient.username}: {title}")
            return notification
            
        except Exception as e:
            logger.error(f"Failed to create notification: {str(e)}")
            return None
    
    def save(self, *args, **kwargs):
        """Override save to handle WebSocket notifications"""
        is_new = self.pk is None
        super().save(*args, **kwargs)
        
        # Send WebSocket notification for new notifications
        if is_new:
            self.send_new_notification_ws()

# ===== TIMETABLE MANAGEMENT =====

class TimeSlot(models.Model):
    PERIOD_CHOICES = [
        (1, '1st Period (8:00-9:00)'),
        (2, '2nd Period (9:00-10:00)'),
        (3, '3rd Period (10:00-11:00)'),
        (4, '4th Period (11:00-12:00)'),
        (5, '5th Period (12:00-1:00)'),
        (6, '6th Period (1:00-2:00)'),
        (7, '7th Period (2:00-3:00)'),
        (8, '8th Period (3:00-4:00)'),
    ]
    
    period_number = models.PositiveSmallIntegerField(choices=PERIOD_CHOICES, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    is_break = models.BooleanField(default=False)
    break_name = models.CharField(max_length=50, blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['period_number']
        verbose_name = 'Time Slot'
        verbose_name_plural = 'Time Slots'
        permissions = [
            ('can_view_timeslot', 'Can view time slot'),
            ('manage_timeslot', 'Can manage time slot'),
        ]
    
    def __str__(self):
        if self.is_break:
            return f"{self.break_name} ({self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')})"
        return f"Period {self.period_number} ({self.start_time.strftime('%H:%M')}-{self.end_time.strftime('%H:%M')})"


class Timetable(models.Model):
    DAYS_OF_WEEK = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
    ]
    
    class_level = models.CharField(max_length=2, choices=CLASS_LEVEL_CHOICES)
    day_of_week = models.PositiveSmallIntegerField(choices=DAYS_OF_WEEK)
    academic_year = models.CharField(max_length=20)
    term = models.PositiveSmallIntegerField(choices=AcademicTerm.TERM_CHOICES)
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('class_level', 'day_of_week', 'academic_year', 'term')
        ordering = ['class_level', 'day_of_week']
        verbose_name = 'Timetable'
        verbose_name_plural = 'Timetables'
        permissions = [
            ('can_view_timetable', 'Can view timetable'),
            ('manage_timetable', 'Can manage timetable'),
        ]
    
    def __str__(self):
        return f"{self.get_class_level_display()} - {self.get_day_of_week_display()} - {self.academic_year} Term {self.term}"


class TimetableEntry(models.Model):
    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name='entries')
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    classroom = models.CharField(max_length=100, blank=True)
    is_break = models.BooleanField(default=False)
    break_name = models.CharField(max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['time_slot__period_number']
        unique_together = ('timetable', 'time_slot')
        verbose_name = 'Timetable Entry'
        verbose_name_plural = 'Timetable Entries'
        permissions = [
            ('view_timetable_entry', 'Can view timetable entry'),
            ('manage_timetable_entry', 'Can manage timetable entry'),
        ]
    
    def __str__(self):
        if self.is_break:
            return f"{self.break_name} - Break"
        return f"{self.time_slot} - {self.subject.name} - {self.teacher.get_full_name()}"

# ===== ANNOUNCEMENTS =====

class Announcement(models.Model):
    PRIORITY_CHOICES = [
        ('LOW', 'Low'),
        ('NORMAL', 'Normal'),
        ('HIGH', 'High'),
        ('URGENT', 'Urgent'),
    ]
    
    TARGET_CHOICES = [
        ('ALL', 'All Users'),
        ('STUDENTS', 'Students'),
        ('TEACHERS', 'Teachers'),
        ('ADMINS', 'Administrators'),
        ('CLASS', 'Specific Classes'),
    ]
    
    title = models.CharField(max_length=200)
    message = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, default='NORMAL')
    target_roles = models.CharField(max_length=20, choices=TARGET_CHOICES, default='ALL')
    target_class_levels = models.CharField(
        max_length=100, 
        blank=True, 
        help_text="Comma-separated class levels (e.g., P1,P2,P3) or leave blank for all"
    )
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    is_active = models.BooleanField(default=True)
    start_date = models.DateTimeField(default=timezone.now)
    end_date = models.DateTimeField(blank=True, null=True)
    attachment = models.FileField(upload_to='announcements/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Announcement'
        verbose_name_plural = 'Announcements'
    
    def __str__(self):
        return self.title
    
    def get_target_class_levels(self):
        """Get list of target class levels"""
        if not self.target_class_levels:
            return []
        return [level.strip() for level in self.target_class_levels.split(',')]
    
    def is_for_class_level(self, class_level):
        """Check if announcement is for a specific class level"""
        if not self.target_class_levels:
            return True
        return class_level in self.get_target_class_levels()
    
    def is_expired(self):
        """Check if announcement has expired"""
        if self.end_date:
            return timezone.now() > self.end_date
        return False
    
    def is_active_now(self):
        """Check if announcement is currently active"""
        return self.is_active and not self.is_expired()
    
    def get_priority_color(self):
        """Get Bootstrap color for priority"""
        colors = {
            'URGENT': 'danger',
            'HIGH': 'warning', 
            'NORMAL': 'info',
            'LOW': 'secondary'
        }
        return colors.get(self.priority, 'secondary')
    
    # NEW PROPERTIES AND METHODS ADDED:
    
    @property
    def views_count(self):
        """Get the number of views for this announcement"""
        return self.userannouncementview_set.count()
    
    @property
    def is_expired_property(self):
        """Property version of is_expired for template usage"""
        return self.is_expired()
    
    @property
    def is_active_now_property(self):
        """Property version of is_active_now for template usage"""
        return self.is_active_now()
    
    def get_days_remaining(self):
        """Get number of days remaining until expiry"""
        if self.end_date and not self.is_expired():
            remaining = self.end_date - timezone.now()
            return max(0, remaining.days)
        return None
    
    def get_status_display(self):
        """Get human-readable status"""
        if not self.is_active:
            return "Inactive"
        elif self.is_expired():
            return "Expired"
        elif self.start_date > timezone.now():
            return "Scheduled"
        else:
            return "Active"
    
    def get_status_color(self):
        """Get Bootstrap color for status"""
        if not self.is_active:
            return "secondary"
        elif self.is_expired():
            return "warning"
        elif self.start_date > timezone.now():
            return "info"
        else:
            return "success"
    
    def get_audience_display(self):
        """Get human-readable audience description"""
        target_classes = self.get_target_class_levels()
        if self.target_roles == 'CLASS' and target_classes:
            class_names = []
            for class_level in target_classes:
                # Map class level codes to display names
                class_display_map = dict(CLASS_LEVEL_CHOICES)
                class_names.append(class_display_map.get(class_level, class_level))
            return f"Classes: {', '.join(class_names)}"
        else:
            return self.get_target_roles_display()
    
    def can_user_access(self, user):
        """Check if user has permission to view this announcement"""
        # Staff and teachers can see all announcements
        if user.is_staff or hasattr(user, 'teacher'):
            return True
        
        # Check if announcement is active and not expired
        if not self.is_active_now():
            return False
        
        # Check target roles
        if self.target_roles == 'STUDENTS' and not hasattr(user, 'student'):
            return False
        elif self.target_roles == 'TEACHERS' and not (hasattr(user, 'teacher') or user.is_staff):
            return False
        elif self.target_roles == 'ADMINS' and not user.is_staff:
            return False
        elif self.target_roles == 'CLASS':
            target_classes = self.get_target_class_levels()
            if hasattr(user, 'student') and user.student.class_level in target_classes:
                return True
            elif hasattr(user, 'parentguardian'):
                # Parents can see announcements for their children's classes
                children_classes = user.parentguardian.students.values_list('class_level', flat=True)
                if any(cls in target_classes for cls in children_classes):
                    return True
            return False
        
        # ALL role or passed other checks
        return True
    
    def mark_as_viewed(self, user):
        """Mark announcement as viewed by a user"""
        UserAnnouncementView.objects.get_or_create(
            user=user,
            announcement=self,
            defaults={'viewed_at': timezone.now()}
        )
    
    def get_view_stats(self):
        """Get viewing statistics for this announcement"""
        views = self.userannouncementview_set.all()
        total_views = views.count()
        unique_viewers = views.values('user').distinct().count()
        dismissed_count = views.filter(dismissed=True).count()
        
        return {
            'total_views': total_views,
            'unique_viewers': unique_viewers,
            'dismissed_count': dismissed_count,
            'engagement_rate': round((unique_viewers / max(1, self.get_target_user_count())) * 100, 1)
        }
    
    def get_target_user_count(self):
        """Estimate number of target users for this announcement"""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        target_classes = self.get_target_class_levels()
        user_query = Q(is_active=True)
        
        if self.target_roles == 'STUDENTS':
            user_query &= Q(student__isnull=False)
            if target_classes:
                user_query &= Q(student__class_level__in=target_classes)
        elif self.target_roles == 'TEACHERS':
            user_query &= (Q(teacher__isnull=False) | Q(is_staff=True))
        elif self.target_roles == 'ADMINS':
            user_query &= Q(is_staff=True)
        elif self.target_roles == 'CLASS' and target_classes:
            user_query &= (
                Q(student__class_level__in=target_classes) |
                Q(parentguardian__students__class_level__in=target_classes) |
                Q(teacher__isnull=False) |
                Q(is_staff=True)
            )
        # ALL role includes all active users
        
        return User.objects.filter(user_query).distinct().count()
    
    def duplicate(self, new_title=None):
        """Create a duplicate of this announcement"""
        duplicate = Announcement.objects.get(pk=self.pk)
        duplicate.pk = None
        duplicate.title = new_title or f"Copy of {self.title}"
        duplicate.created_at = timezone.now()
        duplicate.updated_at = timezone.now()
        duplicate.is_active = False  # Keep duplicate inactive by default
        duplicate.save()
        return duplicate
    
    def extend_expiry(self, days=7):
        """Extend the expiry date by specified number of days"""
        if self.end_date:
            self.end_date += timezone.timedelta(days=days)
        else:
            self.end_date = timezone.now() + timezone.timedelta(days=days)
        self.save()
    
    def get_time_until_expiry(self):
        """Get human-readable time until expiry"""
        if not self.end_date or self.is_expired():
            return "No expiry" if not self.end_date else "Expired"
        
        delta = self.end_date - timezone.now()
        
        if delta.days > 0:
            return f"{delta.days} day{'s' if delta.days != 1 else ''}"
        elif delta.seconds // 3600 > 0:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours != 1 else ''}"
        else:
            minutes = (delta.seconds % 3600) // 60
            return f"{minutes} minute{'s' if minutes != 1 else ''}"



class UserAnnouncementView(models.Model):
    """Track which users have seen/dismissed which announcements"""
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    announcement = models.ForeignKey(Announcement, on_delete=models.CASCADE)
    dismissed = models.BooleanField(default=False)
    viewed_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('user', 'announcement')
        verbose_name = 'User Announcement View'
        verbose_name_plural = 'User Announcement Views'
        ordering = ['-viewed_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.announcement.title} ({'Dismissed' if self.dismissed else 'Viewed'})"
    
    @classmethod
    def get_user_unread_count(cls, user):
        """Get count of unread announcements for a user"""
        from .announcement_views import should_user_see_announcement
        
        active_announcements = Announcement.objects.filter(
            is_active=True,
            start_date__lte=timezone.now(),
        ).filter(
            Q(end_date__isnull=True) | Q(end_date__gte=timezone.now())
        )
        
        unread_count = 0
        for announcement in active_announcements:
            if (should_user_see_announcement(user, announcement) and 
                not cls.objects.filter(user=user, announcement=announcement).exists()):
                unread_count += 1
        
        return unread_count


# ===== AUDIT AND SECURITY =====

class AuditAlertRule(models.Model):

    SEVERITY_CHOICES = [
        ('LOW', 'Low'),
        ('MEDIUM', 'Medium'), 
        ('HIGH', 'High'),
        ('CRITICAL', 'Critical'),
    ]
    
    CONDITION_TYPES = [
        ('FREQUENCY', 'Frequency Threshold'),
        ('PATTERN', 'Pattern Detection'),
        ('RISK_SCORE', 'Risk Score Threshold'),
        ('CUSTOM', 'Custom Condition'),
    ]
    
    ACTION_CHOICES = [
        ('ALERT', 'Generate Alert'),
        ('NOTIFY', 'Send Notification'),
        ('BLOCK', 'Block Action'),
        ('ESCALATE', 'Escalate to Admin'),
    ]
    
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    condition_type = models.CharField(max_length=20, choices=CONDITION_TYPES)
    condition_config = models.JSONField(default=dict)  # Store condition parameters
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='MEDIUM')
    action = models.CharField(max_length=20, choices=ACTION_CHOICES, default='ALERT')
    is_active = models.BooleanField(default=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_alert_rules')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Audit Alert Rule"
        verbose_name_plural = "Audit Alert Rules"


class SecurityEvent(models.Model):
    # Define SEVERITY_CHOICES here - use the same as AuditAlertRule
    SEVERITY_CHOICES = AuditAlertRule.SEVERITY_CHOICES
    
    EVENT_TYPES = [
        ('LOGIN_ATTEMPT', 'Login Attempt'),
        ('DATA_ACCESS', 'Data Access'),
        ('DATA_MODIFICATION', 'Data Modification'),
        ('CONFIG_CHANGE', 'Configuration Change'),
        ('SECURITY_ALERT', 'Security Alert'),
        ('SYSTEM_EVENT', 'System Event'),
    ]
    
    rule = models.ForeignKey(AuditAlertRule, on_delete=models.CASCADE, related_name='security_events', null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    event_type = models.CharField(max_length=20, choices=EVENT_TYPES, default='SYSTEM_EVENT')
    severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default='MEDIUM')
    title = models.CharField(max_length=255)
    description = models.TextField()
    details = models.JSONField(default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    is_resolved = models.BooleanField(default=False)
    resolved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='resolved_events')
    resolved_at = models.DateTimeField(null=True, blank=True)
    resolved_notes = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.title} - {self.created_at}"

    class Meta:
        verbose_name = "Security Event"
        verbose_name_plural = "Security Events"
        ordering = ['-created_at']


class AuditReport(models.Model):
    REPORT_TYPES = [
        ('DAILY', 'Daily Report'),
        ('WEEKLY', 'Weekly Report'),
        ('MONTHLY', 'Monthly Report'),
        ('SECURITY', 'Security Report'),
        ('COMPLIANCE', 'Compliance Report'),
        ('CUSTOM', 'Custom Report'),
    ]
    
    name = models.CharField(max_length=200)
    report_type = models.CharField(max_length=20, choices=REPORT_TYPES)
    parameters = models.JSONField(default=dict)
    generated_by = models.ForeignKey(User, on_delete=models.CASCADE)
    generated_at = models.DateTimeField(auto_now_add=True)
    file_path = models.FileField(upload_to='audit_reports/', null=True, blank=True)
    is_archived = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} - {self.generated_at}"

    class Meta:
        verbose_name = "Audit Report"
        verbose_name_plural = "Audit Reports"



class DataRetentionPolicy(models.Model):
    RETENTION_TYPES = [
        ('AUDIT_LOG', 'Audit Logs'),
        ('SECURITY_EVENT', 'Security Events'),
        ('USER_DATA', 'User Data'),
        ('BACKUP', 'Backup Files'),
    ]
    
    name = models.CharField(max_length=200)
    retention_type = models.CharField(max_length=20, choices=RETENTION_TYPES)
    retention_period_days = models.IntegerField(help_text="Number of days to retain data")
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.name

    class Meta:
        verbose_name = "Data Retention Policy"
        verbose_name_plural = "Data Retention Policies"



class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
        ('ACCESS', 'Access'),
        ('OTHER', 'Other'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='audit_logs')
    action = models.CharField(max_length=10, choices=ACTION_CHOICES, db_index=True)
    model_name = models.CharField(max_length=50, db_index=True)
    object_id = models.CharField(max_length=50, db_index=True, blank=True, null=True)
    details = models.JSONField(blank=True, null=True, default=dict)
    ip_address = models.GenericIPAddressField(null=True, blank=True, db_index=True)
    timestamp = models.DateTimeField(auto_now_add=True, db_index=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Audit Log'
        verbose_name_plural = 'Audit Logs'
        indexes = [
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['action', 'timestamp']),
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user']),
            models.Index(fields=['action']),
        ]
    
    def __str__(self):
        return f"{self.user or 'System'} {self.action}d {self.model_name} at {self.timestamp}"

    @classmethod
    def log_action(cls, user, action, model_name=None, object_id=None, details=None, ip_address=None):
        return cls.objects.create(
            user=user,
            action=action,
            model_name=model_name or '',
            object_id=str(object_id) if object_id else None,
            details=details or {},
            ip_address=ip_address
        )


# ===== ANALYTICS =====

class AnalyticsCache(models.Model):
    """Cache for pre-computed analytics data"""
    name = models.CharField(max_length=100, unique=True)
    data = models.JSONField()
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Analytics Cache'
        verbose_name_plural = 'Analytics Caches'
    
    @classmethod
    def get_cached_data(cls, name, default=None):
        try:
            return cls.objects.get(name=name).data
        except cls.DoesNotExist:
            return default or {}

class GradeAnalytics(models.Model):
    """Model to store grade-related analytics"""
    class_level = models.CharField(max_length=20, choices=CLASS_LEVEL_CHOICES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    average_score = models.FloatField()
    highest_score = models.FloatField()
    lowest_score = models.FloatField()
    date_calculated = models.DateField(auto_now_add=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('class_level', 'subject', 'date_calculated')
        verbose_name = 'Grade Analytics'
        verbose_name_plural = 'Grade Analytics'

class AttendanceAnalytics(models.Model):
    """Model to store attendance analytics"""
    class_level = models.CharField(max_length=20, choices=CLASS_LEVEL_CHOICES)
    date = models.DateField()
    present_count = models.IntegerField()
    absent_count = models.IntegerField()
    late_count = models.IntegerField()
    attendance_rate = models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('class_level', 'date')
        verbose_name = 'Attendance Analytics'
        verbose_name_plural = 'Attendance Analytics'

# Utility function
def get_unread_count(user):
    """
    Get count of unread notifications for a user
    """
    return Notification.objects.filter(recipient=user, is_read=False).count()


class Holiday(models.Model):
    """Model to store school holidays"""
    name = models.CharField(max_length=200)
    date = models.DateField()
    is_school_holiday = models.BooleanField(default=True)
    description = models.TextField(blank=True, null=True)
    
    class Meta:
        verbose_name = "Holiday"
        verbose_name_plural = "Holidays"
        ordering = ['-date']
    
    def __str__(self):
        return f"{self.name} ({self.date})"


# Add to your models.py
class Budget(models.Model):
    """Model for budget planning and tracking"""
    academic_year = models.CharField(max_length=9)
    notes = models.TextField(blank=True, null=True)
    category = models.ForeignKey(FeeCategory, on_delete=models.CASCADE)
    allocated_amount = models.DecimalField(max_digits=10, decimal_places=2)
    actual_spent = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('academic_year', 'category')
        verbose_name = 'Budget'
        verbose_name_plural = 'Budgets'
        ordering = ['academic_year', 'category']
    
    def __str__(self):
        return f"{self.category.name} - {self.academic_year}"
    
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
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    date = models.DateField()
    description = models.TextField()
    receipt_number = models.CharField(max_length=50, blank=True)
    recorded_by = models.ForeignKey(User, on_delete=models.PROTECT)
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


# Add this to your SECURITY MODELS section (around the end of your file)

# ===== SECURITY MODELS =====

class UserProfile(models.Model):
    """Extended user profile for additional user management features"""
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='profile')
    is_blocked = models.BooleanField(default=False)
    blocked_reason = models.TextField(blank=True, null=True)
    blocked_at = models.DateTimeField(blank=True, null=True)
    blocked_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, 
                                 blank=True, null=True, related_name='blocked_users')
    
    # Temporary blocking fields
    block_duration = models.DurationField(blank=True, null=True, help_text="Duration for temporary block")
    block_until = models.DateTimeField(blank=True, null=True, help_text="Block until this date/time")
    auto_unblock_at = models.DateTimeField(blank=True, null=True)
    
    login_attempts = models.PositiveIntegerField(default=0)
    last_login_attempt = models.DateTimeField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'User Profile'
        verbose_name_plural = 'User Profiles'

    def __str__(self):
        return f"{self.user.username} - {'Blocked' if self.is_blocked else 'Active'}"

    def block_user(self, blocked_by, reason="", duration=None):
        """Block this user"""
        self.is_blocked = True
        self.blocked_reason = reason
        self.blocked_at = timezone.now()
        self.blocked_by = blocked_by
        
        if duration:
            self.block_duration = duration
            self.block_until = timezone.now() + duration
            self.auto_unblock_at = self.block_until
        else:
            self.block_duration = None
            self.block_until = None
            
        self.save()
        
        # Log the action
        details = {
            'reason': reason,
            'username': self.user.username,
            'blocked_at': self.blocked_at.isoformat(),
            'duration': str(duration) if duration else 'permanent'
        }
        AuditLog.log_action(
            user=blocked_by,
            action='BLOCK',
            model_name='User',
            object_id=self.user.id,
            details=details
        )

    def unblock_user(self, unblocked_by, reason=""):
        """Unblock this user"""
        self.is_blocked = False
        self.blocked_reason = ""
        self.blocked_at = None
        self.blocked_by = None
        self.block_duration = None
        self.block_until = None
        self.auto_unblock_at = None
        self.login_attempts = 0
        self.save()
        
        # Log the action
        AuditLog.log_action(
            user=unblocked_by,
            action='UNBLOCK',
            model_name='User',
            object_id=self.user.id,
            details={
                'reason': reason,
                'username': self.user.username,
                'unblocked_at': timezone.now().isoformat()
            }
        )



# In core/models.py - Update the MaintenanceMode model
class MaintenanceMode(models.Model):
    """Model to track system maintenance mode"""
    is_active = models.BooleanField(default=False)
    message = models.TextField(blank=True, help_text="Message to display to users during maintenance")
    start_time = models.DateTimeField(null=True, blank=True)
    end_time = models.DateTimeField(null=True, blank=True)
    allowed_ips = models.TextField(blank=True, help_text="Comma-separated list of IPs allowed during maintenance")
    
    # NEW: Allow specific users to bypass maintenance mode
    allowed_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name='maintenance_bypass_users',
        help_text="Users who can access the system during maintenance"
    )
    
    # NEW: Allow all staff users to bypass
    allow_staff_access = models.BooleanField(
        default=True,
        help_text="Allow all staff users to access the system during maintenance"
    )
    
    # NEW: Allow all superusers to bypass  
    allow_superuser_access = models.BooleanField(
        default=True,
        help_text="Allow all superusers to access the system during maintenance"
    )
    
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Maintenance Mode'
        verbose_name_plural = 'Maintenance Mode'
    
    def __str__(self):
        return f"Maintenance Mode - {'Active' if self.is_active else 'Inactive'}"
    
    def is_currently_active(self):
        """Check if maintenance is currently active based on time window"""
        if not self.is_active:
            return False
        
        now = timezone.now()
        if self.start_time and now < self.start_time:
            return False
        if self.end_time and now > self.end_time:
            return False
            
        return True
    
    def can_user_bypass(self, user):
        """Check if user can bypass maintenance mode"""
        if not user or not user.is_authenticated:
            return False
            
        # Superusers can always bypass if allowed
        if self.allow_superuser_access and user.is_superuser:
            return True
            
        # Staff users can bypass if allowed
        if self.allow_staff_access and user.is_staff:
            return True
            
        # Specific allowed users can bypass
        if self.allowed_users.filter(id=user.id).exists():
            return True
            
        return False
    
    @classmethod
    def get_current_maintenance(cls):
        """Get the current maintenance mode instance"""
        return cls.objects.filter(is_active=True).first()
    
    @classmethod
    def can_user_access(cls, user):
        """Check if user can access the system (bypass maintenance)"""
        maintenance = cls.get_current_maintenance()
        
        # No active maintenance - everyone can access
        if not maintenance or not maintenance.is_currently_active():
            return True
            
        # Check if user can bypass maintenance
        return maintenance.can_user_bypass(user)

class ScheduledMaintenance(models.Model):
    """Model for scheduled maintenance windows"""
    MAINTENANCE_TYPES = [
        ('EMERGENCY', 'Emergency Maintenance'),
        ('SCHEDULED', 'Scheduled Maintenance'),
        ('UPGRADE', 'System Upgrade'),
    ]
    
    title = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    maintenance_type = models.CharField(max_length=20, choices=MAINTENANCE_TYPES, default='SCHEDULED')
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    message = models.TextField(help_text="Message to display to users during maintenance")
    is_active = models.BooleanField(default=True)
    was_executed = models.BooleanField(default=False)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Scheduled Maintenance'
        verbose_name_plural = 'Scheduled Maintenance'
        ordering = ['-start_time']
    
    def __str__(self):
        return f"{self.title} ({self.start_time} to {self.end_time})"
    
    def is_currently_active(self):
        """Check if maintenance is currently active"""
        now = timezone.now()
        return self.start_time <= now <= self.end_time and self.is_active
    
    def is_upcoming(self):
        """Check if maintenance is upcoming"""
        return self.start_time > timezone.now() and self.is_active
    
    def duration(self):
        """Calculate maintenance duration"""
        return self.end_time - self.start_time


# Signals for UserProfile
@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if created:
        UserProfile.objects.get_or_create(user=instance)

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def save_user_profile(sender, instance, **kwargs):
    if hasattr(instance, 'profile'):
        instance.profile.save()


# ===== UTILITY FUNCTIONS =====

def create_notification(recipient, title, message, notification_type="GENERAL", link=None, related_object=None):
    """Utility function to create notifications"""
    from .models import Notification
    return Notification.create_notification(
        recipient=recipient,
        title=title,
        message=message,
        notification_type=notification_type,
        link=link,
        related_object=related_object
    )

def is_admin(user):
    """Check if user is admin"""
    return user.is_staff or user.is_superuser

def is_student(user):
    """Check if user is a student"""
    return hasattr(user, 'student')

def is_teacher(user):
    """Check if user is a teacher"""
    return hasattr(user, 'teacher')

def is_parent(user):
    """Check if user is a parent"""
    return hasattr(user, 'parentguardian')

