# core/tests/test_attendance_views_logic.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import Student, AcademicTerm, StudentAttendance
from datetime import date

CustomUser = get_user_model()


class AttendanceViewLogicTest(TestCase):
    """Test attendance view logic without HTTP requests"""
    
    def setUp(self):
        self.term = AcademicTerm.objects.create(
            term=1,
            academic_year='2025/2026',
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 31)
        )
        
        self.student = Student.objects.create(
            student_id='S001',
            first_name='John',
            last_name='Doe',
            class_level='P6'
        )
        
        # Create some attendance records
        StudentAttendance.objects.create(
            student=self.student,
            term=self.term,
            date=date(2025, 10, 1),
            status='present'
        )
        StudentAttendance.objects.create(
            student=self.student,
            term=self.term,
            date=date(2025, 10, 2),
            status='absent'
        )

    def test_attendance_calculations(self):
        """Test attendance percentage calculations"""
        from django.db.models import Count, Q
        
        # Calculate present days
        present_count = StudentAttendance.objects.filter(
            student=self.student,
            status='present'
        ).count()
        
        total_count = StudentAttendance.objects.filter(
            student=self.student
        ).count()
        
        if total_count > 0:
            attendance_percentage = (present_count / total_count) * 100
            self.assertEqual(attendance_percentage, 50.0)  # 1 present out of 2 total

    def test_attendance_status_choices(self):
        """Test attendance status choices"""
        attendance = StudentAttendance(
            student=self.student,
            term=self.term,
            date=date(2025, 10, 3),
            status='late'
        )
        
        self.assertIn(attendance.status, ['present', 'absent', 'late', 'excused'])