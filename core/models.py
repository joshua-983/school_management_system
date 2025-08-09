from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import os
from datetime import date
from django.urls import reverse
from django.core.validators import RegexValidator
from django.db import transaction
from django.core.exceptions import ValidationError
from django.conf import settings


User = get_user_model()

def student_image_path(instance, filename):
    ext = filename.split('.')[-1]
    filename = f"{instance.student_id}.{ext}"
    return os.path.join('students', filename)

class Student(models.Model):
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
    
    student_id = models.CharField(max_length=20, unique=True)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='student')
    first_name = models.CharField(max_length=100)
    middle_name = models.CharField(max_length=100, blank=True)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=GENDER_CHOICES)
    nationality = models.CharField(max_length=100)
    ethnicity = models.CharField(max_length=100, blank=True)
    religion = models.CharField(max_length=100, blank=True)
    place_of_birth = models.CharField(max_length=100)
    residential_address = models.TextField()
    profile_picture = models.ImageField(upload_to=student_image_path, blank=True, null=True)
    class_level = models.CharField(max_length=2, choices=CLASS_LEVEL_CHOICES)
    admission_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        ordering = ['class_level', 'last_name', 'first_name']
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.student_id}) - {self.get_class_level_display()}"
    
    def get_full_name(self):
        return f"{self.first_name} {self.middle_name} {self.last_name}".strip()
    
    def get_age(self):
        today = date.today()
        return today.year - self.date_of_birth.year - ((today.month, today.day) < (self.date_of_birth.month, self.date_of_birth.day))

    def save(self, *args, **kwargs):
        # Generate student ID if this is a new student
        if not self.student_id:
            current_year = str(timezone.now().year)
            class_level = self.class_level
            
            # Get the last student in this class for the current year
            last_student = Student.objects.filter(
                student_id__startswith=f'STUD{current_year}{class_level}'
            ).order_by('-student_id').first()
            
            if last_student:
                # Extract the sequence number and increment
                last_sequence = int(last_student.student_id[-3:])
                new_sequence = last_sequence + 1
            else:
                # First student in this class for the year
                new_sequence = 1
                
            # Format the new student ID
            self.student_id = f'STUD{current_year}{class_level}{new_sequence:03d}'
            
        super().save(*args, **kwargs)   

class ParentGuardian(models.Model):
    RELATIONSHIP_CHOICES = [
        ('F', 'Father'),
        ('M', 'Mother'),
        ('B', 'Brother'),
        ('S', 'Sister'),
        ('O', 'Other Relative'),
        ('G', 'Guardian'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='parents')
    full_name = models.CharField(max_length=200)
    occupation = models.CharField(max_length=100, blank=True)
    relationship = models.CharField(max_length=1, choices=RELATIONSHIP_CHOICES)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True)
    address = models.TextField(blank=True)
    is_emergency_contact = models.BooleanField(default=False)
    emergency_contact_priority = models.PositiveSmallIntegerField(default=1)
    
    class Meta:
        ordering = ['student', 'emergency_contact_priority']
        verbose_name_plural = "Parents/Guardians"
    
    def __str__(self):
        return f"{self.full_name} ({self.get_relationship_display()}) of {self.student}"

class Subject(models.Model):
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=10, unique=True)
    description = models.TextField(blank=True)
    
    class Meta:
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.code})"

class Teacher(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='teacher')
    first_name = models.CharField(max_length=100)
    last_name = models.CharField(max_length=100)
    date_of_birth = models.DateField()
    gender = models.CharField(max_length=1, choices=Student.GENDER_CHOICES)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField()
    address = models.TextField()
    subjects = models.ManyToManyField(Subject, related_name='teachers')
    class_levels = models.CharField(max_length=50)  # Comma-separated list of class levels
    is_active = models.BooleanField(default=True)
    
    def __str__(self):
        return f"{self.first_name} {self.last_name}"
    
    def get_full_name(self):
        return f"{self.first_name} {self.last_name}"

