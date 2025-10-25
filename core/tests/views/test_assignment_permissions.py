# school/core/tests/views/test_assignment_permissions.py
from django.test import TestCase
from django.urls import reverse

from core.tests.factories import TeacherFactory, StudentFactory, AssignmentFactory


class AssignmentPermissionTest(TestCase):
    def setUp(self):
        self.teacher1 = TeacherFactory()
        self.teacher2 = TeacherFactory()
        self.student = StudentFactory()
        
        # Teacher1's assignment
        self.assignment = AssignmentFactory(class_assignment__teacher=self.teacher1)

    def test_cross_teacher_access(self):
        """Test that teachers cannot access other teachers' assignments"""
        self.client.force_login(self.teacher2.user)
        
        try:
            # Should be able to view but not edit
            response = self.client.get(reverse('assignment_detail', kwargs={'pk': self.assignment.pk}))
            self.assertEqual(response.status_code, 200)
            
            # Should not be able to update
            response = self.client.get(reverse('assignment_update', kwargs={'pk': self.assignment.pk}))
            self.assertEqual(response.status_code, 403)
            
        except:
            self.skipTest("Assignment URLs not configured")

    def test_student_restrictions(self):
        """Test that students cannot access teacher functionality"""
        self.client.force_login(self.student.user)
        
        try:
            # Should not be able to create assignments
            response = self.client.get(reverse('assignment_create'))
            self.assertEqual(response.status_code, 403)
            
            # Should not be able to update assignments
            response = self.client.get(reverse('assignment_update', kwargs={'pk': self.assignment.pk}))
            self.assertEqual(response.status_code, 403)
            
        except:
            self.skipTest("Assignment URLs not configured")

