# core/tests/test_attendance_templates.py
from django.test import TestCase
from django.template import Template, Context
from core.models import StudentAttendance, Student, AcademicTerm


class AttendanceTemplatesTest(TestCase):
    """Test cases for attendance template rendering"""
    
    def setUp(self):
        self.term = AcademicTerm.objects.create(
            term=1,
            academic_year='2025/2026',
            start_date='2025-09-01',
            end_date='2025-12-31'
        )
        
        self.student = Student.objects.create(
            student_id='S001',
            first_name='John',
            last_name='Doe',
            class_level='P6'
        )
    
    def test_attendance_status_display(self):
        """Test attendance status display in templates"""
        template = Template("""
            {% load custom_filters %}
            {{ attendance.get_status_display }}
        """)
        
        attendance = StudentAttendance(
            student=self.student,
            term=self.term,
            date='2025-10-25',
            status='present'
        )
        
        context = Context({'attendance': attendance})
        rendered = template.render(context)
        
        self.assertIn('Present', rendered)
    
    def test_attendance_stats_template(self):
        """Test attendance statistics template rendering"""
        template = Template("""
            {% for stat in stats %}
            <div class="stat-card {{ stat.color }}">
                <i class="bi bi-{{ stat.icon }}"></i>
                <div class="stat-value">{{ stat.value }}</div>
                <div class="stat-label">{{ stat.label }}</div>
            </div>
            {% endfor %}
        """)
        
        stats = [
            {'label': 'Total Students', 'value': 25, 'color': 'primary', 'icon': 'people-fill'},
            {'label': 'Present Today', 'value': 20, 'color': 'success', 'icon': 'check-circle-fill'},
        ]
        
        context = Context({'stats': stats})
        rendered = template.render(context)
        
        self.assertIn('Total Students', rendered)
        self.assertIn('Present Today', rendered)
        self.assertIn('25', rendered)
        self.assertIn('20', rendered)