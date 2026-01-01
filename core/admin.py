from django.contrib import admin
from django.shortcuts import redirect
from django.urls import reverse
from django.contrib import messages
from django.contrib.contenttypes.models import ContentType
from django import forms
from django.core.exceptions import ValidationError
from django.db.models import Q

from .models import (
    Student, AcademicTerm, Announcement, Assignment, AttendancePeriod,
    AttendanceSummary, AuditLog, ClassAssignment, Fee, FeeCategory, 
    FeePayment, Grade, Notification, ParentGuardian, ReportCard, 
    StudentAssignment, StudentAttendance, Subject, Teacher,
    SchoolConfiguration, AnalyticsCache, GradeAnalytics, AttendanceAnalytics,
    TimeSlot, Timetable, TimetableEntry
)

# ===========================================
# CUSTOM FORMS FOR VALIDATION
# ===========================================

class AssignmentAdminForm(forms.ModelForm):
    """Custom form for Assignment to prevent empty attachments"""
    class Meta:
        model = Assignment
        fields = '__all__'
    
    def clean_attachment(self):
        """Prevent empty string attachments and validate file uploads"""
        attachment = self.cleaned_data.get('attachment')
        
        # Check if attachment is being cleared (set to empty)
        if attachment is None or attachment == '':
            return None
        
        # Check if attachment has a name
        if attachment and hasattr(attachment, 'name'):
            if not attachment.name.strip():
                raise forms.ValidationError("Please select a valid file. The file name cannot be empty.")
            
            # Check file size
            if attachment.size == 0:
                raise forms.ValidationError("The selected file appears to be empty. Please select a valid file.")
            
            # Check file extension
            allowed_extensions = ['.pdf', '.doc', '.docx', '.txt', '.jpg', '.jpeg', '.png', '.xls', '.xlsx', '.ppt', '.pptx']
            file_extension = attachment.name.lower()
            if not any(file_extension.endswith(ext) for ext in allowed_extensions):
                raise forms.ValidationError(
                    f"File type not supported. Allowed types: {', '.join([ext.strip('.') for ext in allowed_extensions])}"
                )
        
        return attachment
    
    def clean(self):
        """Overall form validation"""
        cleaned_data = super().clean()
        
        # Ensure empty strings are converted to None
        if 'attachment' in cleaned_data and cleaned_data['attachment'] == '':
            cleaned_data['attachment'] = None
        
        return cleaned_data


# ===========================================
# ADMIN CLASSES
# ===========================================

@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    list_display = ('student_id', 'first_name', 'last_name', 'class_level', 'date_of_birth', 'is_active')
    search_fields = ('student_id', 'first_name', 'last_name', 'phone_number')
    list_filter = ('class_level', 'gender', 'is_active')
    ordering = ('class_level', 'last_name', 'first_name')
    list_per_page = 50


@admin.register(ParentGuardian)
class ParentGuardianAdmin(admin.ModelAdmin):
    list_display = ('get_user_full_name', 'get_relationship_display', 'get_students_list', 'is_emergency_contact', 'account_status')
    list_filter = ('relationship', 'is_emergency_contact', 'account_status', 'students__class_level')
    search_fields = ('user__first_name', 'user__last_name', 'students__first_name', 'students__last_name', 'phone_number', 'email')
    filter_horizontal = ('students',)
    list_per_page = 50
    
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
    list_display = ('term', 'academic_year', 'start_date', 'end_date', 'is_active', 'get_progress_percentage')
    list_editable = ('is_active',)
    ordering = ('-academic_year', 'term')
    search_fields = ('academic_year',)
    list_per_page = 20
    
    def get_progress_percentage(self, obj):
        return f"{obj.get_progress_percentage()}%"
    get_progress_percentage.short_description = 'Progress'


@admin.register(AttendancePeriod)
class AttendancePeriodAdmin(admin.ModelAdmin):
    list_display = ('period_type', 'name', 'term', 'start_date', 'end_date', 'is_locked', 'get_total_school_days')
    list_filter = ('period_type', 'term', 'is_locked')
    ordering = ('-start_date',)
    search_fields = ('name',)
    list_per_page = 20
    
    def get_total_school_days(self, obj):
        return obj.get_total_school_days()
    get_total_school_days.short_description = 'School Days'


