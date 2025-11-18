import time
import socket
import requests
import subprocess
from django.core.management import execute_from_command_line
import os
import sys

# Setup Django
sys.path.append('/mnt/e/projects/school')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'school_mgt_system.settings')

try:
    import django
    django.setup()
except:
    pass

def test_network_connectivity():
    print("🌐 NETWORK CONNECTIVITY TEST")
    print("=" * 50)
    
    # Test 1: Django Application
    print("\n1. 🚀 DJANGO APPLICATION")
    try:
        start = time.time()
        response = requests.get('http://localhost:8000/', timeout=5)
        latency = (time.time() - start) * 1000
        print(f"   ✅ HTTP {response.status_code} - {latency:.1f}ms")
    except requests.exceptions.ConnectionError:
        print("   ❌ Cannot connect - Server may not be running")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 2: Redis
    print("\n2. 💾 REDIS")
    try:
        start = time.time()
        result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True, timeout=5)
        latency = (time.time() - start) * 1000
        if 'PONG' in result.stdout:
            print(f"   ✅ Connected - {latency:.1f}ms")
        else:
            print("   ❌ Not responding properly")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 3: MySQL
    print("\n3. 🗄️  MYSQL")
    try:
        import MySQLdb
        from django.conf import settings
        start = time.time()
        db = MySQLdb.connect(
            host=settings.DATABASES['default']['HOST'],
            user=settings.DATABASES['default']['USER'],
            passwd=settings.DATABASES['default']['PASSWORD'],
            db=settings.DATABASES['default']['NAME'],
            port=int(settings.DATABASES['default']['PORT'])
        )
        latency = (time.time() - start) * 1000
        db.close()
        print(f"   ✅ Connected - {latency:.1f}ms")
    except Exception as e:
        print(f"   ❌ Error: {e}")

    # Test 4: DNS Resolution
    print("\n4. 🌍 DNS RESOLUTION")
    domains = ['google.com', 'github.com', 'djangoproject.com']
    for domain in domains:
        try:
            start = time.time()
            socket.gethostbyname(domain)
            latency = (time.time() - start) * 1000
            print(f"   ✅ {domain}: {latency:.1f}ms")
        except Exception as e:
            print(f"   ❌ {domain}: Failed")

    # Test 5: External Services
    print("\n5. 🔗 EXTERNAL SERVICES")
    services = [
        ('Google', 'https://www.google.com'),
        ('GitHub', 'https://api.github.com'),
        ('Django Docs', 'https://docs.djangoproject.com'),
    ]
    
    for name, url in services:
        try:
            start = time.time()
            response = requests.get(url, timeout=10)
            latency = (time.time() - start) * 1000
            print(f"   ✅ {name}: {latency:.1f}ms (HTTP {response.status_code})")
        except Exception as e:
            print(f"   ❌ {name}: Failed")

    # Test 6: Port Checking
    print("\n6. 🔌 PORT AVAILABILITY")
    ports = [8000, 3306, 6379]
    for port in ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex(('localhost', port))
            sock.close()
            if result == 0:
                print(f"   ✅ Port {port}: Open")
            else:
                print(f"   ❌ Port {port}: Closed")
        except Exception as e:
            print(f"   ❌ Port {port}: Error")

    print("\n" + "=" * 50)
    print("🎯 NETWORK TEST COMPLETE")

if __name__ == "__main__":
    test_network_connectivity()
