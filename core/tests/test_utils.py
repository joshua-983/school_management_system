# core/tests/test_utils.py
from django.test import TestCase
from django.contrib.auth import get_user_model

CustomUser = get_user_model()


class BaseTestCase(TestCase):
    """Base test case with common utilities"""
    
    def create_user(self, username='testuser', password='testpass123', **kwargs):
        """Create a test user"""
        return CustomUser.objects.create_user(
            username=username,
            password=password,
            **kwargs
        )
    
    def create_superuser(self, username='admin', password='testpass123', **kwargs):
        """Create a test superuser"""
        return CustomUser.objects.create_superuser(
            username=username,
            password=password,
            **kwargs
        )
    
    def login(self, user):
        """Login user without session issues"""
        self.client.force_login(user)
    
    def assertResponseOK(self, response):
        """Assert response status is 200"""
        self.assertEqual(response.status_code, 200)
    
    def assertResponseRedirect(self, response, expected_url=None):
        """Assert response is a redirect"""
        self.assertEqual(response.status_code, 302)
        if expected_url:
            self.assertEqual(response.url, expected_url)