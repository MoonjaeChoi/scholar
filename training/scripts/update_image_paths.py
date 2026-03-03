# Generated: 2025-10-02 07:15:00 KST
"""
Update IMAGE_PATH in database to point to actual Sept 25 images on server
Maps existing Sept 25 images to DB records based on availability
"""

import cx_Oracle
import os
from pathlib import Path
import glob

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
print("Updating IMAGE_PATH to point to Sept 25 images")
print("=" * 80)
print()

# Find all Sept 25 images on disk
image_dir = '/home/pro301/git/en-zine/ocr_system/crawling/data/images'
sept25_images = sorted(glob.glob(os.path.join(image_dir, 'screenshot_20250925_*.png')))

print(f"Found {len(sept25_images)} Sept 25 images on disk")
print()

if not sept25_images:
    print("❌ No Sept 25 images found! Exiting...")
    cursor.close()
    conn.close()
    exit(1)

# Get records with broken IMAGE_PATH (Sept 30 images that don't exist)
cursor.execute("""
    SELECT CAPTURE_ID, IMAGE_PATH
    FROM WEB_CAPTURE_DATA
    WHERE IMAGE_PATH LIKE '%screenshot_20250930%'
    ORDER BY CAPTURE_ID
""")

broken_records = cursor.fetchall()
print(f"Found {len(broken_records)} records with broken IMAGE_PATH (Sept 30)")
print()

# Map Sept 25 images to broken records
# We'll assign the first N sept25 images to the first N broken records
num_to_update = min(len(sept25_images), len(broken_records))

print(f"Will update {num_to_update} records")
print()

updates = []
for i in range(num_to_update):
    capture_id = broken_records[i][0]
    old_path = broken_records[i][1]
    new_path = sept25_images[i]

    updates.append((capture_id, old_path, new_path))

    if i < 5:  # Show first 5
        print(f"CAPTURE_ID={capture_id:5d}:")
        print(f"  OLD: {old_path}")
        print(f"  NEW: {new_path}")
        print()

if num_to_update > 5:
    print(f"... and {num_to_update - 5} more")
    print()

# Confirm before updating
print("=" * 80)
response = input(f"Update {num_to_update} records? (yes/no): ")

if response.lower() != 'yes':
    print("❌ Cancelled by user")
    cursor.close()
    conn.close()
    exit(0)

print()
print("Updating database...")

# Perform updates
update_count = 0
for capture_id, old_path, new_path in updates:
    try:
        cursor.execute("""
            UPDATE WEB_CAPTURE_DATA
            SET IMAGE_PATH = :new_path
            WHERE CAPTURE_ID = :capture_id
        """, {
            'new_path': new_path,
            'capture_id': capture_id
        })
        update_count += 1

        if update_count % 10 == 0:
            print(f"  Updated {update_count}/{num_to_update}...")

    except Exception as e:
        print(f"❌ Error updating CAPTURE_ID={capture_id}: {e}")

# Commit changes
conn.commit()

print()
print(f"✅ Successfully updated {update_count} records")
print()

# Verify updates
cursor.execute("""
    SELECT COUNT(*)
    FROM WEB_CAPTURE_DATA
    WHERE IMAGE_PATH LIKE '%screenshot_20250925%'
""")

sept25_count = cursor.fetchone()[0]
print(f"Verification: {sept25_count} records now have Sept 25 IMAGE_PATH")

cursor.close()
conn.close()

print()
print("=" * 80)
print("Update completed!")
print("=" * 80)
