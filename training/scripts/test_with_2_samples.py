#!/usr/bin/env python3
# Generated: 2025-10-01 23:15:00 KST
"""
Test training with 2 crawled images
"""

import sys
from pathlib import Path
from loguru import logger

sys.path.append('/home/pro301/git/en-zine/ocr_system/paddleocr_training')
from database_connection import DatabaseConnection

def create_test_dataset():
    """Create test dataset with 2 samples"""
    try:
        from convert_database_to_paddleocr import PaddleOCRDatasetConverter

        # Create test directory
        test_dir = Path("/home/pro301/git/en-zine/ocr_system/paddleocr_training/data_test")
        test_dir.mkdir(exist_ok=True)

        logger.info(f"Test directory: {test_dir}")

        # Initialize converter
        converter = PaddleOCRDatasetConverter(str(test_dir))

        # Get quality captures
        captures = converter.get_quality_captures(min_quality_score=0.7)
        logger.info(f"Total quality captures: {len(captures)}")

        # Select 2 samples with moderate bbox count (50-300 for faster testing)
        filtered_captures = [c for c in captures if 50 <= c['bbox_count'] <= 300]
        logger.info(f"Filtered to {len(filtered_captures)} captures with 50-300 bboxes")

        test_samples = filtered_captures[:2] if filtered_captures else captures[:2]
        logger.info(f"Selected {len(test_samples)} samples for test:")
        for sample in test_samples:
            logger.info(f"  - CAPTURE_ID: {sample['capture_id']}, "
                       f"bbox_count: {sample['bbox_count']}, "
                       f"confidence: {sample['avg_confidence']:.2f}")

        # Convert samples
        train_count = converter._convert_samples(test_samples, converter.train_dir)
        logger.info(f"Converted {train_count} training samples")

        # Create file list
        train_list_path = test_dir / "train_list.txt"
        with open(train_list_path, 'w') as f:
            label_dir = converter.train_dir / "labels"
            for label_file in sorted(label_dir.glob("*.txt")):
                with open(label_file, 'r') as label_f:
                    f.write(label_f.read())

        logger.info(f"Created file list: {train_list_path}")

        # Verify
        with open(train_list_path, 'r') as f:
            line_count = len(f.readlines())
        logger.info(f"Total annotation lines: {line_count}")

        logger.success("Test dataset preparation completed!")
        return True

    except Exception as e:
        logger.error(f"Error creating test dataset: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = create_test_dataset()
    sys.exit(0 if success else 1)
