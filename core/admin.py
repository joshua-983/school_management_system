from django.contrib import admin
from .models import (
    Student, ParentGuardian, Fee, Subject, Teacher,
    ClassAssignment, Assignment, StudentAssignment, Grade, ReportCard,
    AcademicTerm, AttendancePeriod, StudentAttendance, AttendanceSummary,
    Notification, AuditLog
)

# Student Admin
@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'first_name', 'last_name', 'class_level', 'date_of_birth')
    search_fields = ('student_id', 'first_name', 'last_name')
    list_filter = ('class_level', 'gender')
    ordering = ('class_level', 'last_name')

# Parent Admin
@admin.register(ParentGuardian)
class ParentGuardianAdmin(admin.ModelAdmin):
    list_display = ('full_name', 'student', 'relationship', 'phone_number')
    search_fields = ('full_name', 'student__first_name', 'student__last_name')
    raw_id_fields = ('student',)

# Academic Term Admin
@admin.register(AcademicTerm)
class AcademicTermAdmin(admin.ModelAdmin):
    list_display = ('term', 'academic_year', 'start_date', 'end_date', 'is_active')
    list_editable = ('is_active',)
    ordering = ('-academic_year', 'term')

# Attendance Period Admin
@admin.register(AttendancePeriod)
class AttendancePeriodAdmin(admin.ModelAdmin):
    list_display = ('period_type', 'term', 'start_date', 'end_date', 'is_locked')
    list_filter = ('period_type', 'term')
    ordering = ('-start_date',)

# Student Attendance Admin
@admin.register(StudentAttendance)
class StudentAttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'status', 'term', 'period', 'recorded_by')
    list_filter = ('status', 'term', 'period')
    search_fields = ('student__first_name', 'student__last_name')
    date_hierarchy = 'date'
    raw_id_fields = ('student', 'period', 'term', 'recorded_by')

# Attendance Summary Admin
@admin.register(AttendanceSummary)
class AttendanceSummaryAdmin(admin.ModelAdmin):
    list_display = ('student', 'term', 'period', 'days_present', 'days_absent', 'attendance_rate')
    list_filter = ('term', 'period')
    readonly_fields = ('attendance_rate',)
    search_fields = ('student__first_name', 'student__last_name')

# Register other models
admin.site.register(Fee)
admin.site.register(Subject)
admin.site.register(Teacher)
admin.site.register(ClassAssignment)
admin.site.register(Assignment)
admin.site.register(StudentAssignment)
admin.site.register(Grade)
admin.site.register(ReportCard)
admin.site.register(Notification)
admin.site.register(AuditLog)