class ClassAssignment(models.Model):
    class_level = models.CharField(max_length=2, choices=Student.CLASS_LEVEL_CHOICES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    academic_year = models.CharField(max_length=9)  # e.g., "2023-2024"
    
    class Meta:
        unique_together = ('class_level', 'subject', 'academic_year')
    
    def __str__(self):
        return f"{self.get_class_level_display()} - {self.subject} ({self.academic_year})"
    
# fee management
class FeeCategory(models.Model):
    """Categories for different types of fees"""
    CATEGORY_TYPES = [
        ('ADMISSION', 'Admission Fees'),
        ('TUITION', 'Tuition Fees'),
        ('FEEDING', 'Feeding Fees'),
        ('UNIFORM', 'Uniform Fees'),
        ('BOOKS', 'Books and Materials'),
        ('TRANSPORT', 'Transportation Fees'),
        ('OTHER', 'Other Fees'),
    ]
    
    name = models.CharField(max_length=100, choices=CATEGORY_TYPES)
    description = models.TextField(blank=True)
    is_mandatory = models.BooleanField(default=True)
    applies_to_all = models.BooleanField(default=True)
    class_levels = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Comma-separated list of class levels this applies to (leave blank for all)"
    )
    
    def __str__(self):
        return self.get_name_display()

class Fee(models.Model):
    PAYMENT_MODE_CHOICES = [
        ('CASH', 'Cash'),
        ('BANK', 'Bank Transfer'),
        ('CARD', 'Credit Card'),
        ('CHECK', 'Check'),
        ('MOBILE', 'Mobile Money'),
    ]
    
    PAYMENT_STATUS_CHOICES = [
        ('PAID', 'Paid'),
        ('UNPAID', 'Unpaid'),
        ('PARTIAL', 'Part Payment'),
        ('OVERDUE', 'Overdue'),
    ]
    
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='fees')
    category = models.ForeignKey(FeeCategory, on_delete=models.PROTECT)
    amount_payable = models.DecimalField(max_digits=10, decimal_places=2)
    amount_paid = models.DecimalField(max_digits=10, decimal_places=2, default=0)
    balance = models.DecimalField(
        max_digits=10, 
        decimal_places=2, 
        editable=False,
        default=0  # Critical fix - add default value
    )
    payment_mode = models.CharField(max_length=10, choices=PAYMENT_MODE_CHOICES, blank=True)
    payment_status = models.CharField(max_length=10, choices=PAYMENT_STATUS_CHOICES, default='UNPAID')
    payment_date = models.DateTimeField(null=True, blank=True)
    receipt_number = models.CharField(max_length=20, unique=True, blank=True, editable=False)
    academic_year = models.CharField(max_length=9)
    term = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(3)])
    due_date = models.DateField()
    date_recorded = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_fees'
    )
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-date_recorded', 'student']
        indexes = [
            models.Index(fields=['receipt_number']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['due_date']),
        ]
        verbose_name_plural = "Fees"
    
    def __str__(self):
        return f"{self.student} - {self.category} ({self.amount_paid}/{self.amount_payable})"
    
    def clean(self):
        """Validate payment status and receipt number consistency"""
        # Convert academic year format if needed
        if '-' in self.academic_year:
            self.academic_year = self.academic_year.replace('-', '/')
        
        # Remove receipt number validation from clean() since we'll handle it in save()
        
        # Validate due date is within academic year
        try:
            academic_year_parts = self.academic_year.split('/')
            if len(academic_year_parts) != 2:
                raise ValidationError("Academic year must be in format YYYY/YYYY or YYYY-YYYY")
                
            academic_year_start = int(academic_year_parts[0])
            academic_year_end = int(academic_year_parts[1])
            
            if not (date(academic_year_start, 9, 1) <= self.due_date <= date(academic_year_end, 8, 31)):
                raise ValidationError("Due date must be within the academic year")
        except (ValueError, IndexError):
            raise ValidationError("Academic year must be in format YYYY/YYYY or YYYY-YYYY")
    
    @classmethod
    def generate_receipt_number(cls):
        """
        Generate a professional receipt number with:
        - Institution code (optional)
        - Year and term
        - Sequential number
        - Check digit for validation
        
        Format: SCH/{year}/{term}/XXXXX-C
        Example: SCH/2023/2/00042-5
        """
        now = timezone.now()
        current_year = now.year
        current_term = cls.determine_current_term()
        
        with transaction.atomic():
            # Get the last receipt for this year/term combination
            prefix = f"SCH/{current_year}/{current_term}/"
            last_receipt = (
                cls.objects
                .select_for_update()
                .filter(receipt_number__startswith=prefix)
                .order_by('-receipt_number')
                .first()
            )
            
            if last_receipt:
                try:
                    # Extract the sequential number part
                    sequence_part = last_receipt.receipt_number.split('/')[-1].split('-')[0]
                    last_num = int(sequence_part)
                    new_num = last_num + 1
                except (ValueError, IndexError, AttributeError):
                    new_num = 1
            else:
                new_num = 1
                
            # Format with leading zeros
            sequence_str = f"{new_num:05d}"
            
            # Calculate check digit (simple modulus 10 for example)
            check_digit = sum(int(d) for d in sequence_str) % 10
            
            return f"{prefix}{sequence_str}-{check_digit}"
    
    @staticmethod
    def determine_current_term():
        """Determine current term based on date"""
        today = timezone.now().date()
        month = today.month
        
        if month in [1, 2, 3, 4]:  # Jan-Apr
            return 1
        elif month in [5, 6, 7, 8]:  # May-Aug
            return 2
        else:  # Sep-Dec
            return 3
    
    def save(self, *args, **kwargs):
        """Override save to handle receipt number generation and balance calculation"""
        # Calculate balance first
        self.balance = self.calculate_balance()
        
        # Update payment status based on balance
        if self.amount_paid >= self.amount_payable:
            self.payment_status = 'PAID'
        elif self.amount_paid > 0:
            self.payment_status = 'PARTIAL'
        else:
            self.payment_status = 'UNPAID'
        
        # Check if payment is overdue
        if self.due_date < timezone.now().date() and self.payment_status != 'PAID':
            self.payment_status = 'OVERDUE'
        
        # Generate receipt number only when payment is marked as PAID and no receipt exists
        if self.payment_status == 'PAID' and not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
            if not self.payment_date:
                self.payment_date = timezone.now()
        
        # Clear receipt number if payment status changes from PAID
        elif self.payment_status != 'PAID' and self.receipt_number:
            self.receipt_number = ''
        
        # Set recorded_by if not set
        if not self.recorded_by and hasattr(self, '_current_user'):
            self.recorded_by = self._current_user
        
        # Validate the model before saving
        try:
            self.full_clean()
            super().save(*args, **kwargs)
        except ValidationError as e:
            if 'receipt_number' in e.message_dict:
                # Regenerate receipt number if duplicate (shouldn't happen with this system)
                self.receipt_number = self.generate_receipt_number()
                super().save(*args, **kwargs)
            else:
                raise
    
    def calculate_balance(self):
        """Calculate the remaining balance with proper null handling"""
        payable = self.amount_payable if self.amount_payable is not None else Decimal('0')
        paid = self.amount_paid if self.amount_paid is not None else Decimal('0')
        return payable - paid
