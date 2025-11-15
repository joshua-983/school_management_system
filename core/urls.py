# core/urls.py - UPDATED VERSION (FIXED)
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

# Import views from modular files
from .views.base_views import home, admin_dashboard, teacher_dashboard
from .views.teacher_views import (
    TeacherListView, TeacherCreateView, TeacherUpdateView, TeacherDeleteView,
    TeacherAssignmentAnalyticsView, TeacherDetailAnalyticsView
)
from .views.student_views import (
    StudentListView, StudentDetailView, StudentCreateView, StudentUpdateView, 
    StudentDeleteView, StudentGradeListView, StudentAttendanceView, 
    StudentFeeListView, StudentProfileView, StudentDashboardView
)
# ==============================
# PARENT VIEWS IMPORTS - FIXED
# ==============================
from .views.parents_views import (
    ParentCreateView, ParentUpdateView, ParentDeleteView,
    ParentChildrenListView, ParentChildDetailView, ParentFeeListView, ParentFeeDetailView,
    ParentFeePaymentView, ParentAttendanceListView, ParentReportCardListView, ParentReportCardDetailView,
    parent_dashboard,
    ParentAnnouncementListView, ParentMessageListView,
    ParentMessageCreateView, ParentMessageDetailView, ParentCalendarView,  # ADDED ParentCalendarView
    ParentDirectoryView, BulkParentMessageView, ParentCommunicationLogView, ParentEngagementDashboardView
)
from .views.fee_views import (
    FeeCategoryListView, FeeCategoryCreateView, FeeCategoryUpdateView, FeeCategoryDeleteView,
    FeeListView, FeeDetailView, FeeCreateView, FeeUpdateView, FeeDeleteView,
    FeePaymentCreateView, FeePaymentDeleteView, FeeReportView, FeeDashboardView,
    FeeStatusReportView, BillPaymentCreateView, GenerateTermFeesView,
    BulkFeeUpdateView, SendPaymentRemindersView, FeeAnalyticsView,
    FinanceDashboardView, RevenueAnalyticsView, FinancialHealthView, BudgetManagementView,
    PaymentSummaryView, RefreshPaymentDataView, BudgetCreateView
)
from .views.subjects_views import SubjectListView, SubjectDetailView, SubjectCreateView, SubjectUpdateView, SubjectDeleteView
from .views.class_assignments import ClassAssignmentListView, ClassAssignmentCreateView, ClassAssignmentUpdateView, ClassAssignmentDeleteView
from .views.assignment_views import (
    AssignmentListView, AssignmentDetailView, AssignmentCreateView, 
    AssignmentUpdateView, AssignmentDeleteView, SubmitAssignmentView,
    AssignmentCalendarView, AssignmentEventJsonView,
    GradeAssignmentView, BulkGradeAssignmentView, AssignmentAnalyticsView, AssignmentExportView
)

# ==============================
# CORRECTED GRADE VIEWS IMPORTS
# ==============================
from .views.grade_views import (
    # Main Grade Views
    GradeListView, GradeDetailView, GradeCreateView, GradeUpdateView, GradeDeleteView,
    GradeEntryView, GradeReportView, BestStudentsView,
    
    # Bulk Operations
    BulkGradeUploadView, GradeUploadTemplateView,
    
    # API & Utility Views
    CalculateGradeAPI, calculate_total_score, check_existing_grade,
    get_students_by_class, get_subjects_by_class, student_grade_summary,
    
    # Grade Management Actions
    lock_grade, unlock_grade, mark_grade_for_review, clear_grade_review,
    
    # Export View - ADD THIS IMPORT
    GradeExportView,
    
    # Legacy/Compatibility
    grade_delete
)

# ==============================
# REPORT CARD VIEWS IMPORTS - FIXED: Import the new Quick View classes
# ==============================
from .views.reportcard_views import (
    ReportCardDashboardView, CreateReportCardView, ReportCardView, 
    ReportCardPDFView, SaveReportCardView,
    QuickViewReportCardView, QuickViewReportCardPDFView  # ADD THESE
)

