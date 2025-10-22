# core/test_assignment_views.py
from django.test import TestCase, RequestFactory, Client
from django.contrib.auth.models import User
from django.urls import reverse
from django.utils import timezone
from django.core.files.uploadedfile import SimpleUploadedFile
from django.http import Http404
from django.core.exceptions import PermissionDenied
import json

from .models import (
    Assignment, StudentAssignment, ClassAssignment, Subject, 
    Student, Teacher
)
from .views.assignment_views import (
    AssignmentListView, AssignmentCreateView, AssignmentDetailView,
    AssignmentUpdateView, AssignmentDeleteView, GradeAssignmentView,
    SubmitAssignmentView, AssignmentCalendarView, AssignmentEventJsonView,
    BulkGradeAssignmentView, AssignmentAnalyticsView, AssignmentExportView,
    TeacherOwnershipRequiredMixin
)
from .forms import AssignmentForm, StudentAssignmentSubmissionForm
from .views.base_views import is_admin, is_teacher, is_student


class AssignmentViewsTestCase(TestCase):
    def setUp(self):
        """Set up test data for all test cases"""
        self.factory = RequestFactory()
        
        # Create users
        self.admin_user = User.objects.create_user(
            username='admin',
            password='testpass123',
            email='admin@school.com',
            is_staff=True
        )
        
        self.teacher_user = User.objects.create_user(
            username='teacher1',
            password='testpass123',
            email='teacher1@school.com'
        )
        
        self.student_user = User.objects.create_user(
            username='student1',
            password='testpass123',
            email='student1@school.com'
        )
        
        self.other_teacher_user = User.objects.create_user(
            username='teacher2',
            password='testpass123',
            email='teacher2@school.com'
        )
        
        # Create teacher profiles
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id='T001',
            date_of_birth='1980-01-01',
            gender='M',
            phone_number='1234567890',
            address='Teacher Address',
            class_levels='P1,P2',
            qualification='M.Ed',
            date_of_joining='2020-01-01',
            is_class_teacher=True,
            is_active=True
        )
        
        self.other_teacher = Teacher.objects.create(
            user=self.other_teacher_user,
            employee_id='T002',
            date_of_birth='1985-01-01',
            gender='F',
            phone_number='0987654321',
            address='Other Teacher Address',
            class_levels='P3,P4',
            qualification='B.Ed',
            date_of_joining='2021-01-01',
            is_class_teacher=True,
            is_active=True
        )
        
        # Create student profile
        self.student = Student.objects.create(
            user=self.student_user,
            student_id='STU001',
            first_name='John',
            last_name='Doe',
            date_of_birth='2010-01-01',
            gender='M',
            nationality='Ghanaian',
            place_of_birth='Accra',
            residential_address='Student Address',
            class_level='P1',
            admission_date='2023-01-01',
            is_active=True
        )
        
        # Create subject
        self.subject = Subject.objects.create(
            name='Mathematics',
            code='MATH',
            description='Mathematics subject'
        )
        
        # Create class assignment
        self.class_assignment = ClassAssignment.objects.create(
            class_level='P1',
            subject=self.subject,
            teacher=self.teacher,
            academic_year='2024/2025'
        )
        
        # Create assignment
        self.assignment = Assignment.objects.create(
            title='Test Assignment',
            description='Test assignment description',
            assignment_type='HOMEWORK',
            subject=self.subject,
            class_assignment=self.class_assignment,
            due_date=timezone.now() + timezone.timedelta(days=7),
            max_score=100,
            weight=20
        )
        
        # Create student assignment
        self.student_assignment = StudentAssignment.objects.create(
            student=self.student,
            assignment=self.assignment,
            status='PENDING'
        )

    def test_assignment_list_view_admin(self):
        """Test AssignmentListView for admin user"""
        request = self.factory.get(reverse('assignment_list'))
        request.user = self.admin_user
        
        view = AssignmentListView()
        view.setup(request)
        
        # Test queryset for admin
        queryset = view.get_queryset()
        self.assertIn(self.assignment, queryset)
        
        # Test context data
        context = view.get_context_data()
        self.assertIn('assignments', context)
        self.assertIn('class_levels', context)
        self.assertIn('subjects', context)

    def test_assignment_list_view_teacher(self):
        """Test AssignmentListView for teacher user"""
        request = self.factory.get(reverse('assignment_list'))
        request.user = self.teacher_user
        
        view = AssignmentListView()
        view.setup(request)
        
        queryset = view.get_queryset()
        self.assertIn(self.assignment, queryset)
        
        # Test that teacher only sees their own assignments
        context = view.get_context_data()
        self.assertTrue(context['is_teacher'])

    def test_assignment_list_view_student(self):
        """Test AssignmentListView for student user"""
        request = self.factory.get(reverse('assignment_list'))
        request.user = self.student_user
        
        view = AssignmentListView()
        view.setup(request)
        
        queryset = view.get_queryset()
        self.assertIn(self.assignment, queryset)
        
        context = view.get_context_data()
        self.assertTrue(context['is_student'])

    def test_assignment_list_filtering(self):
        """Test AssignmentListView filtering functionality"""
        # Test subject filter
        request = self.factory.get(f"{reverse('assignment_list')}?subject={self.subject.id}")
        request.user = self.admin_user
        
        view = AssignmentListView()
        view.setup(request)
        queryset = view.get_queryset()
        
        self.assertEqual(queryset.count(), 1)
        self.assertEqual(queryset.first().subject, self.subject)

    def test_assignment_create_view_permissions(self):
        """Test AssignmentCreateView permissions"""
        # Test admin access
        request = self.factory.get(reverse('assignment_create'))
        request.user = self.admin_user
        
        view = AssignmentCreateView()
        view.setup(request)
        self.assertTrue(view.test_func())
        
        # Test teacher access
        request.user = self.teacher_user
        view.setup(request)
        self.assertTrue(view.test_func())
        
        # Test student access (should be denied)
        request.user = self.student_user
        view.setup(request)
        self.assertFalse(view.test_func())

    def test_assignment_create_form_valid(self):
        """Test AssignmentCreateView form validation"""
        form_data = {
            'title': 'New Assignment',
            'description': 'New assignment description',
            'assignment_type': 'HOMEWORK',
            'subject': self.subject.id,
            'class_assignment': self.class_assignment.id,
            'due_date': (timezone.now() + timezone.timedelta(days=14)).strftime('%Y-%m-%d %H:%M:%S'),
            'max_score': 100,
            'weight': 25
        }
        
        request = self.factory.post(reverse('assignment_create'), data=form_data)
        request.user = self.teacher_user
        
        view = AssignmentCreateView()
        view.setup(request)
        view.request = request
        
        form = AssignmentForm(data=form_data, request=request)
        self.assertTrue(form.is_valid())

    def test_assignment_detail_view_permissions(self):
        """Test AssignmentDetailView permissions and context"""
        request = self.factory.get(reverse('assignment_detail', kwargs={'pk': self.assignment.pk}))
        request.user = self.student_user
        
        view = AssignmentDetailView()
        view.setup(request)
        
        # Test that student can access
        response = view.get(request, pk=self.assignment.pk)
        self.assertEqual(response.status_code, 200)
        
        # Test context data for student
        view.object = self.assignment
        context = view.get_context_data()
        self.assertIn('student_assignment', context)
        self.assertTrue(context['is_student'])

    def test_assignment_update_view_ownership(self):
        """Test AssignmentUpdateView ownership validation"""
        # Test teacher ownership
        request = self.factory.get(reverse('assignment_update', kwargs={'pk': self.assignment.pk}))
        request.user = self.teacher_user
        
        view = AssignmentUpdateView()
        view.setup(request)
        self.assertTrue(view.test_func())
        
        # Test other teacher access (should be denied)
        request.user = self.other_teacher_user
        view.setup(request)
        self.assertFalse(view.test_func())

    def test_assignment_delete_view(self):
        """Test AssignmentDeleteView"""
        request = self.factory.get(reverse('assignment_delete', kwargs={'pk': self.assignment.pk}))
        request.user = self.teacher_user
        
        view = AssignmentDeleteView()
        view.setup(request)
        self.assertTrue(view.test_func())

    def test_grade_assignment_view_get(self):
        """Test GradeAssignmentView GET method"""
        request = self.factory.get(
            reverse('grade_assignment', kwargs={'student_assignment_id': self.student_assignment.id})
        )
        request.user = self.teacher_user
        
        view = GradeAssignmentView()
        view.setup(request, student_assignment_id=self.student_assignment.id)
        
        self.assertTrue(view.test_func())
        
        response = view.get(request, student_assignment_id=self.student_assignment.id)
        self.assertEqual(response.status_code, 200)

    def test_grade_assignment_view_post(self):
        """Test GradeAssignmentView POST method"""
        grade_data = {
            'grade': '85',
            'feedback': 'Good work!'
        }
        
        request = self.factory.post(
            reverse('grade_assignment', kwargs={'student_assignment_id': self.student_assignment.id}),
            data=grade_data
        )
        request.user = self.teacher_user
        
        view = GradeAssignmentView()
        view.setup(request, student_assignment_id=self.student_assignment.id)
        
        response = view.post(request, student_assignment_id=self.student_assignment.id)
        self.assertEqual(response.status_code, 200)
        
        # Refresh student assignment
        self.student_assignment.refresh_from_db()
        self.assertEqual(self.student_assignment.score, 85)
        self.assertEqual(self.student_assignment.status, 'GRADED')

    def test_grade_assignment_view_ajax(self):
        """Test GradeAssignmentView with AJAX request"""
        grade_data = {
            'grade': '90',
            'feedback': 'Excellent work!'
        }
        
        request = self.factory.post(
            reverse('grade_assignment', kwargs={'student_assignment_id': self.student_assignment.id}),
            data=grade_data,
            HTTP_X_REQUESTED_WITH='XMLHttpRequest'
        )
        request.user = self.teacher_user
        
        view = GradeAssignmentView()
        view.setup(request, student_assignment_id=self.student_assignment.id)
        
        response = view.post(request, student_assignment_id=self.student_assignment.id)
        self.assertEqual(response.status_code, 200)
        
        # Check JSON response
        response_data = json.loads(response.content)
        self.assertTrue(response_data['success'])
        self.assertEqual(response_data['grade'], 90)

    def test_submit_assignment_view(self):
        """Test SubmitAssignmentView"""
        # Create a file for submission
        test_file = SimpleUploadedFile(
            "test_assignment.pdf",
            b"file_content",
            content_type="application/pdf"
        )
        
        submit_data = {
            'file': test_file,
            'status': 'SUBMITTED'
        }
        
        request = self.factory.post(
            reverse('submit_assignment', kwargs={'pk': self.student_assignment.id}),
            data=submit_data
        )
        request.user = self.student_user
        
        view = SubmitAssignmentView()
        view.setup(request, pk=self.student_assignment.id)
        
        self.assertTrue(view.test_func())
        
        # Test form validation
        form = StudentAssignmentSubmissionForm(
            data=submit_data,
            files={'file': test_file},
            assignment=self.assignment,
            instance=self.student_assignment
        )
        self.assertTrue(form.is_valid())

    def test_assignment_calendar_view(self):
        """Test AssignmentCalendarView"""
        request = self.factory.get(reverse('assignment_calendar'))
        request.user = self.student_user
        
        view = AssignmentCalendarView()
        view.setup(request)
        
        response = view.get(request)
        self.assertEqual(response.status_code, 200)
        
        context = view.get_context_data()
        self.assertIn('month', context)
        self.assertIn('year', context)

    def test_assignment_event_json_view_student(self):
        """Test AssignmentEventJsonView for student"""
        request = self.factory.get(
            reverse('assignment_calendar_events'),
            {'start': '2024-01-01', 'end': '2024-12-31'}
        )
        request.user = self.student_user
        
        view = AssignmentEventJsonView()
        view.setup(request)
        
        response = view.get(request)
        self.assertEqual(response.status_code, 200)
        
        events = json.loads(response.content)
        self.assertIsInstance(events, list)

    def test_assignment_event_json_view_teacher(self):
        """Test AssignmentEventJsonView for teacher"""
        request = self.factory.get(
            reverse('assignment_calendar_events'),
            {'start': '2024-01-01', 'end': '2024-12-31'}
        )
        request.user = self.teacher_user
        
        view = AssignmentEventJsonView()
        view.setup(request)
        
        response = view.get(request)
        self.assertEqual(response.status_code, 200)

    def test_bulk_grade_assignment_view(self):
        """Test BulkGradeAssignmentView"""
        grades_data = {
            'grades_data': json.dumps({
                str(self.student.id): {
                    'score': 88,
                    'feedback': 'Good work in bulk grading'
                }
            })
        }
        
        request = self.factory.post(
            reverse('bulk_grade_assignment', kwargs={'pk': self.assignment.id}),
            data=grades_data
        )
        request.user = self.teacher_user
        
        view = BulkGradeAssignmentView()
        view.setup(request, pk=self.assignment.id)
        
        self.assertTrue(view.test_func())
        
        response = view.post(request, pk=self.assignment.id)
        self.assertEqual(response.status_code, 200)

    def test_assignment_analytics_view(self):
        """Test AssignmentAnalyticsView"""
        request = self.factory.get(
            reverse('assignment_analytics', kwargs={'pk': self.assignment.id})
        )
        request.user = self.teacher_user
        
        view = AssignmentAnalyticsView()
        view.setup(request, pk=self.assignment.id)
        
        self.assertTrue(view.test_func())
        
        response = view.get(request, pk=self.assignment.id)
        self.assertEqual(response.status_code, 200)

    def test_assignment_export_view(self):
        """Test AssignmentExportView"""
        request = self.factory.get(
            reverse('assignment_export', kwargs={'pk': self.assignment.id})
        )
        request.user = self.teacher_user
        
        view = AssignmentExportView()
        view.setup(request, pk=self.assignment.id)
        
        self.assertTrue(view.test_func())
        
        response = view.get(request, pk=self.assignment.id)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response['Content-Type'], 'text/csv')

    def test_teacher_ownership_mixin(self):
        """Test TeacherOwnershipRequiredMixin"""
        request = self.factory.get('/')
        request.user = self.teacher_user
        
        class TestView(TeacherOwnershipRequiredMixin):
            def get_object(self):
                return self.assignment
        
        view = TestView()
        view.setup(request)
        view.assignment = self.assignment
        
        # Test that teacher can access their own assignment
        try:
            view.dispatch(request)
            # If no exception raised, test passes
            self.assertTrue(True)
        except PermissionDenied:
            self.fail("Teacher should have access to their own assignment")

    def test_assignment_color_coding(self):
        """Test assignment color coding logic"""
        view = AssignmentEventJsonView()
        
        # Test student assignment color coding
        colors = []
        
        # Test graded assignment
        self.student_assignment.status = 'GRADED'
        color = view.get_assignment_color(self.student_assignment)
        colors.append(color)
        self.assertEqual(color, '#28a745')  # Green
        
        # Test submitted assignment
        self.student_assignment.status = 'SUBMITTED'
        color = view.get_assignment_color(self.student_assignment)
        colors.append(color)
        self.assertEqual(color, '#17a2b8')  # Blue
        
        # Test late assignment
        self.student_assignment.status = 'LATE'
        color = view.get_assignment_color(self.student_assignment)
        colors.append(color)
        self.assertEqual(color, '#dc3545')  # Red

    def test_error_handling(self):
        """Test error handling in views"""
        # Test non-existent assignment
        request = self.factory.get(reverse('assignment_detail', kwargs={'pk': 9999}))
        request.user = self.admin_user
        
        view = AssignmentDetailView()
        view.setup(request, pk=9999)
        
        with self.assertRaises(Http404):
            view.get_object()

    def test_assignment_statistics(self):
        """Test assignment statistics calculation"""
        request = self.factory.get(reverse('assignment_list'))
        request.user = self.teacher_user
        
        view = AssignmentListView()
        view.setup(request)
        
        context = view.get_context_data()
        
        # Check that statistics are calculated
        self.assertIn('assignments_count', context)
        self.assertIn('completed_count', context)
        self.assertIn('pending_count', context)
        self.assertIn('overdue_count', context)
        
        # All counts should be integers
        self.assertIsInstance(context['assignments_count'], int)
        self.assertIsInstance(context['completed_count'], int)
        self.assertIsInstance(context['pending_count'], int)
        self.assertIsInstance(context['overdue_count'], int)


