from django.db import migrations, models

class Migration(migrations.Migration):
    dependencies = [
        # This depends on your data fix migration
        ('core', '0009_fix_auditlog_json'),
    ]

    operations = [
        migrations.AlterField(
            model_name='auditlog',
            name='details',
            field=models.JSONField(
                default=dict,  # Proper default value
                help_text='Stores audit log details in JSON format',
            ),
        ),
    ]