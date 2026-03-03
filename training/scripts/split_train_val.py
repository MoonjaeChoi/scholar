#!/usr/bin/env python3.9
# Generated: 2025-10-02 01:35:00 KST
"""
Split 2 samples into train (1) and val (1)
"""
import sys
import os
from pathlib import Path

def split_data():
    """Split train_list.txt into train and val"""
    data_dir = Path("/home/pro301/git/en-zine/ocr_system/paddleocr_training/data_test")
    train_list_path = data_dir / "train_list.txt"

    # Read all lines
    with open(train_list_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    print(f"Total samples: {len(lines)}")

    if len(lines) < 2:
        print("❌ Need at least 2 samples for train/val split")
        return False

    # Split: first sample for train, second for val
    train_lines = [lines[0]]
    val_lines = [lines[1]]

    # Write train list
    train_output = data_dir / "train_list.txt"
    with open(train_output, 'w', encoding='utf-8') as f:
        f.writelines(train_lines)
    print(f"✓ Train set: {len(train_lines)} samples → {train_output}")

    # Write val list
    val_output = data_dir / "val_list.txt"
    with open(val_output, 'w', encoding='utf-8') as f:
        f.writelines(val_lines)
    print(f"✓ Val set: {len(val_lines)} samples → {val_output}")

    # Display first line of each
    print(f"\nTrain sample: {train_lines[0][:100]}...")
    print(f"Val sample: {val_lines[0][:100]}...")

    return True

if __name__ == "__main__":
    success = split_data()
    sys.exit(0 if success else 1)
