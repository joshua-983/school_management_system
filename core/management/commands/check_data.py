# core/management/commands/check_data.py - COMPLETE FIXED VERSION
"""
Django management command to check database data for report cards.
Run with: python manage.py check_data
"""
from django.core.management.base import BaseCommand
from django.db.models import Count, Avg, Q
from datetime import date, timedelta
import sys

class Command(BaseCommand):
    help = 'Check database data for report cards and attendance'

    def add_arguments(self, parser):
        parser.add_argument(
            '--student-id',
            type=int,
            help='Check specific student by ID',
        )
        parser.add_argument(
            '--academic-year',
            type=str,
            default='2024/2025',
            help='Academic year to check (default: 2024/2025)',
        )
        parser.add_argument(
            '--term',
            type=int,
            default=2,
            help='Term to check (default: 2)',
        )
        parser.add_argument(
            '--fix',
            action='store_true',
            help='Create missing data automatically',
        )

    def handle(self, *args, **options):
        self.stdout.write("=" * 70)
        self.stdout.write("DATABASE DATA CHECK - REPORT CARD SYSTEM")
        self.stdout.write("=" * 70)
        
        student_id = options['student_id']
        academic_year = options['academic_year']
        term = options['term']
        fix_data = options['fix']
        
        # Import models - FIXED IMPORTS
        from core.models.student import Student
        from core.models.academic import AcademicTerm
        from core.models.attendance import StudentAttendance  # FIXED
        from core.models.grades import Grade
        from core.models.subject import Subject
        from core.models.report_card import ReportCard
        
        self.stdout.write(f"\nAcademic Year: {academic_year}, Term: {term}")
        self.stdout.write(f"Fix Mode: {'ON' if fix_data else 'OFF'}")
        
        # 1. Check Academic Terms
        self.check_academic_terms(academic_year, term, fix_data)
        
        # 2. Check Students
        students = self.check_students(student_id, fix_data)
        
        if students:
            student = students[0]
            # 3. Check Attendance
            self.check_attendance(student, academic_year, term, fix_data)
            
            # 4. Check Grades
            self.check_grades(student, academic_year, term, fix_data)
            
            # 5. Check Report Cards
            self.check_report_cards(student, academic_year, term, fix_data)
            
            # 6. Test Utility Functions
            self.test_utility_functions(student, academic_year, term)
        
        self.stdout.write("\n" + "=" * 70)
        self.stdout.write("CHECK COMPLETE")
        self.stdout.write("=" * 70)
    
    def check_academic_terms(self, academic_year, term, fix_data):
        """Check academic terms"""
        from core.models.academic import AcademicTerm
        
        self.stdout.write("\n1. ACADEMIC TERMS")
        self.stdout.write("-" * 40)
        
        # Try different formats
        formats = [
            academic_year,  # "2024/2025"
            academic_year.replace('/', '-'),  # "2024-2025"
            academic_year.replace('/', '_'),  # "2024_2025"
        ]
        
        term_obj = None
        for fmt in formats:
            term_obj = AcademicTerm.objects.filter(
                academic_year=fmt,
                term=term
            ).first()
            if term_obj:
                self.stdout.write(f"   ✓ Found: {term_obj.academic_year} Term {term_obj.term}")
                self.stdout.write(f"      Dates: {term_obj.start_date} to {term_obj.end_date}")
                self.stdout.write(f"      Active: {term_obj.is_active}")
                break
        
        if not term_obj:
            self.stdout.write(f"   ❌ NOT FOUND: {academic_year} Term {term}")
            
            if fix_data:
                self.stdout.write("   Creating term...")
                term_obj = AcademicTerm.objects.create(
                    academic_year=formats[1],  # Use dash format
                    term=term,
                    start_date=date(2024, 5, 1),
                    end_date=date(2024, 8, 31),
                    is_active=True,
                    name=f"Term {term} {academic_year}"
                )
                self.stdout.write(f"   ✓ Created: {term_obj.academic_year} Term {term_obj.term}")
        
        # List all terms
        all_terms = AcademicTerm.objects.all().order_by('-start_date')
        self.stdout.write(f"\n   All terms in database ({all_terms.count()}):")
        for t in all_terms[:10]:  # Show first 10
            self.stdout.write(f"      - {t.academic_year} Term {t.term}: {t.start_date} to {t.end_date}")
    
    def check_students(self, student_id, fix_data):
        """Check students"""
        from core.models.student import Student
        
        self.stdout.write("\n2. STUDENTS")
        self.stdout.write("-" * 40)
        
        if student_id:
            students = Student.objects.filter(id=student_id, is_active=True)
        else:
            students = Student.objects.filter(is_active=True).order_by('class_level', 'last_name')
        
        self.stdout.write(f"   Active students: {students.count()}")
        
        if students.exists():
            self.stdout.write("\n   First 5 students:")
            for i, student in enumerate(students[:5], 1):
                self.stdout.write(f"      {i}. {student.get_full_name()}")
                self.stdout.write(f"         ID: {student.id}, Student ID: {student.student_id}")
                self.stdout.write(f"         Class: {student.get_class_level_display()}")
                self.stdout.write(f"         Gender: {student.get_gender_display()}")
        else:
            self.stdout.write("   ❌ No active students found!")
            
            if fix_data:
                self.stdout.write("   ⚠️  Cannot auto-create students - requires manual setup")
        
        return list(students)
    
    def check_attendance(self, student, academic_year, term, fix_data):
        """Check attendance for a student"""
        from core.models.academic import AcademicTerm
        from core.models.attendance import StudentAttendance  # FIXED
        
        self.stdout.write(f"\n3. ATTENDANCE FOR {student.get_full_name()}")
        self.stdout.write("-" * 40)
        
        # Find term
        formats = [academic_year, academic_year.replace('/', '-'), academic_year.replace('/', '_')]
        term_obj = None
        for fmt in formats:
            term_obj = AcademicTerm.objects.filter(academic_year=fmt, term=term).first()
            if term_obj:
                break
        
        if not term_obj:
            self.stdout.write("   ❌ Cannot check attendance - academic term not found")
            return
        
        # Check attendance linked to term
        term_attendance = StudentAttendance.objects.filter(student=student, term=term_obj)
        self.stdout.write(f"   Attendance linked to term: {term_attendance.count()} records")
        
        if term_attendance.exists():
            # Show status counts
            status_counts = term_attendance.values('status').annotate(count=Count('status'))
            for item in status_counts:
                self.stdout.write(f"      {item['status']}: {item['count']}")
            
            # Show first 3 records
            self.stdout.write("\n   First 3 records:")
            for att in term_attendance[:3]:
                self.stdout.write(f"      - {att.date}: {att.status}")
                if att.notes:
                    self.stdout.write(f"        Notes: {att.notes[:50]}...")
        else:
            self.stdout.write("   ❌ No attendance records linked to this term")
            
            # Check date range
            date_range_attendance = StudentAttendance.objects.filter(
                student=student,
                date__range=[term_obj.start_date, term_obj.end_date]
            )
            self.stdout.write(f"   Attendance in date range: {date_range_attendance.count()} records")
        
        # Check all attendance for this student
        all_attendance = StudentAttendance.objects.filter(student=student)
        self.stdout.write(f"\n   All attendance records: {all_attendance.count()}")
        
        if fix_data and term_attendance.count() == 0:
            self.create_sample_attendance(student, term_obj)
    
    def create_sample_attendance(self, student, term_obj):
        """Create sample attendance records"""
        from core.models.attendance import StudentAttendance  # FIXED
        
        self.stdout.write("   Creating sample attendance...")
        
        created_count = 0
        current_date = term_obj.start_date
        
        while current_date <= term_obj.end_date and created_count < 20:
            # Only create for weekdays
            if current_date.weekday() < 5:  # Monday-Friday
                status = 'present' if created_count % 10 != 0 else 'absent'
                
                att, created = StudentAttendance.objects.get_or_create(
                    student=student,
                    date=current_date,
                    term=term_obj,
                    defaults={
                        'status': status,
                        'notes': 'Sample data created by check_data command'
                    }
                )
                
                if created:
                    created_count += 1
            
            current_date += timedelta(days=1)
        
        self.stdout.write(f"   ✓ Created {created_count} attendance records")
    
    def check_grades(self, student, academic_year, term, fix_data):
        """Check grades for a student"""
        from core.models.grades import Grade
        from core.models.subject import Subject
        
        self.stdout.write(f"\n4. GRADES FOR {student.get_full_name()}")
        self.stdout.write("-" * 40)
        
        # Check grades for the specific period
        grades = Grade.objects.filter(
            student=student,
            academic_year=academic_year,
            term=term
        ).select_related('subject')
        
        self.stdout.write(f"   Grades for {academic_year} Term {term}: {grades.count()}")
        
        if grades.exists():
            self.stdout.write("\n   Grade Details:")
            for grade in grades:
                self.stdout.write(f"      - {grade.subject.name}:")
                self.stdout.write(f"        Homework: {grade.homework_percentage}%")
                self.stdout.write(f"        Classwork: {grade.classwork_percentage}%")
                self.stdout.write(f"        Test: {grade.test_percentage}%")
                self.stdout.write(f"        Exam: {grade.exam_percentage}%")
                self.stdout.write(f"        Total: {grade.total_score}%")
                self.stdout.write(f"        Grade: {grade.ges_grade} ({grade.letter_grade})")
                
                # Check if weighted contributions work
                try:
                    contributions = grade.get_weighted_contributions()
                    self.stdout.write(f"        Contributions: HW={contributions['homework']['contribution']}, "
                                     f"CW={contributions['classwork']['contribution']}")
                except Exception as e:
                    self.stdout.write(f"        ❌ Error getting contributions: {e}")
        else:
            self.stdout.write("   ❌ No grades found for this period")
            
            # Check any grades for this student
            all_grades = Grade.objects.filter(student=student)
            self.stdout.write(f"   All grades for student: {all_grades.count()}")
            
            if all_grades.exists():
                self.stdout.write("\n   Recent grades:")
                for grade in all_grades.order_by('-academic_year', '-term')[:3]:
                    self.stdout.write(f"      - {grade.academic_year} Term {grade.term}: "
                                     f"{grade.subject.name} - {grade.total_score}%")
            
            if fix_data:
                self.create_sample_grades(student, academic_year, term)
    
    def create_sample_grades(self, student, academic_year, term):
        """Create sample grades"""
        from core.models.grades import Grade
        from core.models.subject import Subject
        
        self.stdout.write("   Creating sample grades...")
        
        # Get subjects for student's class level
        subjects = Subject.objects.filter(class_level=student.class_level)[:3]
        
        if not subjects.exists():
            self.stdout.write("   ❌ No subjects found for student's class level")
            return
        
        created_count = 0
        for subject in subjects:
            grade, created = Grade.objects.get_or_create(
                student=student,
                subject=subject,
                academic_year=academic_year,
                term=term,
                defaults={
                    'homework_percentage': 75.0,
                    'classwork_percentage': 80.0,
                    'test_percentage': 70.0,
                    'exam_percentage': 85.0,
                    'class_level': student.class_level
                }
            )
            
            if created:
                # Calculate totals
                grade.calculate_total_score()
                grade.determine_grades()
                grade.save()
                created_count += 1
        
        self.stdout.write(f"   ✓ Created {created_count} grade records")
    
    def check_report_cards(self, student, academic_year, term, fix_data):
        """Check report cards"""
        from core.models.report_card import ReportCard
        
        self.stdout.write(f"\n5. REPORT CARDS FOR {student.get_full_name()}")
        self.stdout.write("-" * 40)
        
        # Check for existing report card
        report_card = ReportCard.objects.filter(
            student=student,
            academic_year=academic_year,
            term=term
        ).first()
        
        if report_card:
            self.stdout.write(f"   ✓ Found report card:")
            self.stdout.write(f"      ID: {report_card.id}")
            self.stdout.write(f"      Average Score: {report_card.average_score}%")
            self.stdout.write(f"      Overall Grade: {report_card.overall_grade}")
            self.stdout.write(f"      Published: {report_card.is_published}")
            self.stdout.write(f"      Created: {report_card.created_at}")
        else:
            self.stdout.write("   ❌ No report card found")
            
            if fix_data:
                self.stdout.write("   Creating report card...")
                try:
                    report_card = ReportCard.generate_report_card(
                        student=student,
                        academic_year=academic_year,
                        term=term
                    )
                    self.stdout.write(f"   ✓ Created report card with ID: {report_card.id}")
                    self.stdout.write(f"      Average: {report_card.average_score}%")
                    self.stdout.write(f"      Grade: {report_card.overall_grade}")
                except Exception as e:
                    self.stdout.write(f"   ❌ Error creating report card: {e}")
    
    def test_utility_functions(self, student, academic_year, term):
        """Test utility functions"""
        from core.utils.main import get_attendance_summary, get_student_position_in_class
        
        self.stdout.write(f"\n6. TESTING UTILITY FUNCTIONS")
        self.stdout.write("-" * 40)
        
        # Test attendance summary
        self.stdout.write("   Testing get_attendance_summary():")
        try:
            attendance_data = get_attendance_summary(student, academic_year, term)
            self.stdout.write(f"      Present Days: {attendance_data.get('present_days', 0)}")
            self.stdout.write(f"      Total Days: {attendance_data.get('total_days', 0)}")
            self.stdout.write(f"      Rate: {attendance_data.get('attendance_rate', 0)}%")
            self.stdout.write(f"      Status: {attendance_data.get('attendance_status', 'N/A')}")
            self.stdout.write(f"      GES Compliant: {attendance_data.get('is_ges_compliant', False)}")
        except Exception as e:
            self.stdout.write(f"      ❌ Error: {e}")
        
        # Test position in class
        self.stdout.write("\n   Testing get_student_position_in_class():")
        try:
            position = get_student_position_in_class(student, academic_year, term)
            self.stdout.write(f"      Position: {position}")
        except Exception as e:
            self.stdout.write(f"      ❌ Error: {e}")