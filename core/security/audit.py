# core/security/audit.py
import logging
from django.conf import settings
from django.db import connection
from django.core.cache import cache
import subprocess
import json

logger = logging.getLogger(__name__)


class SecurityAuditor:
    """Perform security audit of financial system"""
    
    def run_comprehensive_audit(self):
        """Run comprehensive security audit"""
        audit_results = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': [],
            'passed': []
        }
        
        # Check Django security settings
        audit_results.update(self._check_django_settings())
        
        # Check database security
        audit_results.update(self._check_database_security())
        
        # Check financial endpoints
        audit_results.update(self._check_financial_endpoints())
        
        # Check encryption
        audit_results.update(self._check_encryption())
        
        # Check audit trail
        audit_results.update(self._check_audit_trail())
        
        # Calculate security score
        audit_results['security_score'] = self._calculate_security_score(audit_results)
        
        return audit_results
    
    def _check_django_settings(self):
        """Check Django security settings"""
        checks = []
        
        # Check DEBUG mode
        if settings.DEBUG:
            checks.append({
                'level': 'critical',
                'check': 'DEBUG Mode',
                'status': 'FAILED',
                'message': 'DEBUG mode is enabled in production',
                'recommendation': 'Set DEBUG = False in production'
            })
        else:
            checks.append({
                'level': 'passed',
                'check': 'DEBUG Mode',
                'status': 'PASSED',
                'message': 'DEBUG mode is disabled'
            })
        
        # Check HTTPS
        if not getattr(settings, 'SECURE_SSL_REDIRECT', False):
            checks.append({
                'level': 'critical',
                'check': 'HTTPS Enforcement',
                'status': 'FAILED',
                'message': 'HTTPS not enforced',
                'recommendation': 'Set SECURE_SSL_REDIRECT = True'
            })
        
        # Check CSRF protection
        if not getattr(settings, 'CSRF_COOKIE_SECURE', False):
            checks.append({
                'level': 'high',
                'check': 'CSRF Cookie Security',
                'status': 'FAILED',
                'message': 'CSRF cookie not secure',
                'recommendation': 'Set CSRF_COOKIE_SECURE = True'
            })
        
        return self._categorize_checks(checks)
    
    def _check_financial_endpoints(self):
        """Check financial endpoints security"""
        checks = []
        
        # Check rate limiting
        if 'core.middleware.security.FinancialSecurityMiddleware' not in settings.MIDDLEWARE:
            checks.append({
                'level': 'high',
                'check': 'Financial Rate Limiting',
                'status': 'FAILED',
                'message': 'Financial rate limiting middleware not enabled',
                'recommendation': 'Add FinancialSecurityMiddleware to MIDDLEWARE'
            })
        
        # Check 2FA configuration
        if not hasattr(settings, 'FINANCIAL_SECURITY'):
            checks.append({
                'level': 'medium',
                'check': 'Financial Security Config',
                'status': 'FAILED',
                'message': 'FINANCIAL_SECURITY settings not configured',
                'recommendation': 'Configure FINANCIAL_SECURITY in settings.py'
            })
        
        return self._categorize_checks(checks)
    
    def _categorize_checks(self, checks):
        """Categorize checks by severity"""
        categorized = {
            'critical': [],
            'high': [],
            'medium': [],
            'low': [],
            'passed': []
        }
        
        for check in checks:
            categorized[check['level']].append(check)
        
        return categorized
    
    def _calculate_security_score(self, audit_results):
        """Calculate overall security score (0-100)"""
        weights = {
            'critical': 0,
            'high': 25,
            'medium': 50,
            'low': 75,
            'passed': 100
        }
        
        total_checks = sum(len(checks) for checks in audit_results.values() if isinstance(checks, list))
        
        if total_checks == 0:
            return 100
        
        weighted_sum = 0
        for level, checks in audit_results.items():
            if level in weights and isinstance(checks, list):
                weighted_sum += len(checks) * weights[level]
        
        return int(weighted_sum / total_checks)