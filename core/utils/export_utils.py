"""
Export and data transformation utilities.
"""
import csv
import json
from io import StringIO
from datetime import datetime
from django.http import HttpResponse
from .main import format_date, format_currency

def export_to_csv(queryset, fields, field_names=None, filename='export.csv'):
    """
    Export queryset to CSV
    
    Args:
        queryset: Django queryset
        fields: List of field names to export
        field_names: Optional display names for headers
        filename: Output filename
    """
    if field_names is None:
        field_names = fields
    
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    writer = csv.writer(response)
    writer.writerow(field_names)
    
    for obj in queryset:
        row = []
        for field in fields:
            value = getattr(obj, field, '')
            
            # Format dates
            if isinstance(value, (datetime, date)):
                value = format_date(value)
            
            # Format currency
            elif field in ['amount', 'balance', 'amount_payable', 'amount_paid']:
                value = format_currency(value)
            
            row.append(str(value))
        
        writer.writerow(row)
    
    return response

def export_to_json(queryset, fields=None, filename='export.json'):
    """
    Export queryset to JSON
    
    Args:
        queryset: Django queryset
        fields: List of field names to export (all if None)
        filename: Output filename
    """
    if fields:
        data = list(queryset.values(*fields))
    else:
        data = list(queryset.values())
    
    response = HttpResponse(
        json.dumps(data, indent=2, default=str),
        content_type='application/json'
    )
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    return response

def generate_csv_data(queryset, fields):
    """Generate CSV data as string (for testing or further processing)"""
    output = StringIO()
    writer = csv.writer(output)
    
    for obj in queryset:
        row = []
        for field in fields:
            value = getattr(obj, field, '')
            row.append(str(value))
        writer.writerow(row)
    
    return output.getvalue()

__all__ = [
    'export_to_csv',
    'export_to_json',
    'generate_csv_data',
]