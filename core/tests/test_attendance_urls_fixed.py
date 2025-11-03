# core/tests/test_attendance_urls_fixed.py
from django.test import TestCase
from django.urls import reverse, resolve
from django.conf import settings


class AttendanceURLConfigurationTest(TestCase):
    """
    Test URL configuration without authentication dependencies
    """
    
    def test_all_attendance_urls_defined(self):
        """Test that all expected attendance URLs are defined"""
        from core.urls import urlpatterns
        
        # Get all URL names
        def get_url_names(patterns):
            names = []
            for pattern in patterns:
                if hasattr(pattern, 'name') and pattern.name:
                    names.append(pattern.name)
                if hasattr(pattern, 'url_patterns'):
                    names.extend(get_url_names(pattern.url_patterns))
            return names
        
        all_url_names = get_url_names(urlpatterns)
        
        required_urls = {
            'attendance_dashboard',
            'attendance_record',
            'student_attendance_list', 
            'load_periods',
            'student_attendance_summary'
        }
        
        for url_name in required_urls:
            with self.subTest(url_name=url_name):
                self.assertIn(url_name, all_url_names)

    def test_url_reverse_resolve_consistency(self):
        """Test URL reversing and resolving consistency"""
        test_cases = [
            ('attendance_dashboard', {}, '/attendance/'),
            ('attendance_record', {}, '/attendance/record/'),
            ('student_attendance_list', {}, '/student-attendance/'),
            ('load_periods', {}, '/attendance/load-periods/'),
            ('student_attendance_summary', {'student_id': 1}, '/student/1/attendance/'),
        ]
        
        for view_name, kwargs, expected_path in test_cases:
            with self.subTest(view_name=view_name):
                # Test reverse
                reversed_path = reverse(view_name, kwargs=kwargs)
                self.assertEqual(reversed_path, expected_path)
                
                # Test resolve  
                resolver_match = resolve(expected_path)
                self.assertEqual(resolver_match.view_name, view_name)

    def test_url_parameter_handling(self):
        """Test URL parameter conversion"""
        # Test different parameter types
        test_cases = [
            (1, '1'),
            ('1', '1'),
            ('S001', 'S001'),
            (123, '123'),
        ]
        
        for input_val, expected_in_url in test_cases:
            with self.subTest(input_val=input_val):
                url = reverse('student_attendance_summary', kwargs={'student_id': input_val})
                self.assertIn(f'/student/{expected_in_url}/attendance/', url)