@admin.register(StudentAttendance)
class StudentAttendanceAdmin(admin.ModelAdmin):
    list_display = ('student', 'date', 'status', 'term', 'period', 'recorded_by', 'is_ghana_school_day')
    list_filter = ('status', 'term', 'period', 'date')
    search_fields = ('student__first_name', 'student__last_name', 'student__student_id')
    date_hierarchy = 'date'
    raw_id_fields = ('student', 'period', 'term', 'recorded_by')
    list_per_page = 50
    
    def is_ghana_school_day(self, obj):
        return "✅" if obj.is_ghana_school_day() else "❌"
    is_ghana_school_day.short_description = 'Valid School Day'


@admin.register(AttendanceSummary)
class AttendanceSummaryAdmin(admin.ModelAdmin):
    list_display = ('student', 'term', 'period', 'days_present', 'days_absent', 'attendance_rate', 'get_ges_compliance')
    list_filter = ('term', 'period')
    readonly_fields = ('attendance_rate', 'present_rate', 'last_updated')
    search_fields = ('student__first_name', 'student__last_name', 'student__student_id')
    list_per_page = 30
    
    def get_ges_compliance(self, obj):
        return "✅" if obj.get_ges_compliance() else "❌"
    get_ges_compliance.short_description = 'GES Compliant'


@admin.register(FeeCategory)
class FeeCategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'default_amount', 'frequency', 'is_active', 'is_mandatory', 'applies_to_all', 'get_frequency_display_with_icon')
    list_filter = ('is_active', 'is_mandatory', 'frequency', 'applies_to_all')
    search_fields = ('name', 'description')
    list_editable = ('is_active', 'is_mandatory', 'default_amount')
    list_per_page = 20
    
    def get_frequency_display_with_icon(self, obj):
        return obj.get_frequency_display_with_icon()
    get_frequency_display_with_icon.short_description = 'Frequency'


@admin.register(Fee)
class FeeAdmin(admin.ModelAdmin):
    list_display = ('student', 'category', 'amount_payable', 'amount_paid', 'balance', 'payment_status', 'due_date', 'get_remaining_days')
    list_filter = ('payment_status', 'category', 'due_date', 'academic_year', 'term')
    search_fields = ('student__first_name', 'student__last_name', 'student__student_id', 'receipt_number')
    raw_id_fields = ('student', 'category', 'bill')
    list_per_page = 50
    
    def get_remaining_days(self, obj):
        return obj.get_remaining_days()
    get_remaining_days.short_description = 'Time Remaining'


@admin.register(FeePayment)
class FeePaymentAdmin(admin.ModelAdmin):
    list_display = ('fee', 'amount', 'payment_mode', 'payment_date', 'receipt_number', 'is_confirmed')
    list_filter = ('payment_mode', 'payment_date', 'is_confirmed')
    search_fields = ('fee__student__first_name', 'fee__student__last_name', 'receipt_number', 'bank_reference')
    raw_id_fields = ('fee', 'bill', 'recorded_by')
    date_hierarchy = 'payment_date'
    list_per_page = 50


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'action', 'model_name', 'object_id', 'timestamp', 'ip_address')
    list_filter = ('action', 'model_name', 'timestamp')
    search_fields = ('user__username', 'user__first_name', 'user__last_name', 'model_name', 'object_id')
    readonly_fields = ('user', 'action', 'model_name', 'object_id', 'timestamp', 'details', 'ip_address')
    date_hierarchy = 'timestamp'
    list_per_page = 100


@admin.register(Subject)
class SubjectAdmin(admin.ModelAdmin):
    list_display = ('name', 'code', 'is_active', 'get_assignment_count')
    search_fields = ('name', 'code')
    ordering = ('name',)
    list_filter = ('is_active',)
    list_editable = ('is_active',)
    list_per_page = 30
    
    def get_assignment_count(self, obj):
        return obj.get_assignment_count()
    get_assignment_count.short_description = 'Assignments'


