# core/urls.py - COMPLETE CORRECTED VERSION
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from django.http import HttpResponseForbidden
from datetime import timedelta
from . import views
from .views.network_views import NetworkHealthView
from accounts import views as accounts_views
from .views.base_views import dashboard, home, admin_dashboard, teacher_dashboard, student_dashboard, parent_dashboard
from .views.fee_views import ClearImportResultsView
from . import views_group_management
from core.models import Teacher
from .views.grade_views import student_subject_grades

from django.views.generic import RedirectView, TemplateView

from .views.backup_views import (
    backup_dashboard, create_backup, download_backup, 
    delete_backup, cleanup_old_backups
)

from .api_views import (
    StudentListAPIView, AcademicTermAPIView, 
    ActiveStudentsAPIView, ParentChildrenAPIView, ParentDashboardAPIView,
    ParentProfileAPIView, ParentAccountStatusAPIView, ParentRegistrationAPIView,
    ParentStatsAPIView
)

# Import teacher views
from .views.teacher_views import (
    TeacherListView, TeacherCreateView, TeacherUpdateView, TeacherDeleteView,
    TeacherAssignmentAnalyticsView, TeacherDetailAnalyticsView
)

# Import student views
from .views.student_views import (
    StudentListView, StudentDetailView, StudentCreateView, StudentUpdateView, 
    StudentDeleteView, StudentGradeListView, StudentAttendanceView, 
    StudentFeeListView, StudentProfileView, StudentDashboardView,
    StudentParentManagementView, StudentAssignmentDocumentView, StudentAssignmentLibraryView,
    StudentAssignmentDetailView, StudentGradedAssignmentsView, StudentSubmittedAssignmentsView,
    DownloadAssignmentDocumentView,
)

# ==============================
# PARENT MANAGEMENT VIEWS (Admin/Teacher)
# ==============================
from .parent_management_views import (
    parent_management_dashboard, parent_account_management, parent_directory,
    admin_parent_create, bulk_parent_creation, bulk_parent_invite,
    activate_parent_account, suspend_parent_account, send_parent_message,
    bulk_parent_message, parent_communication_log, parent_engagement_dashboard,
    export_parent_data, parent_registration_management
)

# ==============================
# PARENT PORTAL VIEWS (Parent Access)
# ==============================
from .views.parents_views import (
    ParentCreateView, ParentUpdateView, ParentDeleteView,
    ParentChildrenListView, ParentChildDetailView, ParentFeeListView, ParentFeeDetailView,
    ParentFeePaymentView, ParentAttendanceListView, ParentReportCardListView, ParentReportCardDetailView,
    ParentAnnouncementListView, ParentMessageListView,
    ParentMessageCreateView, ParentMessageDetailView, ParentCalendarView,
    ParentDirectoryView, BulkParentMessageView, ParentCommunicationLogView, ParentEngagementDashboardView,
    ParentFeeStatementView, BulkMessageResultsView, ParentMessageAnalyticsView
)

# ==============================
# PARENT AUTHENTICATION VIEWS
# ==============================
from .parent_auth_views import (
    ParentRegistrationView, ParentLoginView, ParentLogoutView,
    ParentProfileView, ParentRegistrationSuccessView, ParentPasswordResetView
)

from .views.fee_views import (
    FeeCategoryListView, FeeCategoryCreateView, FeeCategoryUpdateView, FeeCategoryDeleteView,
    FeeListView, FeeDetailView, FeeCreateView, FeeUpdateView, FeeDeleteView,
    FeePaymentCreateView, FeePaymentDeleteView, FeeReportView, FeeDashboardView,
    FeeStatusReportView, GenerateTermFeesView,
    BulkFeeUpdateView, SendPaymentRemindersView, FeeAnalyticsView,
    FinanceDashboardView, RevenueAnalyticsView, FinancialHealthView,
    PaymentSummaryView, RefreshPaymentDataView,
    BulkFeeImportView, BulkFeeCreationView, DownloadFeeTemplateView
)

from .views.budget_views import (
    BudgetManagementView, BudgetCreateView, BudgetUpdateView, BudgetDeleteView
)

from .views.subjects_views import SubjectListView, SubjectDetailView, SubjectCreateView, SubjectUpdateView, SubjectDeleteView
from .views.class_assignments import (
    ClassAssignmentListView, ClassAssignmentCreateView, ClassAssignmentUpdateView, 
    ClassAssignmentDeleteView, get_assignment_students, TeacherQualificationUpdateView,
    get_teacher_qualifications, assignment_statistics, QuickClassAssignmentCreateView,
    bulk_delete_assignments, toggle_assignment_status, ExportAssignmentsView, debug_database_stats
)

from .views.assignment_views import (
    AssignmentListView, AssignmentDetailView, AssignmentCreateView, 
    AssignmentUpdateView, AssignmentDeleteView, SubmitAssignmentView,
    AssignmentCalendarView, AssignmentEventJsonView,
    GradeAssignmentView, BulkGradeAssignmentView, AssignmentAnalyticsView, AssignmentExportView,
    AssignmentCreateSelectionView, QuickClassAssignmentView
)

# ==============================
# GRADE VIEWS
# ==============================
from .views.grade_views import (
    GradeListView, GradeDetailView, GradeCreateView, GradeUpdateView, GradeDeleteView,
    GradeEntryView, GradeReportView, BestStudentsView,
    PromotionListView, PromotionCheckView, PromoteStudentsView, PromotionConfigurationView,
    BulkGradeUploadView, GradeUploadTemplateView, BulkUploadProgressAPI,
    GradeConfigurationView,
    CalculateGradeAPI, calculate_total_score, check_existing_grade,
    get_students_by_class, get_subjects_by_class,
    StudentGradeSummaryAPI,
    lock_grade, unlock_grade, mark_grade_for_review, clear_grade_review,
    GradeExportView,
    GradingQueueView, GradeCalculatorView,
    GradeValidationAPI, GradeStatisticsAPI, ClearGradeCacheView,
    grade_delete,
    student_subject_grades,
)

# ==============================
# REPORT CARD VIEWS
# ==============================
from .views.reportcard_views import (
    ReportCardDashboardView, CreateReportCardView, ReportCardView, 
    ReportCardPDFView, SaveReportCardView,
    QuickViewReportCardView, QuickViewReportCardPDFView, AddGradeView,
    publish_report_card,
    force_recalculate_reportcards,
    report_card_statistics_debug
)

