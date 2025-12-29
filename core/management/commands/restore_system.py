"""
Restore system from backup.
Usage: python manage.py restore_system <backup_path> [--type=full|database|media]
"""
import os
import shutil
import zipfile
import json
from pathlib import Path
import subprocess
from django.core.management.base import BaseCommand
from django.conf import settings
from django.utils import timezone
import logging

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Restore system from backup'
    
    def add_arguments(self, parser):
        parser.add_argument(
            'backup_path',
            type=str,
            help='Path to backup directory or ZIP file'
        )
        parser.add_argument(
            '--type',
            type=str,
            default='full',
            choices=['full', 'database', 'media'],
            help='Type of restore to perform'
        )
        parser.add_argument(
            '--yes',
            action='store_true',
            help='Skip confirmation prompt'
        )
    
    def handle(self, *args, **options):
        backup_path = Path(options['backup_path'])
        restore_type = options['type']
        skip_confirmation = options['yes']
        
        if not backup_path.exists():
            self.stdout.write(self.style.ERROR(f"❌ Backup not found: {backup_path}"))
            return
        
        # Check if it's a ZIP file
        is_zip = backup_path.suffix.lower() == '.zip'
        
        # Extract backup if needed
        if is_zip:
            backup_dir = self.extract_backup(backup_path)
        else:
            backup_dir = backup_path
        
        # Verify backup structure
        if not self.verify_backup(backup_dir):
            self.stdout.write(self.style.ERROR("❌ Invalid backup structure"))
            if is_zip:
                shutil.rmtree(backup_dir)
            return
        
        # Show backup info
        self.show_backup_info(backup_dir)
        
        # Confirm restore
        if not skip_confirmation:
            confirm = input("\n⚠️  WARNING: This will overwrite existing data!\nType 'YES' to continue: ")
            if confirm != 'YES':
                self.stdout.write("Restore cancelled")
                if is_zip:
                    shutil.rmtree(backup_dir)
                return
        
        try:
            self.stdout.write(f"🔄 Starting {restore_type} restore...")
            
            if restore_type in ['full', 'database']:
                self.restore_database(backup_dir)
            
            if restore_type in ['full', 'media']:
                self.restore_media_files(backup_dir)
            
            # Clean up extracted directory
            if is_zip:
                shutil.rmtree(backup_dir)
            
            self.stdout.write(self.style.SUCCESS("✅ Restore completed successfully!"))
            
            # Log restore action
            self.log_restore_action(restore_type, str(backup_path), True)
            
        except Exception as e:
            error_msg = f"Restore failed: {str(e)}"
            self.stdout.write(self.style.ERROR(f"❌ {error_msg}"))
            logger.error(error_msg, exc_info=True)
            self.log_restore_action(restore_type, str(backup_path), False, str(e))
    
    def extract_backup(self, zip_path):
        """Extract ZIP backup to temporary directory"""
        temp_dir = Path(tempfile.mkdtemp(prefix='restore_'))
        self.stdout.write(f"📦 Extracting backup to: {temp_dir}")
        
        with zipfile.ZipFile(zip_path, 'r') as zipf:
            zipf.extractall(temp_dir)
        
        return temp_dir
    
    def verify_backup(self, backup_dir):
        """Verify backup structure"""
        required_files = ['backup_metadata.json']
        
        for file in required_files:
            if not (backup_dir / file).exists():
                return False
        
        return True
    
    def show_backup_info(self, backup_dir):
        """Display backup information"""
        metadata_file = backup_dir / 'backup_metadata.json'
        
        if metadata_file.exists():
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
            
            self.stdout.write("\n📊 Backup Information:")
            self.stdout.write(f"   Type: {metadata.get('backup_type', 'Unknown')}")
            self.stdout.write(f"   Date: {metadata.get('timestamp', 'Unknown')}")
            self.stdout.write(f"   Django: {metadata.get('django_version', 'Unknown')}")
            self.stdout.write(f"   Environment: {metadata.get('environment', 'Unknown')}")
            self.stdout.write(f"   Database: {metadata.get('database_engine', 'Unknown')}")
            self.stdout.write(f"   Files: {metadata.get('file_count', 0)}")
            self.stdout.write(f"   Size: {metadata.get('total_size', 'Unknown')}")
    
    def restore_database(self, backup_dir):
        """Restore database from backup"""
        self.stdout.write("🔍 Restoring database...")
        
        db_config = settings.DATABASES['default']
        engine = db_config['ENGINE']
        
        # Find backup files
        sql_files = list(backup_dir.glob('mysql_backup_*.sql'))
        sqlite_files = list(backup_dir.glob('sqlite_backup_*.db'))
        
        if 'mysql' in engine and sql_files:
            self.restore_mysql(db_config, sql_files[0])
        elif 'sqlite3' in engine and sqlite_files:
            self.restore_sqlite(db_config, sqlite_files[0])
        else:
            self.stdout.write("   ⚠️  No matching database backup found, skipping...")
    
    def restore_mysql(self, db_config, backup_file):
        """Restore MySQL database"""
        db_name = db_config['NAME']
        db_user = db_config['USER']
        db_password = db_config['PASSWORD']
        db_host = db_config['HOST'] or 'localhost'
        db_port = db_config['PORT'] or '3306'
        
        # First, drop and recreate database
        self.stdout.write(f"   Dropping and recreating database: {db_name}")
        
        drop_cmd = [
            'mysql',
            f'--user={db_user}',
            f'--password={db_password}',
            f'--host={db_host}',
            f'--port={db_port}',
            '-e',
            f"DROP DATABASE IF EXISTS {db_name}; CREATE DATABASE {db_name};"
        ]
        
        subprocess.run(drop_cmd, check=True, capture_output=True)
        
        # Restore from backup
        self.stdout.write(f"   Restoring from: {backup_file}")
        
        restore_cmd = [
            'mysql',
            f'--user={db_user}',
            f'--password={db_password}',
            f'--host={db_host}',
            f'--port={db_port}',
            db_name
        ]
        
        with open(backup_file, 'r') as f:
            subprocess.run(restore_cmd, stdin=f, check=True, capture_output=True)
        
        self.stdout.write("   ✓ MySQL database restored")
    
    def restore_sqlite(self, db_config, backup_file):
        """Restore SQLite database"""
        db_path = Path(db_config['NAME'])
        if not db_path.is_absolute():
            db_path = settings.BASE_DIR / db_path
        
        # Backup current database first
        if db_path.exists():
            backup_current = db_path.with_suffix('.db.bak')
            shutil.copy2(db_path, backup_current)
            self.stdout.write(f"   Backed up current database to: {backup_current}")
        
        # Restore from backup
        shutil.copy2(backup_file, db_path)
        self.stdout.write(f"   ✓ SQLite database restored from: {backup_file}")
    
    def restore_media_files(self, backup_dir):
        """Restore media files"""
        media_backup = backup_dir / 'media'
        media_root = Path(settings.MEDIA_ROOT)
        
        if not media_backup.exists():
            self.stdout.write("   ⚠️  No media backup found, skipping...")
            return
        
        # Backup current media files
        if media_root.exists():
            media_backup_dir = settings.BASE_DIR / 'media_backup' / timezone.now().strftime('%Y%m%d_%H%M%S')
            media_backup_dir.mkdir(parents=True, exist_ok=True)
            
            for item in media_root.iterdir():
                dest = media_backup_dir / item.name
                if item.is_dir():
                    shutil.copytree(item, dest)
                else:
                    shutil.copy2(item, dest)
            
            self.stdout.write(f"   Backed up current media to: {media_backup_dir}")
        
        # Clear current media directory
        if media_root.exists():
            shutil.rmtree(media_root)
        
        # Restore from backup
        shutil.copytree(media_backup, media_root)
        
        # Count restored files
        file_count = sum(1 for _ in media_root.rglob('*') if _.is_file())
        self.stdout.write(f"   ✓ Media files restored: {file_count} files")
    
    def log_restore_action(self, restore_type, backup_path, success, error_message=None):
        """Log restore action to AuditLog"""
        try:
            from core.models import AuditLog
            
            AuditLog.objects.create(
                user=None,  # System action
                action='SYSTEM_RESTORE',
                model_name='System',
                object_id='restore',
                details={
                    'restore_type': restore_type,
                    'backup_path': backup_path,
                    'success': success,
                    'error_message': error_message,
                    'timestamp': timezone.now().isoformat(),
                },
                ip_address='127.0.0.1',
                user_agent='RestoreSystem/1.0'
            )
        except Exception as e:
            logger.warning(f"Failed to log restore action: {e}")