# Generated: 2025-10-02 07:25:00 KST
"""
Update all IMAGE_PATH in database to new location after migration
OLD: /home/pro301/git/en-zine/ocr_system/crawling/data/images
NEW: /home/en-zine-data/crawling/data/images
"""

import cx_Oracle
import os
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
print("Updating IMAGE_PATH after data migration (014 document)")
print("=" * 80)
print()

OLD_PATH = '/home/pro301/git/en-zine/ocr_system/crawling/data/images'
NEW_PATH = '/home/en-zine-data/crawling/data/images'

print(f"OLD PATH: {OLD_PATH}")
print(f"NEW PATH: {NEW_PATH}")
print()

# Count records to update
cursor.execute("""
    SELECT COUNT(*)
    FROM WEB_CAPTURE_DATA
    WHERE IMAGE_PATH LIKE :old_path || '%'
""", {'old_path': OLD_PATH})

count_to_update = cursor.fetchone()[0]

print(f"Records to update: {count_to_update}")
print()

if count_to_update == 0:
    print("✅ No records need updating. All paths are already correct.")
    cursor.close()
    conn.close()
    exit(0)

# Show sample before update
cursor.execute("""
    SELECT CAPTURE_ID, IMAGE_PATH
    FROM WEB_CAPTURE_DATA
    WHERE IMAGE_PATH LIKE :old_path || '%'
    AND ROWNUM <= 3
    ORDER BY CAPTURE_ID
""", {'old_path': OLD_PATH})

print("Sample records (before update):")
for capture_id, image_path in cursor.fetchall():
    print(f"  CAPTURE_ID={capture_id:5d}: {image_path}")
print()

# Get user confirmation
response = input(f"Update {count_to_update} records? (yes/no): ")

if response.lower() != 'yes':
    print("❌ Cancelled by user")
    cursor.close()
    conn.close()
    exit(0)

print()
print("Updating IMAGE_PATH...")

# Perform bulk update using REPLACE
cursor.execute("""
    UPDATE WEB_CAPTURE_DATA
    SET IMAGE_PATH = REPLACE(IMAGE_PATH, :old_path, :new_path)
    WHERE IMAGE_PATH LIKE :old_path || '%'
""", {
    'old_path': OLD_PATH,
    'new_path': NEW_PATH
})

updated_count = cursor.rowcount

# Commit changes
conn.commit()

print(f"✅ Successfully updated {updated_count} records")
print()

# Verify update
cursor.execute("""
    SELECT CAPTURE_ID, IMAGE_PATH
    FROM WEB_CAPTURE_DATA
    WHERE IMAGE_PATH LIKE :new_path || '%'
    AND ROWNUM <= 3
    ORDER BY CAPTURE_ID
""", {'new_path': NEW_PATH})

print("Sample records (after update):")
for capture_id, image_path in cursor.fetchall():
    exists = "✅ EXISTS" if os.path.exists(image_path) else "❌ NOT FOUND"
    print(f"  {exists} CAPTURE_ID={capture_id:5d}: {image_path}")

print()

# Final counts
cursor.execute("""
    SELECT COUNT(*)
    FROM WEB_CAPTURE_DATA
    WHERE IMAGE_PATH LIKE :new_path || '%'
""", {'new_path': NEW_PATH})

new_path_count = cursor.fetchone()[0]

cursor.execute("""
    SELECT COUNT(*)
    FROM WEB_CAPTURE_DATA
    WHERE IMAGE_PATH IS NOT NULL
""")

total_count = cursor.fetchone()[0]

print("=" * 80)
print("Update Summary:")
print("=" * 80)
print(f"Total records with IMAGE_PATH: {total_count}")
print(f"Records with new path: {new_path_count}")
print(f"Records updated: {updated_count}")
print()

if new_path_count == total_count:
    print("✅ All IMAGE_PATH records successfully updated!")
else:
    print(f"⚠️  {total_count - new_path_count} records still have old paths")

cursor.close()
conn.close()

print()
print("=" * 80)
print("Update completed!")
print("=" * 80)
