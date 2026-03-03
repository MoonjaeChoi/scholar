# Generated: 2025-10-01 15:25:00 KST
# Check and remove corrupted image files

import os
import cv2
from pathlib import Path

def check_images(directory):
    corrupted = []
    total = 0
    for img_path in Path(directory).glob("*.jpg"):
        total += 1
        try:
            img = cv2.imread(str(img_path))
            if img is None:
                corrupted.append(str(img_path))
                print(f"Corrupted: {img_path}")
        except Exception as e:
            corrupted.append(str(img_path))
            print(f"Error reading {img_path}: {e}")
    return corrupted, total

print("Checking train images...")
train_corrupted, train_total = check_images("data/train/images/")
print(f"Train: {len(train_corrupted)} corrupted out of {train_total}")

print("\nChecking val images...")
val_corrupted, val_total = check_images("data/val/images/")
print(f"Val: {len(val_corrupted)} corrupted out of {val_total}")

# 손상된 파일 삭제
all_corrupted = train_corrupted + val_corrupted
if all_corrupted:
    for f in all_corrupted:
        os.remove(f)
        print(f"Deleted: {f}")
    print(f"\nTotal deleted: {len(all_corrupted)}")
else:
    print("\nNo corrupted files found!")
