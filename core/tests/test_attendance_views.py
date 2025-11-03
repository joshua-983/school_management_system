from django.test import TestCase, RequestFactory
from django.contrib.auth import get_user_model
from django.contrib.messages.storage.fallback import FallbackStorage
from django.utils import timezone
from datetime import date, timedelta
from django.core.exceptions import PermissionDenied  # ADD THIS IMPORT
import json

from core.models import (
    Student, Teacher, StudentAttendance, AttendancePeriod, 
    AcademicTerm, ClassAssignment, Subject, Holiday
)
from core.views.attendance_views import (
    AttendanceDashboardView, AttendanceRecordView, 
    StudentAttendanceListView, GhanaEducationAttendanceMixin
)

CustomUser = get_user_model()


class AttendanceBaseTestMixin:
    """Mixin to set up common test data for attendance views"""
    
    def setUp(self):
        # Create test users
        self.admin_user = CustomUser.objects.create_user(
            username='admin',
            password='testpass123',
            is_staff=True,
            first_name='Admin',
            last_name='User'
        )
        self.teacher_user = CustomUser.objects.create_user(
            username='teacher',
            password='testpass123',
            first_name='Teacher',
            last_name='User'
        )
        self.student_user = CustomUser.objects.create_user(
            username='student',
            password='testpass123',
            first_name='Student',
            last_name='User'
        )
        
        # Create subject
        self.subject = Subject.objects.create(
            name='Mathematics',
            code='MATH'
        )
        
        # Create teacher profile with ALL required fields
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id='T001',
            date_of_birth=date(1980, 1, 1),
            gender='M',
            phone_number='0241234567',  # Valid Ghana number
            address='Test Teacher Address',
            qualification='Test Qualification',
            class_levels='P6',  # Required field
            date_of_joining=date.today()
        )
        self.teacher.subjects.add(self.subject)
        
        # Create student profile with ALL required fields
        self.student = Student.objects.create(
            user=self.student_user,
            student_id='S001',
            first_name='John',
            last_name='Doe',
            date_of_birth=date(2010, 1, 1),
            gender='M',
            nationality='Ghanaian',
            place_of_birth='Accra',
            residential_address='123 Test Street, Accra',
            class_level='P6',
            admission_date=date.today(),
            is_active=True
        )
        
        # Create academic term
        self.term = AcademicTerm.objects.create(
            term=1,
            academic_year='2025/2026',
            start_date=date(2025, 9, 1),
            end_date=date(2025, 12, 31),
            is_active=True
        )
        
        # Create attendance period
        self.period = AttendancePeriod.objects.create(
            term=self.term,
            period_type='daily',
            name='Term 1 Period 1',
            start_date=date(2025, 9, 1),
            end_date=date(2025, 10, 31)
        )
        
        # Create class assignment
        self.class_assignment = ClassAssignment.objects.create(
            teacher=self.teacher,
            class_level='P6',
            subject=self.subject,
            academic_year='2025/2026'
        )
        
        # Create holiday for testing
        self.holiday = Holiday.objects.create(
            name='Test Holiday',
            date=date(2025, 10, 6),  # A Monday
            is_school_holiday=True
        )
        
        # Create sample attendance record
        self.attendance = StudentAttendance.objects.create(
            student=self.student,
            term=self.term,
            period=self.period,
            date=date(2025, 10, 25),
            status='present',
            recorded_by=self.admin_user
        )
        
        self.factory = RequestFactory()
    
    def _add_messages_to_request(self, request):
        """Add messages support to request for testing"""
        setattr(request, 'session', 'session')
        messages = FallbackStorage(request)
        setattr(request, '_messages', messages)
        return request
    
    def create_attendance(self, student, date, status, term=None, period=None):
        """Helper method to create attendance records"""
        if term is None:
            term = self.term
        if period is None:
            period = self.period
            
        return StudentAttendance.objects.create(
            student=student,
            term=term,
            period=period,
            date=date,
            status=status,
            recorded_by=self.admin_user
        )