from .views.analytics_views import ComprehensiveAnalyticsDashboardView

from .views.audit_views import (
    AuditLogListView, AuditLogDetailView, AuditDashboardView, 
    audit_export_csv, audit_statistics_api, user_activity_report, 
    system_health_check, student_progress_chart, class_performance_chart
)

# ==============================
# ENHANCED AUDIT VIEWS IMPORTS - FIXED: Import security API functions
# ==============================
from .views.audit_enhancements import (
    SecurityEventListView, SecurityEventDetailView,
    AuditAlertRuleListView, AuditAlertRuleCreateView, AuditAlertRuleUpdateView,
    AdvancedAnalyticsView, AuditReportListView, DataRetentionPolicyListView,
    run_anomaly_detection, generate_custom_report, apply_retention_policies,
    resolve_security_event, toggle_alert_rule, security_dashboard,
    security_stats_api, security_notifications_api, system_health_api  # ADD THESE IMPORTANT MISSING IMPORTS
)

from .views.attendance_views import AttendanceDashboardView, AttendanceRecordView, load_periods, StudentAttendanceListView
from .views.timetable_views import (
    TimeSlotListView, TimeSlotCreateView, TimeSlotUpdateView, TimeSlotDeleteView,
    TimetableListView, TimetableCreateView, TimetableDetailView, TimetableManageView, TimetableDeleteView,
    StudentTimetableView, TeacherTimetableView, get_timetable_entries, generate_weekly_timetable
)
from .views.notifications_views import (
    NotificationListView, 
    mark_notification_read, 
    mark_all_notifications_read,
    get_unread_count
)

# ==============================
# BILL VIEWS IMPORTS - FIXED: Import all bill views directly
# ==============================
from .views.bill_views import (
    BillListView, BillDetailView, BillGenerateView, BillPaymentView, BillCancelView,
    BulkSendRemindersView, BulkExportBillsView, BulkMarkPaidView, BulkDeleteBillsView
)


# ==============================
# ANNOUNCEMENT VIEWS IMPORTS
# ==============================
from .views.announcement_views import (
    AnnouncementListView, CreateAnnouncementView, UpdateAnnouncementView, 
    DeleteAnnouncementView, get_active_announcements, dismiss_announcement, 
    dismiss_all_announcements, announcement_detail, toggle_announcement_status,
    bulk_action_announcements, AnnouncementStatsView
)

# Import API views
from .api import FeeCategoryViewSet
from .views.api import fee_category_detail