@admin.register(Teacher)
class TeacherAdmin(admin.ModelAdmin):
    list_display = ['id', 'employee_id', 'get_first_name', 'get_last_name', 'get_email', 'is_active', 'is_class_teacher', 'date_of_joining']
    list_filter = ['is_active', 'is_class_teacher', 'class_levels', 'date_of_joining']
    search_fields = ['employee_id', 'user__first_name', 'user__last_name', 'user__email', 'phone_number']
    list_per_page = 50
    
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

    # Auto-generate employee ID
    def save_model(self, request, obj, form, change):
        if not obj.employee_id or obj.employee_id == 'temporary':
            current_year = str(timezone.now().year)
            
            # Find the highest sequence number
            last_teacher = Teacher.objects.filter(
                employee_id__startswith=f'TCH{current_year}'
            ).exclude(employee_id='temporary').order_by('-employee_id').first()
            
            if last_teacher:
                try:
                    last_sequence = int(last_teacher.employee_id[7:10])
                    new_sequence = last_sequence + 1
                except (ValueError, IndexError):
                    new_sequence = 1
            else:
                new_sequence = 1
            
            # Format: TCH + Year + 3-digit sequence
            obj.employee_id = f'TCH{current_year}{new_sequence:03d}'
            
            # Ensure uniqueness
            counter = 1
            original_id = obj.employee_id
            while Teacher.objects.filter(employee_id=obj.employee_id).exclude(pk=obj.pk).exists():
                new_sequence += 1
                obj.employee_id = f'TCH{current_year}{new_sequence:03d}'
                counter += 1
                if counter > 1000:
                    raise ValueError("Could not generate unique employee ID")
        
        super().save_model(request, obj, form, change)


@admin.register(ClassAssignment)
class ClassAssignmentAdmin(admin.ModelAdmin):
    list_display = ('class_level', 'subject', 'teacher', 'academic_year', 'is_active', 'get_students_count')
    list_filter = ('class_level', 'academic_year', 'is_active')
    raw_id_fields = ('teacher', 'subject')
    search_fields = ('subject__name', 'teacher__user__first_name', 'teacher__user__last_name')
    list_editable = ('is_active',)
    list_per_page = 30
    
    def get_students_count(self, obj):
        return obj.get_students_count()
    get_students_count.short_description = 'Students'


@admin.register(Assignment)
class AssignmentAdmin(admin.ModelAdmin):
    form = AssignmentAdminForm  # Use custom form for validation
    list_display = ('title', 'assignment_type', 'subject', 'class_assignment', 'due_date', 'has_attachment', 'is_active', 'get_completion_percentage')
    list_filter = ('assignment_type', 'subject', 'class_assignment', 'is_active')
    search_fields = ('title', 'description', 'instructions')
    raw_id_fields = ('class_assignment', 'subject')
    date_hierarchy = 'due_date'
    list_per_page = 30
    actions = ['fix_empty_attachments', 'toggle_active_status']
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('title', 'description', 'assignment_type', 'subject', 'class_assignment')
        }),
        ('Dates & Scoring', {
            'fields': ('due_date', 'max_score', 'weight', 'allow_late_submissions')
        }),
        ('Assignment Content', {
            'fields': ('attachment', 'instructions', 'learning_objectives', 'resources')
        }),
        ('Additional Materials', {
            'fields': ('rubric', 'sample_solution'),
            'classes': ('collapse',)
        }),
        ('Status', {
            'fields': ('is_active',)
        }),
    )
    
    # Custom method to show if assignment has attachment
    def has_attachment(self, obj):
        if obj.attachment and str(obj.attachment).strip():
            return "✅ Yes"
        return "❌ No"
    has_attachment.short_description = 'Has Document'
    
    # Custom method to show completion percentage
    def get_completion_percentage(self, obj):
        return f"{obj.get_completion_percentage()}%"
    get_completion_percentage.short_description = 'Completion'
    
    # Admin action to fix empty attachments
    def fix_empty_attachments(self, request, queryset):
        """Fix assignments with empty string attachments"""
        fixed_count = 0
        for assignment in queryset:
            if assignment.attachment == '':
                assignment.attachment = None
                assignment.save(update_fields=['attachment'])
                fixed_count += 1
        
        if fixed_count:
            self.message_user(request, f"✅ Fixed {fixed_count} assignments with empty attachments.")
        else:
            self.message_user(request, "ℹ️ No assignments with empty attachments found.")
    fix_empty_attachments.short_description = "Fix empty attachments"
    
    # Admin action to toggle active status
    def toggle_active_status(self, request, queryset):
        """Toggle is_active status for selected assignments"""
        updated_count = 0
        for assignment in queryset:
            assignment.is_active = not assignment.is_active
            assignment.save(update_fields=['is_active'])
            updated_count += 1
        
        self.message_user(request, f"✅ Updated {updated_count} assignments.")
    toggle_active_status.short_description = "Toggle active status"
    
    # Override save to auto-create student assignments
    def save_model(self, request, obj, form, change):
        # Ensure empty strings are converted to None
        if obj.attachment == '':
            obj.attachment = None
        
        # Save the assignment
        super().save_model(request, obj, form, change)
        
        # Only create student assignments for NEW assignments
        if not change:
            try:
                obj.create_student_assignments()
                self.message_user(request, f"✅ Created student assignments for {obj.get_students_count()} students.")
            except Exception as e:
                self.message_user(request, f"⚠️ Error creating student assignments: {str(e)}", level='error')