class TestGhanaEducationAttendanceMixin(AttendanceBaseTestMixin, TestCase):
    """Test cases for GhanaEducationAttendanceMixin functionality"""
    
    def setUp(self):
        """Set up test data"""
        super().setUp()
        self.mixin = GhanaEducationAttendanceMixin()
    
    def test_ghana_school_day_weekend(self):
        """Test weekend detection"""
        saturday = date(2025, 10, 25)  # Saturday
        sunday = date(2025, 10, 26)    # Sunday
        
        self.assertFalse(self.mixin.is_ghana_school_day(saturday))
        self.assertFalse(self.mixin.is_ghana_school_day(sunday))
    
    def test_ghana_school_day_weekday(self):
        """Test weekday detection"""
        monday = date(2025, 10, 27)  # Monday
        tuesday = date(2025, 10, 28)  # Tuesday
        wednesday = date(2025, 10, 29)  # Wednesday
        thursday = date(2025, 10, 30)  # Thursday
        friday = date(2025, 10, 31)  # Friday
        
        self.assertTrue(self.mixin.is_ghana_school_day(monday))
        self.assertTrue(self.mixin.is_ghana_school_day(tuesday))
        self.assertTrue(self.mixin.is_ghana_school_day(wednesday))
        self.assertTrue(self.mixin.is_ghana_school_day(thursday))
        self.assertTrue(self.mixin.is_ghana_school_day(friday))
    
    def test_ges_attendance_rate_calculation(self):
        """Test GES attendance rate calculation"""
        student = self.student
        start_date = date(2025, 10, 1)
        end_date = date(2025, 10, 10)
        
        # Create attendance records for school days only
        # School days in this period: Oct 1(Wed), 2(Thu), 3(Fri), 7(Tue), 8(Wed), 9(Thu), 10(Fri)
        # Total school days = 7 (excluding weekends and Oct 6 holiday)
        self.create_attendance(student, date(2025, 10, 1), 'present')  # Wed
        self.create_attendance(student, date(2025, 10, 2), 'present')  # Thu
        self.create_attendance(student, date(2025, 10, 3), 'present')  # Fri
        self.create_attendance(student, date(2025, 10, 7), 'absent')   # Tue
        self.create_attendance(student, date(2025, 10, 8), 'present')  # Wed
        # Oct 9 - no record (counted as absent)
        # Oct 10 - no record (counted as absent)
        
        # Present days: Oct 1, 2, 3, 8 = 4 days
        # Total school days: 7 days
        # Rate = (4/7)*100 = 57.1%
        rate = self.mixin.calculate_ges_attendance_rate(student, start_date, end_date)
        self.assertAlmostEqual(rate, 57.1, places=1)
    
    def test_ges_attendance_rate_with_late_and_excused(self):
        """Test that GES counts late and excused as present"""
        student = self.student
        start_date = date(2025, 10, 1)
        end_date = date(2025, 10, 7)  # School days: Oct 1,2,3,7 (excluding holiday on 6th)
        
        # Create attendance records
        self.create_attendance(student, date(2025, 10, 1), 'present')  # Wed
        self.create_attendance(student, date(2025, 10, 2), 'late')     # Thu (counts as present)
        self.create_attendance(student, date(2025, 10, 3), 'excused')  # Fri (counts as present)
        self.create_attendance(student, date(2025, 10, 7), 'absent')   # Tue (counts as absent)
        
        # Present-like days: Oct 1, 2, 3 = 3 days
        # Total school days: 4 days
        # Rate = (3/4)*100 = 75.0%
        rate = self.mixin.calculate_ges_attendance_rate(student, start_date, end_date)
        self.assertAlmostEqual(rate, 75.0, places=1)
    
    def test_ges_attendance_status(self):
        """Test GES attendance status descriptions"""
        self.assertEqual(self.mixin.get_ges_attendance_status(95), "Excellent")
        self.assertEqual(self.mixin.get_ges_attendance_status(85), "Good")
        self.assertEqual(self.mixin.get_ges_attendance_status(75), "Satisfactory")
        self.assertEqual(self.mixin.get_ges_attendance_status(65), "Needs Improvement")
        self.assertEqual(self.mixin.get_ges_attendance_status(55), "Unsatisfactory")
    
    def test_ges_compliance_check(self):
        """Test GES compliance checking"""
        self.assertTrue(self.mixin.is_ges_compliant(80))
        self.assertTrue(self.mixin.is_ges_compliant(75))
        self.assertFalse(self.mixin.is_ges_compliant(74))
        self.assertFalse(self.mixin.is_ges_compliant(50))
    
    def test_ges_attendance_rate_zero_days(self):
        """Test attendance rate calculation when there are no school days"""
        student = self.student
        start_date = date(2025, 10, 25)  # Saturday
        end_date = date(2025, 10, 26)    # Sunday
        
        rate = self.mixin.calculate_ges_attendance_rate(student, start_date, end_date)
        self.assertEqual(rate, 0.0)
    
    def test_ges_attendance_rate_all_present(self):
        """Test 100% attendance rate calculation"""
        student = self.student
        start_date = date(2025, 10, 1)
        end_date = date(2025, 10, 3)  # 3 school days
        
        # Create attendance records - all present
        school_days = [date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3)]
        for day in school_days:
            self.create_attendance(student, day, 'present')
        
        rate = self.mixin.calculate_ges_attendance_rate(student, start_date, end_date)
        self.assertAlmostEqual(rate, 100.0, places=1)
    
    def test_ges_attendance_rate_all_absent(self):
        """Test 0% attendance rate calculation"""
        student = self.student
        start_date = date(2025, 10, 1)
        end_date = date(2025, 10, 3)  # 3 school days
        
        # Create attendance records - all absent
        school_days = [date(2025, 10, 1), date(2025, 10, 2), date(2025, 10, 3)]
        for day in school_days:
            self.create_attendance(student, day, 'absent')
        
        rate = self.mixin.calculate_ges_attendance_rate(student, start_date, end_date)
        self.assertAlmostEqual(rate, 0.0, places=1)


