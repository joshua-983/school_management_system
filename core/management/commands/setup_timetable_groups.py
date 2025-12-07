# core/management/commands/setup_timetable_groups.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from core.models import Timetable, TimetableEntry, TimeSlot

class Command(BaseCommand):
    help = 'Set up user groups and permissions for timetable management'

    def handle(self, *args, **kwargs):
        with transaction.atomic():
            # Get content types
            timetable_ct = ContentType.objects.get_for_model(Timetable)
            timetable_entry_ct = ContentType.objects.get_for_model(TimetableEntry)
            timeslot_ct = ContentType.objects.get_for_model(TimeSlot)
            
            self.stdout.write('Creating timetable permissions...')
            
            # Create permissions if they don't exist
            timetable_perms = [
                ('view_timetable', 'Can view timetable'),
                ('add_timetable', 'Can add timetable'),
                ('change_timetable', 'Can change timetable'),
                ('delete_timetable', 'Can delete timetable'),
                ('manage_timetable', 'Can manage timetable'),
            ]
            
            timetable_entry_perms = [
                ('view_timetableentry', 'Can view timetable entry'),
                ('add_timetableentry', 'Can add timetable entry'),
                ('change_timetableentry', 'Can change timetable entry'),
                ('delete_timetableentry', 'Can delete timetable entry'),
                ('manage_timetableentry', 'Can manage timetable entry'),
            ]
            
            timeslot_perms = [
                ('view_timeslot', 'Can view time slot'),
                ('add_timeslot', 'Can add time slot'),
                ('change_timeslot', 'Can change time slot'),
                ('delete_timeslot', 'Can delete time slot'),
            ]
            
            # Create permissions
            permissions_map = {}
            for codename, name in timetable_perms:
                perm, created = Permission.objects.get_or_create(
                    codename=codename,
                    content_type=timetable_ct,
                    defaults={'name': name}
                )
                permissions_map[codename] = perm
                
            for codename, name in timetable_entry_perms:
                perm, created = Permission.objects.get_or_create(
                    codename=codename,
                    content_type=timetable_entry_ct,
                    defaults={'name': name}
                )
                permissions_map[codename] = perm
                
            for codename, name in timeslot_perms:
                perm, created = Permission.objects.get_or_create(
                    codename=codename,
                    content_type=timeslot_ct,
                    defaults={'name': name}
                )
                permissions_map[codename] = perm
            
            # Create or update groups
            self.stdout.write('Creating user groups...')
            
            # 1. Admin Group - All permissions
            admin_group, created = Group.objects.get_or_create(name='Timetable Admin')
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created group: {admin_group.name}'))
            
            # Add all permissions to admin group
            admin_permissions = [
                'view_timetable', 'add_timetable', 'change_timetable', 'delete_timetable', 'manage_timetable',
                'view_timetableentry', 'add_timetableentry', 'change_timetableentry', 'delete_timetableentry', 'manage_timetableentry',
                'view_timeslot', 'add_timeslot', 'change_timeslot', 'delete_timeslot'
            ]
            
            for perm_codename in admin_permissions:
                admin_group.permissions.add(permissions_map[perm_codename])
            admin_group.save()
            self.stdout.write(self.style.SUCCESS(f'Added all permissions to {admin_group.name} group'))
            
            # 2. Teacher Group - View permissions only
            teacher_group, created = Group.objects.get_or_create(name='Timetable Teacher')
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created group: {teacher_group.name}'))
            
            teacher_permissions = [
                'view_timetable',
                'view_timetableentry',
                'view_timeslot'
            ]
            
            for perm_codename in teacher_permissions:
                teacher_group.permissions.add(permissions_map[perm_codename])
            teacher_group.save()
            self.stdout.write(self.style.SUCCESS(f'Added view permissions to {teacher_group.name} group'))
            
            # 3. Student Group - Custom permission for viewing own timetable
            student_group, created = Group.objects.get_or_create(name='Timetable Student')
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created group: {student_group.name}'))
            
            # Student can only view timetables (will be filtered by class in views)
            student_group.permissions.add(permissions_map['view_timetable'])
            student_group.permissions.add(permissions_map['view_timetableentry'])
            student_group.save()
            self.stdout.write(self.style.SUCCESS(f'Added limited view permissions to {student_group.name} group'))
            
            # 4. Parent Group - Custom permission for viewing child's timetable
            parent_group, created = Group.objects.get_or_create(name='Timetable Parent')
            if created:
                self.stdout.write(self.style.SUCCESS(f'Created group: {parent_group.name}'))
            
            parent_group.permissions.add(permissions_map['view_timetable'])
            parent_group.permissions.add(permissions_map['view_timetableentry'])
            parent_group.save()
            self.stdout.write(self.style.SUCCESS(f'Added limited view permissions to {parent_group.name} group'))
            
            self.stdout.write(self.style.SUCCESS('\n✅ Successfully set up all timetable groups and permissions!'))
            self.stdout.write('\nGroup Summary:')
            self.stdout.write(f'  • {admin_group.name}: Full CRUD access to all timetable components')
            self.stdout.write(f'  • {teacher_group.name}: View access to timetables and entries')
            self.stdout.write(f'  • {student_group.name}: View access to own timetable (filtered by class)')
            self.stdout.write(f'  • {parent_group.name}: View access to child\'s timetable')