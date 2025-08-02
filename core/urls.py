from urllib.parse import urlencode
from . import views
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
    
    # Fee-related views
    FeeCategoryListView, FeeCategoryCreateView, FeeCategoryUpdateView, FeeCategoryDeleteView,
    FeeListView, FeeDetailView, FeeCreateView, FeeUpdateView, FeeDeleteView,
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
    
    #Attendance views
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
    path('fees/<int:pk>/edit/', views.FeeUpdateView.as_view(), name='fee_edit'),
    
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
    # Assignment URLs
    path('assignments/', views.AssignmentListView.as_view(), name='assignment_list'),
    path('assignments/create/', views.AssignmentCreateView.as_view(), name='assignment_create'),
    path('assignments/<int:pk>/', views.AssignmentDetailView.as_view(), name='assignment_detail'),
    path('assignments/<int:pk>/update/', views.AssignmentUpdateView.as_view(), name='assignment_update'),
    path('assignments/<int:pk>/delete/', views.AssignmentDeleteView.as_view(), name='assignment_delete'),
    
    
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
    
    # Academic Term URLs
   

    path('attendance/', AttendanceDashboardView.as_view(), name='attendance_dashboard'),
    path('attendance/record/', AttendanceRecordView.as_view(), name='attendance_record'),
    path('attendance/load-periods/', load_periods, name='load_periods'),
    
    # AJAX URLs
    path('attendance/load-periods/', load_periods, name='load_periods'),
    path('attendance/record/', AttendanceRecordView.as_view(), name='attendance_record'),
]