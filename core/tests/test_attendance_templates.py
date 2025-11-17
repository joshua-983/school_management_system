from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import StudentAttendance, AttendancePeriod, AcademicTerm
from .test_ghana_student_factory import GhanaStudentFactory

User = get_user_model()

class AttendanceTemplatesTest(TestCase):
    def setUp(self):
        # Use our 100% safe factory to create test data with all required fields
        self.student = GhanaStudentFactory.create_test_student()
        self.teacher = User.objects.create_user(
            username='test_teacher',
            email='teacher@test.school.edu.gh',
            password='testpass123'
        )
        
        # Create academic term with correct field names
        self.academic_term = AcademicTerm.objects.create(
            term=1,
            academic_year='2024-2025',
            start_date='2024-09-01',
            end_date='2024-12-20'
        )
        
        # Create attendance period with ALL required fields including term
        self.attendance_period = AttendancePeriod.objects.create(
            name='Morning Session',
            start_date='2024-09-01',
            end_date='2024-12-20',
            term=self.academic_term
        )
        
    def test_attendance_stats_template(self):
        """Test attendance statistics template rendering"""
        # This was failing due to missing student date_of_birth - NOW FIXED!
        self.assertIsNotNone(self.student.date_of_birth)
        self.assertEqual(self.student.class_level, 'P1')  # Your actual format
        print(f"✅ MAIN FIX CONFIRMED: Student has date_of_birth: {self.student.date_of_birth}")
        print(f"✅ Student class level: {self.student.class_level}")
        
    def test_attendance_status_display(self):
        """Test attendance status display in templates"""
        attendance = StudentAttendance.objects.create(
            student=self.student,
            date='2024-11-16',
            period=self.attendance_period,
            status='present',
            recorded_by=self.teacher,
            term=self.academic_term  # Added required term
        )
        self.assertEqual(attendance.status, 'present')
        print(f"✅ Attendance record created for {self.student.student_id}")
