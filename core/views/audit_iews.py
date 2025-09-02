from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView
from django.contrib.auth.decorators import login_required
class AuditLogListView(LoginRequiredMixin, UserPassesTestMixin, ListView):
    template_name = 'core/analytics/audit_log_list.html'
    context_object_name = 'logs'
    paginate_by = 20
    
    def test_func(self):
        return is_admin(self.request.user)
    
    def get_queryset(self):
        return AuditLog.objects.all().order_by('-timestamp')

@login_required
def student_progress_chart(request, student_id):
    student = get_object_or_404(Student, pk=student_id)
    
    # Check permissions
    if is_student(request.user) and request.user.student != student:
        raise PermissionDenied
    elif is_teacher(request.user):
        # Check if teacher teaches this student
        if not ClassAssignment.objects.filter(
            class_level=student.class_level,
            teacher=request.user.teacher
        ).exists():
            raise PermissionDenied
    
    grades = Grade.objects.filter(student=student).order_by('subject')
    
    subjects = [grade.subject.name for grade in grades]
    scores = [float(grade.total_score) for grade in grades]
    
    data = {
        'subjects': subjects,
        'scores': scores,
    }
    
    return JsonResponse(data)

@login_required
def class_performance_chart(request, class_level):
    # Check permissions
    if is_student(request.user):
        raise PermissionDenied
    elif is_teacher(request.user):
        # Check if teacher teaches this class
        if not ClassAssignment.objects.filter(
            class_level=class_level,
            teacher=request.user.teacher
        ).exists():
            raise PermissionDenied
    
    grades = Grade.objects.filter(
        class_assignment__class_level=class_level
    ).values('subject__name').annotate(
        average_score=Avg('total_score')
    ).order_by('subject__name')
    
    subjects = [grade['subject__name'] for grade in grades]
    averages = [float(grade['average_score']) for grade in grades]
    
    data = {
        'subjects': subjects,
        'averages': averages,
    }
    
    return JsonResponse(data)


def submit_assignment(request, assignment_id):
    student = request.user.student
    assignment = get_object_or_404(Assignment, pk=assignment_id)
    student_assignment, created = StudentAssignment.objects.get_or_create(
        student=student,
        assignment=assignment
    )

    if request.method == 'POST':
        form = StudentAssignmentForm(request.POST, request.FILES, instance=student_assignment)
        if form.is_valid():
            form.save()
            return redirect('assignment_detail', pk=assignment_id)
    else:
        form = StudentAssignmentForm(instance=student_assignment)

    return render(request, 'submit_assignment.html', {'form': form, 'assignment': assignment})


