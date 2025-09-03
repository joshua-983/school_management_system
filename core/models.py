from datetime import date, timedelta
from django.contrib.contenttypes.models import ContentType
from django.contrib.contenttypes.fields import GenericForeignKey
from decimal import Decimal
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
from django.utils.safestring import mark_safe
from django.apps import apps  # Add this import at the top

from django.db.models.signals import post_save
from django.dispatch import receiver




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
    
    CLASS_LEVEL_DISPLAY_MAP = dict(CLASS_LEVEL_CHOICES)
    
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
    
    def get_parents(self):
        """Get all parents/guardians for this student"""
        return self.parents.all()
    
    def get_emergency_contacts(self):
        """Get all emergency contacts ordered by priority"""
        return self.parents.filter(is_emergency_contact=True).order_by('emergency_contact_priority')
    
    def get_current_fees(self, academic_year=None, term=None):
        """Get current fees for the student"""
        if not academic_year:
            academic_year = f"{timezone.now().year}/{timezone.now().year + 1}"
        fees = self.fees.filter(academic_year=academic_year)
        if term:
            fees = fees.filter(term=term)
        return fees
    
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
    
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='parentguardian', null=True, blank=True)
    student = models.ForeignKey(Student, on_delete=models.CASCADE, related_name='parents')  # Only keep this one
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
        # Prevent duplicate emergency contact priorities for same student
        unique_together = ['student', 'emergency_contact_priority']
        
        
    def __str__(self):
        return f"{self.full_name} ({self.get_relationship_display()}) - {self.student.get_full_name()}"
    
    def clean(self):
        """Validate that email is unique per student"""
        if self.email:
            existing = ParentGuardian.objects.filter(
                student=self.student, 
                email=self.email
            ).exclude(pk=self.pk)
            if existing.exists():
                raise ValidationError({'email': 'This email is already registered for this student'})

