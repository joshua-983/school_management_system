


# tests/test_assignments.py
from django.test import TestCase
from django.urls import reverse
from core.models import Assignment, ClassAssignment, Subject
from users.models import Teacher

class AssignmentCreationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.teacher = Teacher.objects.create_user(username='teacher1', password='test123')
        cls.subject = Subject.objects.create(name='Mathematics')
        cls.subject.teachers.add(cls.teacher)
        cls.class_assignment = ClassAssignment.objects.create(
            class_level='P1',
            teacher=cls.teacher,
            subject=cls.subject
        )

    def test_assignment_creation(self):
        self.client.force_login(self.teacher)
        response = self.client.post(reverse('assignment_create'), {
            'title': 'Algebra Basics',
            'subject': self.subject.id,
            'class_assignment': self.class_assignment.id,
            'due_date': '2023-12-31 23:59',
            'max_score': 100,
            'weight': 20,
            'assignment_type': 'HOMEWORK'
        })
        self.assertEqual(response.status_code, 302)
        self.assertTrue(Assignment.objects.exists())