import datetime
from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import Student, AcademicTerm, AttendancePeriod, StudentAttendance

class AttendanceModelsTest(TestCase):
    def setUp(self):
        # Create user first
        User = get_user_model()
        self.user = User.objects.create_user(
            username='teststudent',
            password='testpass123',
            first_name='John',
            last_name='Doe'
        )
        
        # Create student with ALL required fields
        self.student = Student.objects.create(
            user=self.user,
            first_name="John",
            last_name="Doe",
            date_of_birth=datetime.date(2010, 1, 1),
            gender='M',
            nationality='Ghanaian',
            place_of_birth="Accra", 
            residential_address="123 Test Street, Accra",
            class_level='P1',
            admission_date=datetime.date.today(),
        )
        
        # Create academic term
        self.academic_term = AcademicTerm.objects.create(
            term=1,
            academic_year="2024/2025",
            start_date=datetime.date(2024, 9, 1),
            end_date=datetime.date(2024, 12, 31),
            is_active=True
        )
        
        # Create attendance period
        self.attendance_period = AttendancePeriod.objects.create(
            period_type='daily',
            name="Morning Session",
            term=self.academic_term,
            start_date=datetime.date(2024, 9, 1),
            end_date=datetime.date(2024, 12, 31)
        )

    def test_academic_term_creation(self):
        """Test AcademicTerm model creation and string representation"""
        self.assertEqual(str(self.academic_term), "Term 1 2024/2025")
        self.assertTrue(self.academic_term.is_active)
        
    def test_attendance_period_creation(self):
        """Test AttendancePeriod model creation"""
        self.assertEqual(str(self.attendance_period), "Morning Session (2024-09-01 to 2024-12-31)")
        self.assertEqual(self.attendance_period.term, self.academic_term)
        
    def test_student_attendance_creation(self):
        """Test StudentAttendance model creation"""
        attendance = StudentAttendance.objects.create(
            student=self.student,
            date=datetime.date(2024, 9, 2),
            status='present',
            period=self.attendance_period,
            term=self.academic_term,
            recorded_by=self.user
        )
        
        self.assertEqual(str(attendance), f"{self.student} - 2024-09-02 - Present")
        self.assertEqual(attendance.status, 'present')
        
    def test_attendance_status_choices(self):
        """Test StudentAttendance status choices"""
        attendance = StudentAttendance.objects.create(
            student=self.student,
            date=datetime.date(2024, 9, 3),
            status='late',
            period=self.attendance_period,
            term=self.academic_term,
            recorded_by=self.user
        )
        
        self.assertTrue(attendance.is_present)  # late should be considered present
        self.assertEqual(attendance.get_status_display(), 'Late')
        
    def test_attendance_unique_constraint(self):
        """Test that duplicate attendance records are prevented"""
        StudentAttendance.objects.create(
            student=self.student,
            date=datetime.date(2024, 9, 4),
            status='present',
            period=self.attendance_period,
            term=self.academic_term,
            recorded_by=self.user
        )
        
        # Try to create duplicate - should raise IntegrityError
        with self.assertRaises(Exception):  # Could be IntegrityError or ValidationError
            StudentAttendance.objects.create(
                student=self.student,
                date=datetime.date(2024, 9, 4),
                status='absent',
                period=self.attendance_period,
                term=self.academic_term,
                recorded_by=self.user
            )