@receiver(post_save, sender=ParentGuardian)
def create_parent_user(sender, instance, created, **kwargs):
    """Automatically create a user account for parents with email"""
    if created and instance.email and not instance.user:
        try:
            # Check if user already exists with this email
            user = User.objects.filter(email=instance.email).first()
            if not user:
                # Create new user - handle potential username conflicts
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
                    first_name=instance.full_name.split()[0],
                    last_name=' '.join(instance.full_name.split()[1:]) if len(instance.full_name.split()) > 1 else ""
                )
            instance.user = user
            instance.save(update_fields=['user'])  # Only update user field to avoid recursion
        except Exception as e:
            # Use logging instead of print for production
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error creating user for parent {instance.email}: {e}")


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
    is_active = models.BooleanField(default=True)  # Added this field
    applies_to_all = models.BooleanField(default=True)
    class_levels = models.CharField(
        max_length=100, 
        blank=True,
        help_text="Comma-separated list of class levels this applies to (leave blank for all)"
    )
    
    def __str__(self):
        return self.get_name_display()
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
    
    TERM_CHOICES = [
        (1, 'Term 1'),
        (2, 'Term 2'),
        (3, 'Term 3'),
    ]

    student = models.ForeignKey(
        Student,
        on_delete=models.PROTECT,
        related_name='fees'
    )
    category = models.ForeignKey(
        FeeCategory,
        on_delete=models.PROTECT,
        related_name='fees'
    )
    academic_year = models.CharField(max_length=9)
    term = models.PositiveSmallIntegerField(choices=TERM_CHOICES)
    
    amount_payable = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    amount_paid = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    balance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))]
    )
    
    payment_status = models.CharField(
        max_length=10,
        choices=PAYMENT_STATUS_CHOICES,
        default='unpaid'
    )
    payment_mode = models.CharField(
        max_length=15,
        choices=PAYMENT_MODE_CHOICES,
        blank=True,
        null=True
    )
    payment_date = models.DateField(blank=True, null=True)
    due_date = models.DateField()
    
    receipt_number = models.CharField(max_length=20, blank=True)
    notes = models.TextField(blank=True)
    
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name='recorded_fees'
    )
    date_recorded = models.DateTimeField(auto_now_add=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_recorded']
        verbose_name_plural = 'Fees'
        indexes = [
            models.Index(fields=['student']),
            models.Index(fields=['payment_status']),
            models.Index(fields=['due_date']),
        ]

    def __str__(self):
        return f"{self.student} - {self.category} ({self.academic_year} Term {self.term})"

    def update_payment_status(self):
        """Enhanced payment status calculation with tolerance and grace period"""
        tolerance = Decimal('1.00')  # Consider $1 difference as paid
        grace_period = 5  # Days after due date before marking overdue
        
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

    def save(self, *args, **kwargs):
        # Calculate balance before saving
        self.balance = self.amount_payable - self.amount_paid
        
        # Auto-update payment status
        self.update_payment_status()
            
        # Set payment date if status is paid and no date exists
        if self.payment_status == 'paid' and not self.payment_date:
            self.payment_date = timezone.now().date()
            
        super().save(*args, **kwargs)

    def clean(self):
        """Add model-level validation"""
        super().clean()
        
        if self.amount_paid > self.amount_payable:
            raise ValidationError({
                'amount_paid': 'Amount paid cannot exceed amount payable'
            })
        
        if self.payment_status == 'paid' and self.amount_paid < self.amount_payable:
            raise ValidationError({
                'payment_status': 'Cannot mark as paid when amount paid is less than payable'
            })

    def get_payment_status_html(self):
        """Improved HTML display for payment status"""
        status_display = self.get_payment_status_display()
        color_map = {
            'paid': 'success',
            'unpaid': 'danger',
            'partial': 'warning',
            'overdue': 'dark'
        }
        color = color_map.get(self.payment_status, 'primary')
        return mark_safe(
            f'<span class="badge bg-{color}">{status_display}</span>'
        )
class FeeInstallment(models.Model):
    fee = models.ForeignKey(Fee, on_delete=models.CASCADE, related_name='installments')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    due_date = models.DateField()
    is_paid = models.BooleanField(default=False)
    payment_date = models.DateField(null=True, blank=True)
    
    class Meta:
        ordering = ['due_date']
        
    def __str__(self):
        return f"Installment of {self.amount} due {self.due_date}"


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
    
    def apply_discount(self, fee_amount):
        if self.discount_type == 'PERCENT':
            return fee_amount * (self.amount / 100)
        return min(fee_amount, self.amount)





    def get_payment_status_html(self):
        """Improved HTML display for payment status"""
        status_display = self.get_payment_status_display()
        color_map = {
            'paid': 'success',
            'unpaid': 'danger',
            'partial': 'warning',
            'overdue': 'dark'
        }
        color = color_map.get(self.payment_status, 'primary')
        return mark_safe(
            f'<span class="badge bg-{color}">{status_display}</span>'
        )

    def clean(self):
        """Add model-level validation"""
        super().clean()
        
        if self.amount_paid > self.amount_payable:
            raise ValidationError({
                'amount_paid': 'Amount paid cannot exceed amount payable'
            })
        
        if self.payment_status == 'paid' and self.amount_paid < self.amount_payable:
            raise ValidationError({
                'payment_status': 'Cannot mark as paid when amount paid is less than payable'
            })
class FeePayment(models.Model):
    """Detailed record of individual payments"""
    PAYMENT_MODE_CHOICES = [
        ('cash', 'Cash'),
        ('check', 'Check'),
        ('bank_transfer', 'Bank Transfer'),
        ('mobile_money', 'Mobile Money'),
        ('other', 'Other'),
    ]
    
    fee = models.ForeignKey(
        'Fee', 
        on_delete=models.CASCADE, 
        related_name='payments'
    )
    amount = models.DecimalField(
        max_digits=10, 
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))]
    )
    payment_date = models.DateTimeField(default=timezone.now)
    payment_mode = models.CharField(
        max_length=15,  # Increased from 10 to 15 to accommodate 'bank_transfer'
        choices=PAYMENT_MODE_CHOICES
    )
    receipt_number = models.CharField(
        max_length=20, 
        unique=True, 
        blank=True
    )
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
        verbose_name = 'Fee Payment'
        verbose_name_plural = 'Fee Payments'
    
    def __str__(self):
        return f"Payment of {self.amount} for {self.fee}"
    
    def save(self, *args, **kwargs):
        if not self.receipt_number:
            self.receipt_number = self.generate_receipt_number()
        super().save(*args, **kwargs)
    
    @classmethod
    def generate_receipt_number(cls):
        """Generate a unique receipt number"""
        from django.utils.crypto import get_random_string
        while True:
            receipt_number = f"RCPT-{get_random_string(10, '0123456789')}"
            if not cls.objects.filter(receipt_number=receipt_number).exists():
                return receipt_number

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
    # GES Standardized Grading Scale (1-9) with detailed descriptors
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

    # Core fields
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
    subject = models.ForeignKey('Subject', on_delete=models.CASCADE)
    class_assignment = models.ForeignKey('ClassAssignment', on_delete=models.CASCADE)
    academic_year = models.CharField(max_length=9, validators=[RegexValidator(r'^\d{4}/\d{4}$')])
    term = models.PositiveSmallIntegerField(choices=[(1, 'Term 1'), (2, 'Term 2'), (3, 'Term 3')])

    # Assessment components
    classwork_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(30)],
        verbose_name="Classwork (30%)"
    )
    homework_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        verbose_name="Homework (10%)"
    )
    test_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(10)],
        verbose_name="Test (10%)"
    )
    exam_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        validators=[MinValueValidator(0), MaxValueValidator(50)],
        verbose_name="Exam (50%)"
    )

    # Calculated fields
    total_score = models.DecimalField(
        max_digits=5, decimal_places=2,
        editable=False, null=True, blank=True
    )
    ges_grade = models.CharField(
        max_length=3, choices=GES_GRADE_CHOICES,
        editable=False, default='N/A'
    )
    remarks = models.TextField(blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ('student', 'subject', 'academic_year', 'term')
        ordering = ['academic_year', 'term', 'student__last_name']

    def save(self, *args, **kwargs):
        self.calculate_total_score()
        self.determine_ges_grade()
        super().save(*args, **kwargs)

    def calculate_total_score(self):
        """Calculate total based on component scores"""
        try:
            self.total_score = (
                self.classwork_score + 
                self.homework_score + 
                self.test_score + 
                self.exam_score
            )
        except (TypeError, AttributeError):
            self.total_score = None

    def determine_ges_grade(self):
        """Convert total score to GES standardized grade (1-9)"""
        if self.total_score is None:
            self.ges_grade = 'N/A'
            return

        score = float(self.total_score)
        
        if score >= 90: self.ges_grade = '1'
        elif score >= 80: self.ges_grade = '2'
        elif score >= 70: self.ges_grade = '3'
        elif score >= 60: self.ges_grade = '4'
        elif score >= 50: self.ges_grade = '5'
        elif score >= 40: self.ges_grade = '6'
        elif score >= 30: self.ges_grade = '7'
        elif score >= 20: self.ges_grade = '8'
        else: self.ges_grade = '9'

    def __str__(self):
        return f"{self.student} - {self.subject} ({self.academic_year} Term {self.term}): {self.ges_grade}"

    @classmethod
    def get_best_students(cls):
        """
        Returns a dictionary with:
        - Best student for each class
        - Overall best student
        """
        from django.db.models import Avg, Max
        
        # Get all classes (P1-P6, J1-J3)
        classes = ['P1', 'P2', 'P3', 'P4', 'P5', 'P6', 'J1', 'J2', 'J3']
        results = {}
        current_year = f"{timezone.now().year}/{timezone.now().year + 1}"
        
        # Find best student per class
        for class_level in classes:
            # Get the highest average score for this class
            best_avg = cls.objects.filter(
                student__class_level=class_level,
                academic_year=current_year
            ).values('student').annotate(
                avg_score=Avg('total_score')
            ).order_by('-avg_score').first()
            
            if best_avg:
                best_student = Student.objects.get(id=best_avg['student'])
                results[class_level] = {
                    'student': best_student,
                    'average': best_avg['avg_score']
                }
        
        # Find overall best student (highest single score across all classes)
        overall_best = cls.objects.filter(
            academic_year=current_year
        ).order_by('-total_score').first()
        
        if overall_best:
            results['overall'] = {
                'student': overall_best.student,
                'average': float(overall_best.total_score),
                'class_level': overall_best.student.class_level
            }
        
        return results

#school configuration
class SchoolConfiguration(models.Model):
    GRADING_SYSTEM_CHOICES = [
        ('GES', 'Ghana Education System (Primary/JHS)'),
        ('WASSCE', 'West African Senior School Certificate Exam'),
    ]
    
    grading_system = models.CharField(
        max_length=10,
        choices=GRADING_SYSTEM_CHOICES,
        default='GES'
    )
    is_locked = models.BooleanField(
        default=False,
        help_text="Lock the grading system to prevent changes"
    )
    last_updated = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "School Configuration"
        verbose_name_plural = "School Configuration"
    
    def save(self, *args, **kwargs):
        # Ensure only one configuration exists
        if SchoolConfiguration.objects.exists() and not self.pk:
            raise ValidationError("Only one school configuration can exist")
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"Active Grading System: {self.get_grading_system_display()} {'(Locked)' if self.is_locked else ''}"


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
        ('ACCESS', 'Access'),
        ('OTHER', 'Other'),
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.SET_NULL, 
        null=True,
        blank=True,
        related_name='audit_logs'
    )
    action = models.CharField(
        max_length=10, 
        choices=ACTION_CHOICES,
        db_index=True
    )
    model_name = models.CharField(
        max_length=50,
        db_index=True
    )
    object_id = models.CharField(
        max_length=50,
        db_index=True,
        blank=True,
        null=True
    )
    details = models.JSONField(
        blank=True,
        null=True,
        default=dict
    )
    ip_address = models.GenericIPAddressField(
        null=True, 
        blank=True,
        db_index=True
    )
    timestamp = models.DateTimeField(
        auto_now_add=True,
        db_index=True
    )
    
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
        """
        Helper method to create audit log entries
        """
        return cls.objects.create(
            user=user,
            action=action,
            model_name=model_name or '',
            object_id=str(object_id) if object_id else None,
            details=details or {},
            ip_address=ip_address
        )
    
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
    
    student = models.ForeignKey('Student', on_delete=models.CASCADE)
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
    
    def __str__(self):
        return f"{self.student}'s Report Card - {self.academic_year} Term {self.term}"
    
    def save(self, *args, **kwargs):
        # Calculate average score and overall grade if not set
        if not self.average_score or not self.overall_grade:
            self.calculate_grades()
        super().save(*args, **kwargs)
    
    def calculate_grades(self):
        # Get all grades for this student, academic year, and term
        grades = Grade.objects.filter(
            student=self.student,
            academic_year=self.academic_year,
            term=self.term
        )
        
        if grades.exists():
            # Calculate average score
            total_score = sum(grade.total_score for grade in grades)
            self.average_score = total_score / grades.count()
            
            # Calculate overall grade
            self.overall_grade = self.calculate_grade(self.average_score)
        else:
            self.average_score = 0.00
            self.overall_grade = ''
    
    @staticmethod
    def calculate_grade(score):
        if score >= 90: return 'A+'
        elif score >= 80: return 'A'
        elif score >= 70: return 'B+'
        elif score >= 60: return 'B'
        elif score >= 50: return 'C+'
        elif score >= 40: return 'C'
        elif score >= 30: return 'D+'
        elif score >= 20: return 'D'
        else: return 'E'
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

