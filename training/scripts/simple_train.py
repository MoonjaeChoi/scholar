#!/usr/bin/env python3.9
# Generated: 2025-10-02 01:10:00 KST
"""
Simple training script with explicit control flow for debugging
"""
import sys
import os
sys.path.insert(0, '/home/pro301/git/en-zine/ocr_system/paddleocr_training/PaddleOCR')

import yaml
import paddle
from ppocr.data import build_dataloader
from ppocr.modeling.architectures import build_model
from ppocr.losses import build_loss
from ppocr.optimizer import build_optimizer
from ppocr.utils.logging import get_logger
from loguru import logger as loguru_logger

def simple_train():
    """Simple training with explicit steps"""
    try:
        # 1. Load config
        config_path = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/configs/det/test_2_samples.yml"
        with open(config_path, 'r') as f:
            config = yaml.safe_load(f)

        loguru_logger.info(f"✓ Config loaded from {config_path}")

        # 2. Set device
        paddle.device.set_device('gpu:0')
        loguru_logger.info("✓ GPU device set")

        # 3. Build model
        loguru_logger.info("Building model...")
        model = build_model(config['Architecture'])
        loguru_logger.info(f"✓ Model built: {type(model)}")

        # 4. Build loss
        loguru_logger.info("Building loss...")
        loss_func = build_loss(config['Loss'])
        loguru_logger.info(f"✓ Loss built: {type(loss_func)}")

        # 5. Build optimizer
        loguru_logger.info("Building optimizer...")
        optimizer, lr_scheduler = build_optimizer(
            config['Optimizer'],
            epochs=config['Global']['epoch_num'],
            step_each_epoch=2,  # We have 2 samples
            model=model
        )
        loguru_logger.info(f"✓ Optimizer built: {type(optimizer)}")

        # 6. Build dataloader
        loguru_logger.info("Building dataloader...")
        paddle_logger = get_logger()
        train_loader = build_dataloader(config, 'Train', None, seed=None, logger=paddle_logger)
        loguru_logger.info(f"✓ Dataloader built: {len(train_loader)} batches")

        # 7. Load pretrained model
        pretrained_path = config['Global']['pretrained_model']
        if os.path.exists(pretrained_path + '.pdparams'):
            loguru_logger.info(f"Loading pretrained model from {pretrained_path}")
            param_dict = paddle.load(pretrained_path + '.pdparams')
            model.set_state_dict(param_dict)
            loguru_logger.info("✓ Pretrained model loaded")

        # 8. Training loop
        loguru_logger.info("\n" + "="*50)
        loguru_logger.info("STARTING TRAINING")
        loguru_logger.info("="*50 + "\n")

        model.train()

        for epoch in range(config['Global']['epoch_num']):
            loguru_logger.info(f"\n📊 EPOCH {epoch + 1}/{config['Global']['epoch_num']}")

            epoch_loss = 0
            for batch_idx, batch in enumerate(train_loader):
                loguru_logger.info(f"  Processing batch {batch_idx + 1}/{len(train_loader)}...")

                # Forward pass
                preds = model(batch[0])

                # Calculate loss
                loss = loss_func(preds, batch[1:])
                avg_loss = loss['loss']

                # Backward pass
                avg_loss.backward()
                optimizer.step()
                optimizer.clear_grad()

                epoch_loss += avg_loss.numpy()[0]

                loguru_logger.info(f"    ✓ Batch {batch_idx + 1} loss: {avg_loss.numpy()[0]:.4f}")

            avg_epoch_loss = epoch_loss / len(train_loader)
            loguru_logger.success(f"✓ Epoch {epoch + 1} completed - Average loss: {avg_epoch_loss:.4f}")

            # Save checkpoint
            save_path = f"/home/pro301/paddleocr_training/output/test_2_samples/epoch_{epoch + 1}"
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            paddle.save(model.state_dict(), save_path + '.pdparams')
            paddle.save(optimizer.state_dict(), save_path + '.pdopt')
            loguru_logger.info(f"  Checkpoint saved to {save_path}")

        loguru_logger.success("\n🎉 TRAINING COMPLETED SUCCESSFULLY!")
        return True

    except Exception as e:
        loguru_logger.error(f"\n❌ Training failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = simple_train()
    sys.exit(0 if success else 1)