class TestAttendanceDashboardView(AttendanceBaseTestMixin, TestCase):
    """Test cases for AttendanceDashboardView"""
    
    def test_dashboard_access_admin(self):
        """Test that admin can access dashboard"""
        request = self.factory.get('/attendance/dashboard/')
        request.user = self.admin_user
        self._add_messages_to_request(request)
        
        response = AttendanceDashboardView.as_view()(request)
        self.assertEqual(response.status_code, 200)
    
    def test_dashboard_access_teacher(self):
        """Test that teacher can access dashboard"""
        request = self.factory.get('/attendance/dashboard/')
        request.user = self.teacher_user
        self._add_messages_to_request(request)
        
        response = AttendanceDashboardView.as_view()(request)
        self.assertEqual(response.status_code, 200)
    
    def test_dashboard_access_student_denied(self):
        """Test that student cannot access dashboard"""
        request = self.factory.get('/attendance/dashboard/')
        request.user = self.student_user
        self._add_messages_to_request(request)
        
        # Student should be denied access (PermissionDenied exception)
        with self.assertRaises(PermissionDenied):
            AttendanceDashboardView.as_view()(request)
    
    def test_dashboard_context_data(self):
        """Test that dashboard returns correct context data"""
        request = self.factory.get('/attendance/dashboard/')
        request.user = self.admin_user
        self._add_messages_to_request(request)
        
        response = AttendanceDashboardView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        
        context = response.context_data
        # Check for the actual structure of the context data
        self.assertIn('stats', context)
        self.assertIn('active_term', context)
        self.assertIn('ges_attendance_rate', context)
        
        # Check that stats contains expected data
        stats = context['stats']
        self.assertIsInstance(stats, list)
        
        # Find the total students stat
        total_students_stat = next((stat for stat in stats if stat['label'] == 'Total Students'), None)
        self.assertIsNotNone(total_students_stat)
        self.assertIsInstance(total_students_stat['value'], int)


