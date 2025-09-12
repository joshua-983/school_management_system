from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views.grade_views import CalculateGradeAPI
# Import from the new modular views
from .views.bill_views import BillListView, BillDetailView, BillGenerateView
from .views.base_views import home, admin_dashboard, teacher_dashboard, student_dashboard
from .views.student_views import StudentListView, StudentDetailView, StudentCreateView, StudentUpdateView, StudentDeleteView, StudentGradeListView, StudentAttendanceView, StudentFeeListView, StudentProfileView
from .views.parents_views import (
    ParentCreateView, ParentUpdateView, ParentDeleteView, parent_dashboard,
    ParentChildrenListView, ParentChildDetailView, ParentFeeListView, ParentFeeDetailView,
    ParentFeePaymentView, ParentAttendanceListView, ParentReportCardListView, ParentReportCardDetailView
)

# Add these imports to your existing parents_views imports
from .views.parents_views import (
    ParentDashboardView, ParentAnnouncementListView, ParentMessageListView,
    ParentMessageCreateView, ParentCalendarView, ParentMessageDetailView
)
from .views.fee_views import (
    FeeCategoryListView, FeeCategoryCreateView, FeeCategoryUpdateView, FeeCategoryDeleteView,
    FeeListView, FeeDetailView, FeeCreateView, FeeUpdateView, FeeDeleteView,
    FeePaymentCreateView, FeePaymentDeleteView, FeeReportView, FeeDashboardView
)
from .views.subjects_views import SubjectListView, SubjectDetailView, SubjectCreateView, SubjectUpdateView, SubjectDeleteView
from .views.teacher_views import TeacherListView, TeacherCreateView, TeacherUpdateView, TeacherDeleteView
from .views.class_assignments import ClassAssignmentListView, ClassAssignmentCreateView, ClassAssignmentUpdateView, ClassAssignmentDeleteView
from .views.assignment_views import AssignmentListView, AssignmentDetailView, AssignmentCreateView, AssignmentUpdateView, AssignmentDeleteView
from .views.grade_views import (
    GradeListView, GradeUpdateView, BulkGradeUploadView, GradeEntryView, GradeReportView,
    BestStudentsView, grade_delete, GradeUploadTemplateView
)
from .views.reportcard_views import ReportCardDashboardView, CreateReportCardView, ReportCardView, ReportCardPDFView, SaveReportCardView
from .views.analytics_views import AnalyticsDashboardView
from .views.audit_views import AuditLogListView, student_progress_chart, class_performance_chart
from .views.attendance_views import AttendanceDashboardView, AttendanceRecordView, load_periods, StudentAttendanceListView
from .views.timetable_views import (
    TimeSlotListView, TimeSlotCreateView, TimeSlotUpdateView, TimeSlotDeleteView,
    TimetableListView, TimetableCreateView, TimetableDetailView, TimetableManageView, TimetableDeleteView,
    StudentTimetableView, TeacherTimetableView, get_timetable_entries, generate_weekly_timetable
)
from .views.api import fee_category_detail
from .views.misc import NotificationListView, mark_notification_read

# Import API views
from .api import FeeCategoryViewSet

router = DefaultRouter()
router.register(r'fee-categories', FeeCategoryViewSet, basename='fee-category')

