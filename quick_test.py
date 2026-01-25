import urllib.request
import json
import sys

NEON_ENDPOINT = "https://ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/sql"
DATABASE_URL = "postgresql://neondb_owner:npg_OYkCRU4aze2l@ep-crimson-bar-aetz67os-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require"

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
