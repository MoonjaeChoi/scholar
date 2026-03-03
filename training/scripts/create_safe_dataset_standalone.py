#!/usr/bin/env python3
# Generated: 2025-10-02 08:25:00 KST
"""
Create safe PaddleOCR dataset - standalone version without external converters
Uses only built-in libraries and PIL (which is available in PaddleOCR container)
"""

import os
import sys
import json
import shutil
from pathlib import Path

sys.path.append('/home/pro301/git/en-zine/ocr_system/paddleocr_training')
from database_connection import DatabaseConnection

def main():
    print("[INFO] Creating safe dataset with strict filtering...")
    print("[INFO] Filters: 60-250 bboxes, bbox size 5-2000px, area >= 25px²")

    # Setup output directory
    output_dir = Path("/home/pro301/git/en-zine/ocr_system/paddleocr_training/data_safe")
    train_dir = output_dir / "train"
    images_dir = train_dir / "images"
    images_dir.mkdir(parents=True, exist_ok=True)

    db_connection = DatabaseConnection()

    # Get safe captures
    try:
        with db_connection.get_connection() as conn:
            cursor = conn.cursor()

            sql = """
            SELECT wcd.CAPTURE_ID, wcd.IMAGE_PATH,
                   COUNT(tbb.BOX_ID) as bbox_count
            FROM WEB_CAPTURE_DATA wcd
            JOIN TEXT_BOUNDING_BOXES tbb ON wcd.CAPTURE_ID = tbb.CAPTURE_ID
            WHERE wcd.PROCESSING_STATUS = 'completed'
              AND wcd.IMAGE_PATH IS NOT NULL
              AND tbb.WIDTH > 5 AND tbb.HEIGHT > 5
              AND tbb.WIDTH < 2000 AND tbb.HEIGHT < 2000
              AND (tbb.WIDTH * tbb.HEIGHT) >= 25
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

            print(f"[INFO] Found {len(captures)} safe captures")

            # Limit to 100 samples
            if len(captures) > 100:
                captures = captures[:100]
                print(f"[INFO] Limited to 100 samples")

            if not captures:
                print("[ERROR] No safe captures found!")
                return 1

            # Process each capture
            successful = 0
            train_list_path = output_dir / "train_list.txt"

            with open(train_list_path, 'w', encoding='utf-8') as train_list:
                for i, capture in enumerate(captures):
                    try:
                        capture_id = capture['capture_id']
                        src_image_path = capture['image_path']

                        # Convert path from database to container path
                        # Database: /home/en-zine-data/crawling/data/images/...
                        # Container: /home/pro301/git/en-zine/ocr_system/crawling/data/images/...
                        if src_image_path.startswith('/home/en-zine-data/crawling/data/'):
                            src_image_path = src_image_path.replace(
                                '/home/en-zine-data/crawling/data/',
                                '/home/pro301/git/en-zine/ocr_system/crawling/data/'
                            )

                        # Check image exists
                        if not os.path.exists(src_image_path):
                            print(f"[WARNING] Image not found: {src_image_path}")
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

                            # Skip invalid boxes
                            if w <= 5 or h <= 5 or w >= 2000 or h >= 2000:
                                continue
                            if x < 0 or y < 0:
                                continue

                            boxes.append({
                                'text': text_content,
                                'x': x, 'y': y, 'w': w, 'h': h
                            })

                        if not boxes:
                            print(f"[WARNING] No valid boxes for capture {capture_id}")
                            continue

                        # Copy image directly (no resize to avoid PIL dependency)
                        image_filename = f"image_{capture_id}.jpg"
                        dst_image_path = images_dir / image_filename

                        try:
                            shutil.copy2(src_image_path, dst_image_path)
                        except Exception as e:
                            print(f"[ERROR] Failed to copy image {src_image_path}: {e}")
                            continue

                        # Create PaddleOCR annotation
                        label_dicts = []
                        for box in boxes:
                            x, y, w, h = box['x'], box['y'], box['w'], box['h']
                            points = [
                                [x, y],          # top-left
                                [x + w, y],      # top-right
                                [x + w, y + h],  # bottom-right
                                [x, y + h]       # bottom-left
                            ]
                            label_dicts.append({
                                "transcription": box['text'],
                                "points": points
                            })

                        # Write to train_list.txt
                        train_list.write(f"images/{image_filename}\t{json.dumps(label_dicts, ensure_ascii=False)}\n")

                        successful += 1
                        if (successful) % 10 == 0:
                            print(f"[INFO] Processed {successful}/{len(captures)} samples")

                    except Exception as e:
                        print(f"[ERROR] Error processing capture {capture.get('capture_id', 'unknown')}: {e}")
                        import traceback
                        traceback.print_exc()
                        continue

            print(f"[SUCCESS] Successfully created {successful} samples")
            print(f"[INFO] Output directory: {output_dir}")
            print(f"[INFO] Train list: {train_list_path}")

            # Verify
            with open(train_list_path, 'r') as f:
                line_count = len(f.readlines())
            print(f"[INFO] Total annotation lines: {line_count}")

            return 0 if successful > 0 else 1

    except Exception as e:
        print(f"[ERROR] Error creating safe dataset: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
