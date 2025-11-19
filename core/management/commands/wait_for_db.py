import time
from django.core.management.base import BaseCommand
from django.db import connections
from django.db.utils import OperationalError

class Command(BaseCommand):
    """Django command to pause execution until database is available"""
    
    def handle(self, *args, **options):
        self.stdout.write('Waiting for database...')
        max_retries = 30
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                # Try to connect to the database
                db_conn = connections['default']
                with db_conn.cursor() as cursor:
                    cursor.execute("SELECT 1;")
                self.stdout.write(self.style.SUCCESS('Database available!'))
                return
            except OperationalError:
                self.stdout.write(
                    self.style.WARNING(
                        f'Database unavailable, waiting 5 seconds... '
                        f'({retry_count + 1}/{max_retries})'
                    )
                )
                retry_count += 1
                time.sleep(5)
        
        self.stdout.write(
            self.style.ERROR('Could not connect to database after maximum retries')
        )
        raise OperationalError("Database connection failed")