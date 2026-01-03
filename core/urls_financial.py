# core/urls_financial.py (COMPLETE VERSION)
from django.urls import path
from django.views.generic import TemplateView
from .views import payment_views  # Use payment_views.py

urlpatterns = [
    # Payment Gateway URLs
    path('payment/initiate/', 
         payment_views.InitiateOnlinePaymentView.as_view(), 
         name='initiate_payment'),
    
    path('payment/callback/<str:gateway>/', 
         payment_views.PaymentCallbackView.as_view(), 
         name='payment_callback'),
    
    path('payment/webhook/<str:gateway>/', 
         payment_views.PaymentWebhookView.as_view(), 
         name='payment_webhook'),
    
    path('payment/history/<int:student_id>/', 
         payment_views.PaymentHistoryView.as_view(), 
         name='student_payment_history'),
    
    path('payment/history/', 
         payment_views.PaymentHistoryView.as_view(), 
         name='my_payment_history'),
    
    # Temporary simple views for missing functionality
    path('receipt/<str:payment_type>/<int:payment_id>/', 
         TemplateView.as_view(template_name='payment/receipt.html'), 
         name='generate_receipt'),
    
    path('payment/contact-support/', 
         TemplateView.as_view(template_name='payment/contact_support.html'), 
         name='contact_support'),
    
    path('payment/success/', 
         TemplateView.as_view(template_name='payment/success.html'), 
         name='payment_success'),
    
    path('payment/error/', 
         TemplateView.as_view(template_name='payment/error.html'), 
         name='payment_error'),
    
    # API Endpoints (ADD THESE)
    path('api/fees/outstanding/', 
         payment_views.OutstandingFeesAPIView.as_view(), 
         name='fee_outstanding_api'),
    
    # Alias for backward compatibility
    path('financial/payment/history/', 
         payment_views.PaymentHistoryView.as_view(), 
         name='payment_history_api'),
]