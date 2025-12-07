# core/admin_timetable_groups.py
from django.contrib import admin
from django.contrib.auth.models import Group, User
from django.contrib.auth.admin import GroupAdmin, UserAdmin
from django.utils.translation import gettext_lazy as _
from django.contrib import messages
from django.urls import reverse
from django.utils.html import format_html

@admin.register(Group)
class CustomGroupAdmin(GroupAdmin):
    list_display = ('name', 'get_user_count', 'get_permission_count', 'actions')
    list_filter = ('name',)
    search_fields = ('name',)
    
    def get_user_count(self, obj):
        return obj.user_set.count()
    get_user_count.short_description = 'Users'
    get_user_count.admin_order_field = 'user_set__count'
    
    def get_permission_count(self, obj):
        return obj.permissions.count()
    get_permission_count.short_description = 'Permissions'
    
    def actions(self, obj):
        if obj.name in ['Timetable Admin', 'Timetable Teacher', 'Timetable Student', 'Timetable Parent']:
            return format_html(
                '<a href="{}" class="button">View Details</a>',
                reverse('admin:auth_group_change', args=[obj.id])
            )
        return '-'
    actions.short_description = 'Actions'
    
    # Customize the form to show permission categories
    def formfield_for_manytomany(self, db_field, request, **kwargs):
        if db_field.name == "permissions":
            kwargs["queryset"] = kwargs.get("queryset", db_field.remote_field.model.objects.exclude(
                content_type__app_label__in=['admin', 'auth', 'contenttypes', 'sessions']
            ))
        return super().formfield_for_manytomany(db_field, request, **kwargs)

# Add timetable group management to UserAdmin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

class CustomUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'first_name', 'last_name', 'is_staff', 'is_active', 'get_timetable_groups')
    list_filter = ('groups__name', 'is_staff', 'is_active')
    
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Timetable Access', {
            'fields': ('groups',),
            'description': 'Control timetable access permissions'
        }),
    )
    
    def get_timetable_groups(self, obj):
        timetable_groups = obj.groups.filter(name__startswith='Timetable')
        if timetable_groups.exists():
            return ', '.join([g.name.replace('Timetable ', '') for g in timetable_groups])
        return 'None'
    get_timetable_groups.short_description = 'Timetable Roles'
    
    def save_model(self, request, obj, form, change):
        # Check if user is being added to admin group
        if 'Timetable Admin' in [g.name for g in obj.groups.all()]:
            # Ensure admin users are also staff
            obj.is_staff = True
            messages.info(request, f"User {obj.username} added to Timetable Admin group. User has been granted staff status.")
        super().save_model(request, obj, form, change)

# Unregister default UserAdmin and register custom one
from django.contrib.auth.models import User
admin.site.unregister(User)
admin.site.register(User, CustomUserAdmin)