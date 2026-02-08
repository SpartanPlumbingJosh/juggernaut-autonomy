import os
import urllib.request
import json
import sys

NEON_ENDPOINT = os.environ.get("NEON_HTTP_ENDPOINT", "")
DATABASE_URL = os.environ.get("DATABASE_URL", "")

def test():
    try:
        headers = {
            "Content-Type": "application/json",
            "Neon-Connection-String": DATABASE_URL
        }
        data = json.dumps({"query": "SELECT 1 as test, NOW() as current_time"}).encode('utf-8')
        req = urllib.request.Request(NEON_ENDPOINT, data=data, headers=headers, method='POST')
        
        print("Testing connection...")
        sys.stdout.flush()
        
        with urllib.request.urlopen(req, timeout=30) as response:
            result = json.loads(response.read().decode('utf-8'))
            print("SUCCESS:", result)
            return True
    except Exception as e:
        print("ERROR:", e)
        return False

if __name__ == "__main__":
    test()
