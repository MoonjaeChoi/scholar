# Generated: 2025-10-12 07:00:00 KST
"""
Retroactively generate PaddleOCR label files from database records.

This script:
1. Queries WEB_CAPTURE_DATA and TEXT_BOUNDING_BOXES from Oracle
2. Extracts text content for each image
3. Generates corresponding .txt label files
4. Reports statistics
"""

import os
import sys
from pathlib import Path
from loguru import logger

# 환경 변수로 Oracle 라이브러리 선택
# 로컬 개발: USE_PYTHON_ORACLEDB=true (python-oracledb Thin Mode)
# 서버 프로덕션: USE_PYTHON_ORACLEDB=false 또는 미설정 (cx_Oracle)
USE_PYTHON_ORACLEDB = os.getenv('USE_PYTHON_ORACLEDB', 'false').lower() == 'true'

if USE_PYTHON_ORACLEDB:
    import oracledb as oracle_lib
    logger.info("✅ generate_missing_labels: Using python-oracledb (Thin Mode)")
else:
    import cx_Oracle as oracle_lib
    logger.info("✅ generate_missing_labels: Using cx_Oracle")

# Add parent directory to path for imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.connection import DatabaseConnection

def generate_labels_from_database(data_root: str, dry_run: bool = False):
    """Generate PaddleOCR label files from database records.

    Args:
        data_root: Root directory for training data
        dry_run: If True, only report what would be done without creating files
    """
    labels_dir = Path(data_root) / 'labels'
    images_dir = Path(data_root) / 'images'

    # Ensure labels directory exists
    if not dry_run:
        labels_dir.mkdir(parents=True, exist_ok=True)

    # Get database connection
    db = DatabaseConnection()

    try:
        with db.get_connection() as conn:
            cursor = conn.cursor()

            # Query all captures with their image paths
            query = """
                SELECT wcd.capture_id, wcd.image_path, wcd.url
                FROM WEB_CAPTURE_DATA wcd
                WHERE wcd.image_path IS NOT NULL
                ORDER BY wcd.capture_id
            """

            cursor.execute(query)
            captures = cursor.fetchall()

            logger.info(f"Found {len(captures)} captures with images")

            created_count = 0
            skipped_count = 0
            error_count = 0

            for capture_id, db_image_path, url in captures:
                try:
                    # Convert database path to host path
                    # Database: /opt/scholar/data/images/...
                    # Host: /home/pro301/git/en-zine/scholar/training/data/images/...

                    # Handle different path formats in database
                    if '/images/' in db_image_path:
                        # Format: /opt/scholar/data/images/20251011/file.png
                        relative_path = db_image_path.split('/images/', 1)[1]
                        image_path = images_dir / relative_path
                    elif '/screenshots/' in db_image_path:
                        # Format: /home/pro301/git/en-zine/scholar/training/data/screenshots/file.png
                        # Extract just the filename
                        filename = Path(db_image_path).name
                        # Check both images and screenshots directories
                        image_path = Path(data_root) / 'screenshots' / filename
                    else:
                        logger.warning(f"Unexpected image path format: {db_image_path}")
                        error_count += 1
                        continue

                    # Check if image file exists
                    if not image_path.exists():
                        logger.debug(f"Image file not found: {image_path}")
                        skipped_count += 1
                        continue

                    # Construct corresponding label path based on image location
                    if '/screenshots/' in db_image_path:
                        # For screenshots, create label in screenshots folder too
                        filename = image_path.stem + '.txt'
                        label_path = Path(data_root) / 'screenshots' / filename
                    else:
                        # For regular images, use relative path structure
                        relative_path = db_image_path.split('/images/', 1)[1] if '/images/' in db_image_path else Path(db_image_path).name
                        label_path = labels_dir / relative_path.replace('.png', '.txt').replace('.jpg', '.txt')

                    # Check if label already exists
                    if label_path.exists() and not dry_run:
                        logger.debug(f"Label already exists: {label_path}")
                        skipped_count += 1
                        continue

                    # Query text content from bounding boxes
                    text_query = """
                        SELECT text_content
                        FROM TEXT_BOUNDING_BOXES
                        WHERE capture_id = :capture_id
                        ORDER BY y_coordinate, x_coordinate
                    """

                    cursor.execute(text_query, {'capture_id': capture_id})
                    text_boxes = cursor.fetchall()

                    if not text_boxes:
                        logger.debug(f"No text content for capture_id {capture_id}")
                        skipped_count += 1
                        continue

                    # Combine all text content (handle LOBs)
                    texts = []
                    for row in text_boxes:
                        if row[0]:
                            # Oracle CLOB requires .read()
                            if hasattr(row[0], 'read'):
                                texts.append(row[0].read())
                            else:
                                texts.append(str(row[0]))
                    combined_text = ' '.join(texts)

                    if not combined_text.strip():
                        logger.debug(f"Empty text content for capture_id {capture_id}")
                        skipped_count += 1
                        continue

                    # Generate label file
                    if dry_run:
                        logger.info(f"[DRY RUN] Would create: {label_path}")
                        logger.info(f"[DRY RUN] Text length: {len(combined_text)} characters")
                        created_count += 1
                    else:
                        # Ensure parent directory exists
                        label_path.parent.mkdir(parents=True, exist_ok=True)

                        # Write label file
                        with open(label_path, 'w', encoding='utf-8') as f:
                            f.write(combined_text)

                        logger.info(f"Created label: {label_path} ({len(combined_text)} chars)")
                        created_count += 1

                except Exception as e:
                    logger.error(f"Error processing capture_id {capture_id}: {e}")
                    error_count += 1

            # Report statistics
            logger.info("=" * 60)
            logger.info("Label Generation Summary:")
            logger.info(f"  Total captures: {len(captures)}")
            logger.info(f"  Labels created: {created_count}")
            logger.info(f"  Skipped: {skipped_count}")
            logger.info(f"  Errors: {error_count}")
            logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Database error: {e}")

def main():
    """Main execution function."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate missing PaddleOCR label files from database')
    parser.add_argument('--data-root',
                        default='/home/pro301/git/en-zine/scholar/training/data',
                        help='Root directory for training data')
    parser.add_argument('--dry-run',
                        action='store_true',
                        help='Report what would be done without creating files')

    args = parser.parse_args()

    logger.info(f"Starting label generation from database")
    logger.info(f"Data root: {args.data_root}")
    logger.info(f"Dry run: {args.dry_run}")

    generate_labels_from_database(args.data_root, args.dry_run)

    logger.info("Label generation complete")

if __name__ == '__main__':
    main()
