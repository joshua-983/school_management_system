import os
import logging
from datetime import date, timedelta
from decimal import Decimal
from django.db import models
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
        """Get attendance rate for this student"""
        if not term:
            term = AcademicTerm.objects.filter(is_active=True).first()
        
        if not term:
            return 0
        
        try:
            summary = AttendanceSummary.objects.get(
                student=self,
                term=term,
                period__isnull=True
            )
            return summary.present_rate
        except AttendanceSummary.DoesNotExist:
            return 0
    
    def get_term_attendance_data(self, term=None):
        """
        Calculate attendance data for a specific term - FIXED VERSION
        """
        try:
            if not term:
                term = AcademicTerm.objects.filter(is_active=True).first()
            
            if not term:
                return {'attendance_rate': 0, 'total_days': 0, 'present_days': 0, 'absence_count': 0}
            
            # Calculate attendance records for this term using the database
            attendance_records = StudentAttendance.objects.filter(
                student=self,
                term=term
            )
            
            total_days = attendance_records.count()
            if total_days == 0:
                return {'attendance_rate': 0, 'total_days': 0, 'present_days': 0, 'absence_count': 0}
            
            # Use database aggregation for better performance
            from django.db.models import Count, Q
            
            present_days = attendance_records.filter(
                Q(status='present') | Q(status='late') | Q(status='excused')
            ).count()
            
            absence_count = attendance_records.filter(status='absent').count()
            
            attendance_rate = round((present_days / total_days) * 100, 1) if total_days > 0 else 0
            
            return {
                'attendance_rate': attendance_rate,
                'total_days': total_days,
                'present_days': present_days,
                'absence_count': absence_count
            }
            
        except Exception as e:
            logger.error(f"Error calculating attendance data for student {self.id}: {e}")
            return {'attendance_rate': 0, 'total_days': 0, 'present_days': 0, 'absence_count': 0}
    
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
        null=True, 
        blank=True,
        editable=False  # Prevent manual editing
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
        # Generate employee_id only when creating a new teacher (not updating)
        if not self.employee_id:
            current_year = str(timezone.now().year)
            
            # Find the last teacher ID for the current year
            last_teacher = Teacher.objects.filter(
                employee_id__startswith=f'TCH{current_year}'
            ).order_by('-employee_id').first()
            
            if last_teacher and last_teacher.employee_id:
                try:
                    # Extract sequence from format TCH2025001, TCH2025002, etc.
                    last_sequence = int(last_teacher.employee_id[7:])  # TCH2025[001]
                    new_sequence = last_sequence + 1
                except (ValueError, IndexError):
                    new_sequence = 1
            else:
                new_sequence = 1
            
            # Format: TCH + Year + 3-digit sequence (TCH2025001, TCH2025002)
            self.employee_id = f'TCH{current_year}{new_sequence:03d}'
            
            # Ensure uniqueness
            while Teacher.objects.filter(employee_id=self.employee_id).exists():
                new_sequence += 1
                self.employee_id = f'TCH{current_year}{new_sequence:03d}'
        
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
def create_parent_user(sender, instance, created, **kwargs):
    """Automatically create a user account for parents with email"""
    if created and instance.email and not instance.user:
        try:
            user = User.objects.filter(email=instance.email).first()
            if not user:
                base_username = instance.email.split('@')[0]
                username = base_username
                counter = 1
                while User.objects.filter(username=username).exists():
                    username = f"{base_username}{counter}"
                    counter += 1
                
                user = User.objects.create_user(
                    username=username,
                    email=instance.email,
                    password=User.objects.make_random_password(),
                    first_name="Parent",
                    last_name=instance.email.split('@')[0]
                )
            instance.user = user
            instance.save(update_fields=['user'])
        except Exception as e:
            logger.error(f"Error creating user for parent {instance.email}: {e}")

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

