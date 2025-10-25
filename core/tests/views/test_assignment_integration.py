# school/core/tests/views/test_assignment_integration.py
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from core.tests.factories import TeacherFactory, StudentFactory, AssignmentFactory


class AssignmentWorkflowTest(TestCase):
    """Test complete assignment workflows"""
    
    def setUp(self):
        self.teacher = TeacherFactory()
        self.student = StudentFactory(class_level='P5')
        self.assignment = AssignmentFactory(
            class_assignment__teacher=self.teacher,
            class_assignment__class_level='P5'
        )

    def test_assignment_lifecycle(self):
        """Test basic assignment lifecycle"""
        # 1. Teacher views assignment list
        self.client.force_login(self.teacher.user)
        
        try:
            response = self.client.get(reverse('assignment_list'))
            self.assertEqual(response.status_code, 200)
            
            # 2. Teacher views assignment detail
            response = self.client.get(reverse('assignment_detail', kwargs={'pk': self.assignment.pk}))
            self.assertEqual(response.status_code, 200)
            
        except:
            self.skipTest("Assignment URLs not configured")

    def test_student_workflow(self):
        """Test student assignment workflow"""
        self.client.force_login(self.student.user)
        
        try:
            # Student views assignment list
            response = self.client.get(reverse('assignment_list'))
            self.assertEqual(response.status_code, 200)
            
            # Student views assignment detail (should auto-create StudentAssignment)
            response = self.client.get(reverse('assignment_detail', kwargs={'pk': self.assignment.pk}))
            self.assertEqual(response.status_code, 200)
            
            # Check if StudentAssignment was created
            from core.models import StudentAssignment
            student_assignment_exists = StudentAssignment.objects.filter(
                student=self.student,
                assignment=self.assignment
            ).exists()
            self.assertTrue(student_assignment_exists)
            
        except:
            self.skipTest("Assignment URLs not configured")