from .views.analytics_views import ComprehensiveAnalyticsDashboardView

from .views.audit_views import (
    AuditLogListView, AuditLogDetailView, AuditDashboardView, 
    audit_export_csv, audit_statistics_api, user_activity_report, 
    system_health_check, student_progress_chart, class_performance_chart
)

# ==============================
# AUDIT ENHANCEMENT VIEWS
# ==============================
from .views.audit_enhancements import (
    SecurityEventListView, SecurityEventDetailView,
    AuditAlertRuleListView, AuditAlertRuleCreateView, AuditAlertRuleUpdateView,
    AdvancedAnalyticsView, AuditReportListView, DataRetentionPolicyListView,
    run_anomaly_detection, generate_custom_report, apply_retention_policies,
    resolve_security_event, toggle_alert_rule
)

from .views.attendance_views import AttendanceDashboardView, AttendanceRecordView, load_periods, StudentAttendanceListView

# ==============================
# TIMETABLE VIEWS
# ==============================
from .views.timetable_views import (
    TimeSlotListView, TimeSlotCreateView, TimeSlotUpdateView, TimeSlotDeleteView,
    TimetableListView, TimetableCreateView, TimetableDetailView, TimetableManageView, TimetableDeleteView,
    StudentTimetableView, TeacherTimetableView, get_timetable_entries, generate_weekly_timetable,
    TeacherTimetableListView, TeacherTimetableDetailView, TimetableUpdateView,
    TimetableCalendarView, print_timetable, get_subjects_for_class, get_available_teachers,
    calendar_data, day_events, event_details, export_calendar,
    timetable_archive_view, timetable_deactivate_view, timetable_duplicate_view, print_weekly_timetable,
    get_class_details, get_subject_details, get_assignment_details,
    add_class_resource, get_class_resources, add_class_note, send_class_announcement,
    export_student_list, get_attendance_form
)

from .views.notifications_views import (
    NotificationListView, 
    mark_notification_read, 
    mark_all_notifications_read,
    get_unread_count
)

# ==============================
# BILL VIEWS
# ==============================
from .views.bill_views import (
    BillListView, BillDetailView, BillGenerateView, BillPaymentView, BillCancelView,
    BulkSendRemindersView, BulkExportBillsView, BulkMarkPaidView, BulkDeleteBillsView,
    BillPaymentCreateView
)

# ==============================
# ANNOUNCEMENT VIEWS
# ==============================
from .views.announcement_views import (
    AnnouncementListView, CreateAnnouncementView, UpdateAnnouncementView, 
    DeleteAnnouncementView, get_active_announcements, dismiss_announcement, 
    dismiss_all_announcements, announcement_detail, toggle_announcement_status,
    bulk_action_announcements, AnnouncementStatsView,
    active_announcements
)

# ==============================
# SECURITY VIEWS
# ==============================
from .views.security_views import (
    security_dashboard, UserManagementView, BlockUserView,
    MaintenanceModeView, ScheduledMaintenanceView, maintenance_mode_page,
    user_blocked_page, security_stats_api, user_details_api, RateLimitExceededView,
    SecuritySettingsView, security_events_api, maintenance_details_api, security_events, alert_rule_list,
    security_status_api, security_notifications_api, emergency_maintenance_bypass, clear_maintenance_bypass,
    axes_lockout_management, unlock_user_api, locked_users_api, unlock_all_users_api,
    system_health_api
)

# Import API views
from .api import FeeCategoryViewSet
from .views.api import fee_category_detail

router = DefaultRouter()
router.register(r'fee-categories', FeeCategoryViewSet, basename='fee-category')

