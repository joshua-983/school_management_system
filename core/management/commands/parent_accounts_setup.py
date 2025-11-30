# core/management/commands/parent_accounts_setup.py
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from core.models import ParentGuardian, Student
from django.utils import timezone

User = get_user_model()

class Command(BaseCommand):
    help = 'Setup parent accounts and assign students'

    def add_arguments(self, parser):
        parser.add_argument(
            '--create-accounts',
            action='store_true',
            help='Create user accounts for parents without accounts',
        )
        parser.add_argument(
            '--assign-students',
            action='store_true',
            help='Assign students to parents based on existing relationships',
        )
        parser.add_argument(
            '--activate-all',
            action='store_true',
            help='Activate all parent accounts',
        )

    def handle(self, *args, **options):
        if options['create_accounts']:
            self.create_parent_accounts()
        
        if options['assign_students']:
            self.assign_students_to_parents()
        
        if options['activate_all']:
            self.activate_all_accounts()

    def create_parent_accounts(self):
        """Create user accounts for parents without accounts"""
        parents_without_accounts = ParentGuardian.objects.filter(user__isnull=True)
        
        self.stdout.write(f"Found {parents_without_accounts.count()} parents without user accounts")
        
        for parent in parents_without_accounts:
            if parent.email:
                try:
                    parent.create_user_account()
                    self.stdout.write(
                        self.style.SUCCESS(f'Created account for {parent.email}')
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error creating account for {parent.email}: {e}')
                    )
        
        self.stdout.write(self.style.SUCCESS('Parent account creation completed'))

    def assign_students_to_parents(self):
        """Assign students to parents based on existing relationships"""
        # This would depend on your existing data structure
        # You might need to customize this based on how students and parents are related
        self.stdout.write('Student assignment functionality would be implemented here')

    def activate_all_accounts(self):
        """Activate all parent accounts"""
        inactive_parents = ParentGuardian.objects.exclude(account_status='active')
        
        self.stdout.write(f"Activating {inactive_parents.count()} parent accounts")
        
        for parent in inactive_parents:
            parent.account_status = 'active'
            parent.save()
        
        self.stdout.write(self.style.SUCCESS('All parent accounts activated'))