@admin.register(StudentAssignment)
class StudentAssignmentAdmin(admin.ModelAdmin):
    list_display = ('student', 'assignment', 'status', 'score', 'submitted_date', 'graded_date', 'is_overdue', 'get_priority_level')
    list_filter = ('status', 'assignment', 'assignment__subject')
    search_fields = ('student__first_name', 'student__last_name', 'assignment__title')
    raw_id_fields = ('student', 'assignment')
    list_per_page = 50
    actions = ['mark_as_graded', 'mark_as_pending']
    
    # Custom method to check if overdue
    def is_overdue(self, obj):
        return "✅" if obj.is_overdue() else "❌"
    is_overdue.short_description = 'Overdue'
    
    # Custom method to show priority level
    def get_priority_level(self, obj):
        return obj.get_priority_level().title()
    get_priority_level.short_description = 'Priority'
    
    # Admin action to mark as graded
    def mark_as_graded(self, request, queryset):
        """Mark selected student assignments as graded"""
        updated_count = 0
        for student_assignment in queryset:
            if student_assignment.status != 'GRADED':
                student_assignment.status = 'GRADED'
                student_assignment.graded_date = timezone.now()
                student_assignment.save()
                updated_count += 1
        
        self.message_user(request, f"✅ Marked {updated_count} assignments as graded.")
    mark_as_graded.short_description = "Mark as graded"
    
    # Admin action to mark as pending
    def mark_as_pending(self, request, queryset):
        """Mark selected student assignments as pending"""
        updated_count = 0
        for student_assignment in queryset:
            if student_assignment.status != 'PENDING':
                student_assignment.status = 'PENDING'
                student_assignment.graded_date = None
                student_assignment.save()
                updated_count += 1
        
        self.message_user(request, f"✅ Marked {updated_count} assignments as pending.")
    mark_as_pending.short_description = "Mark as pending"


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ('student', 'subject', 'academic_year', 'term', 'total_score', 'ges_grade', 'letter_grade', 'is_passing', 'requires_review')
    list_filter = ('academic_year', 'term', 'subject', 'ges_grade', 'requires_review')
    search_fields = ('student__first_name', 'student__last_name', 'subject__name')
    raw_id_fields = ('student', 'subject', 'class_assignment')
    list_per_page = 50
    actions = ['mark_for_review', 'clear_review_flag']
    
    # Custom method to check if passing
    def is_passing(self, obj):
        return "✅" if obj.is_passing() else "❌"
    is_passing.short_description = 'Passing'
    
    # Admin action to mark for review
    def mark_for_review(self, request, queryset):
        """Mark selected grades for review"""
        updated_count = queryset.update(requires_review=True)
        self.message_user(request, f"✅ Marked {updated_count} grades for review.")
    mark_for_review.short_description = "Mark for review"
    
    # Admin action to clear review flag
    def clear_review_flag(self, request, queryset):
        """Clear review flag from selected grades"""
        updated_count = queryset.update(requires_review=False)
        self.message_user(request, f"✅ Cleared review flag from {updated_count} grades.")
    clear_review_flag.short_description = "Clear review flag"


