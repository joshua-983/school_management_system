from urllib.parse import urlencode
from . import views
from .views import AnalyticsDashboardView
from .views import GradeEntryView 
from .views import FeeCreateView
from django.urls import path
from .views import (
    # Basic views
    home, admin_dashboard, teacher_dashboard, student_dashboard,
    student_progress_chart, class_performance_chart,
    
    # Student-related views
    StudentListView, StudentDetailView, StudentCreateView, 
    StudentUpdateView, StudentDeleteView, 
    
    # Parent-related views
    ParentCreateView, ParentUpdateView, ParentDeleteView,
    parent_dashboard, ParentChildrenListView, ParentChildDetailView,
    ParentFeeListView, ParentFeeDetailView, ParentFeePaymentView,
    ParentAttendanceListView, ParentReportCardListView, ParentReportCardDetailView,
    
    # Fee-related views
    FeeCategoryListView, FeeCategoryCreateView, FeeCategoryUpdateView, FeeCategoryDeleteView,
    FeeListView, FeeDetailView, FeeUpdateView, FeeDeleteView,
    FeePaymentCreateView, FeePaymentDeleteView, FeeReportView,
    
    # Subject-related views
    SubjectListView, SubjectCreateView, SubjectUpdateView, SubjectDeleteView, SubjectDetailView,
    
    # Teacher-related views
    TeacherListView, TeacherCreateView, TeacherUpdateView, TeacherDeleteView,
    
    # Assignment-related views
    ClassAssignmentListView, ClassAssignmentCreateView, 
    ClassAssignmentUpdateView, ClassAssignmentDeleteView,
    AssignmentListView, AssignmentDetailView, AssignmentCreateView,
    AssignmentUpdateView, AssignmentDeleteView,
    
    # Grade-related views
    GradeListView, GradeUpdateView, BulkGradeUploadView, 
    
    # Report Card views
    ReportCardDashboardView, ReportCardView, ReportCardPDFView,
    
    # Other views
    NotificationListView, AuditLogListView,
    
    # Attendance views
    AttendanceDashboardView, AttendanceRecordView, load_periods, StudentAttendanceListView
)

