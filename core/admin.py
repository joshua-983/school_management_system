from django.contrib import admin
from django.contrib.contenttypes.models import ContentType
from .models import (
    Student, AcademicTerm, Announcement, Assignment, AttendancePeriod,
    AttendanceSummary, AuditLog,  ClassAssignment, 
     Fee, FeeCategory, FeePayment, Grade, Notification,
    ParentGuardian, ReportCard, StudentAssignment, StudentAttendance,
    Subject, Teacher
)

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'first_name', 'last_name', 'class_level', 'date_of_birth')
    search_fields = ('student_id', 'first_name', 'last_name')
    list_filter = ('class_level', 'gender')
    ordering = ('class_level', 'last_name')

@admin.register(ParentGuardian)
class ParentGuardianAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'relationship', 'student', 'is_emergency_contact')
    search_fields = ('full_name', 'student__first_name', 'student__last_name')
    raw_id_fields = ('student',)

@admin.register(AcademicTerm)
class AcademicTermAdmin(admin.ModelAdmin):
    list_display = ('term', 'academic_year', 'start_date', 'end_date', 'is_active')
    list_editable = ('is_active',)
    ordering = ('-academic_year', 'term')

@admin.register(AttendancePeriod)
class AttendancePeriodAdmin(admin.ModelAdmin):
    list_display = ('period_type', 'term', 'start_date', 'end_date', 'is_locked')
    list_filter = ('period_type', 'term')
    ordering = ('-start_date',)

@admin.register(StudentAttendance)
class StudentAttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'status', 'term', 'period', 'recorded_by')
    list_filter = ('status', 'term', 'period')
    search_fields = ('student__first_name', 'student__last_name')
    date_hierarchy = 'date'
    raw_id_fields = ('student', 'period', 'term', 'recorded_by')

@admin.register(AttendanceSummary)
class AttendanceSummaryAdmin(admin.ModelAdmin):
    list_display = ('student', 'term', 'period', 'days_present', 'days_absent', 'attendance_rate')
    list_filter = ('term', 'period')
    readonly_fields = ('attendance_rate',)
    search_fields = ('student__first_name', 'student__last_name')

@admin.register(FeeCategory)
class FeeCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'is_active', 'is_mandatory')
    search_fields = ('name',)
    list_filter = ('is_active', 'is_mandatory')

@admin.register(Fee)
class FeeAdmin(admin.ModelAdmin):
    list_display = ('student', 'category', 'amount_payable', 'amount_paid', 'balance', 'payment_status', 'due_date')
    list_filter = ('payment_status', 'category', 'due_date')
    search_fields = ('student__first_name', 'student__last_name', 'student__student_id')
    raw_id_fields = ('student',)

@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = ('fee', 'amount', 'payment_mode', 'payment_date', 'receipt_number')
    list_filter = ('payment_mode', 'payment_date')
    search_fields = ('fee__student__first_name', 'fee__student__last_name', 'receipt_number')
    raw_id_fields = ('fee', 'recorded_by')



@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'model_name', 'object_id', 'timestamp')
    list_filter = ('action', 'model_name', 'timestamp')
    search_fields = ('user__username', 'user__first_name', 'user__last_name')
    readonly_fields = ('user', 'action', 'model_name', 'object_id', 'timestamp', 'details')
    date_hierarchy = 'timestamp'

@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')
    ordering = ('name',)

@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ('user', 'first_name', 'last_name', 'is_active')
    search_fields = ('first_name', 'last_name', 'user__username')
    list_filter = ('is_active',)
    raw_id_fields = ('user',)

@admin.register(ClassAssignment)
class ClassAssignmentAdmin(admin.ModelAdmin):
    list_display = ('class_level', 'subject', 'teacher', 'academic_year')
    list_filter = ('class_level', 'academic_year')
    raw_id_fields = ('teacher', 'subject')

@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    list_display = ('title', 'assignment_type', 'subject', 'class_assignment', 'due_date')
    list_filter = ('assignment_type', 'subject', 'class_assignment')
    search_fields = ('title', 'description')
    raw_id_fields = ('class_assignment', 'subject')

@admin.register(StudentAssignment)
class StudentAssignmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'assignment', 'status', 'score')
    list_filter = ('status', 'assignment')
    search_fields = ('student__first_name', 'student__last_name')
    raw_id_fields = ('student', 'assignment')

@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'academic_year', 'term', 'total_score', 'get_grade')
    list_filter = ('academic_year', 'term', 'subject')
    search_fields = ('student__first_name', 'student__last_name')
    raw_id_fields = ('student', 'subject', 'class_assignment')

    def get_grade(self, obj):
        """
        Converts total_score to a letter grade (A, B, C, etc.).
        - Adjust thresholds as needed.
        - Handles null/0 scores safely.
        """
        if obj.total_score is None:  # Handle missing scores
            return "N/A"
        if obj.total_score >= 90:
            return "A"
        elif obj.total_score >= 80:
            return "B"
        elif obj.total_score >= 70:
            return "C"
        elif obj.total_score >= 60:
            return "D"
        else:
            return "F"
    get_grade.short_description = 'Grade'  # Sets column header
    
@admin.register(ReportCard)
class ReportCardAdmin(admin.ModelAdmin):
    list_display = ('student', 'academic_year', 'term', 'is_published')
    list_filter = ('academic_year', 'term', 'is_published')
    search_fields = ('student__first_name', 'student__last_name')
    raw_id_fields = ('student',)

@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'notification_type', 'title', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('recipient__username', 'title')
    raw_id_fields = ('recipient',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
