# school/core/tests/factories.py
import factory
from factory.django import DjangoModelFactory
from django.utils import timezone
from django.contrib.auth import get_user_model

User = get_user_model()

class UserFactory(DjangoModelFactory):
    class Meta:
        model = User
    
    username = factory.Sequence(lambda n: f'user{n}')
    email = factory.Sequence(lambda n: f'user{n}@school.com')
    password = factory.PostGenerationMethodCall('set_password', 'password')
    first_name = factory.Faker('first_name')
    last_name = factory.Faker('last_name')

# Try to import your models - handle gracefully if they don't exist
try:
    from core.models import Student, Teacher, Subject, ClassAssignment, Assignment, StudentAssignment
    
    class StudentFactory(DjangoModelFactory):
        class Meta:
            model = Student
        
        user = factory.SubFactory(UserFactory)
        student_id = factory.Sequence(lambda n: f'STUD2024{n:03d}')
        first_name = factory.Faker('first_name')
        last_name = factory.Faker('last_name')
        class_level = 'P5'
        is_active = True
        date_of_birth = factory.Faker('date_of_birth', minimum_age=10, maximum_age=15)
        gender = 'M'
        admission_date = factory.LazyFunction(timezone.now)

    class TeacherFactory(DjangoModelFactory):
        class Meta:
            model = Teacher
        
        user = factory.SubFactory(UserFactory)
        employee_id = factory.Sequence(lambda n: f'T{n:04d}')
        is_active = True
        date_of_birth = factory.Faker('date_of_birth', minimum_age=25, maximum_age=60)
        gender = 'M'
        phone_number = '+233123456789'
        address = factory.Faker('address')
        qualification = 'M.Ed'
        date_of_joining = factory.LazyFunction(timezone.now)

    class SubjectFactory(DjangoModelFactory):
        class Meta:
            model = Subject
        
        name = factory.Sequence(lambda n: f'Subject {n}')
        code = factory.Sequence(lambda n: f'SUB{n:03d}')
        is_active = True

    class ClassAssignmentFactory(DjangoModelFactory):
        class Meta:
            model = ClassAssignment
        
        teacher = factory.SubFactory(TeacherFactory)
        subject = factory.SubFactory(SubjectFactory)
        class_level = 'P5'
        academic_year = '2024/2025'
        is_active = True

    class AssignmentFactory(DjangoModelFactory):
        class Meta:
            model = Assignment
        
        title = factory.Sequence(lambda n: f'Assignment {n}')
        description = factory.Faker('text', max_nb_chars=200)
        assignment_type = 'HOMEWORK'
        subject = factory.SubFactory(SubjectFactory)
        class_assignment = factory.SubFactory(ClassAssignmentFactory)
        due_date = factory.LazyFunction(lambda: timezone.now() + timezone.timedelta(days=7))
        max_score = 100
        weight = 10
        is_active = True

    class StudentAssignmentFactory(DjangoModelFactory):
        class Meta:
            model = StudentAssignment
        
        student = factory.SubFactory(StudentFactory)
        assignment = factory.SubFactory(AssignmentFactory)
        status = 'PENDING'

except ImportError as e:
    print(f"Warning: Could not import models for factories: {e}")