@admin.register(ReportCard)
class ReportCardAdmin(admin.ModelAdmin):
    list_display = ('student', 'academic_year', 'term', 'average_score', 'overall_grade', 'is_published', 'created_at')
    list_filter = ('academic_year', 'term', 'is_published')
    search_fields = ('student__first_name', 'student__last_name', 'student__student_id')
    raw_id_fields = ('student', 'created_by')
    list_per_page = 30
    actions = ['publish_report_cards', 'unpublish_report_cards']
    
    # Admin action to publish report cards
    def publish_report_cards(self, request, queryset):
        """Publish selected report cards"""
        updated_count = queryset.update(is_published=True)
        self.message_user(request, f"✅ Published {updated_count} report cards.")
    publish_report_cards.short_description = "Publish report cards"
    
    # Admin action to unpublish report cards
    def unpublish_report_cards(self, request, queryset):
        """Unpublish selected report cards"""
        updated_count = queryset.update(is_published=False)
        self.message_user(request, f"✅ Unpublished {updated_count} report cards.")
    unpublish_report_cards.short_description = "Unpublish report cards"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('recipient', 'notification_type', 'title', 'is_read', 'created_at', 'get_time_ago')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('recipient__username', 'recipient__email', 'title', 'message')
    raw_id_fields = ('recipient',)
    readonly_fields = ('created_at',)
    date_hierarchy = 'created_at'
    list_per_page = 50
    actions = ['mark_as_read', 'mark_as_unread']
    
    # Custom method to show time ago
    def get_time_ago(self, obj):
        from django.utils import timezone
        from datetime import timedelta
        
        now = timezone.now()
        diff = now - obj.created_at
        
        if diff.days > 0:
            return f"{diff.days} day{'s' if diff.days > 1 else ''} ago"
        elif diff.seconds > 3600:
            hours = diff.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        else:
            minutes = diff.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
    get_time_ago.short_description = 'Time Ago'
    
    # Admin action to mark as read
    def mark_as_read(self, request, queryset):
        """Mark selected notifications as read"""
        updated_count = queryset.update(is_read=True)
        self.message_user(request, f"✅ Marked {updated_count} notifications as read.")
    mark_as_read.short_description = "Mark as read"
    
    # Admin action to mark as unread
    def mark_as_unread(self, request, queryset):
        """Mark selected notifications as unread"""
        updated_count = queryset.update(is_read=False)
        self.message_user(request, f"✅ Marked {updated_count} notifications as unread.")
    mark_as_unread.short_description = "Mark as unread"


@admin.register(SchoolConfiguration)
class SchoolConfigurationAdmin(admin.ModelAdmin):
    list_display = ['grading_system', 'academic_year', 'current_term', 'is_locked', 'school_name']
    list_editable = ['is_locked', 'current_term']
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


@admin.register(Announcement)
class AnnouncementAdmin(admin.ModelAdmin):
    list_display = ('title', 'priority', 'target_roles', 'created_by', 'created_at', 'is_active', 'is_expired', 'views_count')
    list_filter = ('priority', 'target_roles', 'is_active', 'created_at')
    search_fields = ('title', 'message', 'created_by__username')
    list_editable = ('is_active', 'priority')
    date_hierarchy = 'created_at'
    list_per_page = 30
    
    # Custom method to check if expired
    def is_expired(self, obj):
        return "✅" if obj.is_expired() else "❌"
    is_expired.short_description = 'Expired'
    
    # Custom method to show views count
    def views_count(self, obj):
        return obj.views_count
    views_count.short_description = 'Views'


# ===========================================
# SIMPLER ADMIN CLASSES
# ===========================================

@admin.register(TimeSlot)
class TimeSlotAdmin(admin.ModelAdmin):
    list_display = ('period_number', 'start_time', 'end_time', 'is_break', 'break_name', 'is_active')
    list_filter = ('is_break', 'is_active')
    ordering = ('period_number',)
    list_editable = ('is_active', 'is_break')
    list_per_page = 20


@admin.register(Timetable)
class TimetableAdmin(admin.ModelAdmin):
    list_display = ('class_level', 'day_of_week', 'academic_year', 'term', 'is_active', 'created_by')
    list_filter = ('class_level', 'day_of_week', 'academic_year', 'term', 'is_active')
    search_fields = ('class_level', 'academic_year')
    ordering = ('class_level', 'day_of_week')
    list_editable = ('is_active',)
    list_per_page = 30


@admin.register(TimetableEntry)
class TimetableEntryAdmin(admin.ModelAdmin):
    list_display = ('timetable', 'time_slot', 'subject', 'teacher', 'classroom', 'is_break')
    list_filter = ('timetable__class_level', 'is_break', 'subject')
    search_fields = ('subject__name', 'teacher__user__first_name', 'teacher__user__last_name')
    raw_id_fields = ('timetable', 'time_slot', 'subject', 'teacher')
    list_per_page = 50


