# Generated: 2025-10-02 06:51:00 KST
"""
Split dataset into Train/Val/Test sets
Default ratio: 70% Train, 15% Val, 15% Test
"""

import argparse
from pathlib import Path
import random
from loguru import logger


def split_dataset(input_file, output_dir, train_ratio=0.7, val_ratio=0.15, test_ratio=0.15, seed=42):
    """
    Split dataset into train/val/test sets

    Args:
        input_file: Path to train_list.txt
        output_dir: Output directory for split files
        train_ratio: Ratio for training set (default: 0.7)
        val_ratio: Ratio for validation set (default: 0.15)
        test_ratio: Ratio for test set (default: 0.15)
        seed: Random seed for reproducibility
    """
    # Validate ratios
    total_ratio = train_ratio + val_ratio + test_ratio
    if abs(total_ratio - 1.0) > 0.001:
        raise ValueError(f"Ratios must sum to 1.0, got {total_ratio}")

    # Read all lines
    input_path = Path(input_file)
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_file}")

    with open(input_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    total_samples = len(lines)
    logger.info(f"📊 Total samples: {total_samples}")

    # Shuffle with seed for reproducibility
    random.seed(seed)
    random.shuffle(lines)

    # Calculate split indices
    train_count = int(total_samples * train_ratio)
    val_count = int(total_samples * val_ratio)
    test_count = total_samples - train_count - val_count

    logger.info(f"📊 Split distribution:")
    logger.info(f"   Train: {train_count} samples ({train_ratio*100:.1f}%)")
    logger.info(f"   Val:   {val_count} samples ({val_ratio*100:.1f}%)")
    logger.info(f"   Test:  {test_count} samples ({test_ratio*100:.1f}%)")

    # Split data
    train_lines = lines[:train_count]
    val_lines = lines[train_count:train_count + val_count]
    test_lines = lines[train_count + val_count:]

    # Create output directory
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    # Write split files
    train_file = output_path / 'train_list.txt'
    val_file = output_path / 'val_list.txt'
    test_file = output_path / 'test_list.txt'

    with open(train_file, 'w', encoding='utf-8') as f:
        f.writelines(train_lines)

    with open(val_file, 'w', encoding='utf-8') as f:
        f.writelines(val_lines)

    with open(test_file, 'w', encoding='utf-8') as f:
        f.writelines(test_lines)

    logger.info(f"✅ Split completed:")
    logger.info(f"   Train: {train_file}")
    logger.info(f"   Val:   {val_file}")
    logger.info(f"   Test:  {test_file}")

    return {
        'train': train_file,
        'val': val_file,
        'test': test_file,
        'counts': {
            'train': train_count,
            'val': val_count,
            'test': test_count
        }
    }


def main():
    parser = argparse.ArgumentParser(description='Split dataset into Train/Val/Test sets')
    parser.add_argument('--input', type=str, required=True,
                        help='Input train_list.txt file path')
    parser.add_argument('--output-dir', type=str, required=True,
                        help='Output directory for split files')
    parser.add_argument('--train', type=float, default=0.7,
                        help='Train ratio (default: 0.7)')
    parser.add_argument('--val', type=float, default=0.15,
                        help='Validation ratio (default: 0.15)')
    parser.add_argument('--test', type=float, default=0.15,
                        help='Test ratio (default: 0.15)')
    parser.add_argument('--seed', type=int, default=42,
                        help='Random seed for reproducibility (default: 42)')

    args = parser.parse_args()

    logger.info("=" * 80)
    logger.info("📊 Dataset Splitting - Train/Val/Test")
    logger.info("=" * 80)
    logger.info(f"Input file: {args.input}")
    logger.info(f"Output directory: {args.output_dir}")
    logger.info(f"Ratios: Train={args.train}, Val={args.val}, Test={args.test}")
    logger.info(f"Random seed: {args.seed}")
    logger.info("")

    try:
        result = split_dataset(
            input_file=args.input,
            output_dir=args.output_dir,
            train_ratio=args.train,
            val_ratio=args.val,
            test_ratio=args.test,
            seed=args.seed
        )

        logger.info("")
        logger.info("=" * 80)
        logger.info("✅ Dataset split completed successfully!")
        logger.info("=" * 80)
        logger.info(f"Next step: Run validate_dataset.py to verify data quality")

    except Exception as e:
        logger.error(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