router = DefaultRouter()
router.register(r'fee-categories', FeeCategoryViewSet, basename='fee-category')

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    
    # Home and dashboards
    path('', home, name='home'),
    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),
    path('teacher-dashboard/', teacher_dashboard, name='teacher_dashboard'),
    
    # Student Dashboard
    path('student-dashboard/', StudentDashboardView.as_view(), name='student_dashboard'),
    
    # ==============================
    # STUDENT URLS
    # ==============================
    path('students/', StudentListView.as_view(), name='student_list'),
    path('students/<int:pk>/', StudentDetailView.as_view(), name='student_detail'),
    path('students/add/', StudentCreateView.as_view(), name='student_add'),
    path('students/<int:pk>/edit/', StudentUpdateView.as_view(), name='student_update'),
    path('students/<int:pk>/delete/', StudentDeleteView.as_view(), name='student_delete'),
    path('student/<int:student_id>/attendance/', AttendanceDashboardView.as_view(), name='student_attendance_summary'),
    
    # Student Profile URLs
    path('student/profile/', StudentProfileView.as_view(), name='student_profile'),
    path('student/grades/', StudentGradeListView.as_view(), name='student_grades'),
    path('student/attendance/', StudentAttendanceView.as_view(), name='student_attendance'),
    path('student/fees/', StudentFeeListView.as_view(), name='student_fees'),
    
    # ==============================
    # PARENT/GUARDIAN URLS
    # ==============================
    path('students/<int:student_id>/parents/add/', ParentCreateView.as_view(), name='parent_create'),
    path('parents/<int:pk>/edit/', ParentUpdateView.as_view(), name='parent_update'),
    path('parents/<int:pk>/delete/', ParentDeleteView.as_view(), name='parent_delete'),
    
    # FEE MANAGEMENT URLS
    # ==============================
    path('fee-categories/', FeeCategoryListView.as_view(), name='fee_category_list'),
    path('fee-categories/add/', FeeCategoryCreateView.as_view(), name='fee_category_create'),
    path('fee-categories/<int:pk>/edit/', FeeCategoryUpdateView.as_view(), name='fee_category_update'),
    path('fee-categories/<int:pk>/delete/', FeeCategoryDeleteView.as_view(), name='fee_category_delete'),
    path('fee-dashboard/', FeeDashboardView.as_view(), name='fee_dashboard'),
    
    # Fee URLs
    path('fees/', FeeListView.as_view(), name='fee_list'),
    path('fees/<int:pk>/', FeeDetailView.as_view(), name='fee_detail'),
    path('fees/<int:pk>/edit/', FeeUpdateView.as_view(), name='fee_update'),
    path('fees/<int:pk>/delete/', FeeDeleteView.as_view(), name='fee_delete'),
    path('students/<int:student_id>/fees/add/', FeeCreateView.as_view(), name='fee_create'),
    
    # ==============================
    # BILL MANAGEMENT URLS - FIXED: Use direct imports instead of bill_views.
    # ==============================
    path('bills/', BillListView.as_view(), name='bill_list'),
    path('bills/<int:pk>/', BillDetailView.as_view(), name='bill_detail'),
    path('bills/generate/', BillGenerateView.as_view(), name='bill_generate'),
    path('bills/<int:pk>/payment/', BillPaymentView.as_view(), name='bill_payment'),
    path('bills/<int:pk>/cancel/', BillCancelView.as_view(), name='bill_cancel'),
    
    # Bulk action URLs
    path('bills/bulk/send-reminders/', BulkSendRemindersView.as_view(), name='bulk_send_reminders'),
    path('bills/bulk/export/', BulkExportBillsView.as_view(), name='bulk_export_bills'),
    path('bills/bulk/mark-paid/', BulkMarkPaidView.as_view(), name='bulk_mark_paid'),
    path('bills/bulk/delete/', BulkDeleteBillsView.as_view(), name='bulk_delete_bills'),
    
    # Fee Payment URLs
    path('fees/<int:fee_id>/payments/add/', FeePaymentCreateView.as_view(), name='fee_payment_create'),
    path('payments/<int:pk>/delete/', FeePaymentDeleteView.as_view(), name='fee_payment_delete'),
    
    # Bill Payment URLs
    path('bills/<int:bill_id>/payments/add/', BillPaymentCreateView.as_view(), name='bill_payment_create'),
    
    # Fee Generation & Automation
    path('fees/generate-term-fees/', GenerateTermFeesView.as_view(), name='generate_term_fees'),
    path('fees/bulk-update/', BulkFeeUpdateView.as_view(), name='bulk_fee_update'),
    path('fees/send-reminders/', SendPaymentRemindersView.as_view(), name='send_payment_reminders'),
    
    # Fee Reports & Analytics
    path('reports/fees/', FeeReportView.as_view(), name='fee_report'),
    path('reports/fee-status/', FeeStatusReportView.as_view(), name='fee_status_report'),
    path('analytics/fees/', FeeAnalyticsView.as_view(), name='fee_analytics'),
    
    # Finance Dashboard URLs
    path('finance/dashboard/', FinanceDashboardView.as_view(), name='finance_dashboard'),
    path('finance/revenue-analytics/', RevenueAnalyticsView.as_view(), name='revenue_analytics'),
    path('finance/financial-health/', FinancialHealthView.as_view(), name='financial_health'),  # SINGLE INSTANCE - REMOVED DUPLICATE
    path('finance/budget-management/', BudgetManagementView.as_view(), name='budget_management'),
    path('finance/payment-summary/', PaymentSummaryView.as_view(), name='payment_summary'),
    path('finance/payment-summary/refresh/', RefreshPaymentDataView.as_view(), name='refresh_payment_data'),
    # Add this to your core/urls.py
    path('finance/budget/create/', BudgetCreateView.as_view(), name='budget_create'),
    # ==============================
    # SUBJECT URLS
    # ==============================
    path('subjects/', SubjectListView.as_view(), name='subject_list'),
    path('subjects/add/', SubjectCreateView.as_view(), name='subject_add'),
    path('subjects/<int:pk>/edit/', SubjectUpdateView.as_view(), name='subject_edit'),
    path('subjects/<int:pk>/delete/', SubjectDeleteView.as_view(), name='subject_delete'),
    path('subjects/<int:pk>/', SubjectDetailView.as_view(), name='subject_detail'),
    
    # ==============================
    # TEACHER URLS
    # ==============================
    path('teachers/', TeacherListView.as_view(), name='teacher_list'),
    path('teachers/add/', TeacherCreateView.as_view(), name='teacher_add'),
    path('teachers/<int:pk>/edit/', TeacherUpdateView.as_view(), name='teacher_edit'),
    path('teachers/<int:pk>/delete/', TeacherDeleteView.as_view(), name='teacher_delete'),
    path('teachers/analytics/', TeacherAssignmentAnalyticsView.as_view(), name='teacher_analytics'),
    path('teachers/<int:pk>/analytics/', TeacherDetailAnalyticsView.as_view(), name='teacher_analytics_detail'),
   
    # ==============================
    # ASSIGNMENT URLS 
    # ==============================
    path('assignments/', AssignmentListView.as_view(), name='assignment_list'),
    path('assignments/create/', AssignmentCreateView.as_view(), name='assignment_create'),
    path('assignments/<int:pk>/', AssignmentDetailView.as_view(), name='assignment_detail'),
    path('assignments/<int:pk>/update/', AssignmentUpdateView.as_view(), name='assignment_update'),
    path('assignments/<int:pk>/delete/', AssignmentDeleteView.as_view(), name='assignment_delete'),
    path('assignments/submit/<int:pk>/', SubmitAssignmentView.as_view(), name='submit_assignment'),
    path('assignments/calendar/', AssignmentCalendarView.as_view(), name='assignment_calendar'),
    path('assignments/calendar/events/', AssignmentEventJsonView.as_view(), name='assignment_calendar_events'),

    # Assignment Grading URLs
    path('assignments/grade/student-assignment/<int:student_assignment_id>/', GradeAssignmentView.as_view(), name='grade_assignment'),
    path('assignments/grade/<int:pk>/', GradeAssignmentView.as_view(), name='grade_assignment_old'),
    path('assignments/<int:pk>/analytics/', AssignmentAnalyticsView.as_view(), name='assignment_analytics'),
    path('assignments/<int:pk>/export/', AssignmentExportView.as_view(), name='assignment_export'),
    path('assignments/<int:pk>/bulk-grade/', BulkGradeAssignmentView.as_view(), name='bulk_grade_assignment'),

    # ==============================
    # CLASS ASSIGNMENT URLS
    # ==============================
    path('class-assignments/', ClassAssignmentListView.as_view(), name='class_assignment_list'),
    path('class-assignments/create/', ClassAssignmentCreateView.as_view(), name='class_assignment_create'),
    path('class-assignments/<int:pk>/update/', ClassAssignmentUpdateView.as_view(), name='class_assignment_update'),
    path('class-assignments/<int:pk>/delete/', ClassAssignmentDeleteView.as_view(), name='class_assignment_delete'),
    
    # ==============================
    # COMPREHENSIVE GRADE MANAGEMENT URLS
    # ==============================
    
    # Main Grade Views
    path('grades/', GradeListView.as_view(), name='grade_list'),
    path('grades/add/', GradeEntryView.as_view(), name='grade_add'),
    path('grades/<int:pk>/', GradeDetailView.as_view(), name='grade_detail'),
    path('grades/<int:pk>/edit/', GradeUpdateView.as_view(), name='grade_edit'),
    path('grades/delete/<int:pk>/', grade_delete, name='grade_delete'),
    path('grades/report/', GradeReportView.as_view(), name='grade_report'),
    path('best-students/', BestStudentsView.as_view(), name='best_students'),
    
    # Bulk Grade Operations
    path('grades/bulk-upload/', BulkGradeUploadView.as_view(), name='grade_bulk_upload'),
    path('grades/upload-template/', GradeUploadTemplateView.as_view(), name='grade_upload_template'),
    
    # Grade Export - FIXED: Use class-based view directly
    path('grades/export/', GradeExportView.as_view(), name='export_grades'),
    
    # Grade Management Actions
    path('grades/<int:pk>/lock/', lock_grade, name='lock_grade'),
    path('grades/<int:pk>/unlock/', unlock_grade, name='unlock_grade'),
    path('grades/<int:pk>/mark-review/', mark_grade_for_review, name='mark_grade_review'),
    path('grades/<int:pk>/clear-review/', clear_grade_review, name='clear_grade_review'),
    
    # Grade API & AJAX Endpoints
    path('api/calculate-grade/', CalculateGradeAPI.as_view(), name='calculate_grade_api'),
    path('grades/calculate-total/', calculate_total_score, name='calculate_total_score'),
    path('grades/check-existing/', check_existing_grade, name='check_existing_grade'),
    path('grades/students-by-class/', get_students_by_class, name='get_students_by_class'),
    path('grades/subjects-by-class/', get_subjects_by_class, name='get_subjects_by_class'),
    path('api/student-grade-summary/<int:student_id>/', student_grade_summary, name='student_grade_summary'),
    
    # FIXED: Remove duplicate line and use the correct path
    path('api/students-by-class/', get_students_by_class, name='api_students_by_class'),
    
    # ==============================
    # REPORT CARD URLS - FIXED: Use direct imports
    # ==============================
    path('report-cards/create/', CreateReportCardView.as_view(), name='create_report_card'),
    path('report-cards/', ReportCardDashboardView.as_view(), name='report_card_dashboard'), 
    path('report-card/<int:student_id>/', ReportCardView.as_view(), name='report_card'),
    path('report-card/<int:student_id>/<int:report_card_id>/', ReportCardView.as_view(), name='report_card_detail'),
    path('report-card/pdf/<int:student_id>/', ReportCardPDFView.as_view(), name='report_card_pdf'),
    path('report-card/pdf/<int:student_id>/<int:report_card_id>/', ReportCardPDFView.as_view(), name='report_card_pdf_detail'),
    path('report-card/save/<int:student_id>/', SaveReportCardView.as_view(), name='save_report_card'),
    
    # Quick View Report Card URLs - FIXED: Use direct imports
    path('quick-view/', QuickViewReportCardView.as_view(), name='quick_view_report_card'),
    path('quick-view/pdf/', QuickViewReportCardPDFView.as_view(), name='quick_view_report_card_pdf'),
    
    # ==============================
    # PROGRESS & ANALYTICS URLS
    # ==============================
    path('students/<int:student_id>/progress-chart/', student_progress_chart, name='student_progress_chart'),
    path('class/<str:class_level>/performance-chart/', class_performance_chart, name='class_performance_chart'),
    path('analytics/', ComprehensiveAnalyticsDashboardView.as_view(), name='analytics_dashboard'),
    
    # ==============================
    # ENHANCED AUDIT LOG URLS
    # ==============================
    path('audit-logs/', AuditLogListView.as_view(), name='audit_log_list'),
    path('audit-logs/<int:pk>/', AuditLogDetailView.as_view(), name='audit_log_detail'),
    path('audit-dashboard/', AuditDashboardView.as_view(), name='audit_dashboard'),
    path('audit-logs/export/', audit_export_csv, name='audit_export_csv'),
    path('audit-logs/statistics/', audit_statistics_api, name='audit_statistics_api'),
    path('user-activity/<int:user_id>/', user_activity_report, name='user_activity_report'),
    path('system-health/', system_health_check, name='system_health_check'),
    
    # ==============================
    # ENHANCED SECURITY & ANALYTICS URLS - FIXED
    # ==============================
    
    # Security Dashboard
    path('audit/security-dashboard/', security_dashboard, name='security_dashboard'),
    
    # Real-time Security Monitoring
    path('audit/security-events/', SecurityEventListView.as_view(), name='security_events'),
    path('audit/security-events/<int:pk>/', SecurityEventDetailView.as_view(), name='security_event_detail'),
    path('audit/security-events/<int:event_id>/resolve/', resolve_security_event, name='resolve_security_event'),
    
    # Alert Rules Management
    path('audit/alert-rules/', AuditAlertRuleListView.as_view(), name='alert_rule_list'),
    path('audit/alert-rules/create/', AuditAlertRuleCreateView.as_view(), name='alert_rule_create'),
    path('audit/alert-rules/<int:pk>/update/', AuditAlertRuleUpdateView.as_view(), name='alert_rule_update'),
    path('audit/alert-rules/<int:rule_id>/toggle/', toggle_alert_rule, name='toggle_alert_rule'),
    
    # Advanced Analytics & Machine Learning
    path('audit/advanced-analytics/', AdvancedAnalyticsView.as_view(), name='advanced_analytics'),
    path('audit/run-anomaly-detection/', run_anomaly_detection, name='run_anomaly_detection'),
    
    # Automated Reporting
    path('audit/reports/', AuditReportListView.as_view(), name='audit_reports'),
    path('audit/generate-report/', generate_custom_report, name='generate_report'),
    
    # Data Retention & Archiving
    path('audit/retention-policies/', DataRetentionPolicyListView.as_view(), name='retention_policies'),
    path('audit/apply-retention/', apply_retention_policies, name='apply_retention'),
    
    # Security API endpoints - FIXED: Use imported functions directly
    path('api/security/stats/', security_stats_api, name='security_stats_api'),
    path('api/security/notifications/', security_notifications_api, name='security_notifications_api'),
    path('api/system-health/', system_health_api, name='system_health_api'),
    
    # ==============================
    # NOTIFICATION URLS
    # ==============================
    path('notifications/', NotificationListView.as_view(), name='notification_list'),
