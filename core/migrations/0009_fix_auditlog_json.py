from django.db import migrations
import json

def fix_json_data(apps, schema_editor):
    AuditLog = apps.get_model('core', 'AuditLog')
    
    for log in AuditLog.objects.all():
        needs_save = False
        
        # Handle null/empty cases
        if log.details is None or log.details == '':
            log.details = {}
            needs_save = True
        # Handle string cases
        elif isinstance(log.details, str):
            try:
                # Try parsing to validate JSON
                parsed = json.loads(log.details)
                # If it's a string representation of a dict, update it
                if isinstance(parsed, dict):
                    log.details = parsed
                    needs_save = True
            except json.JSONDecodeError:
                # Save invalid data in a structured way
                log.details = {
                    '_migration_note': 'auto_fixed_invalid_json',
                    'original_value': log.details
                }
                needs_save = True
        
        if needs_save:
            log.save()

class Migration(migrations.Migration):
    dependencies = [
        ('core', '0008_feediscount_feeinstallment_delete_financialanalytics_and_more'),
    ]

    operations = [
        migrations.RunPython(fix_json_data),
    ]