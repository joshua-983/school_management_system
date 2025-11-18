from django.contrib.auth.models import AbstractUser
from django.db import models

class CustomUser(AbstractUser):
    # Add custom fields here
    phone_number = models.CharField(max_length=10, blank=True)
    address = models.TextField(blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    
    # Add any additional methods or meta options
    class Meta:
        verbose_name = 'User'
        verbose_name_plural = 'Users'

    def __str__(self):
        return self.username


    def get_anonymous_user_instance(user_model):
        """
        Returns an anonymous user instance for django-guardian
        """
        return user_model.objects.get_or_create(
            username='AnonymousUser',
            defaults={'is_active': False, 'is_staff': False}
        )[0]