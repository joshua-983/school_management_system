# Create a management command to initialize fee categories
# In core/management/commands/init_fee_categories.py

from django.core.management.base import BaseCommand
from core.models import FeeCategory

class Command(BaseCommand):
    help = 'Initialize default fee categories'

    def handle(self, *args, **kwargs):
        default_categories = [
            {
                'name': 'TUITION',
                'description': 'Tuition fee for academic instruction',
                'default_amount': 5000.00,
                'frequency': 'termly',
                'is_mandatory': True,
                'is_active': True,
            },
            {
                'name': 'TRANSPORT',
                'description': 'Transportation fee',
                'default_amount': 800.00,
                'frequency': 'termly',
                'is_mandatory': False,
                'is_active': True,
            },
            {
                'name': 'EXAMINATION',
                'description': 'Examination fee',
                'default_amount': 200.00,
                'frequency': 'termly',
                'is_mandatory': True,
                'is_active': True,
            },
            {
                'name': 'PTA',
                'description': 'Parent-Teacher Association fee',
                'default_amount': 100.00,
                'frequency': 'termly',
                'is_mandatory': True,
                'is_active': True,
            },
        ]
        
        created_count = 0
        for cat_data in default_categories:
            category, created = FeeCategory.objects.get_or_create(
                name=cat_data['name'],
                defaults=cat_data
            )
            if created:
                created_count += 1
                self.stdout.write(f"Created category: {category.get_name_display()}")
        
        self.stdout.write(self.style.SUCCESS(f'Successfully created {created_count} fee categories'))