# Create aliases for backward compatibility
audit_security_dashboard = security_dashboard
audit_security_stats_api = security_stats_api
audit_security_notifications_api = security_notifications_api
audit_system_health_api = system_health_api

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    
    # ==============================
    # HOME & DASHBOARDS
    # ==============================
    path('', home, name='home'),
    path('dashboard/', dashboard, name='dashboard'),
    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),
    path('teacher-dashboard/', teacher_dashboard, name='teacher_dashboard'),
    path('student-dashboard/', student_dashboard, name='student_dashboard'),
    path('parent-dashboard/', parent_dashboard, name='parent_dashboard'),  # Function-based dashboard
    
    # ==============================
    # PASSWORD CHANGE
    # ==============================
    path('password-change/', accounts_views.password_change, name='password_change'),
    path('password-change/done/', accounts_views.password_change_done, name='password_change_done'),
    path('accounts/password-change/', accounts_views.PasswordChangeView.as_view(), name='accounts_password_change'),
    
    # ==============================
    # STUDENT MANAGEMENT (Admin/Teacher)
    # ==============================
    path('students/', include([
        path('', StudentListView.as_view(), name='student_list'),
        path('add/', StudentCreateView.as_view(), name='student_add'),
        path('<int:pk>/', StudentDetailView.as_view(), name='student_detail'),
        path('<int:pk>/edit/', StudentUpdateView.as_view(), name='student_update'),
        path('<int:pk>/delete/', StudentDeleteView.as_view(), name='student_delete'),
        path('<int:pk>/parents/', StudentParentManagementView.as_view(), name='student_parent_management'),
        path('<int:student_id>/parents/add/', ParentCreateView.as_view(), name='parent_create_for_student'),
        path('<int:student_id>/fees/add/', FeeCreateView.as_view(), name='fee_create'),
        path('<int:student_id>/attendance/', AttendanceDashboardView.as_view(), name='student_attendance_summary'),
        path('submit/<int:pk>/', SubmitAssignmentView.as_view(), name='student_submit_assignment'),
    ])),
    
    # ==============================
    # STUDENT PORTAL (Student Access)
    # ==============================
    path('student-portal/', include([
        path('dashboard/', StudentDashboardView.as_view(), name='student_portal_dashboard'),
        path('profile/', StudentProfileView.as_view(), name='student_portal_profile'),
        path('grades/', StudentGradeListView.as_view(), name='student_portal_grades'),
        path('attendance/', StudentAttendanceView.as_view(), name='student_portal_attendance'),
        path('fees/', StudentFeeListView.as_view(), name='student_portal_fees'),
        
        # Student Assignments
        path('assignments/', include([
            path('', StudentAssignmentLibraryView.as_view(), name='student_portal_assignments'),
            path('documents/', StudentAssignmentDocumentView.as_view(), name='student_portal_documents'),
            path('graded/', StudentGradedAssignmentsView.as_view(), name='student_portal_graded'),
            path('submitted/', StudentSubmittedAssignmentsView.as_view(), name='student_portal_submitted'),
            path('<int:pk>/', StudentAssignmentDetailView.as_view(), name='student_portal_assignment_detail'),
            path('<int:pk>/download/', DownloadAssignmentDocumentView.as_view(), name='student_portal_download'),
        ])),
    ])),
    
    # ==============================
    # PARENT AUTHENTICATION
    # ==============================
    path('parents/auth/', include([
        path('register/', ParentRegistrationView.as_view(), name='parent_register'),
        path('login/', ParentLoginView.as_view(), name='parent_login'),
        path('logout/', ParentLogoutView.as_view(), name='parent_logout'),
        path('profile/', ParentProfileView.as_view(), name='parent_profile'),
        path('registration/success/', ParentRegistrationSuccessView.as_view(), name='parent_registration_success'),
        path('password/reset/', ParentPasswordResetView.as_view(), name='parent_password_reset'),
    ])),
    
    # ==============================
    # PARENT PORTAL (Parent Access Only) - CLEAN STRUCTURE
    # ==============================
    path('parent-portal/', include([
        path('dashboard/', ParentChildrenListView.as_view(), name='parent_portal_dashboard'),  # List children as dashboard
        path('children/', ParentChildrenListView.as_view(), name='parent_portal_children'),
        path('children/<int:pk>/', ParentChildDetailView.as_view(), name='parent_portal_child_detail'),
        
        # Financial
        path('fees/', ParentFeeListView.as_view(), name='parent_portal_fees'),
        path('fees/<int:pk>/', ParentFeeDetailView.as_view(), name='parent_portal_fee_detail'),
        path('fees/<int:pk>/pay/', ParentFeePaymentView.as_view(), name='parent_portal_fee_payment'),
        path('fees/statement/<int:pk>/', ParentFeeStatementView.as_view(), name='parent_portal_fee_statement'),
        
        # Academic
        path('attendance/', ParentAttendanceListView.as_view(), name='parent_portal_attendance'),
        path('report-cards/', ParentReportCardListView.as_view(), name='parent_portal_report_cards'),
        path('report-cards/<int:student_id>/', ParentReportCardDetailView.as_view(), name='parent_portal_report_card'),
        path('report-cards/<int:student_id>/<int:report_card_id>/', ParentReportCardDetailView.as_view(), name='parent_portal_report_card_detail'),
        
        # Communication
        path('announcements/', ParentAnnouncementListView.as_view(), name='parent_portal_announcements'),
        path('messages/', ParentMessageListView.as_view(), name='parent_portal_messages'),
        path('messages/create/', ParentMessageCreateView.as_view(), name='parent_portal_message_create'),
        path('messages/<int:pk>/', ParentMessageDetailView.as_view(), name='parent_portal_message_detail'),
        
        # Calendar
        path('calendar/', ParentCalendarView.as_view(), name='parent_portal_calendar'),
    ])),
    
    # ==============================
    # PARENT MANAGEMENT (Admin/Teacher Only) - CLEAN STRUCTURE
    # ==============================
    path('management/parents/', include([
        # Dashboard & Overview
        path('', parent_management_dashboard, name='parent_management_dashboard'),
        path('dashboard/', ParentEngagementDashboardView.as_view(), name='parent_engagement_dashboard'),
        
        # Account Management
        path('accounts/', parent_account_management, name='parent_account_management'),
        path('registration/', parent_registration_management, name='parent_registration_management'),
        
        # Directory & Search
        path('directory/', ParentDirectoryView.as_view(), name='parent_directory'),
        
        # Create Parents
        path('create/', admin_parent_create, name='admin_parent_create'),
        path('create/<int:student_id>/', admin_parent_create, name='admin_parent_create_for_student'),
        path('bulk-create/', bulk_parent_creation, name='bulk_parent_creation'),
        path('bulk-invite/', bulk_parent_invite, name='bulk_parent_invite'),
        
        # Individual Parent Actions (Admin)
        path('<int:pk>/edit/', ParentUpdateView.as_view(), name='parent_update'),
        path('<int:pk>/delete/', ParentDeleteView.as_view(), name='parent_delete'),
        path('<int:parent_id>/activate/', activate_parent_account, name='activate_parent_account'),
        path('<int:parent_id>/suspend/', suspend_parent_account, name='suspend_parent_account'),
        path('<int:parent_id>/message/', send_parent_message, name='send_parent_message'),
        
        # Communication
        path('bulk-message/', BulkParentMessageView.as_view(), name='bulk_parent_message'),
        path('communication-log/', ParentCommunicationLogView.as_view(), name='parent_communication_log'),
        
        path('bulk-message-results/', BulkMessageResultsView.as_view(), name='parent_bulk_message_results'),
        path('message-analytics/', ParentMessageAnalyticsView.as_view(), name='parent_message_analytics'),
        
        # Export & Reports
        path('export/', export_parent_data, name='export_parent_data'),
    ])),
    
    # ==============================
    # FEE MANAGEMENT
    # ==============================
    path('fees/', include([
        path('', FeeListView.as_view(), name='fee_list'),
        path('dashboard/', FeeDashboardView.as_view(), name='fee_dashboard'),
        path('<int:pk>/', FeeDetailView.as_view(), name='fee_detail'),
        path('<int:pk>/edit/', FeeUpdateView.as_view(), name='fee_update'),
        path('<int:pk>/delete/', FeeDeleteView.as_view(), name='fee_delete'),
        path('<int:fee_id>/payments/add/', FeePaymentCreateView.as_view(), name='fee_payment_create'),
        path('generate-term-fees/', GenerateTermFeesView.as_view(), name='generate_term_fees'),
        path('bulk-update/', BulkFeeUpdateView.as_view(), name='bulk_fee_update'),
        path('send-reminders/', SendPaymentRemindersView.as_view(), name='send_payment_reminders'),
        path('bulk-import/', BulkFeeImportView.as_view(), name='bulk_fee_import'),
        path('bulk-creation/', BulkFeeCreationView.as_view(), name='bulk_fee_creation'),
        path('download-template/<str:file_type>/', DownloadFeeTemplateView.as_view(), name='download_fee_template'),
    ])),
    
    # Fee Categories
    path('fee-categories/', include([
        path('', FeeCategoryListView.as_view(), name='fee_category_list'),
        path('add/', FeeCategoryCreateView.as_view(), name='fee_category_create'),
        path('<int:pk>/edit/', FeeCategoryUpdateView.as_view(), name='fee_category_update'),
        path('<int:pk>/delete/', FeeCategoryDeleteView.as_view(), name='fee_category_delete'),
    ])),
    
    # ==============================
    # BILL MANAGEMENT
    # ==============================
    path('bills/', include([
        path('', BillListView.as_view(), name='bill_list'),
        path('<int:pk>/', BillDetailView.as_view(), name='bill_detail'),
        path('generate/', BillGenerateView.as_view(), name='bill_generate'),
        path('<int:pk>/payment/', BillPaymentView.as_view(), name='bill_payment'),
        path('<int:pk>/cancel/', BillCancelView.as_view(), name='bill_cancel'),
        path('<int:bill_id>/payments/add/', BillPaymentCreateView.as_view(), name='bill_payment_create'),
        # Bulk actions
        path('bulk/send-reminders/', BulkSendRemindersView.as_view(), name='bulk_send_reminders'),
        path('bulk/export/', BulkExportBillsView.as_view(), name='bulk_export_bills'),
        path('bulk/mark-paid/', BulkMarkPaidView.as_view(), name='bulk_mark_paid'),
        path('bulk/delete/', BulkDeleteBillsView.as_view(), name='bulk_delete_bills'),
    ])),
    
    # ==============================
    # FINANCE MANAGEMENT
    # ==============================
    path('finance/', include([
        path('dashboard/', FinanceDashboardView.as_view(), name='finance_dashboard'),
        path('revenue-analytics/', RevenueAnalyticsView.as_view(), name='revenue_analytics'),
        path('financial-health/', FinancialHealthView.as_view(), name='financial_health'),
        path('payment-summary/', PaymentSummaryView.as_view(), name='payment_summary'),
        path('payment-summary/refresh/', RefreshPaymentDataView.as_view(), name='refresh_payment_data'),
    ])),
    
    # Budget Management
    path('finance/budget/', include([
        path('', BudgetManagementView.as_view(), name='budget_management'),
        path('create/', BudgetCreateView.as_view(), name='budget_create'),
        path('<int:pk>/update/', BudgetUpdateView.as_view(), name='budget_update'),
        path('<int:pk>/delete/', BudgetDeleteView.as_view(), name='budget_delete'),
    ])),
    
    # Fee Reports & Analytics
    path('reports/', include([
        path('fees/', FeeReportView.as_view(), name='fee_report'),
        path('fee-status/', FeeStatusReportView.as_view(), name='fee_status_report'),
        path('fee-analytics/', FeeAnalyticsView.as_view(), name='fee_analytics'),
    ])),
    
    # ==============================
    # SUBJECT MANAGEMENT
    # ==============================
    path('subjects/', include([
        path('', SubjectListView.as_view(), name='subject_list'),
        path('add/', SubjectCreateView.as_view(), name='subject_add'),
        path('<int:pk>/', SubjectDetailView.as_view(), name='subject_detail'),
        path('<int:pk>/edit/', SubjectUpdateView.as_view(), name='subject_edit'),
        path('<int:pk>/delete/', SubjectDeleteView.as_view(), name='subject_delete'),
    ])),
    
    # ==============================
    # TEACHER MANAGEMENT
    # ==============================
    path('teachers/', include([
        path('', TeacherListView.as_view(), name='teacher_list'),
        path('add/', TeacherCreateView.as_view(), name='teacher_add'),
        path('<int:pk>/edit/', TeacherUpdateView.as_view(), name='teacher_edit'),
        path('<int:pk>/delete/', TeacherDeleteView.as_view(), name='teacher_delete'),
        path('analytics/', TeacherAssignmentAnalyticsView.as_view(), name='teacher_analytics'),
        path('<int:pk>/analytics/', TeacherDetailAnalyticsView.as_view(), name='teacher_analytics_detail'),
    ])),
    
    # ==============================
    # CLASS ASSIGNMENTS
    # ==============================
    path('class-assignments/', include([
        path('', ClassAssignmentListView.as_view(), name='class_assignment_list'),
        path('create/', ClassAssignmentCreateView.as_view(), name='class_assignment_create'),
        path('quick-create/', QuickClassAssignmentCreateView.as_view(), name='quick_class_assignment_create'),
        path('<int:pk>/update/', ClassAssignmentUpdateView.as_view(), name='class_assignment_update'),
        path('<int:pk>/delete/', ClassAssignmentDeleteView.as_view(), name='class_assignment_delete'),
        # Teacher qualifications
        path('teachers/<int:teacher_id>/qualifications/', TeacherQualificationUpdateView.as_view(), name='teacher_qualifications_update'),
        # API endpoints
        path('<int:assignment_id>/students/', get_assignment_students, name='assignment_students'),
        path('statistics/', assignment_statistics, name='assignment_statistics'),
        path('bulk-delete/', bulk_delete_assignments, name='bulk_delete_assignments'),
        path('<int:assignment_id>/toggle/', toggle_assignment_status, name='toggle_assignment_status'),
        path('export/', ExportAssignmentsView.as_view(), name='export_assignments'),
    ])),
    
    # ==============================
    # ASSIGNMENT MANAGEMENT
    # ==============================
    path('assignments/', include([
        path('', AssignmentListView.as_view(), name='assignment_list'),
        path('create/selection/', AssignmentCreateSelectionView.as_view(), name='assignment_create_selection'),
        path('create/', AssignmentCreateView.as_view(), name='assignment_create'),
        path('quick-assign/', QuickClassAssignmentView.as_view(), name='quick_class_assignment'),
        path('<int:pk>/', AssignmentDetailView.as_view(), name='assignment_detail'),
        path('<int:pk>/update/', AssignmentUpdateView.as_view(), name='assignment_update'),
        path('<int:pk>/delete/', AssignmentDeleteView.as_view(), name='assignment_delete'),
        path('submit/<int:pk>/', SubmitAssignmentView.as_view(), name='submit_assignment'),
        path('calendar/', AssignmentCalendarView.as_view(), name='assignment_calendar'),
        path('calendar/events/', AssignmentEventJsonView.as_view(), name='assignment_calendar_events'),
        path('grade/student-assignment/<int:student_assignment_id>/', GradeAssignmentView.as_view(), name='grade_assignment'),
        path('grade/<int:pk>/', GradeAssignmentView.as_view(), name='grade_assignment_old'),
        path('<int:pk>/analytics/', AssignmentAnalyticsView.as_view(), name='assignment_analytics'),
        path('<int:pk>/export/', AssignmentExportView.as_view(), name='assignment_export'),
        path('<int:pk>/bulk-grade/', BulkGradeAssignmentView.as_view(), name='bulk_grade_assignment'),
    ])),

    # ==============================
    # GRADE MANAGEMENT
    # ==============================
    path('grades/', include([
        # Main grade management paths
        path('', GradeListView.as_view(), name='grade_list'),
        path('add/', GradeEntryView.as_view(), name='grade_add'),
        path('<int:pk>/', GradeDetailView.as_view(), name='grade_detail'),
        path('<int:pk>/edit/', GradeUpdateView.as_view(), name='grade_edit'),
        path('<int:pk>/delete/', GradeDeleteView.as_view(), name='grade_delete'),
        path('delete/<int:pk>/', GradeDeleteView.as_view(), name='grade_delete_legacy'),
        path('report/', GradeReportView.as_view(), name='grade_report'),
        path('best-students/', BestStudentsView.as_view(), name='best_students'),

        # Bulk operations
        path('bulk-upload/', BulkGradeUploadView.as_view(), name='grade_bulk_upload'),
        path('upload-template/', GradeUploadTemplateView.as_view(), name='grade_upload_template'),
        path('export/', GradeExportView.as_view(), name='export_grades'),

        # Grade management actions
        path('<int:pk>/lock/', lock_grade, name='lock_grade'),
        path('<int:pk>/unlock/', unlock_grade, name='unlock_grade'),
        path('<int:pk>/mark-review/', mark_grade_for_review, name='mark_grade_review'),
        path('<int:pk>/clear-review/', clear_grade_review, name='clear_grade_review'),
        # Utility endpoints
        path('calculate-total/', calculate_total_score, name='calculate_total_score'),
        path('check-existing/', check_existing_grade, name='check_existing_grade'),
        path('students-by-class/', get_students_by_class, name='get_students_by_class'),
        path('subjects-by-class/', get_subjects_by_class, name='get_subjects_by_class'),
        
        # API endpoints
        path('api/', include([
            path('calculate-grade/', CalculateGradeAPI.as_view(), name='calculate_grade_api'),
            path('students-by-class/', get_students_by_class, name='api_students_by_class'),
            path('subjects-by-class/', get_subjects_by_class, name='api_subjects_by_class'),
            path('validate/', GradeValidationAPI.as_view(), name='grade_validate'),
            path('statistics/', GradeStatisticsAPI.as_view(), name='grade_statistics'),
            path('student-subject-grades/<int:student_id>/', student_subject_grades, name='student_subject_grades'),
            path('student-grade-summary/<int:student_id>/', StudentGradeSummaryAPI.as_view(), name='student_grade_summary_api'),
            path('bulk-upload/progress/', BulkUploadProgressAPI.as_view(), name='bulk_upload_progress'),
        ])),
        
        # Advanced grade management
        path('queue/', GradingQueueView.as_view(), name='grading_queue'),
        path('configuration/', GradeConfigurationView.as_view(), name='grade_configuration'),
        path('calculator/', GradeCalculatorView.as_view(), name='grade_calculator'),

        # Cache management
        path('clear-cache/', ClearGradeCacheView.as_view(), name='clear_grade_cache'),
    ])),

    # ==============================
    # PROMOTION MANAGEMENT
    # ==============================
    path('promotion/', include([
        path('', PromotionListView.as_view(), name='promotion_list'),
        path('check/', PromotionCheckView.as_view(), name='promotion_check'),
        path('promote/', PromoteStudentsView.as_view(), name='promote_students'),
        path('configuration/', PromotionConfigurationView.as_view(), name='promotion_config'),
    ])),

    # ==============================
    # REPORT CARDS
    # ==============================
    path('report-cards/', include([
        path('', ReportCardDashboardView.as_view(), name='report_card_dashboard'),
        path('create/', CreateReportCardView.as_view(), name='create_report_card'),
        path('<int:student_id>/', ReportCardView.as_view(), name='report_card'),
        path('<int:student_id>/<int:report_card_id>/', ReportCardView.as_view(), name='report_card_detail'),
        path('pdf/<int:student_id>/', ReportCardPDFView.as_view(), name='report_card_pdf'),
        path('pdf/<int:student_id>/<int:report_card_id>/', ReportCardPDFView.as_view(), name='report_card_pdf_detail'),
        path('save/<int:student_id>/', SaveReportCardView.as_view(), name='save_report_card'),
        path('quick-view/', QuickViewReportCardView.as_view(), name='quick_view_report_card'),
        path('quick-view/pdf/', QuickViewReportCardPDFView.as_view(), name='quick_view_report_card_pdf'),
        path('<int:report_card_id>/edit-grades/', GradeEntryView.as_view(), name='grade_edit_report_card'),
        path('grades/add/<int:student_id>/', AddGradeView.as_view(), name='add_grade'),
        path('<int:report_card_id>/publish/', publish_report_card, name='publish_report_card'),
        path('force-recalculate/', force_recalculate_reportcards, name='force_recalculate_reportcards'),
        path('statistics-debug/', report_card_statistics_debug, name='report_card_statistics_debug'),
    ])),
    
    # ==============================
    # ANALYTICS & PROGRESS
    # ==============================
    path('analytics/', include([
        path('', ComprehensiveAnalyticsDashboardView.as_view(), name='analytics_dashboard'),
        path('student/<int:student_id>/progress-chart/', student_progress_chart, name='student_progress_chart'),
        path('class/<str:class_level>/performance-chart/', class_performance_chart, name='class_performance_chart'),
    ])),
    
    # ==============================
    # SECURITY MANAGEMENT
    # ==============================
    path('security/', include([
        # Security Dashboard
        path('dashboard/', security_dashboard, name='security_dashboard'),
        # User Management
        path('user-management/', UserManagementView.as_view(), name='user_management'),
        path('user/<int:user_id>/block/', BlockUserView.as_view(), name='block_user'),
        # Maintenance Management
        path('maintenance-mode/', MaintenanceModeView.as_view(), name='maintenance_mode'),
        path('scheduled-maintenance/', ScheduledMaintenanceView.as_view(), name='scheduled_maintenance'),
        # Security Settings
        path('settings/', SecuritySettingsView.as_view(), name='security_settings'),
        # Security Events & Audit
        path('events/', security_events, name='security_events'),
        path('events/<int:pk>/', SecurityEventDetailView.as_view(), name='security_event_detail'),
        # Alert Rules Management
        path('alert-rules/', AuditAlertRuleListView.as_view(), name='alert_rule_list'),
        path('alert-rules/create/', AuditAlertRuleCreateView.as_view(), name='alert_rule_create'),
        path('alert-rules/<int:pk>/update/', AuditAlertRuleUpdateView.as_view(), name='alert_rule_update'),
        # Lockout Management
        path('lockout-management/', axes_lockout_management, name='lockout_management'),
        # API endpoints
        path('api/status/', security_status_api, name='security_status_api'),
        path('api/stats/', security_stats_api, name='security_stats_api'),
        path('api/events/', security_events_api, name='security_events_api'),
        path('api/notifications/', security_notifications_api, name='security_notifications_api'),
        path('api/user-details/<int:user_id>/', user_details_api, name='user_details_api'),
        path('api/maintenance-details/<int:maintenance_id>/', maintenance_details_api, name='maintenance_details_api'),
        # Lockout Management API
        path('api/unlock-user/<str:username>/', unlock_user_api, name='unlock_user_api'),
        path('api/locked-users/', locked_users_api, name='locked_users_api'),
        path('api/unlock-all-users/', unlock_all_users_api, name='unlock_all_users_api'),
    ])),
    
    # ==============================
    # AUDIT LOG
    # ==============================
    path('audit/', include([
        path('logs/', AuditLogListView.as_view(), name='audit_log_list'),
        path('logs/<int:pk>/', AuditLogDetailView.as_view(), name='audit_log_detail'),
        path('dashboard/', AuditDashboardView.as_view(), name='audit_dashboard'),
        path('logs/export/', audit_export_csv, name='audit_export_csv'),
        path('logs/statistics/', audit_statistics_api, name='audit_statistics_api'),
        path('user-activity/<int:user_id>/', user_activity_report, name='user_activity_report'),
        path('system-health/', system_health_check, name='system_health_check'),
        # Enhanced Security (Backward Compatibility)
        path('security-dashboard/', audit_security_dashboard, name='audit_security_dashboard'),
        path('security-events/', SecurityEventListView.as_view(), name='audit_security_events'),
        path('security-events/<int:pk>/', SecurityEventDetailView.as_view(), name='audit_security_event_detail'),
        path('security-events/<int:event_id>/resolve/', resolve_security_event, name='resolve_security_event'),
        # Alert Rules
        path('alert-rules/', AuditAlertRuleListView.as_view(), name='audit_alert_rule_list'),
        path('alert-rules/create/', AuditAlertRuleCreateView.as_view(), name='audit_alert_rule_create'),
        path('alert-rules/<int:pk>/update/', AuditAlertRuleUpdateView.as_view(), name='audit_alert_rule_update'),
        path('alert-rules/<int:rule_id>/toggle/', toggle_alert_rule, name='toggle_alert_rule'),
        # Advanced Analytics
        path('advanced-analytics/', AdvancedAnalyticsView.as_view(), name='advanced_analytics'),
        path('run-anomaly-detection/', run_anomaly_detection, name='run_anomaly_detection'),
        # Automated Reporting
        path('reports/', AuditReportListView.as_view(), name='audit_reports'),
        path('generate-report/', generate_custom_report, name='generate_report'),
        # Data Retention
        path('retention-policies/', DataRetentionPolicyListView.as_view(), name='retention_policies'),
        path('apply-retention/', apply_retention_policies, name='apply_retention'),
        # API endpoints
        path('api/stats/', audit_security_stats_api, name='audit_security_stats_api'),
        path('api/notifications/', audit_security_notifications_api, name='audit_security_notifications_api'),
        path('api/system-health/', audit_system_health_api, name='audit_system_health_api'),
    ])),
    
    # ==============================
    # SYSTEM PAGES
    # ==============================
    path('maintenance/', maintenance_mode_page, name='maintenance_mode_page'),
    path('blocked/', user_blocked_page, name='user_blocked'),
    path('rate-limit-exceeded/', RateLimitExceededView.as_view(), name='rate_limit_exceeded'),
    path('emergency-bypass/', emergency_maintenance_bypass, name='emergency_bypass'),
    path('emergency-bypass/<str:secret_key>/', emergency_maintenance_bypass, name='emergency_bypass_key'),
    path('clear-bypass/', clear_maintenance_bypass, name='clear_bypass'),
    
    # ==============================
    # NOTIFICATIONS
    # ==============================
    path('notifications/', include([
        path('', NotificationListView.as_view(), name='notification_list'),
        path('mark-all-read/', mark_all_notifications_read, name='mark_all_notifications_read'),
        path('<int:pk>/mark-read/', mark_notification_read, name='mark_notification_read'),
        path('api/count/', get_unread_count, name='get_unread_count'),
        path('api/mark-read/<int:pk>/', mark_notification_read, name='api_mark_notification_read'),
    ])),
    
    # ==============================
    # ATTENDANCE
    # ==============================
    path('attendance/', include([
        path('', AttendanceDashboardView.as_view(), name='attendance_dashboard'),
        path('record/', AttendanceRecordView.as_view(), name='attendance_record'),
        path('load-periods/', load_periods, name='load_periods'),
        path('student-attendance/', StudentAttendanceListView.as_view(), name='student_attendance_list'),
        path('report/', TemplateView.as_view(template_name='core/attendance/report.html'), name='attendance_report'),
    ])),
    
    # ==============================
    # TIMETABLE
    # ==============================
    path('timetable/', include([
        # AJAX endpoints
        path('ajax/get-subjects-for-class/<str:class_level>/', get_subjects_for_class, name='get_subjects_for_class'),
        path('ajax/get-available-teachers/', get_available_teachers, name='get_available_teachers'),
        path('ajax/entries/', get_timetable_entries, name='admin_timetable_ajax_entries'),
        
        # Main admin timetable views
        path('', TimetableListView.as_view(), name='admin_timetable_list'),
        path('create/', TimetableCreateView.as_view(), name='admin_timetable_create'),
        path('<int:pk>/', TimetableDetailView.as_view(), name='admin_timetable_detail'),
        path('<int:pk>/manage/', TimetableManageView.as_view(), name='admin_timetable_manage'),
        path('<int:pk>/update/', TimetableUpdateView.as_view(), name='timetable_update'),
        path('<int:pk>/edit/', TimetableUpdateView.as_view(), name='admin_timetable_edit'),
        path('<int:pk>/delete/', TimetableDeleteView.as_view(), name='admin_timetable_delete'),
        path('generate-weekly/', generate_weekly_timetable, name='admin_generate_weekly_timetable'),
        path('<int:pk>/print/', print_timetable, name='admin_print_timetable'),
        
        path('<int:pk>/archive/', timetable_archive_view, name='archive_timetable'),
        path('<int:pk>/deactivate/', timetable_deactivate_view, name='deactivate_timetable'),
        path('<int:pk>/duplicate/', timetable_duplicate_view, name='duplicate_timetable'),
        
        # Calendar views
        path('calendar/', TimetableCalendarView.as_view(), name='timetable_calendar'),
        path('calendar/data/', calendar_data, name='calendar_data'),
        path('calendar/day-events/', day_events, name='day_events'),
        path('calendar/event/<str:event_id>/', event_details, name='event_details'),
        path('calendar/export/', export_calendar, name='export_calendar'),
        
        # Class resources and attendance
        path('class/<int:timetable_id>/resources/', get_class_resources, name='get_class_resources'),
        path('add-resource/', add_class_resource, name='add_class_resource'),
        path('add-note/', add_class_note, name='add_class_note'),
        path('send-announcement/', send_class_announcement, name='send_class_announcement'),
        path('export-students/<int:pk>/', export_student_list, name='export_student_list'),
        path('get-attendance-form/', get_attendance_form, name='get_attendance_form'),
        
        # Print views
        path('print/', print_weekly_timetable, name='print_weekly_timetable'),
    ])),
    
    # Time Slots
    path('timeslots/', include([
        path('', TimeSlotListView.as_view(), name='admin_timeslot_list'),
        path('create/', TimeSlotCreateView.as_view(), name='admin_timeslot_create'),
        path('<int:pk>/edit/', TimeSlotUpdateView.as_view(), name='admin_timeslot_edit'),
        path('<int:pk>/delete/', TimeSlotDeleteView.as_view(), name='admin_timeslot_delete'),
    ])),
    
    # ==============================
    # TEACHER TIMETABLE
    # ==============================
    path('teacher/timetable/', include([
        path('', TeacherTimetableListView.as_view(), name='teacher_timetable_list'),
        path('<int:pk>/', TeacherTimetableDetailView.as_view(), name='teacher_timetable_detail'),
        path('my-schedule/', TeacherTimetableView.as_view(), name='teacher_my_schedule'),
        path('ajax/entries/', get_timetable_entries, name='teacher_timetable_ajax_entries'),
        path('<int:pk>/print/', print_timetable, name='teacher_print_timetable'),
        path('class/<int:timetable_id>/resources/', get_class_resources, name='teacher_get_class_resources'),
        path('add-resource/', add_class_resource, name='teacher_add_class_resource'),
        path('get-attendance-form/', get_attendance_form, name='teacher_get_attendance_form'),
    ])),
    
    # ==============================
    # STUDENT TIMETABLE
    # ==============================
    path('student/timetable/', include([
        path('', StudentTimetableView.as_view(), name='student_timetable'),
        path('print/', print_weekly_timetable, name='print_weekly_timetable'),
        path('<int:pk>/print/', print_timetable, name='student_print_timetable'),
    ])),
    
    # ==============================
    # COMMON TIMETABLE VIEWS
    # ==============================
    path('timetable-view/', include([
        path('', TimetableListView.as_view(), name='timetable_list'),
        path('student/', StudentTimetableView.as_view(), name='student_timetable_view'),
        path('teacher/', TeacherTimetableView.as_view(), name='teacher_timetable_view'),
        path('calendar/', TimetableCalendarView.as_view(), name='timetable_calendar_view'),
        path('ajax/entries/', get_timetable_entries, name='timetable_ajax_entries'),
        path('generate-weekly/', generate_weekly_timetable, name='generate_weekly_timetable'),
        path('api/entries/', get_timetable_entries, name='timetable_ajax_entries'),
        path('print/', print_weekly_timetable, name='timetable_print'),
        path('<int:pk>/print/', print_timetable, name='timetable_print_single'),
        path('class-details/<int:period_id>/', get_class_details, name='get_class_details'),
        path('subject-details/<int:subject_id>/', get_subject_details, name='get_subject_details'),
        path('assignment-details/<int:assignment_id>/', get_assignment_details, name='get_assignment_details'),
        path('class/<int:timetable_id>/resources/', get_class_resources, name='timetable_get_class_resources'),
        path('add-resource/', add_class_resource, name='timetable_add_class_resource'),
        path('add-note/', add_class_note, name='timetable_add_class_note'),
        path('send-announcement/', send_class_announcement, name='timetable_send_class_announcement'),
        path('export-students/<int:pk>/', export_student_list, name='timetable_export_student_list'),
        path('get-attendance-form/', get_attendance_form, name='timetable_get_attendance_form'),
    ])),
    
    # Common timeslot views
    path('timeslots-view/', include([
        path('', TimeSlotListView.as_view(), name='timeslot_list'),
        path('create/', TimeSlotCreateView.as_view(), name='timeslot_create'),
        path('<int:pk>/update/', TimeSlotUpdateView.as_view(), name='timeslot_update'),
        path('<int:pk>/delete/', TimeSlotDeleteView.as_view(), name='timeslot_delete'),
    ])),
    
    # ==============================
    # ANNOUNCEMENTS
    # ==============================
    path('announcements/', include([
        path('', AnnouncementListView.as_view(), name='announcement_list'),
        path('create/', CreateAnnouncementView.as_view(), name='create_announcement'),
        path('active/', active_announcements, name='active_announcements'),
        path('<int:pk>/', announcement_detail, name='announcement_detail'),
        path('<int:pk>/update/', UpdateAnnouncementView.as_view(), name='update_announcement'),
        path('<int:pk>/delete/', DeleteAnnouncementView.as_view(), name='delete_announcement'),
        path('<int:pk>/toggle-status/', toggle_announcement_status, name='toggle_announcement_status'),
        path('<int:pk>/dismiss/', dismiss_announcement, name='dismiss_announcement'),
        path('dismiss-all/', dismiss_all_announcements, name='dismiss_all_announcements'),
        path('bulk-action/', bulk_action_announcements, name='bulk_action_announcements'),
        path('stats/', AnnouncementStatsView.as_view(), name='announcement_stats'),
    ])),
    
    # ==============================
    # API ENDPOINTS
    # ==============================
    path('api/', include([
        path('network/health/', NetworkHealthView.as_view(), name='network_health'),
        path('fee-categories/<int:pk>/', fee_category_detail, name='fee_category_api_detail'),
        
        # Student API
        path('students/', StudentListAPIView.as_view(), name='api_students'),
        path('students/active/', ActiveStudentsAPIView.as_view(), name='api_students_active'),
        path('academic-terms/', AcademicTermAPIView.as_view(), name='api_academic_terms'),
        
        # Student Assignment API
        path('student/assignments/', StudentAssignmentLibraryView.as_view(), name='api_student_assignments'),
        path('student/assignments/active/', StudentAssignmentLibraryView.as_view(), name='api_student_assignments_active'),
        
        # Parent API
        path('parents/', include([
            path('students/', StudentListAPIView.as_view(), name='api_parent_students'),
            path('students/active/', ActiveStudentsAPIView.as_view(), name='api_parent_active_students'),
            path('children/', ParentChildrenAPIView.as_view(), name='api_parent_children'),
            path('dashboard/', ParentDashboardAPIView.as_view(), name='api_parent_dashboard'),
            path('profile/', ParentProfileAPIView.as_view(), name='api_parent_profile'),
            path('accounts/', ParentAccountStatusAPIView.as_view(), name='api_parent_accounts'),
            path('accounts/<int:parent_id>/', ParentAccountStatusAPIView.as_view(), name='api_parent_account_action'),
            path('register/', ParentRegistrationAPIView.as_view(), name='api_parent_register'),
            path('stats/', ParentStatsAPIView.as_view(), name='api_parent_stats'),
        ])),
        
        # Security API
        path('security/notifications/', security_notifications_api, name='security_notifications_api'),
        path('system-health/', system_health_api, name='system_health_api'),
        
        # Class Assignment API
        path('class-assignments/', include([
            path('', assignment_statistics, name='api_class_assignments'),
            path('statistics/', assignment_statistics, name='api_class_assignments_statistics'),
            path('<int:assignment_id>/students/', get_assignment_students, name='api_class_assignment_students'),
            path('<int:assignment_id>/toggle/', toggle_assignment_status, name='api_toggle_assignment_status'),
        ])),
        
        # Teacher Qualifications API
        path('teachers/<int:teacher_id>/qualifications/', get_teacher_qualifications, name='api_teacher_qualifications'),
        
        # Bulk Operations API
        path('bulk/delete-assignments/', bulk_delete_assignments, name='api_bulk_delete_assignments'),
        
        # Timetable API
        path('timetable/entries/', get_timetable_entries, name='api_timetable_entries'),
    ])),
    
    # Payment URLs
    path('payments/<int:pk>/delete/', FeePaymentDeleteView.as_view(), name='fee_payment_delete'),
    
    # ==============================
    # FALLBACK & UTILITY URLS
    # ==============================
    path('class-assignment/<int:assignment_id>/students/', get_assignment_students, name='fallback_assignment_students'),
    path('teacher/<int:teacher_id>/qualifications/', get_teacher_qualifications, name='fallback_teacher_qualifications'),
    path('api/debug/database-stats/', debug_database_stats, name='debug_database_stats'),
    
    # Group Management
    path('admin/timetable/groups/', views_group_management.manage_timetable_groups, name='manage_timetable_groups'),
    path('admin/timetable/users/', views_group_management.user_group_management, name='user_group_management'),
    path('admin/timetable/users/<int:user_id>/group/<int:group_id>/assign/', 
         views_group_management.assign_user_to_group, name='assign_user_to_group'),
    path('admin/timetable/users/<int:user_id>/group/<int:group_id>/remove/', 
         views_group_management.remove_user_from_group, name='remove_user_from_group'),
    
    # System URLs
    path('admin/group-permissions/', 
         RedirectView.as_view(pattern_name='admin:auth_group_changelist'), 
         name='group_permissions'),
    
    path('system/status/', 
         TemplateView.as_view(template_name='core/admin/system_status.html'), 
         name='system_status'),
    
    path('clear-import-results/', ClearImportResultsView.as_view(), name='clear_import_results'),
]

