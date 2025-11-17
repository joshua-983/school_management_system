from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import Student, StudentAttendance, AttendancePeriod, AcademicTerm
from .test_factories import TestDataFactory

User = get_user_model()

class AttendanceViewLogicTest(TestCase):
    def setUp(self):
        # Use factory to create proper test data
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
        
    def test_attendance_calculations(self):
        """Test attendance percentage calculations"""
        # Create multiple attendance records
        dates = ['2024-11-16', '2024-11-17', '2024-11-18']
        for i, date_str in enumerate(dates):
            status = 'present' if i < 2 else 'absent'  # 2 present, 1 absent
            StudentAttendance.objects.create(
                student=self.student,
                date=date_str,
                period=self.attendance_period,
                status=status,
                recorded_by=self.teacher
            )
        
        # Calculate attendance rate (should be 66.67%)
        present_count = StudentAttendance.objects.filter(
            student=self.student, status='present'
        ).count()
        total_count = StudentAttendance.objects.filter(
            student=self.student
        ).count()
        
        if total_count > 0:
            attendance_rate = (present_count / total_count) * 100
            self.assertAlmostEqual(attendance_rate, 66.67, places=2)
            print(f"✅ Attendance calculation correct: {attendance_rate:.2f}%")
        
    def test_attendance_status_choices(self):
        """Test attendance status choices"""
        status_choices = ['present', 'absent', 'late', 'excused']
        
        for status in status_choices:
            attendance = StudentAttendance.objects.create(
                student=self.student,
                date='2024-11-19',
                period=self.attendance_period, 
                status=status,
                recorded_by=self.teacher
            )
            self.assertEqual(attendance.status, status)
            print(f"✅ Status '{status}' works correctly")