class FeePayment(models.Model):
    """Detailed record of individual payments"""
    fee = models.ForeignKey(Fee, on_delete=models.CASCADE, related_name='payments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_date = models.DateTimeField(default=timezone.now)
    payment_mode = models.CharField(max_length=10, choices=Fee.PAYMENT_MODE_CHOICES)
    receipt_number = models.CharField(max_length=20, unique=True, blank=True)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        related_name='recorded_payments'
    )
    notes = models.TextField(blank=True)
    bank_reference = models.CharField(max_length=50, blank=True)
    is_confirmed = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['-payment_date']
    
    def __str__(self):
        return f"Payment of {self.amount} for {self.fee}"
    
    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = Fee.generate_receipt_number()
        super().save(*args, **kwargs)


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
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-due_date', 'subject']
    
    def __str__(self):
        return f"{self.get_assignment_type_display()} - {self.subject} ({self.class_assignment.get_class_level_display()})"

class StudentAssignment(models.Model):
    student = models.ForeignKey(Student, on_delete=models.CASCADE)
    assignment = models.ForeignKey(Assignment, on_delete=models.CASCADE)
    status = models.CharField(max_length=10, choices=Assignment.STATUS_CHOICES, default='PENDING')
    submitted_date = models.DateTimeField(null=True, blank=True)
    score = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    feedback = models.TextField(blank=True)
    file = models.FileField(upload_to='assignments/', blank=True, null=True)
    
    class Meta:
        unique_together = ('student', 'assignment')
        ordering = ['assignment__due_date', 'student']
    
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

