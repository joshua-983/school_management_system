"""
Backup management views for admin interface.
"""
import os
import json
from pathlib import Path
from datetime import datetime
from django.contrib.auth.decorators import login_required, user_passes_test
from django.http import JsonResponse, HttpResponse
from django.shortcuts import render
from django.conf import settings
from django.core.management import call_command
from django.views.decorators.http import require_http_methods
import logging

logger = logging.getLogger(__name__)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def backup_dashboard(request):
    """Backup management dashboard"""
    backups_dir = settings.BASE_DIR / 'backups'
    
    # Get backup statistics
    backups = []
    total_size = 0
    
    if backups_dir.exists():
        for item in sorted(backups_dir.iterdir(), key=lambda x: x.stat().st_mtime, reverse=True):
            if item.is_dir() or item.suffix == '.zip':
                size = item.stat().st_size if item.is_file() else sum(
                    f.stat().st_size for f in item.rglob('*') if f.is_file()
                )
                
                backups.append({
                    'name': item.name,
                    'path': str(item),
                    'type': 'directory' if item.is_dir() else 'zip',
                    'size': size,
                    'size_human': human_readable_size(size),
                    'modified': datetime.fromtimestamp(item.stat().st_mtime),
                    'file_count': len(list(item.rglob('*'))) if item.is_dir() else 1,
                })
                total_size += size
    
    # Get system info
    system_info = {
        'database_engine': settings.DATABASES['default']['ENGINE'],
        'media_size': get_directory_size(settings.MEDIA_ROOT) if os.path.exists(settings.MEDIA_ROOT) else 0,
        'code_size': get_directory_size(settings.BASE_DIR, exclude=['backups', 'media', 'venv', '__pycache__']),
        'backup_count': len(backups),
        'total_backup_size': total_size,
        'last_backup': backups[0]['modified'] if backups else None,
    }
    
    context = {
        'backups': backups,
        'system_info': system_info,
        'total_size_human': human_readable_size(total_size),
        'media_size_human': human_readable_size(system_info['media_size']),
    }
    
    return render(request, 'core/admin/backup_dashboard.html', context)


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["POST"])
def create_backup(request):
    """Create a new backup via AJAX"""
    backup_type = request.POST.get('type', 'database')
    compress = request.POST.get('compress', 'true').lower() == 'true'
    
    try:
        # Run backup command
        args = ['backup_system', '--type', backup_type]
        if compress:
            args.append('--compress')
        
        call_command(*args)
        
        return JsonResponse({
            'success': True,
            'message': f'{backup_type.capitalize()} backup created successfully'
        })
        
    except Exception as e:
        logger.error(f"Backup creation failed: {str(e)}")
        return JsonResponse({
            'success': False,
            'message': f'Backup failed: {str(e)}'
        }, status=500)


@login_required
@user_passes_test(lambda u: u.is_superuser)
def download_backup(request, backup_name):
    """Download backup file"""
    backup_path = settings.BASE_DIR / 'backups' / backup_name
    
    if not backup_path.exists():
        return JsonResponse({'error': 'Backup not found'}, status=404)
    
    # For security, only allow downloading of backup files
    if not (backup_path.name.startswith('backup_') or backup_path.name.startswith('mysql_') or 
            backup_path.name.startswith('sqlite_')):
        return JsonResponse({'error': 'Invalid backup file'}, status=403)
    
    # Create response
    if backup_path.is_file():
        with open(backup_path, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/octet-stream')
            response['Content-Disposition'] = f'attachment; filename="{backup_path.name}"'
            return response
    else:
        # For directories, create a zip file first
        import tempfile
        import zipfile
        
        temp_zip = tempfile.NamedTemporaryFile(delete=False, suffix='.zip')
        
        with zipfile.ZipFile(temp_zip, 'w', zipfile.ZIP_DEFLATED) as zipf:
            for root, dirs, files in os.walk(backup_path):
                for file in files:
                    file_path = Path(root) / file
                    arcname = file_path.relative_to(backup_path)
                    zipf.write(file_path, arcname)
        
        temp_zip.close()
        
        with open(temp_zip.name, 'rb') as f:
            response = HttpResponse(f.read(), content_type='application/zip')
            response['Content-Disposition'] = f'attachment; filename="{backup_path.name}.zip"'
        
        os.unlink(temp_zip.name)
        return response


@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["DELETE"])
def delete_backup(request, backup_name):
    """Delete backup file"""
    backup_path = settings.BASE_DIR / 'backups' / backup_name
    
    if not backup_path.exists():
        return JsonResponse({'error': 'Backup not found'}, status=404)
    
    try:
        if backup_path.is_file():
            backup_path.unlink()
        else:
            import shutil
            shutil.rmtree(backup_path)
        
        return JsonResponse({'success': True, 'message': 'Backup deleted'})
        
    except Exception as e:
        logger.error(f"Backup deletion failed: {str(e)}")
        return JsonResponse({'success': False, 'message': str(e)}, status=500)


def human_readable_size(size_bytes):
    """Convert bytes to human readable format"""
    for unit in ['B', 'KB', 'MB', 'GB']:
        if size_bytes < 1024.0:
            return f"{size_bytes:.1f} {unit}"
        size_bytes /= 1024.0
    return f"{size_bytes:.1f} TB"


def get_directory_size(directory, exclude=None):
    """Get total size of directory excluding specified patterns"""
    if not os.path.exists(directory):
        return 0
    
    total_size = 0
    exclude = exclude or []
    
    for root, dirs, files in os.walk(directory):
        # Skip excluded directories
        dirs[:] = [d for d in dirs if not any(ex in d for ex in exclude)]
        
        for file in files:
            if any(ex in file for ex in exclude):
                continue
            
            file_path = os.path.join(root, file)
            if os.path.exists(file_path):
                total_size += os.path.getsize(file_path)
    
    return total_size
@login_required
@user_passes_test(lambda u: u.is_superuser)
@require_http_methods(["POST"])
def cleanup_old_backups(request):
    """Clean up old backup files"""
    try:
        backup_dir = settings.BASE_DIR / 'backups'
        if not backup_dir.exists():
            return JsonResponse({
                'success': True, 
                'message': 'No backup directory found'
            })
        
        # Delete backups older than 90 days
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=90)
        
        deleted_count = 0
        total_size = 0
        
        for item in backup_dir.iterdir():
            try:
                # Parse date from filename
                if item.name.startswith('backup_') and item.suffix == '.zip':
                    date_str = item.name[7:22]  # backup_YYYYMMDD_HHMMSS.zip
                    item_date = datetime.strptime(date_str, '%Y%m%d_%H%M%S')
                    
                    if item_date < cutoff_date:
                        size = item.stat().st_size
                        item.unlink()
                        deleted_count += 1
                        total_size += size
            except (ValueError, IndexError):
                continue
        
        logger.info(f"Cleaned up {deleted_count} old backups")
        
        return JsonResponse({
            'success': True,
            'message': f'Cleaned {deleted_count} old backups ({human_readable_size(total_size)})'
        })
        
    except Exception as e:
        logger.error(f"Backup cleanup failed: {str(e)}")
        return JsonResponse({
            'success': False, 
            'message': f'Cleanup failed: {str(e)}'
        }, status=500)