class AssignmentViewIntegrationTests(TestCase):
    """Integration tests for assignment views"""
    
    def setUp(self):
        self.client = Client()
        self.teacher_user = User.objects.create_user(
            username='testteacher',
            password='testpass123',
            email='teacher@test.com'
        )
        self.teacher = Teacher.objects.create(
            user=self.teacher_user,
            employee_id='T999',
            date_of_birth='1980-01-01',
            gender='M',
            phone_number='1234567890',
            address='Test Address',
            class_levels='P1',
            is_active=True
        )
        
        self.student_user = User.objects.create_user(
            username='teststudent',
            password='testpass123',
            email='student@test.com'++
            
        )
        self.student = Student.objects.create(
            user=self.student_user,
            student_id='STU999',
            first_name='Test',
            last_name='Student',
            date_of_birth='2010-01-01',
            gender='M',
            class_level='P1',
            is_active=True
        )
        
        self.subject = Subject.objects.create(name='Test Subject', code='TEST')
        self.class_assignment = ClassAssignment.objects.create(
            class_level='P1',
            subject=self.subject,
            teacher=self.teacher,
            academic_year='2024/2025'
        )
        
        self.assignment = Assignment.objects.create(
            title='Integration Test Assignment',
            description='Test description',
            assignment_type='HOMEWORK',
            subject=self.subject,
            class_assignment=self.class_assignment,
            due_date=timezone.now() + timezone.timedelta(days=7),
            max_score=100,
            weight=20
        )

    def test_assignment_creation_flow(self):
        """Test complete assignment creation flow"""
        # Login as teacher
        self.client.login(username='testteacher', password='testpass123')
        
        # Access assignment creation page
        response = self.client.get(reverse('assignment_create'))
        self.assertEqual(response.status_code, 200)
        
        # Create new assignment
        new_assignment_data = {
            'title': 'New Integration Assignment',
            'description': 'Integration test assignment',
            'assignment_type': 'TEST',
            'subject': self.subject.id,
            'class_assignment': self.class_assignment.id,
            'due_date': (timezone.now() + timezone.timedelta(days=14)).strftime('%Y-%m-%d %H:%M:%S'),
            'max_score': 50,
            'weight': 15
        }
        
        response = self.client.post(reverse('assignment_create'), data=new_assignment_data)
        self.assertEqual(response.status_code, 302)  # Should redirect
        
        # Verify assignment was created
        new_assignment = Assignment.objects.get(title='New Integration Assignment')
        self.assertIsNotNone(new_assignment)

    def test_assignment_grading_flow(self):
        """Test complete assignment grading flow"""
        # Create student assignment
        student_assignment = StudentAssignment.objects.create(
            student=self.student,
            assignment=self.assignment,
            status='SUBMITTED',
            submitted_date=timezone.now()
        )
        
        # Login as teacher
        self.client.login(username='testteacher', password='testpass123')
        
        # Grade the assignment
        grade_data = {
            'grade': '92',
            'feedback': 'Excellent integration test work!'
        }
        
        response = self.client.post(
            reverse('grade_assignment', kwargs={'student_assignment_id': student_assignment.id}),
            data=grade_data
        )
        
        self.assertEqual(response.status_code, 200)
        
        # Verify grading was successful
        student_assignment.refresh_from_db()
        self.assertEqual(student_assignment.score, 92)
        self.assertEqual(student_assignment.status, 'GRADED')


# Quick test runner for development
def run_quick_tests():
    """Run a quick subset of tests for development"""
    import django
    from django.conf import settings
    
    if not settings.configured:
        django.setup()
    
    # Create a minimal test case
    quick_test = AssignmentViewsTestCase()
    quick_test.setUp()
    
    print("Running quick assignment view tests...")
    
    try:
        quick_test.test_assignment_list_view_admin()
        print("✓ Assignment list view (admin) test passed")
        
        quick_test.test_assignment_create_view_permissions()
        print("✓ Assignment create permissions test passed")
        
        quick_test.test_assignment_detail_view_student()
        print("✓ Assignment detail view (student) test passed")
        
        quick_test.test_grade_assignment_view_post()
        print("✓ Grade assignment view test passed")
        
        print("🎉 All quick tests passed! ✅")
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    run_quick_tests()