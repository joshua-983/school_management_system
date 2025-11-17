from datetime import date
from django.test import TestCase
from django.contrib.auth import get_user_model
from core.models import Student, ClassAssignment

User = get_user_model()

class TestDataFactory:
    """Factory for creating test data with all required fields"""
    
    @staticmethod
    def create_test_student(**kwargs):
        """Create a test student with all required fields"""
        defaults = {
            'student_id': 'TEST001',
            'first_name': 'Test',
            'middle_name': 'Middle',
            'last_name': 'Student',
            'date_of_birth': date(2005, 1, 1),
            'gender': 'male',
            'ethnicity': 'Test Ethnicity',
            'religion': 'Test Religion', 
            'place_of_birth': 'Test City',
            'residential_address': 'Test Address',
            'phone_number': '+1234567890',
            'class_level': 'JHS 1',
        }
        defaults.update(kwargs)
        
        # Create user if not provided
        if 'user' not in kwargs:
            user = User.objects.create_user(
                username=defaults['student_id'],
                email=f"{defaults['student_id']}@test.com",
                password='testpass123'
            )
            defaults['user'] = user
        
        return Student.objects.create(**defaults)
    
    @staticmethod
    def create_test_class(**kwargs):
        """Create a test class assignment"""
        defaults = {
            'name': 'Test Class',
            'grade_level': 'JHS 1',
            'academic_year': '2024-2025',
        }
        defaults.update(kwargs)
        return ClassAssignment.objects.create(**defaults)

class FactoryTestCase(TestCase):
    """Test cases for the TestDataFactory"""
    
    def test_create_test_student(self):
        """Test that we can create a student with all required fields"""
        student = TestDataFactory.create_test_student()
        self.assertIsNotNone(student)
        self.assertEqual(student.student_id, 'TEST001')
        self.assertIsNotNone(student.date_of_birth)
        print("✅ Student factory works correctly")
    
    def test_create_test_class(self):
        """Test that we can create a class assignment"""
        class_assignment = TestDataFactory.create_test_class()
        self.assertIsNotNone(class_assignment)
        self.assertEqual(class_assignment.name, 'Test Class')
        print("✅ Class assignment factory works correctly")