@admin.register(AnalyticsCache)
class AnalyticsCacheAdmin(admin.ModelAdmin):
    list_display = ('name', 'last_updated', 'created_at')
    search_fields = ('name',)
    readonly_fields = ('last_updated', 'created_at')
    list_per_page = 20


@admin.register(GradeAnalytics)
class GradeAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('class_level', 'subject', 'average_score', 'highest_score', 'lowest_score', 'date_calculated')
    list_filter = ('class_level', 'subject', 'date_calculated')
    search_fields = ('subject__name',)
    readonly_fields = ('date_calculated', 'created_at')
    list_per_page = 30


@admin.register(AttendanceAnalytics)
class AttendanceAnalyticsAdmin(admin.ModelAdmin):
    list_display = ('class_level', 'date', 'present_count', 'absent_count', 'attendance_rate')
    list_filter = ('class_level', 'date')
    date_hierarchy = 'date'
    readonly_fields = ('created_at',)
    list_per_page = 30


# ===========================================
# DATA CLEANUP ADMIN (NEW)
# ===========================================

    """Admin for data cleanup operations"""
    actions = ['cleanup_empty_attachments', 'recalculate_attendance_summaries', 'recalculate_grade_averages']
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def cleanup_empty_attachments(self, request, queryset):
        """Clean up ALL assignments with empty string attachments"""
        from core.models import Assignment
        
        # Find all assignments with empty string attachments
        empty_assignments = Assignment.objects.filter(Q(attachment='') | Q(attachment__isnull=True))
        fixed_count = 0
        
        for assignment in empty_assignments:
            assignment.attachment = None
            assignment.save()
            fixed_count += 1
        
        self.message_user(request, f"✅ Fixed {fixed_count} assignments with empty attachments.")
    
    def recalculate_attendance_summaries(self, request, queryset):
        """Recalculate attendance summaries for all terms"""
        from core.models import AttendanceSummary, AcademicTerm
        
        terms = AcademicTerm.objects.all()
        recalculated_count = 0
        
        for term in terms:
            summaries = AttendanceSummary.objects.filter(term=term)
            for summary in summaries:
                summary.calculate_summary()
                recalculated_count += 1
        
        self.message_user(request, f"✅ Recalculated {recalculated_count} attendance summaries.")
    
    def recalculate_grade_averages(self, request, queryset):
        """Recalculate report card averages"""
        from core.models import ReportCard
        
        report_cards = ReportCard.objects.all()
        recalculated_count = 0
        
        for report_card in report_cards:
            report_card.calculate_grades()
            report_card.save()
            recalculated_count += 1
        
        self.message_user(request, f"✅ Recalculated {recalculated_count} report cards.")
    
    cleanup_empty_attachments.short_description = "🚨 Fix ALL empty attachments"
    recalculate_attendance_summaries.short_description = "📊 Recalculate attendance summaries"
    recalculate_grade_averages.short_description = "📈 Recalculate grade averages"


from django.db import models

#     """Proxy model for data cleanup operations"""
#     class Meta:
#         verbose_name = "Data Maintenance"
#         verbose_name_plural = "Data Maintenance"
#         proxy = True
# 
# 

# ===========================================
# ADDITIONAL IMPORTS AND SETUP
# ===========================================

# Import timezone for use in methods
from django.utils import timezone

# Customize admin site header
admin.site.site_header = "Judith's School Management System"
admin.site.site_title = "School Admin"
admin.site.index_title = "Welcome to School Administration"

print("✅ Admin configuration loaded successfully!")
# Check for empty attachments and warn if any exist
try:
    from core.models import Assignment, StudentAssignment
    assignment_empty = Assignment.objects.filter(attachment='').count()
    student_empty = StudentAssignment.objects.filter(file='').count()
    total_empty = assignment_empty + student_empty
    if total_empty > 0:
        print(f"🚨 IMPORTANT: Found {total_empty} empty attachments/files. Go to 'Data Maintenance' and run 'Fix ALL empty attachments'")
    else:
        print("✅ No empty attachments found - all clean!")
except Exception as e:
    # If we can't check, show the generic warning
    print("🚨 IMPORTANT: To fix existing empty attachments, go to 'Data Maintenance' and run 'Fix ALL empty attachments'")
    print(f"   (Error checking: {e})")