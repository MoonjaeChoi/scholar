# Generated: 2025-10-02 07:12:00 KST
"""
Find September 25 images in database and check their paths
"""

import cx_Oracle

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
print("Searching for September 25 images in database:")
print("=" * 80)

# Find Sept 25 images
cursor.execute("""
    SELECT CAPTURE_ID, IMAGE_PATH
    FROM WEB_CAPTURE_DATA
    WHERE IMAGE_PATH LIKE '%screenshot_20250925%'
    AND ROWNUM <= 10
    ORDER BY CAPTURE_ID
""")

sept25_records = cursor.fetchall()

if sept25_records:
    print(f"\nFound {len(sept25_records)} records with Sept 25 images:")
    for capture_id, image_path in sept25_records:
        print(f"  CAPTURE_ID={capture_id:5d}, PATH={image_path}")
else:
    print("\n❌ No September 25 images found in database!")
    print("\nThis means the Sept 25 images on disk are NOT in the database.")

print()

# Count total records with IMAGE_PATH
cursor.execute("""
    SELECT COUNT(*)
    FROM WEB_CAPTURE_DATA
    WHERE IMAGE_PATH IS NOT NULL
""")

total_with_path = cursor.fetchone()[0]
print(f"Total records with IMAGE_PATH: {total_with_path}")

# Check date distribution
cursor.execute("""
    SELECT
        SUBSTR(IMAGE_PATH, INSTR(IMAGE_PATH, 'screenshot_') + 11, 8) as date_str,
        COUNT(*) as count
    FROM WEB_CAPTURE_DATA
    WHERE IMAGE_PATH LIKE '%screenshot_%'
    GROUP BY SUBSTR(IMAGE_PATH, INSTR(IMAGE_PATH, 'screenshot_') + 11, 8)
    ORDER BY date_str DESC
""")

print("\nDate distribution in IMAGE_PATH:")
for date_str, count in cursor.fetchall():
    print(f"  {date_str}: {count} records")

cursor.close()
conn.close()

print()
print("=" * 80)
