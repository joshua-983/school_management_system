"""
Backup system management command.
Usage: python manage.py backup_system [--type=full|database|media|code] [--compress]
"""
import os
import sys
import shutil
import zipfile
import json
from datetime import datetime
from pathlib import Path
import subprocess
import tempfile
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Create system backup (database, media, code)'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--type',
            type=str,
            default='full',
            choices=['full', 'database', 'media', 'code'],
            help='Type of backup to create'
        )
        parser.add_argument(
            '--compress',
            action='store_true',
            help='Compress backup into ZIP file'
        )
        parser.add_argument(
            '--retention-days',
            type=int,
            default=30,
            help='Clean backups older than X days'
        )
        parser.add_argument(
            '--output-dir',
            type=str,
            default=None,
            help='Custom output directory for backup'
        )
    
    def handle(self, *args, **options):
        backup_type = options['type']
        compress = options['compress']
        retention_days = options['retention_days']
        
        # Create backup directory
        if options['output_dir']:
            backup_dir = Path(options['output_dir'])
        else:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            backup_dir = settings.BASE_DIR / 'backups' / timestamp
        
        backup_dir.mkdir(parents=True, exist_ok=True)
        
        self.stdout.write(f"📦 Starting {backup_type} backup to: {backup_dir}")
        
        try:
            # Perform backup based on type
            if backup_type in ['full', 'database']:
                self.backup_database(backup_dir)
            
            if backup_type in ['full', 'media']:
                self.backup_media_files(backup_dir)
            
            if backup_type in ['full', 'code']:
                self.backup_project_code(backup_dir)
            
            # Create metadata file
            self.create_metadata(backup_dir, backup_type)
            
            # Clean old backups
            if retention_days > 0:
                self.clean_old_backups(retention_days)
            
            # Compress if requested
            if compress:
                backup_zip = self.compress_backup(backup_dir)
                self.stdout.write(self.style.SUCCESS(f"✅ Backup compressed: {backup_zip}"))
                # Remove uncompressed directory
                shutil.rmtree(backup_dir)
                backup_path = backup_zip
            else:
                backup_path = backup_dir
            
            self.stdout.write(self.style.SUCCESS(f"✅ Backup completed successfully!"))
            self.stdout.write(f"   Location: {backup_path}")
            self.stdout.write(f"   Size: {self.get_size(backup_path)}")
            
            # Log to AuditLog
            self.log_backup_action(backup_type, str(backup_path), True)
            
        except Exception as e:
            error_msg = f"Backup failed: {str(e)}"
            self.stdout.write(self.style.ERROR(f"❌ {error_msg}"))
            logger.error(error_msg, exc_info=True)
            self.log_backup_action(backup_type, str(backup_dir), False, str(e))
            sys.exit(1)
    
    def backup_database(self, backup_dir):
        """Backup database based on engine type"""
        db_config = settings.DATABASES['default']
        engine = db_config['ENGINE']
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        
        if 'mysql' in engine:
            self.backup_mysql(db_config, backup_dir, timestamp)
        elif 'sqlite3' in engine:
            self.backup_sqlite(db_config, backup_dir, timestamp)
        else:
            raise ValueError(f"Unsupported database engine: {engine}")
    
    def backup_mysql(self, db_config, backup_dir, timestamp):
        """Backup MySQL database"""
        self.stdout.write("🔍 Backing up MySQL database...")
        
        db_name = db_config['NAME']
        db_user = db_config['USER']
        db_password = db_config['PASSWORD']
        db_host = db_config['HOST'] or 'localhost'
        db_port = db_config['PORT'] or '3306'
        
        backup_file = backup_dir / f'mysql_backup_{timestamp}.sql'
        
        # Create mysqldump command
        cmd = [
            'mysqldump',
            f'--user={db_user}',
            f'--password={db_password}',
            f'--host={db_host}',
            f'--port={db_port}',
            '--single-transaction',
            '--routines',
            '--triggers',
            '--events',
            db_name
        ]
        
        try:
            with open(backup_file, 'w') as f:
                process = subprocess.run(
                    cmd,
                    stdout=f,
                    stderr=subprocess.PIPE,
                    text=True,
                    check=True
                )
            
            # Also export as JSON for easier inspection
            json_file = backup_dir / f'database_schema_{timestamp}.json'
            self.export_database_schema(json_file)
            
            self.stdout.write(f"   ✓ MySQL backup: {backup_file}")
            self.stdout.write(f"   ✓ Schema export: {json_file}")
            
        except subprocess.CalledProcessError as e:
            raise Exception(f"MySQL backup failed: {e.stderr}")
        except FileNotFoundError:
            raise Exception("mysqldump command not found. Install mysql-client.")
    
    def backup_sqlite(self, db_config, backup_dir, timestamp):
        """Backup SQLite database"""
        self.stdout.write("🔍 Backing up SQLite database...")
        
        db_path = Path(db_config['NAME'])
        if not db_path.is_absolute():
            db_path = settings.BASE_DIR / db_path
        
        backup_file = backup_dir / f'sqlite_backup_{timestamp}.db'
        
        try:
            shutil.copy2(db_path, backup_file)
            self.stdout.write(f"   ✓ SQLite backup: {backup_file}")
        except Exception as e:
            raise Exception(f"SQLite backup failed: {str(e)}")
    
    def backup_media_files(self, backup_dir):
        """Backup media files"""
        self.stdout.write("🖼️  Backing up media files...")
        
        media_root = Path(settings.MEDIA_ROOT)
        if not media_root.exists():
            self.stdout.write("   ⚠️  Media directory not found, skipping...")
            return
        
        media_backup = backup_dir / 'media'
        
        try:
            # Copy media files
            if media_backup.exists():
                shutil.rmtree(media_backup)
            
            shutil.copytree(media_root, media_backup)
            
            # Count files
            file_count = sum(1 for _ in media_backup.rglob('*') if _.is_file())
            self.stdout.write(f"   ✓ Media files: {file_count} files copied")
            
        except Exception as e:
            raise Exception(f"Media backup failed: {str(e)}")
    
    def backup_project_code(self, backup_dir):
        """Backup project code (excluding venv, backups, etc.)"""
        self.stdout.write("💻 Backing up project code...")
        
        code_backup = backup_dir / 'code'
        code_backup.mkdir(exist_ok=True)
        
        # Files/directories to exclude
        exclude_patterns = [
            '__pycache__',
            '*.pyc',
            '*.pyo',
            '*.pyd',
            '.git',
            'venv',
            'env',
            'node_modules',
            'backups',
            'media',
            'staticfiles',
            '*.log',
            '*.sqlite3',
            '*.db',
            '.DS_Store',
        ]
        
        try:
            # Copy key files
            key_files = [
                'manage.py',
                'requirements.txt',
                'Dockerfile',
                'docker-compose.yml',
                '.env.example',
                'pyproject.toml',
            ]
            
            for file_name in key_files:
                file_path = settings.BASE_DIR / file_name
                if file_path.exists():
                    shutil.copy2(file_path, code_backup / file_name)
            
            # Copy directories
            dirs_to_copy = ['core', 'accounts', 'templates', 'static']
            for dir_name in dirs_to_copy:
                dir_path = settings.BASE_DIR / dir_name
                if dir_path.exists() and dir_path.is_dir():
                    dest_dir = code_backup / dir_name
                    shutil.copytree(
                        dir_path,
                        dest_dir,
                        ignore=shutil.ignore_patterns(*exclude_patterns)
                    )
            
            self.stdout.write(f"   ✓ Project code backed up")
            
        except Exception as e:
            raise Exception(f"Code backup failed: {str(e)}")
    
    def export_database_schema(self, json_file):
        """Export database schema as JSON"""
        from django.core.management import call_command
        from io import StringIO
        
        out = StringIO()
        call_command('dumpdata', '--exclude', 'contenttypes', '--exclude', 'auth.permission', 
                    '--exclude', 'admin.logentry', '--exclude', 'sessions.session',
                    '--exclude', 'axes.accessattempt', '--exclude', 'axes.accessfailure',
                    '--exclude', 'axes.accesslog', '--indent', '2', stdout=out)
        
        with open(json_file, 'w') as f:
            f.write(out.getvalue())
    
    def create_metadata(self, backup_dir, backup_type):
        """Create metadata file for backup"""
        metadata = {
            'backup_type': backup_type,
            'timestamp': timezone.now().isoformat(),
            'django_version': self.get_django_version(),
            'project_name': 'School Management System',
            'environment': getattr(settings, 'ENVIRONMENT', 'unknown'),
            'database_engine': settings.DATABASES['default']['ENGINE'],
            'file_count': self.count_files(backup_dir),
            'total_size': self.get_size(backup_dir),
        }
        
        metadata_file = backup_dir / 'backup_metadata.json'
        with open(metadata_file, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        self.stdout.write(f"   ✓ Metadata: {metadata_file}")
    
    def clean_old_backups(self, retention_days):
        """Remove backups older than retention_days"""
        backups_dir = settings.BASE_DIR / 'backups'
        if not backups_dir.exists():
            return
        
        cutoff_date = timezone.now() - timezone.timedelta(days=retention_days)
        deleted_count = 0
        
        for backup in backups_dir.iterdir():
            if backup.is_dir():
                try:
                    # Parse date from directory name (YYYYMMDD_HHMMSS)
                    dir_date = datetime.strptime(backup.name[:15], '%Y%m%d_%H%M%S')
                    if dir_date.replace(tzinfo=timezone.utc) < cutoff_date:
                        shutil.rmtree(backup)
                        deleted_count += 1
                except (ValueError, IndexError):
                    # If directory name doesn't match pattern, skip
                    continue
        
        if deleted_count > 0:
            self.stdout.write(f"🧹 Cleaned {deleted_count} old backups")
    
    def compress_backup(self, backup_dir):
        """Compress backup directory into ZIP file"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_path = settings.BASE_DIR / 'backups' / f'backup_{timestamp}.zip'
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(backup_dir):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(backup_dir)
                    zipf.write(file_path, arcname)
        
        return zip_path
    
    def get_django_version(self):
        import django
        return django.get_version()
    
    def count_files(self, directory):
        return sum(1 for _ in Path(directory).rglob('*') if _.is_file())
    
    def get_size(self, path):
        """Get size of file or directory in human readable format"""
        path = Path(path)
        if path.is_file():
            size = path.stat().st_size
        else:
            size = sum(f.stat().st_size for f in path.rglob('*') if f.is_file())
        
        # Convert to human readable
        for unit in ['B', 'KB', 'MB', 'GB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} TB"
    
    def log_backup_action(self, backup_type, location, success, error_message=None):
        """Log backup action to AuditLog"""
        try:
            from core.models import AuditLog
            
            AuditLog.objects.create(
                user=None,  # System action
                action='SYSTEM_BACKUP',
                model_name='System',
                object_id='backup',
                details={
                    'backup_type': backup_type,
                    'location': location,
                    'success': success,
                    'error_message': error_message,
                    'timestamp': timezone.now().isoformat(),
                },
                ip_address='127.0.0.1',
                user_agent='BackupSystem/1.0'
            )
        except Exception as e:
            logger.warning(f"Failed to log backup action: {e}")