urlpatterns = [
    # API endpoints
    path('api/', include(router.urls)),
    path('__debug__/', include('debug_toolbar.urls')),
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
    
    # Student URLs
    path('student/profile/', StudentProfileView.as_view(), name='student_profile'),
    path('student/grades/', StudentGradeListView.as_view(), name='student_grades'),
    path('student/attendance/', StudentAttendanceView.as_view(), name='student_attendance'),
    path('student/fees/', StudentFeeListView.as_view(), name='student_fees'),
    
    # Parent/Guardian URLs
    path('students/<int:student_id>/parents/add/', ParentCreateView.as_view(), name='parent_create'),
    path('parents/<int:pk>/edit/', ParentUpdateView.as_view(), name='parent_update'),
    path('parents/<int:pk>/delete/', ParentDeleteView.as_view(), name='parent_delete'),
    
    # Fee Category URLs
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
    
    # Fee Payment URLs
    path('fees/<int:fee_id>/payments/add/', FeePaymentCreateView.as_view(), name='fee_payment_create'),
    path('payments/<int:pk>/delete/', FeePaymentDeleteView.as_view(), name='fee_payment_delete'),
    
    # Fee Reports
    path('reports/fees/', FeeReportView.as_view(), name='fee_report'),
# bill
    path('bills/', BillListView.as_view(), name='bill_list'),
    path('bills/generate/', BillGenerateView.as_view(), name='bill_generate'),
    path('bills/<int:pk>/', BillDetailView.as_view(), name='bill_detail'),
    
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
    path('grades/add/', GradeEntryView.as_view(), name='grade_add'),
    path('grades/<int:pk>/edit/', GradeUpdateView.as_view(), name='grade_edit'),
    path('grades/bulk-upload/', BulkGradeUploadView.as_view(), name='grade_bulk_upload'),
    path('grades/upload-template/', GradeUploadTemplateView.as_view(), name='grade_upload_template'),
    path('grades/report/', GradeReportView.as_view(), name='grade_report'),
    path('best-students/', BestStudentsView.as_view(), name='best_students'),
    path('grades/delete/<int:pk>/', grade_delete, name='grade_delete'),
    path('api/calculate-grade/', CalculateGradeAPI.as_view(), name='calculate_grade_api'),
    # Report Cards
    path('report-cards/', ReportCardDashboardView.as_view(), name='report_card_dashboard'),
    path('report-card/create/', CreateReportCardView.as_view(), name='create_report_card'), 
    path('report-card/<int:student_id>/', ReportCardView.as_view(), name='report_card'),
    path('report-card/<int:student_id>/<int:report_card_id>/', ReportCardView.as_view(), name='report_card_detail'),
    path('report-card/pdf/<int:student_id>/', ReportCardPDFView.as_view(), name='report_card_pdf'),
    path('report-card/pdf/<int:student_id>/<int:report_card_id>/', ReportCardPDFView.as_view(), name='report_card_pdf_detail'),
    path('report-card/save/<int:student_id>/', SaveReportCardView.as_view(), name='save_report_card'),
    
    # Progress Charts
    path('students/<int:student_id>/progress-chart/', student_progress_chart, name='student_progress_chart'),
    path('class/<str:class_level>/performance-chart/', class_performance_chart, name='class_performance_chart'),
    
    # Notifications and Audit Logs
    path('notifications/', NotificationListView.as_view(), name='notification_list'),
    path('notifications/<int:pk>/mark-read/', mark_notification_read, name='mark_notification_read'),
    path('audit-logs/', AuditLogListView.as_view(), name='audit_log_list'),
    
    # Attendance URLs
    path('attendance/', AttendanceDashboardView.as_view(), name='attendance_dashboard'),
    path('attendance/record/', AttendanceRecordView.as_view(), name='attendance_record'),
    path('attendance/load-periods/', load_periods, name='load_periods'),
    path('student-attendance/', StudentAttendanceListView.as_view(), name='student_attendance_list'),
    
    # Parent URLs
    path('parent/dashboard/', parent_dashboard, name='parent_dashboard'),
    path('parent/children/', ParentChildrenListView.as_view(), name='parent_children_list'),
    path('parent/children/<int:pk>/', ParentChildDetailView.as_view(), name='parent_child_detail'),
    path('parent/fees/', ParentFeeListView.as_view(), name='parent_fee_list'),
    path('parent/fees/<int:pk>/', ParentFeeDetailView.as_view(), name='parent_fee_detail'),
    path('parent/fees/<int:pk>/pay/', ParentFeePaymentView.as_view(), name='parent_fee_payment'),
    path('parent/attendance/', ParentAttendanceListView.as_view(), name='parent_attendance_list'),
    path('parent/report-cards/', ParentReportCardListView.as_view(), name='parent_report_card_list'),
    path('parent/report-cards/<int:student_id>/', ParentReportCardDetailView.as_view(), name='parent_report_card_detail'),
    path('parent/report-cards/<int:student_id>/<int:report_card_id>/', ParentReportCardDetailView.as_view(), name='parent_report_card_detail'),
    
    # Add to your urls.py in the parent section
    
    # Parent URLs
    path('parent/dashboard/', ParentDashboardView.as_view(), name='parent_dashboard'),
    path('parent/children/', ParentChildrenListView.as_view(), name='parent_children_list'),
    path('parent/child/<int:pk>/', ParentChildDetailView.as_view(), name='parent_child_detail'),
    path('parent/fees/', ParentFeeListView.as_view(), name='parent_fee_list'),
    path('parent/fee/<int:pk>/', ParentFeeDetailView.as_view(), name='parent_fee_detail'),
    path('parent/attendance/', ParentAttendanceListView.as_view(), name='parent_attendance_list'),
    path('parent/report-cards/', ParentReportCardListView.as_view(), name='parent_report_card_list'),
    
    
    
    # Analytics Dashboard
    path('analytics/', AnalyticsDashboardView.as_view(), name='analytics_dashboard'),
    path('api/fee-categories/<int:pk>/', fee_category_detail, name='fee_category_api_detail'),

    # Timetable URLs
    # TimeSlot URLs
    path('timeslots/', TimeSlotListView.as_view(), name='timeslot_list'),
    path('timeslots/create/', TimeSlotCreateView.as_view(), name='timeslot_create'),
    path('timeslots/<int:pk>/update/', TimeSlotUpdateView.as_view(), name='timeslot_update'),
    path('timeslots/<int:pk>/delete/', TimeSlotDeleteView.as_view(), name='timeslot_delete'),
    
    # Timetable URLs
    path('timetable/', TimetableListView.as_view(), name='timetable_list'),
    path('timetable/create/', TimetableCreateView.as_view(), name='timetable_create'),
    path('timetable/<int:pk>/', TimetableDetailView.as_view(), name='timetable_detail'),
    path('timetable/<int:pk>/manage/', TimetableManageView.as_view(), name='timetable_manage'),
    path('timetable/<int:pk>/delete/', TimetableDeleteView.as_view(), name='timetable_delete'),
    
    # Student/Parent/Teacher Views
    path('timetable/student/', StudentTimetableView.as_view(), name='student_timetable'),
    path('timetable/teacher/', TeacherTimetableView.as_view(), name='teacher_timetable'),
    
    # AJAX URLs
    path('timetable/ajax/entries/', get_timetable_entries, name='timetable_ajax_entries'),
    path('timetable/generate-weekly/', generate_weekly_timetable, name='generate_weekly_timetable'),
    path('api/timetable-entries/', get_timetable_entries, name='get_timetable_entries'),
]