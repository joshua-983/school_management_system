from twilio.rest import Client
from django_otp.plugins.otp_totp.models import TOTPDevice

def send_verification_code(user):
    device = TOTPDevice.objects.get_or_create(user=user)[0]
    token = device.generate_challenge()
    
    client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
    message = client.messages.create(
        body=f"Your verification code is {token}",
        from_=settings.TWILIO_PHONE_NUMBER,
        to=user.phone_number  # Ensure user model has phone_number field
    )
    return message.sid