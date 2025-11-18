# core/views/network_views.py
import time
import requests
import socket
import psutil
from django.http import JsonResponse
from django.views import View
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_exempt

class NetworkHealthView(View):
    def get(self, request):
        """Comprehensive network health check"""
        results = {
            'timestamp': time.time(),
            'checks': {}
        }
        
        # Local network check
        results['checks']['localhost'] = self.check_localhost()
        
        # DNS resolution check
        results['checks']['dns'] = self.check_dns_resolution()
        
        # External service checks
        results['checks']['external_services'] = self.check_external_services()
        
        # Database connection latency
        results['checks']['database'] = self.check_database_latency()
        
        # Cache latency
        results['checks']['cache'] = self.check_cache_latency()
        
        # System network stats
        results['checks']['system_network'] = self.get_network_stats()
        
        return JsonResponse(results)
    
    def check_localhost(self):
        """Check if localhost services are responding"""
        services = {
            'django_app': 'http://localhost:8000/',
            'redis': ('localhost', 6379),
            'mysql': ('localhost', 3306),
        }
        
        results = {}
        for service, target in services.items():
            try:
                start = time.time()
                if isinstance(target, tuple):  # TCP port check
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)
                    result = sock.connect_ex(target)
                    sock.close()
                    latency = time.time() - start
                    results[service] = {
                        'status': 'up' if result == 0 else 'down',
                        'latency': round(latency * 1000, 2),
                        'port': target[1]
                    }
                else:  # HTTP check
                    response = requests.get(target, timeout=5)
                    latency = time.time() - start
                    results[service] = {
                        'status': 'up' if response.status_code == 200 else 'down',
                        'latency': round(latency * 1000, 2),
                        'status_code': response.status_code
                    }
            except Exception as e:
                results[service] = {'status': 'down', 'error': str(e)}
        
        return results
    
    def check_dns_resolution(self):
        """Check DNS resolution for critical services"""
        domains = ['google.com', 'github.com', 'djangoproject.com']
        results = {}
        
        for domain in domains:
            try:
                start = time.time()
                socket.gethostbyname(domain)
                latency = time.time() - start
                results[domain] = {
                    'status': 'resolved',
                    'latency': round(latency * 1000, 2)
                }
            except Exception as e:
                results[domain] = {'status': 'failed', 'error': str(e)}
        
        return results
    
    def check_external_services(self):
        """Check connectivity to external APIs"""
        services = {
            'google': 'https://www.google.com',
            'github': 'https://api.github.com',
            'django_docs': 'https://docs.djangoproject.com',
        }
        
        results = {}
        for name, url in services.items():
            try:
                start = time.time()
                response = requests.get(url, timeout=10)
                latency = time.time() - start
                results[name] = {
                    'status': 'up',
                    'latency': round(latency * 1000, 2),
                    'status_code': response.status_code,
                    'response_size': len(response.content)
                }
            except Exception as e:
                results[name] = {'status': 'down', 'error': str(e)}
        
        return results
    
    def check_database_latency(self):
        """Check database connection latency"""
        try:
            from django.db import connection
            start = time.time()
            with connection.cursor() as cursor:
                cursor.execute("SELECT 1")
            latency = time.time() - start
            return {'status': 'connected', 'latency': round(latency * 1000, 2)}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def check_cache_latency(self):
        """Check cache latency"""
        try:
            from django.core.cache import cache
            start = time.time()
            cache.set('network_test', 'value', 10)
            cache.get('network_test')
            latency = time.time() - start
            return {'status': 'working', 'latency': round(latency * 1000, 2)}
        except Exception as e:
            return {'status': 'error', 'error': str(e)}
    
    def get_network_stats(self):
        """Get system network statistics"""
        try:
            stats = psutil.net_io_counters()
            return {
                'bytes_sent': stats.bytes_sent,
                'bytes_recv': stats.bytes_recv,
                'packets_sent': stats.packets_sent,
                'packets_recv': stats.packets_recv,
            }
        except Exception as e:
            return {'error': str(e)}