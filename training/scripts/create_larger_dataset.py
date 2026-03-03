# Generated: 2025-10-02 06:50:00 KST
"""
Create larger dataset for PaddleOCR training
Selects high-quality samples from Oracle database with bbox count filtering
"""

import sys
import os
from pathlib import Path
import argparse
import json

# Add parent directory to Python path for imports
sys.path.append(str(Path(__file__).parent.parent.parent / 'crawling'))

try:
    import cx_Oracle
except ImportError:
    print("❌ cx_Oracle not installed. Installing...")
    os.system("pip install cx-Oracle")
    import cx_Oracle

from loguru import logger


def connect_to_oracle():
    """Connect to Oracle database"""
    try:
        dsn = cx_Oracle.makedsn(
            host=os.getenv('ORACLE_HOST', '192.168.75.194'),
            port=int(os.getenv('ORACLE_PORT', '1521')),
            service_name=os.getenv('ORACLE_SERVICE_NAME', 'XEPDB1')
        )

        connection = cx_Oracle.connect(
            user=os.getenv('ORACLE_USERNAME', 'ocr_admin'),
            password=os.getenv('ORACLE_PASSWORD', 'admin_password'),
            dsn=dsn,
            encoding='UTF-8'
        )

        logger.info("✅ Connected to Oracle database")
        return connection

    except Exception as e:
        logger.error(f"❌ Oracle connection failed: {e}")
        raise


def select_quality_samples(connection, num_samples=100, min_bbox=50, max_bbox=300):
    """
    Select quality samples from database

    Args:
        connection: Oracle connection object
        num_samples: Number of samples to select
        min_bbox: Minimum bbox count
        max_bbox: Maximum bbox count

    Returns:
        List of (capture_id, bbox_count) tuples
    """
    query = """
    SELECT
        wcd.CAPTURE_ID,
        COUNT(tbb.BOX_ID) as bbox_count
    FROM
        WEB_CAPTURE_DATA wcd
    INNER JOIN
        TEXT_BOUNDING_BOXES tbb ON wcd.CAPTURE_ID = tbb.CAPTURE_ID
    WHERE
        wcd.IMAGE_PATH IS NOT NULL
        AND LENGTH(tbb.TEXT_CONTENT) > 0
    GROUP BY
        wcd.CAPTURE_ID
    HAVING
        COUNT(tbb.BOX_ID) BETWEEN :min_bbox AND :max_bbox
    ORDER BY
        COUNT(tbb.BOX_ID) ASC,
        wcd.CAPTURE_ID
    FETCH FIRST :num_samples ROWS ONLY
    """

    cursor = connection.cursor()
    cursor.execute(query, {
        'min_bbox': min_bbox,
        'max_bbox': max_bbox,
        'num_samples': num_samples
    })

    samples = cursor.fetchall()
    cursor.close()

    logger.info(f"✅ Selected {len(samples)} quality samples")
    logger.info(f"   Bbox range: {min_bbox}-{max_bbox}")
    logger.info(f"   Sample bbox counts: {[s[1] for s in samples[:5]]}... (first 5)")

    return samples