urlpatterns = [
    # Home and dashboards
    path('', home, name='home'),
    path('admin-dashboard/', admin_dashboard, name='admin_dashboard'),
    path('teacher-dashboard/', teacher_dashboard, name='teacher_dashboard'),
    path('student-dashboard/', student_dashboard, name='student_dashboard'),
    
    # Student URLs
    path('students/', StudentListView.as_view(), name='student_list'),
    path('students/<int:pk>/', StudentDetailView.as_view(), name='student_detail'),
    path('students/add/', StudentCreateView.as_view(), name='student_add'),
    path('students/<int:pk>/edit/', StudentUpdateView.as_view(), name='student_update'),
    path('students/<int:pk>/delete/', StudentDeleteView.as_view(), name='student_delete'),
    path('student/<int:student_id>/attendance/', AttendanceDashboardView.as_view(), name='student_attendance_summary'),
    
    # Parent/Guardian URLs
    path('students/<int:student_id>/parents/add/', ParentCreateView.as_view(), name='parent_create'),
    path('parents/<int:pk>/edit/', ParentUpdateView.as_view(), name='parent_update'),
    path('parents/<int:pk>/delete/', ParentDeleteView.as_view(), name='parent_delete'),
    
    # Fee Category URLs
    path('fee-categories/', FeeCategoryListView.as_view(), name='fee_category_list'),
    path('fee-categories/add/', FeeCategoryCreateView.as_view(), name='fee_category_create'),
    path('fee-categories/<int:pk>/edit/', FeeCategoryUpdateView.as_view(), name='fee_category_update'),
    path('fee-categories/<int:pk>/delete/', FeeCategoryDeleteView.as_view(), name='fee_category_delete'),
    
    # Fee URLs
    path('fees/', FeeListView.as_view(), name='fee_list'),
    path('fees/<int:pk>/', FeeDetailView.as_view(), name='fee_detail'),
    path('fees/<int:pk>/edit/', FeeUpdateView.as_view(), name='fee_update'),
    path('fees/<int:pk>/delete/', FeeDeleteView.as_view(), name='fee_delete'),
    path('students/<int:student_id>/fees/add/', FeeCreateView.as_view(), name='fee_create'),
    
    # Fee Payment URLs
    path('fees/<int:fee_id>/payments/add/', FeePaymentCreateView.as_view(), name='fee_payment_create'),
    path('payments/<int:pk>/delete/', FeePaymentDeleteView.as_view(), name='fee_payment_delete'),
    
    # Fee Reports
    path('reports/fees/', FeeReportView.as_view(), name='fee_report'),
    
    # Subject URLs
    path('subjects/', SubjectListView.as_view(), name='subject_list'),
    path('subjects/add/', SubjectCreateView.as_view(), name='subject_add'),
    path('subjects/<int:pk>/edit/', SubjectUpdateView.as_view(), name='subject_edit'),
    path('subjects/<int:pk>/delete/', SubjectDeleteView.as_view(), name='subject_delete'),
    path('subjects/<int:pk>/', SubjectDetailView.as_view(), name='subject_detail'),
    
    # Teacher URLs
    path('teachers/', TeacherListView.as_view(), name='teacher_list'),
    path('teachers/add/', TeacherCreateView.as_view(), name='teacher_add'),
    path('teachers/<int:pk>/edit/', TeacherUpdateView.as_view(), name='teacher_edit'),
    path('teachers/<int:pk>/delete/', TeacherDeleteView.as_view(), name='teacher_delete'),
   
    # Assignment URLs
    path('assignments/', AssignmentListView.as_view(), name='assignment_list'),
    path('assignments/create/', AssignmentCreateView.as_view(), name='assignment_create'),
    path('assignments/<int:pk>/', AssignmentDetailView.as_view(), name='assignment_detail'),
    path('assignments/<int:pk>/update/', AssignmentUpdateView.as_view(), name='assignment_update'),
    path('assignments/<int:pk>/delete/', AssignmentDeleteView.as_view(), name='assignment_delete'),
    
    # Class Assignment URLs
    path('class-assignments/', ClassAssignmentListView.as_view(), name='class_assignment_list'),
    path('class-assignments/create/', ClassAssignmentCreateView.as_view(), name='class_assignment_create'),
    path('class-assignments/<int:pk>/update/', ClassAssignmentUpdateView.as_view(), name='class_assignment_update'),
    path('class-assignments/<int:pk>/delete/', ClassAssignmentDeleteView.as_view(), name='class_assignment_delete'),
    path('assignments/add/', AssignmentCreateView.as_view(), name='assignment_add'),
    # Grade URLs
    path('grades/', GradeListView.as_view(), name='grade_list'),
    path('grades/<int:pk>/edit/', GradeUpdateView.as_view(), name='grade_edit'),
    path('grades/bulk-upload/', BulkGradeUploadView.as_view(), name='grade_bulk_upload'),
    path('grades/upload-template/', views.GradeUploadTemplateView.as_view(), name='grade_upload_template'),
    path('grades/add/', GradeEntryView.as_view(), name='grade_add'),
    
    # Report Cards
    path('report-cards/', ReportCardDashboardView.as_view(), name='report_card_dashboard'),
    path('report-card/<int:student_id>/', ReportCardView.as_view(), name='report_card'),
    path('report-card/<int:student_id>/<int:report_card_id>/', ReportCardView.as_view(), name='report_card_detail'),
    path('report-card/pdf/<int:student_id>/', ReportCardPDFView.as_view(), name='report_card_pdf'),
    path('report-card/pdf/<int:student_id>/<int:report_card_id>/', ReportCardPDFView.as_view(), name='report_card_pdf_detail'),
    
    # Progress Charts
    path('students/<int:student_id>/progress-chart/', student_progress_chart, name='student_progress_chart'),
    path('class/<str:class_level>/performance-chart/', class_performance_chart, name='class_performance_chart'),
    
    # Notifications and Audit Logs
    path('notifications/', NotificationListView.as_view(), name='notification_list'),
    path('audit-logs/', AuditLogListView.as_view(), name='audit_log_list'),
    
    # Attendance URLs
    path('attendance/', AttendanceDashboardView.as_view(), name='attendance_dashboard'),
    path('attendance/record/', AttendanceRecordView.as_view(), name='attendance_record'),
    path('attendance/load-periods/', load_periods, name='load_periods'),
    path('student-attendance/', StudentAttendanceListView.as_view(), name='student_attendance_list'),
    
    # Parent URLs
    path('parent/', parent_dashboard, name='parent_dashboard'),
    path('parent/children/', ParentChildrenListView.as_view(), name='parent_children_list'),
    path('parent/children/<int:pk>/', ParentChildDetailView.as_view(), name='parent_child_detail'),
    path('parent/fees/', ParentFeeListView.as_view(), name='parent_fee_list'),
    path('parent/fees/<int:pk>/', ParentFeeDetailView.as_view(), name='parent_fee_detail'),
    path('parent/fees/<int:pk>/pay/', ParentFeePaymentView.as_view(), name='parent_fee_payment'),
    path('parent/attendance/', ParentAttendanceListView.as_view(), name='parent_attendance_list'),
    path('parent/report-cards/', ParentReportCardListView.as_view(), name='parent_report_card_list'),
    path('parent/report-cards/<int:student_id>/', ParentReportCardDetailView.as_view(), name='parent_report_card_detail'),
    path('parent/report-cards/<int:student_id>/<int:report_card_id>/', ParentReportCardDetailView.as_view(), name='parent_report_card_detail'),
    
    # Analytics Dashboard
    path('analytics/', views.AnalyticsDashboardView.as_view(), name='analytics_dashboard'),
]