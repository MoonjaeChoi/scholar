#!/usr/bin/env python3
# Generated: 2025-10-02 08:15:00 KST
"""
Create safe PaddleOCR dataset by reusing converter with strict filtering
"""

import sys
sys.path.append('/home/pro301/git/en-zine/ocr_system/paddleocr_training')

from convert_database_to_paddleocr import PaddleOCRDatasetConverter
from database_connection import DatabaseConnection

def main():
    print("[INFO] Creating safe dataset with strict filtering...")
    print("[INFO] Filters: 60-250 bboxes, bbox size 5-2000px, area >= 25px²")

    # Create converter with specific output directory
    converter = PaddleOCRDatasetConverter("/home/pro301/git/en-zine/ocr_system/paddleocr_training/data_safe")

    # Get quality captures with stricter filtering
    try:
        with converter.db_connection.get_connection() as conn:
            cursor = conn.cursor()

            sql = """
            SELECT wcd.CAPTURE_ID, wcd.URL, wcd.IMAGE_PATH,
                   COUNT(tbb.BOX_ID) as bbox_count,
                   AVG(tbb.CONFIDENCE_SCORE) as avg_confidence
            FROM WEB_CAPTURE_DATA wcd
            JOIN TEXT_BOUNDING_BOXES tbb ON wcd.CAPTURE_ID = tbb.CAPTURE_ID
            WHERE wcd.PROCESSING_STATUS = 'completed'
              AND wcd.IMAGE_PATH IS NOT NULL
              AND tbb.WIDTH > 5 AND tbb.HEIGHT > 5
              AND tbb.WIDTH < 2000 AND tbb.HEIGHT < 2000
              AND (tbb.WIDTH * tbb.HEIGHT) >= 25
            GROUP BY wcd.CAPTURE_ID, wcd.URL, wcd.IMAGE_PATH
            HAVING COUNT(tbb.BOX_ID) BETWEEN 60 AND 250
               AND AVG(tbb.CONFIDENCE_SCORE) >= 0.7
            ORDER BY COUNT(tbb.BOX_ID) ASC
            """

            cursor.execute(sql)
            results = []

            for row in cursor.fetchall():
                results.append({
                    'capture_id': row[0],
                    'source_url': row[1],
                    'image_path': row[2],
                    'bbox_count': row[3],
                    'avg_confidence': row[4]
                })

            print(f"[INFO] Found {len(results)} safe captures")

            # Limit to 100 samples
            if len(results) > 100:
                results = results[:100]
                print(f"[INFO] Limited to 100 samples")

            # Convert samples
            if results:
                train_count = converter._convert_samples(results, converter.train_dir)
                print(f"[SUCCESS] Converted {train_count} training samples")

                # Create file list
                train_list_path = converter.output_dir / "train_list.txt"
                with open(train_list_path, 'w') as f:
                    label_dir = converter.train_dir / "labels"
                    for label_file in sorted(label_dir.glob("*.txt")):
                        with open(label_file, 'r') as label_f:
                            f.write(label_f.read())

                print(f"[SUCCESS] Created file list: {train_list_path}")

                # Verify
                with open(train_list_path, 'r') as f:
                    line_count = len(f.readlines())
                print(f"[INFO] Total annotation lines: {line_count}")

                return 0
            else:
                print("[ERROR] No safe captures found!")
                return 1

    except Exception as e:
        print(f"[ERROR] Error creating safe dataset: {e}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    sys.exit(main())
