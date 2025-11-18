import time
import socket
import requests

def quick_check():
    services = [
        ("Django App", "http://localhost:8000/"),
        ("Redis", 6379),
        ("MySQL", 3306),
    ]
    
    print("🔄 REAL-TIME CONNECTION MONITOR (Ctrl+C to stop)")
    print("=" * 50)
    
    try:
        while True:
            results = []
            for name, target in services:
                try:
                    start = time.time()
                    if isinstance(target, int):  # Port check
                        sock = socket.socket()
                        sock.settimeout(1)
                        result = sock.connect_ex(('localhost', target))
                        sock.close()
                        status = "✅" if result == 0 else "❌"
                        latency = (time.time() - start) * 1000
                        results.append(f"{name}: {latency:.0f}ms")
                    else:  # HTTP check
                        response = requests.get(target, timeout=2)
                        latency = (time.time() - start) * 1000
                        status = "✅" if response.status_code == 200 else "❌"
                        results.append(f"{name}: {latency:.0f}ms")
                except:
                    results.append(f"{name}: ❌")
            
            print(f"\r🕒 {time.strftime('%H:%M:%S')} | {' | '.join(results)}", end="", flush=True)
            time.sleep(3)
    except KeyboardInterrupt:
        print("\n\n🛑 Monitoring stopped")

if __name__ == "__main__":
    quick_check()
