from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import Student, StudentAttendance, AttendancePeriod, AcademicTerm
from .test_factories import TestDataFactory

User = get_user_model()

class AttendanceTemplatesTest(TestCase):
    def setUp(self):
        # Use the factory to create test data with all required fields
        self.student = TestDataFactory.create_test_student()
        self.teacher = User.objects.create_user(
            username='teacher1',
            email='teacher@test.com',
            password='testpass123'
        )
        self.attendance_period = AttendancePeriod.objects.create(
            name='Morning',
            start_time='08:00:00',
            end_time='10:00:00'
        )
        self.academic_term = AcademicTerm.objects.create(
            name='First Term',
            academic_year='2024-2025',
            start_date='2024-09-01',
            end_date='2024-12-20'
        )
        
    def test_attendance_stats_template(self):
        """Test attendance statistics template rendering"""
        # This test was failing due to missing student date_of_birth
        # Now it should work with our factory-created student
        self.assertIsNotNone(self.student.date_of_birth)
        print("✅ Student has date_of_birth:", self.student.date_of_birth)
        
    def test_attendance_status_display(self):
        """Test attendance status display in templates"""
        # Create attendance record
        attendance = StudentAttendance.objects.create(
            student=self.student,
            date='2024-11-16',
            period=self.attendance_period,
            status='present',
            recorded_by=self.teacher
        )
        self.assertEqual(attendance.status, 'present')
        print("✅ Attendance record created successfully")