#timetable
# Add to core/models.py

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
    
    class Meta:
        ordering = ['period_number']
    
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
    
    class_level = models.CharField(max_length=2, choices=Student.CLASS_LEVEL_CHOICES)
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
    
    def __str__(self):
        return f"{self.get_class_level_display()} - {self.get_day_of_week_display()} - {self.academic_year} Term {self.term}"

class TimetableEntry(models.Model):
    timetable = models.ForeignKey(Timetable, on_delete=models.CASCADE, related_name='entries')
    time_slot = models.ForeignKey(TimeSlot, on_delete=models.CASCADE)
    subject = models.ForeignKey(Subject, on_delete=models.CASCADE)
    teacher = models.ForeignKey(Teacher, on_delete=models.CASCADE)
    classroom = models.CharField(max_length=100, blank=True)
    is_break = models.BooleanField(default=False)
    
    class Meta:
        ordering = ['time_slot__period_number']
        unique_together = ('timetable', 'time_slot')
    
    def __str__(self):
        if self.is_break:
            return f"{self.time_slot.break_name} - Break"
        return f"{self.time_slot} - {self.subject.name} - {self.teacher.get_full_name()}"


























def get_unread_count(user):
    """
    Get count of unread notifications for a user
    """
    return Notification.objects.filter(recipient=user, is_read=False).count()

