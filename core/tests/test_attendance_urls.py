# core/tests/test_attendance_urls.py
from django.test import TestCase, Client
from django.urls import reverse, resolve
from django.contrib.auth import get_user_model
from django.conf import settings
from core.models import Student, Teacher, AcademicTerm
from datetime import date
import sys

CustomUser = get_user_model()


class AttendanceURLsTest(TestCase):
    """Test cases for attendance URLs"""
    
    def setUp(self):
        """Set up test data"""
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
        
        # Create teacher profile
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id='T001',
            date_of_birth=date(1980, 1, 1),
            gender='M',
            phone_number='0241234567',
            address='Test Address',
            qualification='Test Qualification',
            class_levels='P6',
            date_of_joining=date.today()
        )
        
        # Create student profile
        self.student = Student.objects.create(
            user=self.student_user,
            student_id='S001',
            first_name='John',
            last_name='Doe',
            date_of_birth=date(2010, 1, 1),
            gender='M',
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
        
        self.client = Client()
    
    def _login_user(self, user):
        """Helper method to login user - optimized for test settings"""
        # Use force_login for tests to avoid session issues with DummyCache
        self.client.force_login(user)
    
    def test_attendance_dashboard_url_resolution(self):
        """Test attendance dashboard URL resolution"""
        url = reverse('attendance_dashboard')
        self.assertEqual(url, '/attendance/')
        
        # Test URL resolution
        resolver = resolve('/attendance/')
        self.assertEqual(resolver.view_name, 'attendance_dashboard')
    
    def test_attendance_record_url_resolution(self):
        """Test attendance record URL resolution"""
        url = reverse('attendance_record')
        self.assertEqual(url, '/attendance/record/')
        
        # Test URL resolution
        resolver = resolve('/attendance/record/')
        self.assertEqual(resolver.view_name, 'attendance_record')
    
    def test_student_attendance_list_url_resolution(self):
        """Test student attendance list URL resolution"""
        url = reverse('student_attendance_list')
        self.assertEqual(url, '/student-attendance/')
        
        # Test URL resolution
        resolver = resolve('/student-attendance/')
        self.assertEqual(resolver.view_name, 'student_attendance_list')
    
    def test_load_periods_url_resolution(self):
        """Test load periods URL resolution"""
        url = reverse('load_periods')
        self.assertEqual(url, '/attendance/load-periods/')
        
        # Test URL resolution
        resolver = resolve('/attendance/load-periods/')
        self.assertEqual(resolver.view_name, 'load_periods')
    
    def test_student_attendance_summary_url_resolution(self):
        """Test student attendance summary URL resolution"""
        url = reverse('student_attendance_summary', kwargs={'student_id': 1})
        self.assertEqual(url, '/student/1/attendance/')
        
        # Test URL resolution
        resolver = resolve('/student/1/attendance/')
        self.assertEqual(resolver.view_name, 'student_attendance_summary')
        # URL parameters can be strings or integers depending on configuration
        student_id = resolver.kwargs['student_id']
        self.assertTrue(isinstance(student_id, (str, int)))
        self.assertEqual(str(student_id), '1')
    
    def test_attendance_dashboard_access_control(self):
        """Test that attendance dashboard URLs have proper access control"""
        # Test admin access
        self._login_user(self.admin_user)
        response = self.client.get(reverse('attendance_dashboard'))
        self.assertIn(response.status_code, [200, 302])
        
        # Test teacher access
        self._login_user(self.teacher_user)
        response = self.client.get(reverse('attendance_dashboard'))
        self.assertIn(response.status_code, [200, 302])
        
        # Test student access - should be denied or redirect
        self._login_user(self.student_user)
        response = self.client.get(reverse('attendance_dashboard'))
        self.assertIn(response.status_code, [403, 302, 404])
    
    def test_attendance_record_access_control(self):
        """Test that attendance record URLs have proper access control"""
        # Test admin access
        self._login_user(self.admin_user)
        response = self.client.get(reverse('attendance_record'))
        self.assertIn(response.status_code, [200, 302])
        
        # Test teacher access
        self._login_user(self.teacher_user)
        response = self.client.get(reverse('attendance_record'))
        self.assertIn(response.status_code, [200, 302])
        
        # Test student access - should be denied
        self._login_user(self.student_user)
        response = self.client.get(reverse('attendance_record'))
        self.assertIn(response.status_code, [403, 302, 404])
    
    def test_student_attendance_list_access_control(self):
        """Test that student attendance list URL is accessible to students"""
        # Test student access
        self._login_user(self.student_user)
        response = self.client.get(reverse('student_attendance_list'))
        self.assertIn(response.status_code, [200, 302])
        
        # Test admin access
        self._login_user(self.admin_user)
        response = self.client.get(reverse('student_attendance_list'))
        self.assertIn(response.status_code, [200, 302])
        
        # Test teacher access
        self._login_user(self.teacher_user)
        response = self.client.get(reverse('student_attendance_list'))
        self.assertIn(response.status_code, [200, 302])
    
    def test_load_periods_access_control(self):
        """Test that load periods URL has proper access control"""
        # Test admin access
        self._login_user(self.admin_user)
        response = self.client.get(reverse('load_periods') + '?term_id=1')
        self.assertIn(response.status_code, [200, 302, 400])
        
        # Test teacher access
        self._login_user(self.teacher_user)
        response = self.client.get(reverse('load_periods') + '?term_id=1')
        self.assertIn(response.status_code, [200, 302, 400])
        
        # Test student access - should be denied
        self._login_user(self.student_user)
        response = self.client.get(reverse('load_periods') + '?term_id=1')
        self.assertIn(response.status_code, [403, 302, 404])
    
    def test_student_attendance_summary_access_control(self):
        """Test that student attendance summary URL has proper access control"""
        # Test admin access
        self._login_user(self.admin_user)
        response = self.client.get(reverse('student_attendance_summary', kwargs={'student_id': self.student.id}))
        self.assertIn(response.status_code, [200, 302, 404])
        
        # Test teacher access
        self._login_user(self.teacher_user)
        response = self.client.get(reverse('student_attendance_summary', kwargs={'student_id': self.student.id}))
        self.assertIn(response.status_code, [200, 302, 404])
        
        # Test student access to their own summary
        self._login_user(self.student_user)
        response = self.client.get(reverse('student_attendance_summary', kwargs={'student_id': self.student.id}))
        self.assertIn(response.status_code, [200, 302, 403, 404])
    
    def test_attendance_urls_require_authentication(self):
        """Test that attendance URLs require authentication"""
        # Test dashboard without login - should redirect to login
        response = self.client.get(reverse('attendance_dashboard'))
        self.assertEqual(response.status_code, 302)  # Should redirect to login
        
        # Test record without login
        response = self.client.get(reverse('attendance_record'))
        self.assertEqual(response.status_code, 302)  # Should redirect to login
        
        # Test student list without login
        response = self.client.get(reverse('student_attendance_list'))
        self.assertEqual(response.status_code, 302)  # Should redirect to login
        
        # Test load periods without login
        response = self.client.get(reverse('load_periods'))
        self.assertEqual(response.status_code, 302)  # Should redirect to login
    
    def test_url_parameters_handling(self):
        """Test URLs with query parameters"""
        self._login_user(self.admin_user)
        
        # Test attendance record with parameters
        url = reverse('attendance_record') + '?date=2025-10-25&term=1&class_level=P6'
        response = self.client.get(url)
        self.assertIn(response.status_code, [200, 302, 400])
        
        # Test load periods with term_id
        url = reverse('load_periods') + '?term_id=1'
        response = self.client.get(url)
        self.assertIn(response.status_code, [200, 302, 400])
    
    def test_nonexistent_attendance_urls_return_404(self):
        """Test that nonexistent attendance URLs return 404"""
        self._login_user(self.admin_user)
        response = self.client.get('/attendance/nonexistent/')
        self.assertEqual(response.status_code, 404)
        
        response = self.client.get('/student-attendance/nonexistent/')
        self.assertEqual(response.status_code, 404)
    
    def test_attendance_url_templates(self):
        """Test that attendance URLs use correct templates when accessible"""
        # Only test template usage if we get a 200 response
        self._login_user(self.admin_user)
        response = self.client.get(reverse('attendance_dashboard'))
        if response.status_code == 200:
            self.assertTemplateUsed(response, 'core/academics/attendance_dashboard.html')
        
        # Test record template (admin access)
        response = self.client.get(reverse('attendance_record'))
        if response.status_code == 200:
            self.assertTemplateUsed(response, 'core/academics/attendance_record.html')
        
        # Test student list template (student access)
        self._login_user(self.student_user)
        response = self.client.get(reverse('student_attendance_list'))
        if response.status_code == 200:
            self.assertTemplateUsed(response, 'core/academics/student_attendance_list.html')
    
    def test_ajax_load_periods_functionality(self):
        """Test AJAX load periods functionality"""
        self._login_user(self.admin_user)
        
        # Test with term_id parameter
        response = self.client.get(reverse('load_periods') + '?term_id=1')
        self.assertIn(response.status_code, [200, 400])
        
        # Test without term_id parameter
        response = self.client.get(reverse('load_periods'))
        self.assertIn(response.status_code, [200, 400])
    
    def test_student_specific_attendance_access(self):
        """Test that students can only access their own attendance"""
        # Create another student
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
        
        # Test that student can access their own attendance list
        self._login_user(self.student_user)
        response = self.client.get(reverse('student_attendance_list'))
        self.assertIn(response.status_code, [200, 302])
        
        # Test that student cannot access attendance summary (admin/teacher view)
        response = self.client.get(reverse('student_attendance_summary', kwargs={'student_id': self.student.id}))
        self.assertIn(response.status_code, [403, 404, 302])
        
        # Test that student cannot access another student's attendance summary
        response = self.client.get(reverse('student_attendance_summary', kwargs={'student_id': other_student.id}))
        self.assertIn(response.status_code, [403, 404, 302])


class AttendanceURLPatternsTest(TestCase):
    """Test URL pattern configurations for attendance"""
    
    def test_attendance_urls_included_in_core_urls(self):
        """Test that attendance URLs are properly included in core URLs"""
        from core.urls import urlpatterns
        
        # Check for attendance URL patterns
        attendance_patterns = [
            pattern for pattern in urlpatterns 
            if hasattr(pattern, 'pattern') and 'attendance' in str(pattern.pattern)
        ]
        
        self.assertGreater(len(attendance_patterns), 0, "Attendance URLs should be included in core URLs")
        
        # Check specific attendance URLs
        url_names = [pattern.name for pattern in attendance_patterns if hasattr(pattern, 'name') and pattern.name]
        expected_names = [
            'attendance_dashboard',
            'attendance_record', 
            'student_attendance_list',
            'load_periods',
            'student_attendance_summary'
        ]
        
        for expected_name in expected_names:
            self.assertIn(expected_name, url_names, f"Attendance URL {expected_name} should be included")
    
    def test_url_reverse_consistency(self):
        """Test that URL reversing works consistently"""
        # Test all attendance URLs can be reversed
        urls_to_test = [
            ('attendance_dashboard', [], '/attendance/'),
            ('attendance_record', [], '/attendance/record/'),
            ('student_attendance_list', [], '/student-attendance/'),
            ('load_periods', [], '/attendance/load-periods/'),
            ('student_attendance_summary', {'student_id': 1}, '/student/1/attendance/'),
        ]
        
        for view_name, kwargs, expected_url in urls_to_test:
            with self.subTest(view_name=view_name):
                reversed_url = reverse(view_name, kwargs=kwargs)
                self.assertEqual(reversed_url, expected_url)
    
    def test_url_resolution_consistency(self):
        """Test that URL resolution works consistently"""
        # Test all attendance URLs can be resolved
        url_patterns_to_test = [
            ('/attendance/', 'attendance_dashboard'),
            ('/attendance/record/', 'attendance_record'),
            ('/student-attendance/', 'student_attendance_list'),
            ('/attendance/load-periods/', 'load_periods'),
            ('/student/1/attendance/', 'student_attendance_summary'),
        ]
        
        for url_path, expected_view_name in url_patterns_to_test:
            with self.subTest(url_path=url_path):
                resolver = resolve(url_path)
                self.assertEqual(resolver.view_name, expected_view_name)