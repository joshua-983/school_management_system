from django.contrib import admin
from .models import DataMaintenance

@admin.register(DataMaintenance)
class DataMaintenanceAdmin(admin.ModelAdmin):
    """Admin for data cleanup operations"""
    
    list_display = ['name', 'created_at', 'get_operations']
    readonly_fields = ['created_at', 'get_operations']
    list_per_page = 20
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return request.user.is_superuser
    
    def has_delete_permission(self, request, obj=None):
        return False
    
    def get_operations(self, obj):
        """Return HTML for maintenance operations"""
        return """
        <div style="padding: 20px;">
            <h3>🚨 System Maintenance Operations</h3>
            <p>Select operations from the action dropdown above and click "Go" to execute.</p>
            <div style="margin-top: 20px; padding: 15px; background: #f8f9fa; border-radius: 5px;">
                <strong>Available Operations:</strong>
                <ul style="margin-top: 10px;">
                    <li><strong>Fix ALL empty attachments</strong> - Cleans up assignments with empty string attachments</li>
                    <li><strong>Recalculate attendance summaries</strong> - Updates all attendance statistics</li>
                    <li><strong>Recalculate grade averages</strong> - Updates report card averages</li>
                    <li><strong>Check academic period migration status</strong> - Shows what needs to be migrated</li>
                </ul>
            </div>
        </div>
        """
    get_operations.short_description = 'Maintenance Operations'
    get_operations.allow_tags = True
    
    actions = [
        'cleanup_empty_attachments', 
        'recalculate_attendance_summaries', 
        'recalculate_grade_averages',
        'migrate_academic_periods'
    ]
    
    # Copy all the action methods from your existing DataMaintenanceAdmin class
    # Just copy the entire methods from your current admin.py DataMaintenanceAdmin class
    # Make sure to import necessary modules at the top of each method