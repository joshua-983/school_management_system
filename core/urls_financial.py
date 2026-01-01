# core/urls_financial.py
from django.urls import path
from .views import payment_gateway_views

urlpatterns = [
    # Payment Gateway URLs
    path('payment/initiate/', 
         payment_gateway_views.InitiatePaymentView.as_view(), 
         name='initiate_payment'),
    
    path('payment/callback/<str:gateway>/', 
         payment_gateway_views.PaymentCallbackView.as_view(), 
         name='payment_callback'),
    
    path('payment/webhook/<str:gateway>/', 
         payment_gateway_views.PaymentWebhookView.as_view(), 
         name='payment_webhook'),
    
    path('payment/history/<int:student_id>/', 
         payment_gateway_views.StudentPaymentHistoryView.as_view(), 
         name='student_payment_history'),
    
    path('payment/history/', 
         payment_gateway_views.StudentPaymentHistoryView.as_view(), 
         name='my_payment_history'),
    
    path('receipt/<str:payment_type>/<int:payment_id>/', 
         payment_gateway_views.GeneratePaymentReceiptView.as_view(), 
         name='generate_receipt'),
    
   

]