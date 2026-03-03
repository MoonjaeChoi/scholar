#!/usr/bin/env python3
# Generated: 2025-10-02 09:55:00 KST
"""
Create validated PaddleOCR dataset - validates images before adding to dataset
"""

import os
import sys
import json
import shutil
from pathlib import Path

sys.path.append('/home/pro301/git/en-zine/ocr_system/paddleocr_training')
from database_connection import DatabaseConnection

def validate_image(image_path):
    """Check if image file is valid and readable"""
    try:
        if not os.path.exists(image_path):
            return False, "File not found"

        if os.path.getsize(image_path) == 0:
            return False, "Empty file"

        # Try to open with PIL-like method (using basic file operations)
        with open(image_path, 'rb') as f:
            # Check for common image file headers
            header = f.read(12)

            # JPEG magic number
            if header[:3] == b'\xff\xd8\xff':
                return True, "Valid JPEG"
            # PNG magic number
            elif header[:8] == b'\x89PNG\r\n\x1a\n':
                return True, "Valid PNG"
            # GIF magic number
            elif header[:3] == b'GIF':
                return True, "Valid GIF"
            else:
                return False, "Unknown image format"

    except Exception as e:
        return False, f"Error: {str(e)}"

def main():
    print("[INFO] Creating validated dataset with strict polygon-safe filtering...")
    print("[INFO] Filters: 60-250 bboxes, width>=15px, height>=15px, area>=225px², x>=0, y>=0, valid images only")

    # Setup output directory
    output_dir = Path("/home/pro301/git/en-zine/ocr_system/paddleocr_training/data_validated")
    train_dir = output_dir / "train"
    images_dir = train_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    db_connection = DatabaseConnection()

    try:
        with db_connection.get_connection() as conn:
            cursor = conn.cursor()

            # Get safe captures (with strict filtering for PaddleOCR polygon creation)
            sql = """
            SELECT wcd.CAPTURE_ID, wcd.IMAGE_PATH,
                   COUNT(tbb.BOX_ID) as bbox_count
            FROM WEB_CAPTURE_DATA wcd
            JOIN TEXT_BOUNDING_BOXES tbb ON wcd.CAPTURE_ID = tbb.CAPTURE_ID
            WHERE wcd.PROCESSING_STATUS = 'completed'
              AND wcd.IMAGE_PATH IS NOT NULL
              AND tbb.X_COORDINATE >= 0
              AND tbb.Y_COORDINATE >= 0
              AND tbb.WIDTH >= 15 AND tbb.HEIGHT >= 15
              AND tbb.WIDTH < 2000 AND tbb.HEIGHT < 2000
              AND (tbb.WIDTH * tbb.HEIGHT) >= 225
            GROUP BY wcd.CAPTURE_ID, wcd.IMAGE_PATH
            HAVING COUNT(tbb.BOX_ID) BETWEEN 60 AND 250
               AND AVG(tbb.CONFIDENCE_SCORE) >= 0.7
            ORDER BY COUNT(tbb.BOX_ID) ASC
            """

            cursor.execute(sql)
            captures = []

            for row in cursor.fetchall():
                captures.append({
                    'capture_id': row[0],
                    'image_path': row[1],
                    'bbox_count': row[2]
                })

            print(f"[INFO] Found {len(captures)} candidate captures")

            # Validate and process
            successful = 0
            skipped = 0
            train_list_path = output_dir / "train_list.txt"

            with open(train_list_path, 'w', encoding='utf-8') as train_list:
                for i, capture in enumerate(captures):
                    if successful >= 100:
                        print(f"[INFO] Reached target of 100 valid samples")
                        break

                    try:
                        capture_id = capture['capture_id']
                        src_image_path = capture['image_path']

                        # Convert database path to container path
                        if src_image_path.startswith('/home/en-zine-data/crawling/data/'):
                            src_image_path = src_image_path.replace(
                                '/home/en-zine-data/crawling/data/',
                                '/home/en-zine-data/crawling/data/'
                            )

                        # Validate image file
                        is_valid, reason = validate_image(src_image_path)
                        if not is_valid:
                            print(f"[SKIP] Capture {capture_id}: {reason}")
                            skipped += 1
                            continue

                        # Get bounding boxes
                        cursor.execute("""
                            SELECT TEXT_CONTENT, X_COORDINATE, Y_COORDINATE,
                                   WIDTH, HEIGHT
                            FROM TEXT_BOUNDING_BOXES
                            WHERE CAPTURE_ID = :1
                            ORDER BY Y_COORDINATE, X_COORDINATE
                        """, (capture_id,))

                        boxes = []
                        for box_row in cursor.fetchall():
                            # Handle CLOB
                            text_content = box_row[0]
                            if hasattr(text_content, 'read'):
                                text_content = text_content.read()
                            text_content = str(text_content) if text_content else ""

                            if not text_content.strip():
                                continue

                            x = float(box_row[1]) if box_row[1] else 0.0
                            y = float(box_row[2]) if box_row[2] else 0.0
                            w = float(box_row[3]) if box_row[3] else 0.0
                            h = float(box_row[4]) if box_row[4] else 0.0

                            # Skip invalid boxes (strict filtering for polygon safety)
                            if w < 15 or h < 15 or w >= 2000 or h >= 2000:
                                continue
                            if x < 0 or y < 0:
                                continue
                            if (w * h) < 225:  # Area check
                                continue

                            boxes.append({
                                'text': text_content,
                                'x': x, 'y': y, 'w': w, 'h': h
                            })

                        if not boxes:
                            print(f"[SKIP] Capture {capture_id}: No valid boxes")
                            skipped += 1
                            continue

                        # Copy image
                        image_filename = f"image_{capture_id}.jpg"
                        dst_image_path = images_dir / image_filename

                        try:
                            shutil.copy2(src_image_path, dst_image_path)
                        except Exception as e:
                            print(f"[SKIP] Capture {capture_id}: Copy failed - {e}")
                            skipped += 1
                            continue

                        # Create PaddleOCR annotation
                        label_dicts = []
                        for box in boxes:
                            x, y, w, h = box['x'], box['y'], box['w'], box['h']
                            points = [
                                [x, y],
                                [x + w, y],
                                [x + w, y + h],
                                [x, y + h]
                            ]
                            label_dicts.append({
                                "transcription": box['text'],
                                "points": points
                            })

                        # Write to train_list.txt
                        train_list.write(f"images/{image_filename}\t{json.dumps(label_dicts, ensure_ascii=False)}\n")

                        successful += 1
                        if (successful) % 10 == 0:
                            print(f"[INFO] Validated {successful} samples, skipped {skipped}")

                    except Exception as e:
                        print(f"[ERROR] Capture {capture.get('capture_id', 'unknown')}: {e}")
                        skipped += 1
                        continue

            print(f"\n[SUCCESS] Created {successful} validated samples")
            print(f"[INFO] Skipped {skipped} invalid/problematic samples")
            print(f"[INFO] Output directory: {output_dir}")
            print(f"[INFO] Train list: {train_list_path}")

            # Verify
            with open(train_list_path, 'r') as f:
                line_count = len(f.readlines())
            print(f"[INFO] Total annotation lines: {line_count}")

            return 0 if successful > 0 else 1

    except Exception as e:
        print(f"[ERROR] Error creating validated dataset: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
