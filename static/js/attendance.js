// Attendance form dynamic behavior
document.addEventListener('DOMContentLoaded', function() {
    // Initialize date pickers
    $('.datepicker').datepicker({
        format: 'yyyy-mm-dd',
        autoclose: true,
        todayHighlight: true
    });

    // Dynamic period loading based on term selection
    $('#id_term').change(function() {
        const termId = $(this).val();
        const periodSelect = $('#id_period');
        
        if (termId) {
            // Clear existing options
            periodSelect.empty();
            periodSelect.append($('<option>', {
                value: '',
                text: 'Select a period'
            }));
            
            // Fetch periods for selected term
            $.ajax({
                url: '/attendance/load-periods/',
                data: {
                    'term_id': termId
                },
                success: function(data) {
                    periodSelect.html(data);
                }
            });
        } else {
            periodSelect.empty();
            periodSelect.append($('<option>', {
                value: '',
                text: 'Select a term first'
            }));
        }
    });

    // Confirm before deleting records
    $('.delete-btn').click(function(e) {
        if (!confirm('Are you sure you want to delete this record?')) {
            e.preventDefault();
        }
    });

    // Initialize attendance status badges tooltips
    $('.attendance-badge').tooltip({
        trigger: 'hover',
        placement: 'top'
    });

    // Initialize summary charts
    if ($('#attendanceChart').length) {
        const ctx = document.getElementById('attendanceChart').getContext('2d');
        const chart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: ['Present', 'Absent', 'Late', 'Excused'],
                datasets: [{
                    label: 'Attendance Summary',
                    data: [
                        $('#present-count').data('count'),
                        $('#absent-count').data('count'),
                        $('#late-count').data('count'),
                        $('#excused-count').data('count')
                    ],
                    backgroundColor: [
                        'rgba(40, 167, 69, 0.7)',
                        'rgba(220, 53, 69, 0.7)',
                        'rgba(255, 193, 7, 0.7)',
                        'rgba(23, 162, 184, 0.7)'
                    ],
                    borderColor: [
                        'rgba(40, 167, 69, 1)',
                        'rgba(220, 53, 69, 1)',
                        'rgba(255, 193, 7, 1)',
                        'rgba(23, 162, 184, 1)'
                    ],
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                scales: {
                    y: {
                        beginAtZero: true
                    }
                }
            }
        });
    }
});