class Grade(models.Model):
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
        ('N/A', 'Not Available'),
    ]
    
    # Relationships
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='grades')
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE, related_name='grades')
    class_assignment = models.ForeignKey('ClassAssignment', on_delete=models.CASCADE, related_name='grades')
    
    # Academic information
    academic_year = models.CharField(max_length=9, validators=[RegexValidator(r'^\d{4}/\d{4}$')])
    term = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(3)])
    
    # Scores
    homework_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    classwork_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    test_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    exam_score = models.DecimalField(
        max_digits=5, 
        decimal_places=2, 
        default=0,
        validators=[MinValueValidator(0), MaxValueValidator(100)]
    )
    
    # Calculated fields
    total_score = models.DecimalField(max_digits=5, decimal_places=2, editable=False, null=True, blank=True)
    grade = models.CharField(max_length=3, choices=GRADE_CHOICES, editable=False, default='N/A')
    remarks = models.TextField(blank=True)
    
    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('student', 'subject', 'class_assignment', 'academic_year', 'term')
        ordering = ['student__last_name', 'student__first_name', 'subject__name']
        verbose_name = 'Grade'
        verbose_name_plural = 'Grades'
    
    def __str__(self):
        return f"{self.student} - {self.subject} ({self.academic_year} Term {self.term}): {self.grade}"
    
    def clean(self):
        """Validate the grade before saving"""
        super().clean()
        
        # Validate scores are within valid ranges
        for score_field in ['homework_score', 'classwork_score', 'test_score', 'exam_score']:
            score = getattr(self, score_field)
            if score < 0 or score > 100:
                raise ValidationError(
                    {score_field: f"Score must be between 0 and 100 (got {score})"}
                )
    
    def calculate_total_score(self):
        """
        Calculate weighted total score based on:
        - 20% homework
        - 30% classwork
        - 10% test
        - 40% exam
        
        Returns None if any required score is missing
        """
        try:
            weights = {
                'homework_score': 0.2,
                'classwork_score': 0.3,
                'test_score': 0.1,
                'exam_score': 0.4
            }
            
            total = 0
            for field, weight in weights.items():
                score = getattr(self, field)
                if score is None:
                    return None
                total += float(score) * weight
            
            return round(total, 2)
        except (TypeError, ValueError):
            return None
    
    @classmethod
    def calculate_grade(cls, score):
        """
        Class method to calculate letter grade from numerical score
        Returns 'N/A' if score is invalid
        """
        if score is None:
            return 'N/A'
            
        try:
            score = float(score)
            if score > 100 or score < 0:
                return 'N/A'
                
            if score >= 90: return 'A+'
            elif score >= 80: return 'A'
            elif score >= 70: return 'B+'
            elif score >= 60: return 'B'
            elif score >= 50: return 'C+'
            elif score >= 40: return 'C'
            elif score >= 30: return 'D+'
            elif score >= 20: return 'D'
            else: return 'E'
        except (ValueError, TypeError):
            return 'N/A'
    
    def save(self, *args, **kwargs):
        """Override save to calculate total score and grade"""
        self.full_clean()  # Run validation first
        
        # Calculate and set totals
        self.total_score = self.calculate_total_score()
        self.grade = self.calculate_grade(self.total_score)
        
        # Update timestamp if needed
        if not self.pk:  # New record
            self.created_at = timezone.now()
        
        super().save(*args, **kwargs)
    
    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('grade_detail', kwargs={'pk': self.pk})
    
    @property
    def is_passing(self):
        """Check if grade is passing (C+ or better)"""
        return self.grade in ['A+', 'A', 'B+', 'B', 'C+']
    
    @classmethod
    def get_student_grades(cls, student, academic_year=None, term=None):
        """Helper method to get grades for a student with optional filters"""
        queryset = cls.objects.filter(student=student)
        
        if academic_year:
            queryset = queryset.filter(academic_year=academic_year)
        if term:
            queryset = queryset.filter(term=term)
            
        return queryset.order_by('subject__name')

# Notification System
class Notification(models.Model):
    NOTIFICATION_TYPES = [
        ('GRADE', 'Grade Update'),
        ('FEE', 'Fee Payment'),
        ('ASSIGNMENT', 'Assignment'),
        ('GENERAL', 'General'),
    ]
    
    recipient = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    notification_type = models.CharField(max_length=10, choices=NOTIFICATION_TYPES)
    title = models.CharField(max_length=200)
    message = models.TextField()
    related_object_id = models.PositiveIntegerField(null=True, blank=True)
    related_content_type = models.CharField(max_length=50, blank=True)
    is_read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.get_notification_type_display()} - {self.title}"
    
    def get_absolute_url(self):
        """Generate URL based on notification type and related object"""
        if self.related_object_id and self.related_content_type:
            try:
                model_class = apps.get_model('core', self.related_content_type)
                obj = model_class.objects.get(pk=self.related_object_id)
                return obj.get_absolute_url()
            except:
                pass
        return reverse('notification_list')
    
    def mark_as_read(self):
        """Mark notification as read and send update via WebSocket"""
        if not self.is_read:
            self.is_read = True
            self.save()
            self.send_ws_update()
    
    def send_ws_update(self):
        """Send WebSocket update for this notification"""
        from channels.layers import get_channel_layer
        from asgiref.sync import async_to_sync
        
        channel_layer = get_channel_layer()
        async_to_sync(channel_layer.group_send)(
            f'notifications_{self.recipient.id}',
            {
                'type': 'notification_update',
                'action': 'single_read',
                'notification_id': self.id,
                'unread_count': self.recipient.notification_set.filter(is_read=False).count()
            }
        )