# ==============================
# LEGACY REDIRECTS (For backward compatibility)
# ==============================
# These redirects ensure old URLs still work
urlpatterns += [
    # Redirect old parent URLs to new structure
    path('parent/', RedirectView.as_view(pattern_name='parent_portal_dashboard', permanent=True)),
    path('parent/dashboard/', RedirectView.as_view(pattern_name='parent_portal_dashboard', permanent=True)),
    path('parent/children/', RedirectView.as_view(pattern_name='parent_portal_children', permanent=True)),
    
    # Redirect old management URLs
    path('parent-management/', RedirectView.as_view(pattern_name='parent_management_dashboard', permanent=True)),
    path('parent-management/dashboard/', RedirectView.as_view(pattern_name='parent_management_dashboard', permanent=True)),
    
    # Redirect old student portal URLs
    path('student/', RedirectView.as_view(pattern_name='student_portal_dashboard', permanent=True)),
    path('student/dashboard/', RedirectView.as_view(pattern_name='student_portal_dashboard', permanent=True)),
]

urlpatterns += [
    path('admin/backups/', backup_dashboard, name='backup_dashboard'),
    path('admin/backups/create/', create_backup, name='create_backup'),
    path('admin/backups/download/<str:backup_name>/', download_backup, name='download_backup'),
    path('admin/backups/delete/<str:backup_name>/', delete_backup, name='delete_backup'),
    path('admin/backups/cleanup/', cleanup_old_backups, name='cleanup_old_backups'),
]