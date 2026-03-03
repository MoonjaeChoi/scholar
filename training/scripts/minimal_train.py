#!/usr/bin/env python3.9
# Generated: 2025-10-02 01:18:00 KST
"""
Minimal training - skip pretrained model loading
"""
import sys
sys.path.insert(0, '/home/pro301/git/en-zine/ocr_system/paddleocr_training/PaddleOCR')

import yaml
import paddle
from ppocr.data import build_dataloader
from ppocr.modeling.architectures import build_model
from ppocr.losses import build_loss
from ppocr.optimizer import build_optimizer
from ppocr.utils.logging import get_logger

def main():
    print("\n" + "="*60)
    print("MINIMAL TRAINING - 2 SAMPLES, 3 EPOCHS")
    print("="*60 + "\n")

    # Load config
    config_path = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/configs/det/test_2_samples.yml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    print("✓ Config loaded")

    # Set device
    paddle.device.set_device('gpu:0')
    print("✓ GPU device set")

    # Build model
    print("Building model...")
    model = build_model(config['Architecture'])
    print(f"✓ Model built")

    # Build loss
    print("Building loss...")
    loss_func = build_loss(config['Loss'])
    print(f"✓ Loss built")

    # Build optimizer
    print("Building optimizer...")
    optimizer, lr_scheduler = build_optimizer(
        config['Optimizer'],
        epochs=3,
        step_each_epoch=2,
        model=model
    )
    print(f"✓ Optimizer built")

    # Build dataloader
    print("Building dataloader...")
    paddle_logger = get_logger()
    train_loader = build_dataloader(config, 'Train', None, seed=None, logger=paddle_logger)
    print(f"✓ Dataloader built: {len(train_loader)} batches")

    # Load pretrained model
    pretrained_path = config['Global']['pretrained_model']
    print(f"\nLoading pretrained model from {pretrained_path}...")
    if os.path.exists(pretrained_path + '.pdparams'):
        param_dict = paddle.load(pretrained_path + '.pdparams')
        model.set_state_dict(param_dict)
        print("✓ Pretrained model loaded successfully\n")
    else:
        print(f"⚠️  Pretrained model not found, training from scratch\n")

    # Training loop
    print("="*60)
    print("STARTING TRAINING LOOP")
    print("="*60 + "\n")

    model.train()

    for epoch in range(3):
        print(f"\n📊 EPOCH {epoch + 1}/3")
        print("-"*40)

        epoch_loss = 0.0
        batch_count = 0

        for batch_idx, batch in enumerate(train_loader):
            try:
                print(f"  Batch {batch_idx + 1}/{len(train_loader)}... ", end='', flush=True)

                # Unpack batch - Detection format expects:
                # [image, threshold_map, threshold_mask, shrink_map, shrink_mask]
                if len(batch) != 5:
                    print(f"❌ Unexpected batch length: {len(batch)}, expected 5")
                    return False

                # Forward
                preds = model(batch[0])

                # Loss - Pass batch to loss function (it will unpack itself)
                loss = loss_func(preds, batch)
                avg_loss = loss['loss']

                # Backward
                avg_loss.backward()
                optimizer.step()
                optimizer.clear_grad()

                loss_val = float(avg_loss.numpy()[0])
                epoch_loss += loss_val
                batch_count += 1

                print(f"loss={loss_val:.4f} ✓")

            except Exception as e:
                print(f"❌ ERROR: {e}")
                import traceback
                traceback.print_exc()
                return False

        avg_loss = epoch_loss / batch_count if batch_count > 0 else 0
        print(f"\n✅ Epoch {epoch + 1} complete - Avg loss: {avg_loss:.4f}")

    print("\n" + "="*60)
    print("🎉 TRAINING COMPLETED!")
    print("="*60)
    return True

if __name__ == "__main__":
    import os
    os.environ['FLAGS_cudnn_exhaustive_search'] = '0'
    os.environ['FLAGS_cudnn_batchnorm_spatial_persistent'] = '0'

    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Training interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Fatal error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
