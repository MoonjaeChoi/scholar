#!/usr/bin/env python3.9
# Generated: 2025-10-02 01:25:00 KST
"""Debug batch structure"""
import sys
sys.path.insert(0, '/home/pro301/git/en-zine/ocr_system/paddleocr_training/PaddleOCR')

import yaml
import paddle
from ppocr.data import build_dataloader
from ppocr.utils.logging import get_logger

config_path = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/configs/det/test_2_samples.yml"
with open(config_path, 'r') as f:
    config = yaml.safe_load(f)

paddle.device.set_device('gpu:0')
paddle_logger = get_logger()
train_loader = build_dataloader(config, 'Train', None, seed=None, logger=paddle_logger)

print("\n" + "="*60)
print("BATCH STRUCTURE ANALYSIS")
print("="*60 + "\n")

for batch_idx, batch in enumerate(train_loader):
    print(f"Batch {batch_idx + 1}:")
    print(f"  Type: {type(batch)}")
    print(f"  Length: {len(batch)}")

    for i, item in enumerate(batch):
        if hasattr(item, 'shape'):
            print(f"  [{i}] Tensor shape: {item.shape}, dtype: {item.dtype}")
        else:
            print(f"  [{i}] Type: {type(item)}, value: {item}")

    print()

    if batch_idx >= 0:  # Just check first batch
        break

print("="*60)
