#!/usr/bin/env python3.9
# Generated: 2025-10-02 00:40:00 KST
"""
Minimal training test to verify data loading
"""
import sys
sys.path.insert(0, '/home/pro301/git/en-zine/ocr_system/paddleocr_training/PaddleOCR')

from ppocr.data import build_dataloader
import yaml
from loguru import logger

def test_data_loading():
    """Test if data can be loaded properly"""
    try:
        # Load config
        config_path = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/configs/det/test_2_samples.yml"
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        logger.info(f"Config loaded from {config_path}")

        # Build dataloader
        logger.info("Building train dataloader...")
        from ppocr.utils.logging import get_logger
        paddle_logger = get_logger()
        train_loader = build_dataloader(config, 'Train', None, seed=None, logger=paddle_logger)
        logger.info(f"Train dataloader has {len(train_loader)} batches")

        # Try to load first batch
        logger.info("Attempting to load first batch...")
        for batch_idx, batch in enumerate(train_loader):
            logger.info(f"Batch {batch_idx} loaded successfully")
            logger.info(f"Batch type: {type(batch)}")
            if isinstance(batch, dict):
                logger.info(f"Batch keys: {list(batch.keys())}")
                if 'image' in batch:
                    logger.info(f"Image shape: {batch['image'].shape}")
            elif isinstance(batch, (list, tuple)):
                logger.info(f"Batch length: {len(batch)}")
                logger.info(f"First element type: {type(batch[0])}")
            if batch_idx >= 1:  # Load 2 batches
                break

        logger.success("Data loading test PASSED!")
        return True

    except Exception as e:
        logger.error(f"Data loading test FAILED: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_data_loading()
    sys.exit(0 if success else 1)
