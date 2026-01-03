from django.db import models

class DataMaintenance(models.Model):
    """Simple model for data maintenance operations"""
    
    name = models.CharField(max_length=100, default="System Maintenance")
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Data Maintenance"
        verbose_name_plural = "Data Maintenance"
    
    def __str__(self):
        return self.name