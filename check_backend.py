import socket
import urllib.request
import json

result = {}

# Test 1: TCP connect
try:
    s = socket.create_connection(("127.0.0.1", 8000), timeout=3)
    s.close()
    result["tcp_connect"] = "SUCCESS"
except Exception as e:
    result["tcp_connect"] = f"FAILED: {e}"

# Test 2: HTTP request
try:
    with urllib.request.urlopen("http://127.0.0.1:8000/health", timeout=3) as r:
        result["http"] = r.read().decode()
except Exception as e:
    result["http"] = f"FAILED: {e}"

# Test 3: Check what's on port 8000
try:
    import subprocess
    out = subprocess.check_output(["netstat", "-ano"], text=True, timeout=5)
    lines = [l for l in out.splitlines() if ":8000" in l]
    result["netstat_8000"] = lines
except Exception as e:
    result["netstat"] = str(e)

with open(r"C:\Users\belha\OneDrive\Bureau\raid-fun\check_result.txt", "w") as f:
    json.dump(result, f, indent=2)

print("Done! Check check_result.txt")
input("Press Enter to close...")
