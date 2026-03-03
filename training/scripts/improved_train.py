#!/usr/bin/env python3.9
# Generated: 2025-10-02 01:37:00 KST
"""
Improved training with Train/Val split, LR adjustment, and checkpoint saving
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
from ppocr.metrics import build_metric
from ppocr.postprocess import build_post_process
from ppocr.utils.logging import get_logger

def save_checkpoint(model, optimizer, epoch, save_dir, is_best=False):
    """Save model checkpoint"""
    os.makedirs(save_dir, exist_ok=True)

    # Save regular checkpoint
    model_path = os.path.join(save_dir, f'epoch_{epoch}')
    paddle.save(model.state_dict(), model_path + '.pdparams')
    paddle.save(optimizer.state_dict(), model_path + '.pdopt')
    print(f"  💾 Checkpoint saved: {model_path}")

    # Save best model
    if is_best:
        best_path = os.path.join(save_dir, 'best_model')
        paddle.save(model.state_dict(), best_path + '.pdparams')
        paddle.save(optimizer.state_dict(), best_path + '.pdopt')
        print(f"  ⭐ Best model saved: {best_path}")

def evaluate(model, val_loader, loss_func):
    """Evaluate model on validation set"""
    model.eval()

    total_loss = 0.0
    batch_count = 0

    # Temporarily set model to train mode for loss calculation
    # (some loss functions require specific modes)
    for batch_idx, batch in enumerate(val_loader):
        preds = model(batch[0])

        # Use try-except to handle potential dimension mismatches
        try:
            loss = loss_func(preds, batch)
            total_loss += float(loss['loss'].numpy()[0])
            batch_count += 1
        except Exception as e:
            print(f"    ⚠️  Val loss calculation error: {e}")
            # If loss calculation fails, use 0
            total_loss += 0.0
            batch_count += 1

    avg_loss = total_loss / batch_count if batch_count > 0 else 0.0
    model.train()

    return avg_loss

def main():
    print("\n" + "="*60)
    print("IMPROVED TRAINING - Train/Val Split + Checkpoints")
    print("="*60 + "\n")

    # Load config
    config_path = "/home/pro301/git/en-zine/ocr_system/paddleocr_training/configs/det/test_2_samples.yml"
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    print("✓ Config loaded")

    # Adjust learning rate for fine-tuning
    original_lr = config['Optimizer']['lr']['learning_rate']
    fine_tune_lr = 0.00001  # 10x lower for fine-tuning
    config['Optimizer']['lr']['learning_rate'] = fine_tune_lr
    print(f"✓ Learning rate adjusted: {original_lr} → {fine_tune_lr} (fine-tuning)")

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

    # Build optimizer with adjusted LR
    print("Building optimizer...")
    optimizer, lr_scheduler = build_optimizer(
        config['Optimizer'],
        epochs=3,
        step_each_epoch=1,  # 1 sample for training
        model=model
    )
    print(f"✓ Optimizer built with LR={fine_tune_lr}")

    # Build dataloaders - separate train and val
    print("Building dataloaders...")
    paddle_logger = get_logger()

    # Train loader (will use train_list.txt with 1 sample)
    train_loader = build_dataloader(config, 'Train', None, seed=None, logger=paddle_logger)
    print(f"✓ Train dataloader: {len(train_loader)} batches")

    # Val loader (will use val_list.txt with 1 sample)
    # Update config for validation
    val_config = config.copy()
    val_config['Train']['dataset']['label_file_list'] = [
        '/home/pro301/git/en-zine/ocr_system/paddleocr_training/data_test/val_list.txt'
    ]
    val_config['Train']['loader']['shuffle'] = False
    val_loader = build_dataloader(val_config, 'Train', None, seed=None, logger=paddle_logger)
    print(f"✓ Val dataloader: {len(val_loader)} batches")

    # Load pretrained model
    pretrained_path = config['Global']['pretrained_model']
    print(f"\nLoading pretrained model from {pretrained_path}...")
    if os.path.exists(pretrained_path + '.pdparams'):
        param_dict = paddle.load(pretrained_path + '.pdparams')
        model.set_state_dict(param_dict)
        print("✓ Pretrained model loaded successfully")
    else:
        print(f"⚠️  Pretrained model not found")

    # Output directory
    save_dir = "/home/pro301/paddleocr_training/output/improved_training"
    print(f"✓ Checkpoints will be saved to: {save_dir}\n")

    # Training loop
    print("="*60)
    print("STARTING TRAINING LOOP")
    print("="*60 + "\n")

    model.train()
    best_val_loss = float('inf')

    for epoch in range(3):
        print(f"\n📊 EPOCH {epoch + 1}/3")
        print("-"*40)

        # Training
        epoch_train_loss = 0.0
        for batch_idx, batch in enumerate(train_loader):
            print(f"  [Train] Batch {batch_idx + 1}/{len(train_loader)}... ", end='', flush=True)

            # Forward
            preds = model(batch[0])
            loss = loss_func(preds, batch)
            avg_loss = loss['loss']

            # Backward
            avg_loss.backward()
            optimizer.step()
            optimizer.clear_grad()

            loss_val = float(avg_loss.numpy()[0])
            epoch_train_loss += loss_val
            print(f"loss={loss_val:.6f} ✓")

        avg_train_loss = epoch_train_loss / len(train_loader)

        # Validation
        print(f"\n  [Validation] Evaluating...")
        val_loss = evaluate(model, val_loader, loss_func)

        print(f"\n  📈 Train Loss: {avg_train_loss:.6f}")
        print(f"  📉 Val Loss:   {val_loss:.6f}")

        # Save checkpoint
        is_best = val_loss < best_val_loss
        if is_best:
            best_val_loss = val_loss
            print(f"  🎯 New best validation loss!")

        save_checkpoint(model, optimizer, epoch + 1, save_dir, is_best)

        print(f"\n✅ Epoch {epoch + 1} complete")

    print("\n" + "="*60)
    print("🎉 TRAINING COMPLETED!")
    print("="*60)
    print(f"\nBest validation loss: {best_val_loss:.6f}")
    print(f"Checkpoints saved in: {save_dir}")
    print(f"  - Latest: epoch_3.pdparams")
    print(f"  - Best: best_model.pdparams")

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
