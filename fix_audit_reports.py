import os
import re

def add_missing_methods():
    """Add missing methods to AuditReportGenerator"""
    file_path = '/mnt/e/projects/school/core/utils/audit_enhancements.py'
    
    print('=== Adding missing methods to AuditReportGenerator ===')
    
    with open(file_path, 'r') as f:
        content = f.read()

    if 'def generate_daily_report' in content:
        new_methods = '''
    def generate_weekly_report(self):
        """Generate weekly security report"""
        try:
            from django.utils import timezone
            from datetime import timedelta
            today = timezone.now().date()
            week_ago = today - timedelta(days=7)

            report_data = {
                'start_date': week_ago,
                'end_date': today,
                'total_actions': AuditLog.objects.filter(timestamp__date__range=[week_ago, today]).count(),
                'security_events': SecurityEvent.objects.filter(created_at__date__range=[week_ago, today]).count(),
                'failed_logins': AuditLog.objects.filter(
                    action='LOGIN_FAILED', timestamp__date__range=[week_ago, today]
                ).count(),
            }

            # For now, create a simple report without PDF/email
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            report = AuditReport.objects.create(
                name=f"Weekly Security Report - {today}",
                report_type='WEEKLY',
                parameters=report_data,
                generated_by=User.objects.filter(is_superuser=True).first(),
                is_scheduled=True,
            )

            return report

        except Exception as e:
            logger.error(f"Error generating weekly report: {str(e)}")
            return None

    def generate_security_report(self):
        """Generate security-focused report"""
        try:
            from django.utils import timezone
            today = timezone.now().date()

            report_data = {
                'date': today,
                'security_events': SecurityEvent.objects.filter(created_at__date=today).count(),
                'failed_logins': AuditLog.objects.filter(
                    action='LOGIN_FAILED', timestamp__date=today
                ).count(),
                'suspicious_activity': self._get_suspicious_activity(today),
            }

            # For now, create a simple report without PDF/email
            from django.contrib.auth import get_user_model
            User = get_user_model()
            
            report = AuditReport.objects.create(
                name=f"Security Report - {today}",
                report_type='SECURITY',
                parameters=report_data,
                generated_by=User.objects.filter(is_superuser=True).first(),
                is_scheduled=True,
            )

            return report

        except Exception as e:
            logger.error(f"Error generating security report: {str(e)}")
            return None
'''

        # Insert the new methods after generate_daily_report
        old_method_end = '        return None'
        if old_method_end in content:
            parts = content.split(old_method_end)
            if len(parts) > 1:
                new_content = parts[0] + old_method_end + new_methods + parts[1]
                
                with open(file_path, 'w') as f:
                    f.write(new_content)
                print('✅ Successfully added missing methods to AuditReportGenerator')
                return True
            else:
                print('❌ Could not find where to insert new methods')
                return False
        else:
            print('❌ Could not find generate_daily_report method end')
            return False
    else:
        print('❌ Could not find generate_daily_report method')
        return False

def fix_user_import():
    """Fix User model import"""
    file_path = '/mnt/e/projects/school/core/utils/audit_enhancements.py'
    
    print('\\n=== Fixing User model import ===')
    
    with open(file_path, 'r') as f:
        content = f.read()

    # Add get_user_model import if not present
    if 'from django.contrib.auth import get_user_model' not in content:
        # Add import after existing imports
        import re
        # Find the last import statement
        imports_end = 0
        lines = content.split('\\n')
        for i, line in enumerate(lines):
            if line.startswith('import ') or line.startswith('from '):
                imports_end = i
            elif line.strip() and not line.startswith('#') and imports_end > 0:
                break
        
        if imports_end > 0:
            lines.insert(imports_end + 1, 'from django.contrib.auth import get_user_model')
            new_content = '\\n'.join(lines)
            
            with open(file_path, 'w') as f:
                f.write(new_content)
            print('✅ Added get_user_model import')
        else:
            print('❌ Could not find where to add import')
    else:
        print('✅ get_user_model import already exists')

def fix_view_null_handling():
    """Fix view to handle None reports"""
    view_path = '/mnt/e/projects/school/core/views/audit_enhancements.py'
    
    print('\\n=== Fixing view to handle None reports ===')
    
    with open(view_path, 'r') as f:
        content = f.read()

    # Find and fix the problematic section
    old_pattern = r"return JsonResponse\\({\\s*'success': True,\\s*'report_id': report\\.id,.*?}\\)"
    new_code = '''        if report:
            return JsonResponse({
                'success': True,
                'report_id': report.id,
                'message': f'{report_type.lower().title()} report generated successfully'
            })
        else:
            return JsonResponse({
                'success': False,
                'error': f'Failed to generate {report_type.lower()} report'
            })'''

    if re.search(old_pattern, content, re.DOTALL):
        content = re.sub(old_pattern, new_code, content, flags=re.DOTALL)
        with open(view_path, 'w') as f:
            f.write(content)
        print('✅ Fixed view to handle None reports')
    else:
        print('❌ Could not find the code to replace in view')

if __name__ == "__main__":
    print("Applying fixes to audit report system...")
    
    # Apply fixes in order
    add_missing_methods()
    fix_user_import()
    fix_view_null_handling()
    
    print("\\n🎉 All fixes applied!")