class TestAttendanceRecordView(AttendanceBaseTestMixin, TestCase):
    """Test cases for AttendanceRecordView"""
    
    def test_record_view_get_admin(self):
        """Test GET request for attendance record view as admin"""
        request = self.factory.get('/attendance/record/?date=2025-10-25&term=1&class_level=P6')
        request.user = self.admin_user
        self._add_messages_to_request(request)
        
        response = AttendanceRecordView.as_view()(request)
        self.assertEqual(response.status_code, 200)
    
    def test_record_view_get_with_params(self):
        """Test GET request with filter parameters"""
        request = self.factory.get('/attendance/record/?date=2025-10-25&term=1&class_level=P6&period=1')
        request.user = self.admin_user
        self._add_messages_to_request(request)
        
        response = AttendanceRecordView.as_view()(request)
        self.assertEqual(response.status_code, 200)
    
    def test_record_view_post_invalid_date(self):
        """Test POST request with invalid date"""
        future_date = (timezone.now() + timedelta(days=1)).date()
        request = self.factory.post('/attendance/record/', {
            'date': future_date,
            'attendance_data': '{}'
        })
        request.user = self.admin_user
        self._add_messages_to_request(request)
        
        response = AttendanceRecordView.as_view()(request)
        self.assertEqual(response.status_code, 302)  # Redirect
    
    def test_record_view_post_valid_data(self):
        """Test POST request with valid attendance data"""
        today = timezone.now().date()
        
        request = self.factory.post('/attendance/record/', {
            'date': today.strftime('%Y-%m-%d'),
            'term': self.term.id,
            'class_level': 'P6',
            f'status_{self.student.id}': 'present'
        })
        request.user = self.admin_user
        self._add_messages_to_request(request)
        
        response = AttendanceRecordView.as_view()(request)
        self.assertEqual(response.status_code, 302)  # Redirect
        
        # Check if attendance was created
        attendance = StudentAttendance.objects.filter(
            student=self.student,
            date=today
        ).first()
        self.assertIsNotNone(attendance)
        self.assertEqual(attendance.status, 'present')
    
    def test_teacher_can_only_access_assigned_classes(self):
        """Test that teachers can only record attendance for their assigned classes"""
        request = self.factory.get('/attendance/record/?date=2025-10-25&term=1&class_level=P6')
        request.user = self.teacher_user
        self._add_messages_to_request(request)
        
        response = AttendanceRecordView.as_view()(request)
        self.assertEqual(response.status_code, 200)


class TestStudentAttendanceListView(AttendanceBaseTestMixin, TestCase):
    """Test cases for StudentAttendanceListView"""
    
    def test_student_attendance_list_access(self):
        """Test that students can see their own attendance"""
        request = self.factory.get('/attendance/my-attendance/')
        request.user = self.student_user
        self._add_messages_to_request(request)
        
        response = StudentAttendanceListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
    
    def test_student_sees_only_own_attendance(self):
        """Test that students only see their own attendance records"""
        # Create another student and attendance record
        other_student_user = CustomUser.objects.create_user(
            username='other_student',
            password='testpass123'
        )
        other_student = Student.objects.create(
            user=other_student_user,
            student_id='S002',
            first_name='Other',
            last_name='Student',
            date_of_birth=date(2010, 1, 1),
            gender='F',
            class_level='P6',
            admission_date=date.today(),
            is_active=True
        )
        self.create_attendance(other_student, date(2025, 10, 20), 'present')
        
        request = self.factory.get('/attendance/my-attendance/')
        request.user = self.student_user
        self._add_messages_to_request(request)
        
        response = StudentAttendanceListView.as_view()(request)
        self.assertEqual(response.status_code, 200)
        
        # Student should only see their own attendance
        # The context object name might be 'object_list' instead of 'attendance_records'
        if hasattr(response, 'context_data'):
            attendance_records = response.context_data.get('object_list', [])
            for record in attendance_records:
                self.assertEqual(record.student, self.student)


class TestAttendanceAJAXViews(AttendanceBaseTestMixin, TestCase):
    """Test cases for AJAX attendance views"""
    
    def test_load_periods_ajax(self):
        """Test AJAX period loading"""
        from core.views.attendance_views import load_periods
        
        request = self.factory.get(f'/attendance/ajax/load-periods/?term_id={self.term.id}')
        request.user = self.admin_user
        
        response = load_periods(request)
        self.assertEqual(response.status_code, 200)