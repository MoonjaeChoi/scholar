# Generated: 2025-10-01 15:45:00 KST
# Test image decoding to diagnose cv2.imdecode errors

import cv2
import numpy as np
import os

def test_image(img_path):
    """Test if an image can be decoded correctly"""
    print(f"\nTesting: {img_path}")

    if not os.path.exists(img_path):
        print(f"  ERROR: File does not exist!")
        return False

    # Check file size
    file_size = os.path.getsize(img_path)
    print(f"  File size: {file_size} bytes")

    if file_size == 0:
        print(f"  ERROR: File is empty!")
        return False

    # Read as bytes (like PaddleOCR does)
    with open(img_path, 'rb') as f:
        img_bytes = f.read()

    print(f"  Bytes read: {len(img_bytes)}")

    # Convert to numpy array
    img_array = np.frombuffer(img_bytes, dtype=np.uint8)
    print(f"  Array shape: {img_array.shape}, dtype: {img_array.dtype}")

    # Decode with cv2
    img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)

    if img is None:
        print(f"  ERROR: cv2.imdecode returned None!")
        return False

    print(f"  SUCCESS: Decoded shape: {img.shape}")
    return True

# Test images from error log
test_images = [
    "data/train/images/image_231.jpg",
    "data/train/images/image_191.jpg",
    "data/train/images/image_124.jpg",
    "data/train/images/image_10.jpg",
]

print("=" * 60)
print("Testing image decoding...")
print("=" * 60)

success_count = 0
for img_path in test_images:
    if test_image(img_path):
        success_count += 1

print(f"\n{'=' * 60}")
print(f"Results: {success_count}/{len(test_images)} images decoded successfully")
print(f"{'=' * 60}")