def export_to_paddleocr_format(connection, samples, output_dir):
    """
    Export samples to PaddleOCR format

    Args:
        connection: Oracle connection object
        samples: List of (capture_id, bbox_count) tuples
        output_dir: Output directory path
    """
    from PIL import Image

    # Create output directories
    output_dir = Path(output_dir)
    images_dir = output_dir / 'train' / 'images'
    images_dir.mkdir(parents=True, exist_ok=True)

    # Prepare label file
    label_file = output_dir / 'train_list.txt'

    logger.info(f"📁 Output directory: {output_dir}")
    logger.info(f"📝 Label file: {label_file}")

    # Query for getting capture data with bboxes
    query = """
    SELECT
        wcd.IMAGE_PATH,
        tbb.TEXT_CONTENT,
        tbb.X_COORDINATE,
        tbb.Y_COORDINATE,
        tbb.WIDTH,
        tbb.HEIGHT
    FROM
        WEB_CAPTURE_DATA wcd
    INNER JOIN
        TEXT_BOUNDING_BOXES tbb ON wcd.CAPTURE_ID = tbb.CAPTURE_ID
    WHERE
        wcd.CAPTURE_ID = :capture_id
        AND LENGTH(tbb.TEXT_CONTENT) > 0
    ORDER BY
        tbb.BOX_ID
    """

    cursor = connection.cursor()

    with open(label_file, 'w', encoding='utf-8') as f:
        for idx, (capture_id, bbox_count) in enumerate(samples, 1):
            # Fetch data for this capture
            cursor.execute(query, {'capture_id': capture_id})
            rows = cursor.fetchall()

            if not rows:
                logger.warning(f"⚠️  No data for CAPTURE_ID={capture_id}, skipping")
                continue

            # Copy image from source path
            source_image_path = rows[0][0]  # IMAGE_PATH from database
            image_filename = f'image_{capture_id}.jpg'
            dest_image_path = images_dir / image_filename

            if source_image_path and Path(source_image_path).exists():
                try:
                    img = Image.open(source_image_path)
                    img.save(dest_image_path, 'JPEG')
                    img.close()
                except Exception as e:
                    logger.error(f"❌ Failed to copy image for CAPTURE_ID={capture_id}: {e}")
                    continue
            else:
                logger.warning(f"⚠️  Image file not found: {source_image_path}, skipping")
                continue

            # Prepare bboxes in PaddleOCR format
            paddleocr_annotations = []
            for row in rows:
                text_content = row[1]
                # Convert CLOB to string if needed
                if hasattr(text_content, 'read'):
                    text_content = text_content.read()
                text_content = str(text_content) if text_content else ""

                x_coord, y_coord, width, height = row[2], row[3], row[4], row[5]

                # Convert to [x1,y1], [x2,y2], [x3,y3], [x4,y4] format
                points = [
                    [int(x_coord), int(y_coord)],
                    [int(x_coord + width), int(y_coord)],
                    [int(x_coord + width), int(y_coord + height)],
                    [int(x_coord), int(y_coord + height)]
                ]

                paddleocr_annotations.append({
                    'transcription': text_content,
                    'points': points
                })

            # Write to label file (one line per image)
            label_line = f"images/{image_filename}\t{json.dumps(paddleocr_annotations, ensure_ascii=False)}\n"
            f.write(label_line)

            if idx % 10 == 0:
                logger.info(f"   Processed {idx}/{len(samples)} samples...")

    cursor.close()

    logger.info(f"✅ Export completed: {len(samples)} samples")
    logger.info(f"   Images: {images_dir}")
    logger.info(f"   Labels: {label_file}")


def main():
    parser = argparse.ArgumentParser(description='Create larger dataset for PaddleOCR training')
    parser.add_argument('--samples', type=int, default=100, help='Number of samples to select (default: 100)')
    parser.add_argument('--min-bbox', type=int, default=50, help='Minimum bbox count (default: 50)')
    parser.add_argument('--max-bbox', type=int, default=300, help='Maximum bbox count (default: 300)')
    parser.add_argument('--output-dir', type=str, default='/home/pro301/paddleocr_training/data_100',
                        help='Output directory (default: /home/pro301/paddleocr_training/data_100)')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("📦 Creating Larger Dataset for PaddleOCR Training")
    logger.info("=" * 80)
    logger.info(f"Target samples: {args.samples}")
    logger.info(f"Bbox range: {args.min_bbox}-{args.max_bbox}")
    logger.info(f"Output directory: {args.output_dir}")
    logger.info("")

    try:
        # Connect to database
        connection = connect_to_oracle()

        # Select quality samples
        samples = select_quality_samples(
            connection,
            num_samples=args.samples,
            min_bbox=args.min_bbox,
            max_bbox=args.max_bbox
        )

        if not samples:
            logger.error("❌ No samples selected. Check your database or criteria.")
            return

        # Export to PaddleOCR format
        export_to_paddleocr_format(connection, samples, args.output_dir)

        # Close connection
        connection.close()
        logger.info("✅ Database connection closed")

        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ Dataset creation completed successfully!")
        logger.info("=" * 80)
        logger.info(f"Next step: Run split_dataset.py to create Train/Val/Test splits")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
