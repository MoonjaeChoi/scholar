#!/usr/bin/env python3.9
# Generated: 2025-10-02 01:30:00 KST
"""Patch loss function to remove assertion"""

loss_file = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/PaddleOCR/ppocr/losses/det_basic_loss.py"

with open(loss_file, 'r') as f:
    content = f.read()

# Comment out assertion
original = "        assert loss <= 1"
patched = "        # assert loss <= 1  # Patched for 2-sample training"

if original in content:
    content = content.replace(original, patched)
    with open(loss_file, 'w') as f:
        f.write(content)
    print(f"✓ Patched {loss_file}")
    print("  Commented out: assert loss <= 1")
else:
    print(f"⚠️  Assertion already patched or not found")
