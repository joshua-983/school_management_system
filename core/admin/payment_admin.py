# core/admin/payment_admin.py
from django.contrib import admin
from django.utils.html import format_html
from core.models import PaymentGateway, OnlinePayment

@admin.register(PaymentGateway)
class PaymentGatewayAdmin(admin.ModelAdmin):
    list_display = ['name', 'is_active', 'test_mode', 'created_at']
    list_filter = ['is_active', 'test_mode', 'name']
    search_fields = ['name']
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'is_active', 'test_mode')
        }),
        ('API Configuration', {
            'fields': ('secret_key', 'public_key', 'encryption_key', 'webhook_hash'),
            'classes': ('collapse',)
        }),
    )

@admin.register(OnlinePayment)
class OnlinePaymentAdmin(admin.ModelAdmin):
    list_display = ['transaction_id', 'status_badge', 'amount', 'student_name', 'payment_type', 'initiated_at']
    list_filter = ['status', 'gateway', 'initiated_at']
    search_fields = ['transaction_id', 'customer_email', 'customer_name']
    readonly_fields = ['transaction_id', 'initiated_at', 'completed_at', 'gateway_response_preview']
    fieldsets = (
        ('Payment Information', {
            'fields': ('transaction_id', 'gateway', 'status', 'amount', 'currency')
        }),
        ('Customer Information', {
            'fields': ('customer_email', 'customer_name', 'customer_phone')
        }),
        ('Related Items', {
            'fields': ('fee', 'bill')
        }),
        ('Timestamps', {
            'fields': ('initiated_at', 'completed_at')
        }),
        ('Gateway Response', {
            'fields': ('gateway_response_preview',),
            'classes': ('collapse',)
        }),
    )
    
    def status_badge(self, obj):
        colors = {
            'PENDING': 'warning',
            'SUCCESS': 'success',
            'FAILED': 'danger',
            'CANCELLED': 'secondary',
            'REFUNDED': 'info',
        }
        color = colors.get(obj.status, 'secondary')
        return format_html(
            '<span class="badge bg-{}">{}</span>',
            color, obj.get_status_display()
        )
    status_badge.short_description = 'Status'
    
    def student_name(self, obj):
        if obj.student:
            return obj.student.get_full_name()
        return '-'
    student_name.short_description = 'Student'
    
    def payment_type(self, obj):
        if obj.fee:
            return 'Fee'
        elif obj.bill:
            return 'Bill'
        return '-'
    payment_type.short_description = 'Type'
    
    def gateway_response_preview(self, obj):
        if obj.gateway_response:
            return format_html('<pre>{}</pre>', json.dumps(obj.gateway_response, indent=2))
        return '-'
    gateway_response_preview.short_description = 'Gateway Response'