import time
import socket
import subprocess
import requests

def http_monitor():
    print("🔄 REAL-TIME HTTP CONNECTION MONITOR (Ctrl+C to stop)")
    print("=" * 60)
    
    try:
        while True:
            results = []
            timestamp = time.strftime('%H:%M:%S')
            
            # Django App - HTTP check
            try:
                start = time.time()
                response = requests.get('http://localhost:8000/', timeout=3)
                latency = (time.time() - start) * 1000
                if response.status_code == 200:
                    results.append(f"Django: {latency:.0f}ms")
                else:
                    results.append(f"Django: HTTP {response.status_code}")
            except requests.exceptions.ConnectionError:
                results.append("Django: ❌ Connection")
            except requests.exceptions.Timeout:
                results.append("Django: ⏰ Timeout")
            except Exception as e:
                results.append(f"Django: ❌ Error")
            
            # Redis
            try:
                start = time.time()
                result = subprocess.run(['redis-cli', 'ping'], capture_output=True, text=True, timeout=2)
                latency = (time.time() - start) * 1000
                if 'PONG' in result.stdout:
                    results.append(f"Redis: {latency:.0f}ms")
                else:
                    results.append("Redis: ❌")
            except:
                results.append("Redis: ❌")
            
            # MySQL
            try:
                start = time.time()
                sock = socket.socket()
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', 3306))
                latency = (time.time() - start) * 1000
                sock.close()
                if result == 0:
                    results.append(f"MySQL: {latency:.0f}ms")
                else:
                    results.append("MySQL: ❌")
            except:
                results.append("MySQL: ❌")
            
            print(f"\r🕒 {timestamp} | {' | '.join(results)}", end="", flush=True)
            time.sleep(3)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Monitoring stopped")

if __name__ == "__main__":
    http_monitor()
