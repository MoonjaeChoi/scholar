# Generated: 2025-10-02 06:52:00 KST
"""
Validate dataset quality for PaddleOCR training
Checks image files, labels, and data integrity
"""

import argparse
from pathlib import Path
import json
from PIL import Image
from loguru import logger
from collections import defaultdict


def validate_label_file(label_file, data_dir):
    """
    Validate label file format and content

    Args:
        label_file: Path to label file (train_list.txt, val_list.txt, etc.)
        data_dir: Data directory containing images

    Returns:
        dict: Validation statistics
    """
    label_path = Path(label_file)
    data_path = Path(data_dir)

    if not label_path.exists():
        raise FileNotFoundError(f"Label file not found: {label_file}")

    stats = {
        'total_lines': 0,
        'valid_lines': 0,
        'missing_images': 0,
        'invalid_json': 0,
        'empty_annotations': 0,
        'total_bboxes': 0,
        'bbox_counts': defaultdict(int),
        'image_sizes': [],
        'errors': []
    }

    with open(label_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    stats['total_lines'] = len(lines)

    for line_num, line in enumerate(lines, 1):
        try:
            # Parse line: image_path\tjson_annotations
            parts = line.strip().split('\t')
            if len(parts) != 2:
                stats['errors'].append(f"Line {line_num}: Invalid format (expected 2 parts, got {len(parts)})")
                continue

            image_rel_path, annotations_json = parts

            # Check image file exists
            image_path = data_path / 'train' / image_rel_path
            if not image_path.exists():
                stats['missing_images'] += 1
                stats['errors'].append(f"Line {line_num}: Image not found: {image_path}")
                continue

            # Validate image
            try:
                img = Image.open(image_path)
                width, height = img.size
                stats['image_sizes'].append((width, height))
                img.close()
            except Exception as e:
                stats['errors'].append(f"Line {line_num}: Cannot open image {image_path}: {e}")
                continue

            # Parse JSON annotations
            try:
                annotations = json.loads(annotations_json)
            except json.JSONDecodeError as e:
                stats['invalid_json'] += 1
                stats['errors'].append(f"Line {line_num}: Invalid JSON: {e}")
                continue

            # Check annotations
            if not annotations or len(annotations) == 0:
                stats['empty_annotations'] += 1
                stats['errors'].append(f"Line {line_num}: Empty annotations")
                continue

            # Validate each bbox
            bbox_count = len(annotations)
            stats['total_bboxes'] += bbox_count
            stats['bbox_counts'][bbox_count] += 1

            for idx, ann in enumerate(annotations):
                if 'transcription' not in ann or 'points' not in ann:
                    stats['errors'].append(
                        f"Line {line_num}, Bbox {idx}: Missing 'transcription' or 'points'"
                    )
                    continue

                # Validate points format
                points = ann['points']
                if not isinstance(points, list) or len(points) != 4:
                    stats['errors'].append(
                        f"Line {line_num}, Bbox {idx}: Invalid points format (expected 4 points)"
                    )
                    continue

                # Check if points are valid coordinates
                for pt_idx, pt in enumerate(points):
                    if not isinstance(pt, list) or len(pt) != 2:
                        stats['errors'].append(
                            f"Line {line_num}, Bbox {idx}, Point {pt_idx}: Invalid point format"
                        )
                        break

            stats['valid_lines'] += 1

        except Exception as e:
            stats['errors'].append(f"Line {line_num}: Unexpected error: {e}")

    return stats


def print_statistics(stats, label_name):
    """Print validation statistics"""
    logger.info(f"📊 {label_name} Validation Results:")
    logger.info(f"   Total lines: {stats['total_lines']}")

    if stats['total_lines'] > 0:
        logger.info(f"   Valid lines: {stats['valid_lines']} ({stats['valid_lines']/stats['total_lines']*100:.1f}%)")
    else:
        logger.info(f"   Valid lines: {stats['valid_lines']} (N/A - empty dataset)")
        return  # Skip remaining stats for empty dataset

    logger.info(f"   Missing images: {stats['missing_images']}")
    logger.info(f"   Invalid JSON: {stats['invalid_json']}")
    logger.info(f"   Empty annotations: {stats['empty_annotations']}")
    logger.info(f"   Total bboxes: {stats['total_bboxes']}")

    if stats['valid_lines'] > 0:
        avg_bboxes = stats['total_bboxes'] / stats['valid_lines']
        logger.info(f"   Avg bboxes per image: {avg_bboxes:.1f}")

    if stats['image_sizes']:
        avg_width = sum(w for w, h in stats['image_sizes']) / len(stats['image_sizes'])
        avg_height = sum(h for w, h in stats['image_sizes']) / len(stats['image_sizes'])
        logger.info(f"   Avg image size: {avg_width:.0f}x{avg_height:.0f}")

    # Bbox distribution
    if stats['bbox_counts']:
        logger.info(f"   Bbox count distribution:")
        sorted_counts = sorted(stats['bbox_counts'].items())
        for count, num_images in sorted_counts[:5]:  # Show first 5
            logger.info(f"      {count} bboxes: {num_images} images")
        if len(sorted_counts) > 5:
            logger.info(f"      ... and {len(sorted_counts)-5} more")

    # Errors
    if stats['errors']:
        logger.warning(f"⚠️  Found {len(stats['errors'])} errors")
        logger.warning(f"   Showing first 10 errors:")
        for error in stats['errors'][:10]:
            logger.warning(f"      {error}")
        if len(stats['errors']) > 10:
            logger.warning(f"   ... and {len(stats['errors'])-10} more errors")


def main():
    parser = argparse.ArgumentParser(description='Validate dataset quality')
    parser.add_argument('--data-dir', type=str, required=True,
                        help='Data directory path')
    parser.add_argument('--train-file', type=str, default='train_list.txt',
                        help='Train label file (default: train_list.txt)')
    parser.add_argument('--val-file', type=str, default='val_list.txt',
                        help='Val label file (default: val_list.txt)')
    parser.add_argument('--test-file', type=str, default='test_list.txt',
                        help='Test label file (default: test_list.txt)')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("🔍 Dataset Quality Validation")
    logger.info("=" * 80)
    logger.info(f"Data directory: {args.data_dir}")
    logger.info("")

    data_path = Path(args.data_dir)
    all_valid = True

    # Validate train set
    train_file = data_path / args.train_file
    if train_file.exists():
        logger.info("📝 Validating Train Set...")
        train_stats = validate_label_file(train_file, data_path)
        print_statistics(train_stats, "Train")
        if train_stats['valid_lines'] != train_stats['total_lines']:
            all_valid = False
        logger.info("")
    else:
        logger.warning(f"⚠️  Train file not found: {train_file}")

    # Validate val set
    val_file = data_path / args.val_file
    if val_file.exists():
        logger.info("📝 Validating Validation Set...")
        val_stats = validate_label_file(val_file, data_path)
        print_statistics(val_stats, "Validation")
        if val_stats['valid_lines'] != val_stats['total_lines']:
            all_valid = False
        logger.info("")
    else:
        logger.warning(f"⚠️  Val file not found: {val_file}")

    # Validate test set
    test_file = data_path / args.test_file
    if test_file.exists():
        logger.info("📝 Validating Test Set...")
        test_stats = validate_label_file(test_file, data_path)
        print_statistics(test_stats, "Test")
        if test_stats['valid_lines'] != test_stats['total_lines']:
            all_valid = False
        logger.info("")
    else:
        logger.warning(f"⚠️  Test file not found: {test_file}")

    logger.info("=" * 80)
    if all_valid:
        logger.info("✅ Dataset validation completed - All data is valid!")
    else:
        logger.warning("⚠️  Dataset validation completed - Found some issues")
        logger.warning("   Please check the errors above and fix them before training")
    logger.info("=" * 80)


if __name__ == '__main__':
    main()