class AuditLog(models.Model):
    ACTION_CHOICES = [
        ('CREATE', 'Create'),
        ('UPDATE', 'Update'),
        ('DELETE', 'Delete'),
        ('LOGIN', 'Login'),
        ('LOGOUT', 'Logout'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    action = models.CharField(max_length=10, choices=ACTION_CHOICES)
    model_name = models.CharField(max_length=50)
    object_id = models.CharField(max_length=50)
    details = models.TextField(blank=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-timestamp']
    
    def __str__(self):
        return f"{self.user} {self.action}d {self.model_name} at {self.timestamp}"
    
class Announcement(models.Model):
    TARGET_CHOICES = [
        ('ALL', 'All Users'),
        ('STUDENTS', 'Students'),
        ('TEACHERS', 'Teachers'),
        ('ADMINS', 'Administrators'),
    ]
    
    title = models.CharField(max_length=200)
    content = models.TextField()
    target_roles = models.CharField(max_length=20, choices=TARGET_CHOICES, default='ALL')
    attachment = models.FileField(upload_to='announcements/', blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return self.title

class ReportCard(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    academic_year = models.CharField(max_length=9, validators=[RegexValidator(r'^\d{4}/\d{4}$')])
    term = models.PositiveSmallIntegerField(validators=[MinValueValidator(1), MaxValueValidator(3)])
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_published = models.BooleanField(default=False)
    teacher_remarks = models.TextField(blank=True)
    principal_remarks = models.TextField(blank=True)
    
    class Meta:
        unique_together = ('student', 'academic_year', 'term')
        ordering = ['-academic_year', '-term']
    
    def __str__(self):
        return f"{self.student}'s Report Card - {self.academic_year} Term {self.term}"

#attendance management
class AcademicTerm(models.Model):
    TERM_CHOICES = [
        (1, 'Term 1'),
        (2, 'Term 2'),
        (3, 'Term 3'),
    ]
    
    term = models.PositiveSmallIntegerField(choices=TERM_CHOICES)
    academic_year = models.CharField(max_length=9)  # Format: YYYY/YYYY
    start_date = models.DateField()
    end_date = models.DateField()
    is_active = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('term', 'academic_year')
        ordering = ['-academic_year', 'term']
    
    def __str__(self):
        return f"{self.get_term_display()} {self.academic_year}"
    
    def clean(self):
        if self.start_date > self.end_date:
            raise ValidationError("End date must be after start date")
        
        # Ensure term duration is 4 months (3 months school + 1 month vacation)
        if (self.end_date - self.start_date).days > 120:  # ~4 months
            raise ValidationError("Term duration should be approximately 4 months (3 months school + 1 month vacation)")
        
        # Ensure only one active term per academic year
        if self.is_active:
            AcademicTerm.objects.filter(
                academic_year=self.academic_year,
                is_active=True
            ).exclude(pk=self.pk).update(is_active=False)

class AttendancePeriod(models.Model):
    PERIOD_CHOICES = [
        ('daily', 'Daily'),
        ('weekly', 'Weekly'),
        ('monthly', 'Monthly'),
    ]
    
    period_type = models.CharField(max_length=10, choices=PERIOD_CHOICES)
    term = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE)
    start_date = models.DateField()
    end_date = models.DateField()
    is_locked = models.BooleanField(default=False)
    
    class Meta:
        unique_together = ('period_type', 'term', 'start_date')
        ordering = ['-start_date']
    
    def __str__(self):
        return f"{self.get_period_type_display()} ({self.start_date} to {self.end_date})"
    
    def clean(self):
        if self.start_date > self.end_date:
            raise ValidationError("End date must be after start date")
        
        # Ensure period is within term dates
        if (self.start_date < self.term.start_date or 
            self.end_date > self.term.end_date):
            raise ValidationError("Period must be within term dates")
        
        # Ensure period doesn't overlap with existing periods of same type
        overlapping = AttendancePeriod.objects.filter(
            period_type=self.period_type,
            term=self.term,
            start_date__lte=self.end_date,
            end_date__gte=self.start_date
        ).exclude(pk=self.pk)
        
        if overlapping.exists():
            raise ValidationError("This period overlaps with an existing period")

class StudentAttendance(models.Model):
    STATUS_CHOICES = [
        ('present', 'Present'),
        ('absent', 'Absent'),
        ('late', 'Late'),
        ('excused', 'Excused'),
    ]
    
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='attendances')
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
    notes = models.TextField(blank=True)
    timestamp = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('student', 'date', 'period')
        ordering = ['-date', 'student__last_name']
        verbose_name = 'Student Attendance'
        verbose_name_plural = 'Student Attendances'
    
    def clean(self):
        # Validate date is within term range
        if not (self.term.start_date <= self.date <= self.term.end_date):
            raise ValidationError("Date must be within the term dates")
        
        # Validate date is within period range if period exists
        if self.period and not (self.period.start_date <= self.date <= self.period.end_date):
            raise ValidationError("Date must be within the period dates")
        
        # Check if period is locked
        if self.pk is None and self.period and self.period.is_locked:
            raise ValidationError("Cannot create attendance for a locked period")
        elif self.pk and self.period and self.period.is_locked:
            original = StudentAttendance.objects.get(pk=self.pk)
            if original.period != self.period or original.date != self.date:
                raise ValidationError("Cannot modify attendance for a locked period")

class AttendanceSummary(models.Model):
    student = models.ForeignKey('Student', on_delete=models.CASCADE, related_name='attendance_summaries')
    term = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE)
    period = models.ForeignKey(AttendancePeriod, on_delete=models.CASCADE, null=True, blank=True)
    days_present = models.PositiveIntegerField(default=0)
    days_absent = models.PositiveIntegerField(default=0)
    days_late = models.PositiveIntegerField(default=0)
    days_excused = models.PositiveIntegerField(default=0)
    total_days = models.PositiveIntegerField(default=0)
    attendance_rate = models.DecimalField(max_digits=5, decimal_places=2, default=0.0)
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('student', 'term', 'period')
        verbose_name_plural = 'Attendance Summaries'
    
    def __str__(self):
        period_name = self.period.get_period_type_display() if self.period else 'Term'
        return f"{self.student} - {period_name} - {self.attendance_rate}%"
    
    def save(self, *args, **kwargs):
        self.total_days = self.days_present + self.days_absent + self.days_late + self.days_excused
        if self.total_days > 0:
            present_days = self.days_present + self.days_excused  # Excused counts as present for rate
            self.attendance_rate = (present_days / self.total_days) * 100
        super().save(*args, **kwargs)

#analytics
class AnalyticsCache(models.Model):
    """Cache for pre-computed analytics data"""
    name = models.CharField(max_length=100, unique=True)
    data = models.JSONField()
    last_updated = models.DateTimeField(auto_now=True)
    
    @classmethod
    def get_cached_data(cls, name, default=None):
        try:
            return cls.objects.get(name=name).data
        except cls.DoesNotExist:
            return default or {}

class GradeAnalytics(models.Model):
    """Model to store grade-related analytics"""
    class_level = models.CharField(max_length=20, choices=Student.CLASS_LEVEL_CHOICES)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    average_score = models.FloatField()
    highest_score = models.FloatField()
    lowest_score = models.FloatField()
    date_calculated = models.DateField(auto_now_add=True)
    
    class Meta:
        unique_together = ('class_level', 'subject', 'date_calculated')

class AttendanceAnalytics(models.Model):
    """Model to store attendance analytics"""
    class_level = models.CharField(max_length=20, choices=Student.CLASS_LEVEL_CHOICES)
    date = models.DateField()
    present_count = models.IntegerField()
    absent_count = models.IntegerField()
    late_count = models.IntegerField()
    attendance_rate = models.FloatField()
    
    class Meta:
        unique_together = ('class_level', 'date')

class FinancialAnalytics(models.Model):
    """Model to store financial analytics"""
    date = models.DateField()
    total_fees_payable = models.DecimalField(max_digits=10, decimal_places=2)
    total_fees_paid = models.DecimalField(max_digits=10, decimal_places=2)
    collection_rate = models.FloatField()
    outstanding_balance = models.DecimalField(max_digits=10, decimal_places=2)
    
    class Meta:
        unique_together = ('date',)