# Generated: 2025-10-02 07:10:00 KST
"""
Check current IMAGE_PATH in database and find actual image locations
"""

import cx_Oracle
import os
from pathlib import Path

# Connect to Oracle
dsn = cx_Oracle.makedsn(
    host='192.168.75.194',
    port=1521,
    service_name='XEPDB1'
)

conn = cx_Oracle.connect(
    user='ocr_admin',
    password='admin_password',
    dsn=dsn,
    encoding='UTF-8'
)

cursor = conn.cursor()

# Check current IMAGE_PATH examples
print("=" * 80)
print("Current IMAGE_PATH in database (first 10 samples):")
print("=" * 80)

cursor.execute("""
    SELECT CAPTURE_ID, IMAGE_PATH
    FROM WEB_CAPTURE_DATA
    WHERE IMAGE_PATH IS NOT NULL
    AND ROWNUM <= 10
    ORDER BY CAPTURE_ID
""")

db_paths = []
for row in cursor.fetchall():
    capture_id, image_path = row
    print(f"CAPTURE_ID={capture_id:5d}, PATH={image_path}")
    db_paths.append((capture_id, image_path))

print()

# Check actual file locations
print("=" * 80)
print("Checking actual file existence:")
print("=" * 80)

for capture_id, image_path in db_paths:
    exists = os.path.exists(image_path) if image_path else False
    status = "✅ EXISTS" if exists else "❌ NOT FOUND"
    print(f"CAPTURE_ID={capture_id:5d}: {status}")

print()

# Find actual images
print("=" * 80)
print("Searching for actual image files on server:")
print("=" * 80)

search_paths = [
    '/home/pro301/git/en-zine/ocr_system/crawling/data/images',
    '/home/pro301/paddleocr_training',
    '/opt/ocr_system/crawling/data/images'
]

for search_path in search_paths:
    if os.path.exists(search_path):
        print(f"\n📁 Searching in: {search_path}")
        try:
            files = list(Path(search_path).rglob('screenshot_*.png'))[:5]
            if files:
                print(f"   Found {len(files)} images (showing first 5):")
                for f in files:
                    print(f"   - {f}")
            else:
                print(f"   No screenshot_*.png files found")
        except Exception as e:
            print(f"   Error: {e}")
    else:
        print(f"\n📁 Path does not exist: {search_path}")

cursor.close()
conn.close()

print()
print("=" * 80)
print("Check completed")
print("=" * 80)