class Grade(models.Model):
    GES_GRADE_CHOICES = [
        ('1', '1 (90-100%) - Outstanding'),
        ('2', '2 (80-89%) - Excellent'),
        ('3', '3 (70-79%) - Very Good'), 
        ('4', '4 (60-69%) - Good'),
        ('5', '5 (50-59%) - Satisfactory'),
        ('6', '6 (40-49%) - Fair'),
        ('7', '7 (30-39%) - Weak'),
        ('8', '8 (20-29%) - Very Weak'),
        ('9', '9 (0-19%) - Fail'),
        ('N/A', 'Not Available'),
    ]

    # Ghana Education Service Standard Weights
    HOMEWORK_WEIGHT = 10
    CLASSWORK_WEIGHT = 30  
    TEST_WEIGHT = 10
    EXAM_WEIGHT = 50

    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    class_assignment = models.ForeignKey(ClassAssignment, on_delete=models.CASCADE)
    academic_year = models.CharField(max_length=9, validators=[RegexValidator(r'^\d{4}/\d{4}$')])
    term = models.PositiveSmallIntegerField(choices=TERM_CHOICES)

    classwork_score = models.DecimalField(
        max_digits=5, decimal_places=2, 
        validators=[MinValueValidator(0), MaxValueValidator(CLASSWORK_WEIGHT)],
        verbose_name=f"Classwork ({CLASSWORK_WEIGHT}%)",
        default=0
    )
    homework_score = models.DecimalField(
        max_digits=5, decimal_places=2, 
        validators=[MinValueValidator(0), MaxValueValidator(HOMEWORK_WEIGHT)],
        verbose_name=f"Homework ({HOMEWORK_WEIGHT}%)",
        default=0
    )
    test_score = models.DecimalField(
        max_digits=5, decimal_places=2, 
        validators=[MinValueValidator(0), MaxValueValidator(TEST_WEIGHT)],
        verbose_name=f"Test ({TEST_WEIGHT}%)", 
        default=0
    )
    exam_score = models.DecimalField(
        max_digits=5, decimal_places=2, 
        validators=[MinValueValidator(0), MaxValueValidator(EXAM_WEIGHT)],
        verbose_name=f"Exam ({EXAM_WEIGHT}%)",
        default=0
    )

    total_score = models.DecimalField(max_digits=5, decimal_places=2, editable=False, null=True, blank=True)
    ges_grade = models.CharField(max_length=3, choices=GES_GRADE_CHOICES, editable=False, default='N/A')
    remarks = models.TextField(blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('student', 'subject', 'academic_year', 'term')
        ordering = ['academic_year', 'term', 'student__last_name']
        verbose_name = 'Grade'
        verbose_name_plural = 'Grades'

    def save(self, *args, **kwargs):
        self.calculate_total_score()
        self.determine_ges_grade()
        super().save(*args, **kwargs)

    def calculate_total_score(self):
        """Calculate total score using standardized Ghanaian weights"""
        try:
            self.total_score = (
                (self.classwork_score or 0) + 
                (self.homework_score or 0) + 
                (self.test_score or 0) + 
                (self.exam_score or 0)
            )
        except (TypeError, AttributeError):
            self.total_score = None

    def determine_ges_grade(self):
        """Determine GES grade based on Ghana Education Service standards"""
        if self.total_score is None:
            self.ges_grade = 'N/A'
            return

        score = float(self.total_score)
        
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

    def get_grade_description(self):
        """Get descriptive text for the grade"""
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
        return descriptions.get(self.ges_grade, '')

    def is_passing(self):
        """Check if grade is passing (GES standards - 40% and above)"""
        return self.total_score and float(self.total_score) >= 40.0

    def get_performance_level(self):
        """Get performance level category"""
        if not self.total_score:
            return 'Unknown'
            
        score = float(self.total_score)
        if score >= 80: return 'Excellent'
        elif score >= 70: return 'Very Good'
        elif score >= 60: return 'Good' 
        elif score >= 50: return 'Satisfactory'
        elif score >= 40: return 'Fair'
        else: return 'Poor'

    def __str__(self):
        return f"{self.student} - {self.subject} ({self.academic_year} Term {self.term}): {self.ges_grade}"

    @classmethod
    def get_subject_statistics(cls, subject, class_level, academic_year, term):
        """Get statistics for a specific subject, class, and term"""
        grades = cls.objects.filter(
            subject=subject,
            student__class_level=class_level,
            academic_year=academic_year,
            term=term
        ).exclude(total_score__isnull=True)
        
        if not grades.exists():
            return None
            
        scores = [float(grade.total_score) for grade in grades]
        
        return {
            'count': len(scores),
            'average': round(sum(scores) / len(scores), 2),
            'highest': max(scores),
            'lowest': min(scores),
            'passing_rate': round(len([s for s in scores if s >= 40]) / len(scores) * 100, 1)
        }


# ===== SCHOOL CONFIGURATION =====

class SchoolConfiguration(models.Model):
    GRADING_SYSTEM_CHOICES = [
        ('GES', 'Ghana Education System (Primary/JHS)'),
        ('WASSCE', 'West African Senior School Certificate Exam'),
    ]
    
    grading_system = models.CharField(max_length=10, choices=GRADING_SYSTEM_CHOICES, default='GES')
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
        if self.due_date and self.due_date <= timezone.now():
            raise ValidationError({'due_date': 'Due date must be in the future'})

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
        is_new = self.pk is None
        super().save(*args, **kwargs)

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

class FeeCategory(models.Model):
    CATEGORY_TYPES = [
        ('ADMISSION', 'Admission Fees'),
        ('TUITION', 'Tuition Fees'),
        ('FEEDING', 'Feeding Fees'),
        ('UNIFORM', 'Uniform Fees'),
        ('BOOKS', 'Books and Materials'),
        ('TRANSPORT', 'Transportation Fees'),
        ('OTHER', 'Other Fees'),
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

class Bill(models.Model):
    """Represents an invoice sent to a student for specific fees"""
    bill_number = models.CharField(max_length=20, unique=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='bills')
    issue_date = models.DateField(auto_now_add=True)
    due_date = models.DateField()
    academic_year = models.CharField(max_length=9)
    term = models.PositiveSmallIntegerField(choices=TERM_CHOICES)
    status = models.CharField(max_length=10, choices=[
        ('issued', 'Issued'),
        ('paid', 'Paid'),
        ('partial', 'Partially Paid'),
        ('overdue', 'Overdue'),
        ('cancelled', 'Cancelled')
    ], default='issued')
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
        
        # Calculate balance
        self.balance = self.total_amount - self.amount_paid
        super().save(*args, **kwargs)
    
    def update_status(self):
        """Update bill status based on payments"""
        # Calculate total payments
        total_payments = sum(payment.amount for payment in self.bill_payments.all())
        self.amount_paid = total_payments
        
        if total_payments >= self.total_amount:
            self.status = 'paid'
        elif total_payments > 0:
            self.status = 'partial'
        elif timezone.now().date() > self.due_date:
            self.status = 'overdue'
        else:
            self.status = 'issued'
        
        # Recalculate balance
        self.balance = self.total_amount - self.amount_paid
        self.save(update_fields=['status', 'amount_paid', 'balance'])
    
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
        ('CASH', 'Cash'),
        ('BANK_TRANSFER', 'Bank Transfer'),
        ('MOBILE_MONEY', 'Mobile Money'),
        ('CHECK', 'Check'),
        ('OTHER', 'Other'),
    ]
    
    bill = models.ForeignKey('Bill', on_delete=models.CASCADE, related_name='bill_payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_mode = models.CharField(max_length=20, choices=PAYMENT_MODES, default='CASH')
    payment_date = models.DateField(default=timezone.now)
    notes = models.TextField(blank=True, null=True)
    recorded_by = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-payment_date']
        verbose_name = 'Bill Payment'
        verbose_name_plural = 'Bill Payments'

    def __str__(self):
        return f"Payment of GH₵{self.amount} for Bill #{self.bill.bill_number}"

    def save(self, *args, **kwargs):
        # Update the bill's paid amount when a payment is saved
        super().save(*args, **kwargs)
        self.bill.update_status()

class Fee(models.Model):
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
        """Update payment status with grace period logic"""
        tolerance = Decimal('1.00')
        grace_period = 5
        today = timezone.now().date()
        effective_due_date = self.due_date + timedelta(days=grace_period)
        difference = abs(self.amount_payable - self.amount_paid)
        
        if difference <= tolerance:
            self.payment_status = 'paid'
        elif self.amount_paid >= self.amount_payable:
            self.payment_status = 'paid'
        elif self.amount_paid > Decimal('0.00'):
            self.payment_status = 'partial'
        elif today > effective_due_date:
            self.payment_status = 'overdue'
        else:
            self.payment_status = 'unpaid'

    @property
    def payment_percentage(self):
        """Calculate payment percentage"""
        if self.amount_payable > 0:
            return (self.amount_paid / self.amount_payable) * 100
        return 0
    
    @property
    def is_overdue(self):
        """Check if fee is overdue"""
        if self.due_date and self.payment_status != 'paid':
            return self.due_date < timezone.now().date()
        return False

    def clean(self):
        """Validate the fee data"""
        if self.amount_paid > self.amount_payable:
            raise ValidationError({'amount_paid': 'Amount paid cannot exceed amount payable'})
        
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
        self.balance = self.amount_payable - self.amount_paid
        self.update_payment_status()
        
        if self.payment_status == 'paid' and not self.payment_date:
            self.payment_date = timezone.now().date()
        elif self.payment_status != 'paid' and self.payment_date:
            self.payment_date = None
            
        super().save(*args, **kwargs)

    def get_payment_status_html(self):
        """Get HTML badge for payment status"""
        status_display = self.get_payment_status_display()
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
    
    def mark_as_read(self):
        """Mark notification as read and send WebSocket update"""
        if not self.is_read:
            self.is_read = True
            self.save(update_fields=['is_read'])
            self.send_ws_update()
            return True
        return False
    
    def send_ws_update(self):
        """Send WebSocket update for this notification"""
        try:
            from channels.layers import get_channel_layer
            from asgiref.sync import async_to_sync
            
            channel_layer = get_channel_layer()
            async_to_sync(channel_layer.group_sync)(
                f'notifications_{self.recipient.id}',
                {
                    'type': 'notification_update',
                    'action': 'single_read',
                    'notification_id': self.id,
                    'unread_count': self.get_unread_count_for_user()
                }
            )
        except Exception as e:
            logger.error(f"WebSocket update failed for notification {self.id}: {str(e)}")
    
    @classmethod
    def get_unread_count_for_user(cls, user):
        """Get unread notification count for a user"""
        return cls.objects.filter(recipient=user, is_read=False).count()
    
    @classmethod
    def create_notification(cls, recipient, title, message, notification_type="GENERAL", link=None, 
                          related_object=None):
        """
        Class method to create a notification with proper error handling
        """
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
            
            notification.send_new_notification_ws()
            
            return notification
            
        except Exception as e:
            logger.error(f"Failed to create notification: {str(e)}")
            return None

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
    
    class Meta:
        ordering = ['period_number']
        verbose_name = 'Time Slot'
        verbose_name_plural = 'Time Slots'
    
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
    
    def __str__(self):
        return f"{self.get_class_level_display()} - {self.get_day_of_week_display()} - {self.academic_year} Term {self.term}"

class TimetableEntry(models.Model):
    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name='entries')
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    classroom = models.CharField(max_length=100, blank=True)
    is_break = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['time_slot__period_number']
        unique_together = ('timetable', 'time_slot')
        verbose_name = 'Timetable Entry'
        verbose_name_plural = 'Timetable Entries'
    
    def __str__(self):
        if self.is_break:
            return f"{self.time_slot.break_name} - Break"
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
    
    def is_expired(self):
        """Check if announcement has expired"""
        if self.end_date:
            return timezone.now() > self.end_date
        return False
    
    def is_active_now(self):
        """Check if announcement is currently active"""
        return self.is_active and not self.is_expired()
    
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
    
    def __str__(self):
        return f"{self.user.username} - {self.announcement.title} ({'Dismissed' if self.dismissed else 'Viewed'})"

# ===== AUDIT AND SECURITY =====

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

class SecurityEvent(models.Model):
    EVENT_TYPES = [
        ('login_success', 'Login Success'),
        ('login_failed', 'Login Failed'),
        ('password_change', 'Password Change'),
        ('user_created', 'User Created'),
        ('user_deleted', 'User Deleted'),
        ('permission_change', 'Permission Change'),
        ('data_access', 'Data Access'),
        ('configuration_change', 'Configuration Change'),
    ]
    
    SEVERITY_LEVELS = [
        ('low', 'Low'),
        ('medium', 'Medium'),
        ('high', 'High'),
        ('critical', 'Critical'),
    ]
    
    timestamp = models.DateTimeField(auto_now_add=True)
    event_type = models.CharField(max_length=50, choices=EVENT_TYPES)
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        related_name='security_events'
    )
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(blank=True)
    description = models.TextField()
    severity = models.CharField(max_length=10, choices=SEVERITY_LEVELS, default='low')
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
        verbose_name = 'Security Event'
        verbose_name_plural = 'Security Events'
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['event_type']),
            models.Index(fields=['severity']),
            models.Index(fields=['user', '-timestamp']),
        ]
    
    def __str__(self):
        username = self.user.username if self.user else 'System'
        return f"{self.get_event_type_display()} - {username} - {self.timestamp.strftime('%Y-%m-%d %H:%M')}"


class AuditAlertRule(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    severity = models.CharField(max_length=10, choices=SecurityEvent.SEVERITY_LEVELS, default='medium')
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = 'Audit Alert Rule'
        verbose_name_plural = 'Audit Alert Rules'
    
    def __str__(self):
        return self.name

class AuditReport(models.Model):
    REPORT_TYPES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
        ('custom', 'Custom'),
    ]
    
    name = models.CharField(max_length=100)
    report_type = models.CharField(max_length=10, choices=REPORT_TYPES, default='daily')
    generated_at = models.DateTimeField(auto_now_add=True)
    report_file = models.FileField(upload_to='audit_reports/', null=True, blank=True)
    is_downloaded = models.BooleanField(default=False)
    
    class Meta:
        verbose_name = 'Audit Report'
        verbose_name_plural = 'Audit Reports'
    
    def __str__(self):
        return self.name

class DataRetentionPolicy(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField()
    retention_days = models.IntegerField(default=365)
    applies_to = models.CharField(max_length=100)  # e.g., 'security_events', 'audit_logs', etc.
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = 'Data Retention Policy'
        verbose_name_plural = 'Data Retention Policies'
    
    def __str__(self):
        return self.name

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