path('notifications/mark-all-read/', mark_all_notifications_read, name='mark_all_notifications_read'),
path('notifications/<int:pk>/mark-read/', mark_notification_read, name='mark_notification_read'),
path('api/notifications/count/', get_unread_count, name='get_unread_count'),
path('api/notifications/mark-read/<int:pk>/', mark_notification_read, name='api_mark_notification_read'),
    
    # ==============================
    # ATTENDANCE URLS
    # ==============================
    path('attendance/', AttendanceDashboardView.as_view(), name='attendance_dashboard'),
    path('attendance/record/', AttendanceRecordView.as_view(), name='attendance_record'),
    path('attendance/load-periods/', load_periods, name='load_periods'),
    path('student-attendance/', StudentAttendanceListView.as_view(), name='student_attendance_list'),
    
    # ==============================
    # PARENT PORTAL URLS
    # ==============================
    path('parent/dashboard/', parent_dashboard, name='parent_dashboard'),
    path('parent/children/', ParentChildrenListView.as_view(), name='parent_children_list'),
    path('parent/child/<int:pk>/', ParentChildDetailView.as_view(), name='parent_child_detail'),
    path('parent/fees/', ParentFeeListView.as_view(), name='parent_fee_list'),
    path('parent/fee/<int:pk>/', ParentFeeDetailView.as_view(), name='parent_fee_detail'),
    path('parent/fee/<int:pk>/pay/', ParentFeePaymentView.as_view(), name='parent_fee_payment'),
    path('parent/attendance/', ParentAttendanceListView.as_view(), name='parent_attendance_list'),
    path('parent/report-cards/', ParentReportCardListView.as_view(), name='parent_report_card_list'),
    path('parent/report-cards/<int:student_id>/', ParentReportCardListView.as_view(), name='parent_report_card_list_view'),
    path('parent/report-cards/<int:student_id>/<int:report_card_id>/', ParentReportCardDetailView.as_view(), name='parent_report_card_detail'),
    path('parent/announcements/', ParentAnnouncementListView.as_view(), name='parent_announcements'),
    path('parent/messages/', ParentMessageListView.as_view(), name='parent_messages'),
    path('parent/messages/create/', ParentMessageCreateView.as_view(), name='parent_message_create'),
    path('parent/messages/<int:pk>/', ParentMessageDetailView.as_view(), name='parent_message_detail'),
    path('parent/calendar/', ParentCalendarView.as_view(), name='parent_calendar'),    
    
    # Parent Portal Management URLs (for Admin/Teachers)
    path('parent-directory/', ParentDirectoryView.as_view(), name='parent_directory'),
    path('bulk-parent-message/', BulkParentMessageView.as_view(), name='bulk_parent_message'),
    path('parent-communication-log/', ParentCommunicationLogView.as_view(), name='parent_communication_log'),
    path('parent-engagement-dashboard/', ParentEngagementDashboardView.as_view(), name='parent_engagement_dashboard'),
    
    # API endpoints
    path('api/fee-categories/<int:pk>/', fee_category_detail, name='fee_category_api_detail'),

    # ==============================
    # TIMETABLE URLS
    # ==============================
    
    # Timetable URLs
    path('timeslots/', TimeSlotListView.as_view(), name='timeslot_list'),
    path('timeslots/create/', TimeSlotCreateView.as_view(), name='timeslot_create'),
    path('timeslots/<int:pk>/update/', TimeSlotUpdateView.as_view(), name='timeslot_update'),
    path('timeslots/<int:pk>/delete/', TimeSlotDeleteView.as_view(), name='timeslot_delete'),
    
    path('timetable/', TimetableListView.as_view(), name='timetable_list'),
    path('timetable/create/', TimetableCreateView.as_view(), name='timetable_create'),
    path('timetable/<int:pk>/', TimetableDetailView.as_view(), name='timetable_detail'),
    path('timetable/<int:pk>/manage/', TimetableManageView.as_view(), name='timetable_manage'),
    path('timetable/<int:pk>/delete/', TimetableDeleteView.as_view(), name='timetable_delete'),
    
    path('timetable/student/', StudentTimetableView.as_view(), name='student_timetable'),
    path('timetable/teacher/', TeacherTimetableView.as_view(), name='teacher_timetable'),
    
    path('timetable/ajax/entries/', get_timetable_entries, name='timetable_ajax_entries'),
    path('timetable/generate-weekly/', generate_weekly_timetable, name='generate_weekly_timetable'),
    # AJAX URLs
    path('timetable/ajax/entries/', get_timetable_entries, name='timetable_ajax_entries'),
    path('timetable/generate-weekly/', generate_weekly_timetable, name='generate_weekly_timetable'),
    path('api/timetable-entries/', get_timetable_entries, name='get_timetable_entries'),
    
    # ==============================
    # ANNOUNCEMENT URLS
    # ==============================
    path('announcements/', AnnouncementListView.as_view(), name='announcement_list'),
    path('announcements/create/', CreateAnnouncementView.as_view(), name='create_announcement'),
    path('announcements/<int:pk>/', announcement_detail, name='announcement_detail'),
    path('announcements/<int:pk>/update/', UpdateAnnouncementView.as_view(), name='update_announcement'),
    path('announcements/<int:pk>/delete/', DeleteAnnouncementView.as_view(), name='delete_announcement'),
    path('announcements/<int:pk>/toggle-status/', toggle_announcement_status, name='toggle_announcement_status'),
    path('announcements/active/', get_active_announcements, name='active_announcements'),
    path('announcements/<int:pk>/dismiss/', dismiss_announcement, name='dismiss_announcement'),
    path('announcements/dismiss-all/', dismiss_all_announcements, name='dismiss_all_announcements'),
    path('announcements/bulk-action/', bulk_action_announcements, name='bulk_action_announcements'),
    path('announcements/stats/', AnnouncementStatsView.as_view(), name='announcement_stats'),
]