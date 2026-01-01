# core/security/two_factor.py
import pyotp
import qrcode
from io import BytesIO
import base64
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

class Financial2FAService:
    """Two-factor authentication for financial operations"""
    
    def __init__(self, user):
        self.user = user
        self.cache_key = f"2fa_attempts_{user.id}"
    
    def generate_secret(self):
        """Generate TOTP secret for user"""
        return pyotp.random_base32()
    
    def generate_qr_code(self, secret, email=None):
        """Generate QR code for authenticator app"""
        if not email:
            email = self.user.email
        
        # Create TOTP object
        totp = pyotp.TOTP(secret)
        
        # Generate provisioning URI
        provisioning_uri = totp.provisioning_uri(
            name=email,
            issuer_name=getattr(settings, 'SCHOOL_NAME', 'School System')
        )
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(provisioning_uri)
        qr.make(fit=True)
        
        # Create image
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Convert to base64
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        buffer.seek(0)
        
        img_str = base64.b64encode(buffer.getvalue()).decode()
        return f"data:image/png;base64,{img_str}"
    
    def verify_code(self, secret, code):
        """Verify TOTP code"""
        # Check rate limiting
        if self._is_rate_limited():
            return False, "Too many attempts. Please wait 5 minutes."
        
        totp = pyotp.TOTP(secret)
        
        if totp.verify(code, valid_window=1):  # Allow 30-second window
            # Reset attempt counter on success
            cache.delete(self.cache_key)
            return True, "Verification successful"
        else:
            # Increment attempt counter
            self._increment_attempts()
            return False, "Invalid verification code"
    
    def require_2fa_for_amount(self, amount):
        """Check if 2FA is required for transaction amount"""
        threshold = getattr(settings, 'FINANCIAL_SECURITY', {}).get(
            'REQUIRE_2FA_ABOVE', Decimal('50000.00')
        )
        
        if isinstance(threshold, (int, float, Decimal)):
            return Decimal(str(amount)) >= Decimal(str(threshold))
        return False
    
    def _is_rate_limited(self):
        """Check if user is rate limited"""
        attempts = cache.get(self.cache_key, 0)
        return attempts >= 5  # Max 5 attempts
    
    def _increment_attempts(self):
        """Increment failed attempt counter"""
        attempts = cache.get(self.cache_key, 0) + 1
        cache.set(self.cache_key, attempts, timeout=300)  # 5 minutes