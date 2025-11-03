from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from .models import (
    Student, AcademicTerm, Announcement, Assignment, AttendancePeriod,
    AttendanceSummary, AuditLog, ClassAssignment, Fee, FeeCategory, 
    FeePayment, Grade, Notification, ParentGuardian, ReportCard, 
    StudentAssignment, StudentAttendance, Subject, Teacher,
    SchoolConfiguration, AnalyticsCache, GradeAnalytics, AttendanceAnalytics,
    TimeSlot, Timetable, TimetableEntry
)

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'first_name', 'last_name', 'class_level', 'date_of_birth')
    search_fields = ('student_id', 'first_name', 'last_name')
    list_filter = ('class_level', 'gender')
    ordering = ('class_level', 'last_name')

@admin.register(ParentGuardian)
class ParentGuardianAdmin(admin.ModelAdmin):
    list_display = ('get_user_full_name', 'get_relationship_display', 'get_students_list', 'is_emergency_contact')
    list_filter = ('relationship', 'is_emergency_contact', 'students__class_level')
    search_fields = ('user__first_name', 'user__last_name', 'students__first_name', 'students__last_name', 'phone_number', 'email')
    filter_horizontal = ('students',)  # For better ManyToMany field interface
    
    # Custom method to display students
    def get_students_list(self, obj):
        return ", ".join([student.get_full_name() for student in obj.students.all()])
    get_students_list.short_description = 'Students'
    
    # Custom method to display user full name
    def get_user_full_name(self, obj):
        return obj.get_user_full_name()
    get_user_full_name.short_description = 'Parent/Guardian Name'

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
    list_display = ['id', 'get_first_name', 'get_last_name', 'get_email', 'is_active']
    list_filter = ['is_active', 'class_levels']
    search_fields = ['user__first_name', 'user__last_name', 'user__email']
    
    # Custom methods to access user fields
    def get_first_name(self, obj):
        return obj.user.first_name
    get_first_name.short_description = 'First Name'
    get_first_name.admin_order_field = 'user__first_name'
    
    def get_last_name(self, obj):
        return obj.user.last_name
    get_last_name.short_description = 'Last Name'
    get_last_name.admin_order_field = 'user__last_name'
    
    def get_email(self, obj):
        return obj.user.email
    get_email.short_description = 'Email'
    get_email.admin_order_field = 'user__email'

    # ADD THIS METHOD FOR AUTO EMPLOYEE ID GENERATION
    def save_model(self, request, obj, form, change):
        if not obj.employee_id:  # Only generate if not already set
            # Get the last teacher by ID
            last_teacher = Teacher.objects.order_by('-id').first()
            if last_teacher and last_teacher.employee_id.startswith('T'):
                try:
                    # Extract number from existing ID (e.g., "T001" -> 1)
                    last_number = int(last_teacher.employee_id[1:])
                    new_number = last_number + 1
                except ValueError:
                    new_number = 1
            else:
                new_number = 1
            # Format as T001, T002, etc.
            obj.employee_id = f"T{new_number:03d}"
        super().save_model(request, obj, form, change)

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
        if obj.total_score is None:
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
    get_grade.short_description = 'Grade'
    
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

@admin.register(SchoolConfiguration)
class SchoolConfigurationAdmin(admin.ModelAdmin):
    list_display = ['grading_system', 'academic_year', 'current_term', 'is_locked']
    list_editable = ['is_locked']
    fieldsets = (
        ('Grading System Configuration', {
            'fields': ('grading_system', 'is_locked'),
            'description': 'Configure the grading system used throughout the application.'
        }),
        ('Academic Information', {
            'fields': ('academic_year', 'current_term')
        }),
        ('School Information', {
            'fields': ('school_name', 'school_address', 'school_phone', 'school_email', 'principal_name')
        }),
    )
    
    def has_add_permission(self, request):
        # Only allow one configuration instance
        return not SchoolConfiguration.objects.exists()


# Register models without custom admin classes
admin.site.register(AnalyticsCache)
admin.site.register(GradeAnalytics)
admin.site.register(AttendanceAnalytics)
admin.site.register(TimeSlot)
admin.site.register(Timetable)
admin.site.register(TimetableEntry)
admin.site.register(Announcement)



