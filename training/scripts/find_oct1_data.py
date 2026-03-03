# Generated: 2025-10-02 07:20:00 KST
"""
Find October 1 data in database and check actual file locations
"""

import cx_Oracle
import os

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

print("=" * 80)
print("Searching for October 1, 2025 data in database:")
print("=" * 80)

# Find Oct 1 images
cursor.execute("""
    SELECT CAPTURE_ID, IMAGE_PATH, CREATED_AT
    FROM WEB_CAPTURE_DATA
    WHERE IMAGE_PATH LIKE '%20251001%'
    ORDER BY CAPTURE_ID
""")

oct1_records = cursor.fetchall()

if oct1_records:
    print(f"\nFound {len(oct1_records)} records with Oct 1 images in IMAGE_PATH:\n")
    for capture_id, image_path, created_at in oct1_records:
        exists = "✅ EXISTS" if os.path.exists(image_path) else "❌ NOT FOUND"
        print(f"CAPTURE_ID={capture_id:5d}, {exists}")
        print(f"  PATH: {image_path}")
        print(f"  CREATED: {created_at}")
        print()
else:
    print("\n❌ No October 1 images found in IMAGE_PATH field!")

print()
print("=" * 80)
print("Checking CREATED_AT date for recent data:")
print("=" * 80)

# Check by CREATED_AT date
cursor.execute("""
    SELECT
        TO_CHAR(CREATED_AT, 'YYYY-MM-DD') as date_str,
        COUNT(*) as count,
        MIN(CAPTURE_ID) as min_id,
        MAX(CAPTURE_ID) as max_id
    FROM WEB_CAPTURE_DATA
    WHERE CREATED_AT >= TO_DATE('2025-10-01', 'YYYY-MM-DD')
    GROUP BY TO_CHAR(CREATED_AT, 'YYYY-MM-DD')
    ORDER BY date_str DESC
""")

print("\nRecords by CREATED_AT date:")
for date_str, count, min_id, max_id in cursor.fetchall():
    print(f"  {date_str}: {count:3d} records (CAPTURE_ID {min_id:5d} - {max_id:5d})")

print()

# Show sample paths for Oct 1 created records
cursor.execute("""
    SELECT CAPTURE_ID, IMAGE_PATH
    FROM WEB_CAPTURE_DATA
    WHERE CREATED_AT >= TO_DATE('2025-10-01', 'YYYY-MM-DD')
    AND ROWNUM <= 10
    ORDER BY CAPTURE_ID
""")

print("=" * 80)
print("Sample IMAGE_PATH for Oct 1 created records:")
print("=" * 80)

for capture_id, image_path in cursor.fetchall():
    exists = "✅" if (image_path and os.path.exists(image_path)) else "❌"
    print(f"{exists} CAPTURE_ID={capture_id:5d}: {image_path}")

# Count total bbox for Oct 1 data
cursor.execute("""
    SELECT COUNT(tbb.BOX_ID)
    FROM WEB_CAPTURE_DATA wcd
    JOIN TEXT_BOUNDING_BOXES tbb ON wcd.CAPTURE_ID = tbb.CAPTURE_ID
    WHERE wcd.CREATED_AT >= TO_DATE('2025-10-01', 'YYYY-MM-DD')
""")

total_bbox = cursor.fetchone()[0]
print(f"\nTotal bboxes for Oct 1 data: {total_bbox}")

cursor.close()
conn.close()

print()
print("=" * 80)
