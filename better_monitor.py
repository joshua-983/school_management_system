import time
import socket
import subprocess

def better_monitor():
    print("🔄 REAL-TIME CONNECTION MONITOR (Ctrl+C to stop)")
    print("=" * 50)
    
    try:
        while True:
            results = []
            timestamp = time.strftime('%H:%M:%S')
            
            # Django App
            try:
                start = time.time()
                sock = socket.socket()
                sock.settimeout(1)
                result = sock.connect_ex(('localhost', 8000))
                latency = (time.time() - start) * 1000
                sock.close()
                if result == 0:
                    results.append(f"Django: {latency:.0f}ms")
                else:
                    results.append("Django: ❌")
            except:
                results.append("Django: ❌")
            
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
            time.sleep(2)
            
    except KeyboardInterrupt:
        print("\n\n🛑 Monitoring stopped")

if __name__ == "__main__":
    better_monitor()
